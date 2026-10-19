#include "BleLab.h"
#if CROSSINK_BLE_LAB
#include <Arduino.h>
#include <cstring>
#include <HalBlePageTurner.h>
#include <HeapDiagnostics.h>
#include <Logging.h>
#include <HalStorage.h>
#include <AppVersion.h>
#include <esp_heap_caps.h>
#include "activities/Activity.h"

BleLab bleLab;
using namespace BleLabPolicy;

bool BleLab::load() {
  if (loaded) return true;
  if (!blePageTurner.labLoadSelection(selection, selected)) {
    finish(StrId::STR_BLE_LAB_STORAGE);
    return false;
  }
  loaded = true;
  return true;
}
void BleLab::sample() {
  free = heap_caps_get_free_size(HeapDiagnostics::Internal);
  largest = heap_caps_get_largest_free_block(HeapDiagnostics::Internal);
  events[eventHead] = {millis(), free, largest, uint32_t(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)),
                       uint8_t(phase), uint8_t(blePageTurner.status())};
  eventHead = (eventHead + 1) % 8;
  if (eventCount < 8) ++eventCount;
  ++revision;
}
void BleLab::enterHome() {
  load();
  if (result == StrId::STR_BLE_LAB_WIFI_OPEN) result = StrId::STR_BLE_LAB_WIFI_RETURN;
  if (result == StrId::STR_BLE_LAB_UPDATE_OPEN) result = StrId::STR_BLE_LAB_UPDATE_RETURN;
  sample();
  LOG_INF("BLELAB", "identity=%s", AppVersion::versionLabel());
}
void BleLab::finish(StrId message) {
  LOG_INF("BLELAB", "result=%s radio=%u failure=%u", I18N.get(message), unsigned(blePageTurner.status()), blePageTurner.failure());
  phase = Phase::Idle; result = message; sample();
}

bool BleLab::request(Command command) {
  LOG_INF("BLELAB", "requested action=%u phase=%u pending=%u", unsigned(command), unsigned(phase), unsigned(pending));
  if (!canRequest(phase, pending, command)) { LOG_INF("BLELAB", "refused: action pending/in progress"); return false; }
  const auto status = blePageTurner.status();
  if (command != Command::Restart && (status == HalBlePageTurner::Status::Stopping ||
      status == HalBlePageTurner::Status::Connecting || status == HalBlePageTurner::Status::Scanning)) { LOG_INF("BLELAB", "refused: radio transition/scan active"); return false; }
  LOG_INF("BLELAB", "accepted action=%u", unsigned(command));
  pending = command;
  ++revision;
  return true;
}
bool BleLab::selectConnected() {
  Selection next{};
  if (phase != Phase::Idle || pending != Command::None) { result = StrId::STR_BLE_LAB_BUSY; sample(); return false; }
  if (!blePageTurner.labConnectedPeer(next)) { finish(StrId::STR_BLE_DEVICE_GONE); return false; }
  if (selected && BleBindings::same(selection.peer, next.peer) &&
      std::memcmp(selection.name, next.name, sizeof(next.name)) == 0) { finish(StrId::STR_BLE_LAB_SELECTED); return true; }
  if (!blePageTurner.labSaveSelection(next)) { finish(StrId::STR_BLE_LAB_STORAGE); return false; }
  selection = next; loaded = selected = true;
  finish(StrId::STR_BLE_LAB_SELECTED);
  return true;
}
bool BleLab::clearSelection(bool all, const char* address, uint8_t type) {
  if (!all && !load()) return false;
  BleBindings::Peer target{};
  std::snprintf(target.address, sizeof(target.address), "%s", address);
  target.type = type;
  if (!all && (!selected || !BleBindings::same(selection.peer, target))) return true;
  if (!blePageTurner.labClearSelection()) { finish(StrId::STR_BLE_LAB_STORAGE); return false; }
  selection = {}; selected = false; pending = Command::None;
  finish(StrId::STR_BLE_LAB_SELECT);
  return true;
}

BleLab::View BleLab::view() const {
  View out;
  out.wifi = blePageTurner.labWifiActive();
  out.free = free; out.largest = largest; out.revision = revision; out.result = result;
  out.busy = pending != Command::None || phase != Phase::Idle ||
             blePageTurner.status() == HalBlePageTurner::Status::Stopping ||
             blePageTurner.status() == HalBlePageTurner::Status::Connecting ||
             blePageTurner.status() == HalBlePageTurner::Status::Scanning;
  out.restarting = restarting();
  if (blePageTurner.status() == HalBlePageTurner::Status::Stopping || phase == Phase::Stop || out.restarting)
    out.radio = Radio::Stopping;
  else if (phase == Phase::Enable || pending == Command::Connect ||
           (pending == Command::Toggle && !blePageTurner.resident())) out.radio = Radio::Starting;
  else if (blePageTurner.enabled()) out.radio = Radio::On;
  else if (blePageTurner.failure()) out.radio = Radio::Error;
  if (!selected) out.link = Link::NotSelected;
  else if (blePageTurner.labPeerConnected(selection.peer)) out.link = Link::Connected;
  else if (blePageTurner.status() == HalBlePageTurner::Status::Connected) out.link = Link::Other;
  else if (phase == Phase::AwaitConnection) out.link = Link::Connecting;
  else out.link = Link::Disconnected;
  return out;
}

void BleLab::tick() {
  if (pending != Command::None) {
    const auto command = pending; pending = Command::None; since = millis();
    toolAction = Command::None;
    if (command == Command::Wifi || command == Command::Logs || command == Command::Update) {
      if (blePageTurner.labWifiActive()) { finish(StrId::STR_BLE_LAB_CLOSE_WIFI); return; }
      if (command == Command::Logs && blePageTurner.resident()) { finish(StrId::STR_BLE_LAB_LOGS_OFF); return; }
      toolAction = command;
      phase = command == Command::Logs ? Phase::ToolReady : Phase::Stop;
      result = StrId::STR_BLE_LAB_WORKING;
    } else if (command == Command::Restart) {
      phase = Phase::RestartStop; result = StrId::STR_BLE_LAB_RESTARTING;
    } else if (command == Command::Toggle) {
      connectAfterEnable = false;
      phase = blePageTurner.resident() ? Phase::Stop : Phase::Enable;
      result = StrId::STR_BLE_LAB_WORKING;
    } else {
      if (!load()) return;
      if (!selected) { finish(StrId::STR_BLE_LAB_SELECT); return; }
      connectAfterEnable = true;
      phase = blePageTurner.enabled() ? Phase::Connect : Phase::Enable;
      result = StrId::STR_BLE_LAB_WORKING;
    }
    sample();
    return; // Let Home observe the pending transition before calling the HAL.
  }
  const auto status = blePageTurner.status();
  if (previousStatus != static_cast<int>(status)) {
    previousStatus = static_cast<int>(status); sample();
    // Result is persistent until the next explicit Lab action.
  }
  switch (phase) {
    case Phase::Idle: return;
    case Phase::Enable: {
      if (!activityManager.isHomeActivity()) { finish(StrId::STR_BLE_LAB_CANCELLED); return; }
      // Match Settings' memory isolation: never race renderer/cache allocation
      // against the guarded controller initialization. Try-lock, never wait.
      RenderLock lock(RenderLock::Mode::Try);
      if (!lock.ownsLock()) return;
      if (blePageTurner.resident()) { finish(StrId::STR_BLE_LAB_BUSY); return; }
      if (!blePageTurner.enable()) {
        finish((blePageTurner.failure() & HalBlePageTurner::Memory) ? StrId::STR_BLE_LOW_MEMORY :
               (blePageTurner.failure() & HalBlePageTurner::Wifi) ? StrId::STR_BLE_WIFI_ACTIVE : StrId::STR_BLE_INIT_FAILED);
      } else if (connectAfterEnable) { phase = Phase::Connect; sample(); }
      else finish(StrId::STR_BLE_LAB_ON);
      return;
    }
    case Phase::Connect:
      if (!blePageTurner.enabled()) { finish(StrId::STR_BLE_LAB_CANCELLED); return; }
      if (blePageTurner.labPeerConnected(selection.peer)) { finish(StrId::STR_BLE_LAB_CONNECTED); return; }
      if (status == HalBlePageTurner::Status::Connected) { finish(StrId::STR_BLE_LAB_OTHER); return; }
      if (!activityManager.isHomeActivity()) { finish(StrId::STR_BLE_LAB_CANCELLED); return; }
      if (!blePageTurner.labConnectSaved(selection.peer)) { finish(StrId::STR_BLE_LAB_PAIR_AGAIN); return; }
      since = millis(); phase = Phase::AwaitConnection; sample();
      return;
    case Phase::AwaitConnection:
      if (blePageTurner.labPeerConnected(selection.peer)) finish(StrId::STR_BLE_LAB_CONNECTED);
      else if (status == HalBlePageTurner::Status::Connected) finish(StrId::STR_BLE_LAB_OTHER);
      else if (!blePageTurner.enabled()) finish(StrId::STR_BLE_LAB_CANCELLED);
      else if (status == HalBlePageTurner::Status::Failed) finish(StrId::STR_BLE_CONNECT_FAILED);
      else if (expired(millis(), since, ConnectionTimeout)) {
        // Cancel the outstanding operation through the existing orderly teardown.
        phase = Phase::Stop; since = millis(); result = StrId::STR_BLE_LAB_TIMEOUT; sample();
      }
      return;
    case Phase::Stop:
    case Phase::RestartStop: {
      RenderLock lock(RenderLock::Mode::Try);
      if (!lock.ownsLock()) return;
      if (blePageTurner.stop(0)) {
        if (phase == Phase::RestartStop) { phase = Phase::RestartReady; sample(); }
        else if (toolAction != Command::None) { phase = Phase::ToolReady; since = millis(); sample(); }
        else finish(result == StrId::STR_BLE_LAB_TIMEOUT ? result : StrId::STR_BLE_LAB_OFF);
      } else if (expired(millis(), since, StopTimeout)) finish(StrId::STR_BLE_LAB_STOP_FAILED);
      return;
    }
    case Phase::ToolReady: {
      if (blePageTurner.resident() || blePageTurner.labWifiActive()) { finish(StrId::STR_BLE_LAB_BUSY); return; }
      const int ready = activityManager.prepareBleLabStorage();
      if (ready < 0) { finish(StrId::STR_BLE_LAB_TOOL_FAILED); return; }
      if (!ready) {
        if (expired(millis(), since, StopTimeout)) finish(StrId::STR_BLE_LAB_TOOL_FAILED);
        return;
      }
      // Renderer parked, lock released. No SD writes in rendering critical sections.
      HeapDiagnostics::snapshot("Lab tool before");
      bool ok = true;
      if (toolAction == Command::Logs) ok = exportDiagnostics();
      else if (toolAction == Command::Wifi) ok = activityManager.goToBleLabTransfer();
      else ok = activityManager.goToBleLabUpdate();
      if (!ok) LOG_ERR("BLELAB", "tool action=%u failed (no success reported)", unsigned(toolAction));
      const auto completed = toolAction;
      toolAction = Command::None;
      HeapDiagnostics::snapshot("Lab tool after");
      activityManager.finishBleLabStorage();
      finish(!ok ? StrId::STR_BLE_LAB_TOOL_FAILED : completed == Command::Logs ? StrId::STR_BLE_LAB_LOGS_SAVED :
             completed == Command::Wifi ? StrId::STR_BLE_LAB_WIFI_OPEN : StrId::STR_BLE_LAB_UPDATE_OPEN);
      return;
    }
    case Phase::RestartReady: {
      const int ready = activityManager.prepareBleLabRestart();
      if (ready < 0) { finish(StrId::STR_BLE_LAB_RESTART_FAILED); return; }
      if (!ready) {
        if (expired(millis(), since, StopTimeout)) finish(StrId::STR_BLE_LAB_RESTART_FAILED);
        return;
      }
      // Main-loop context, render task parked, RenderLock released, BLE fully Off.
      LOG_INF("BLELAB", "Confirmed software restart; watchdogs and saved Bluetooth data unchanged");
      ESP.restart();
      return;
    }
  }
}
#endif
