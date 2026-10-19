#include "HalBlePageTurner.h"

#if CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <BleKeyboardHost.h>
#include <HalPowerManager.h>
#include <Logging.h>
#include <WiFi.h>
#include <esp_heap_caps.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <cstring>

#include "BleMemoryPolicy.h"

#if !defined(CROSSINK_BLE_HOST_PSRAM) || !CONFIG_BT_NIMBLE_MEM_ALLOC_MODE_EXTERNAL
#error "X4 Pro BLE memory policy requires the PSRAM NimBLE host allocator"
#endif

HalBlePageTurner blePageTurner;

namespace {
static_assert(WIFI_MODE_NULL == 0);
auto& host() { return freeink::BleKeyboardHost::getInstance(); }
BleMemoryPolicy::Snapshot memorySnapshot() {
  return {heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
          heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
          heap_caps_get_free_size(MALLOC_CAP_SPIRAM), static_cast<int>(WiFi.getMode()), psramFound()};
}
bool logGuard(const char* stage, const BleMemoryPolicy::Snapshot& heap, const BleMemoryPolicy::Budget& budget,
              uint8_t* reasons = nullptr) {
  const auto fail = BleMemoryPolicy::evaluate(heap, budget);
  if (reasons) {
    *reasons = (fail.wifi ? HalBlePageTurner::Wifi : 0) |
               (fail.freeInternal || fail.largestInternal || fail.psram ? HalBlePageTurner::Memory : 0);
  }
  LOG_INF("BLE", "%s: wifi_mode=%d wifi_block=%u internal_free=%u largest=%u psram_free=%u psram_ok=%u", stage,
          heap.wifiMode, fail.wifi, heap.freeInternal, heap.largestInternal, heap.freePsram, heap.psramAvailable);
  LOG_INF("BLE", "%s guard: need_free=%u need_largest=%u fail_free=%u fail_largest=%u fail_psram=%u pass=%u", stage,
          budget.freeInternal, budget.largestInternal, fail.freeInternal, fail.largestInternal, fail.psram, !fail.any());
  return !fail.any();
}
}  // namespace

bool HalBlePageTurner::resident() const { return host().isRunning() || host().isStopping(); }
bool HalBlePageTurner::enabled() const { return optedIn && host().isRunning(); }

bool HalBlePageTurner::enable() {
  if (resident()) return optedIn;
  failureReasons = None;
  // BLE needs controller RAM and task stacks even on PSRAM-equipped boards.
  if (!logGuard("preflight", memorySnapshot(), BleMemoryPolicy::Start, &failureReasons)) {
    LOG_ERR("BLE", "Start refused; see individual guard failures above");
    state = Status::LowMemory;
    return false;
  }
  HalPowerManager::Lock powerLock;
  LOG_INF("BLE", "NimBLE host allocator=PSRAM; controller and task stacks remain internal");
  if (!logGuard("before start", memorySnapshot(), BleMemoryPolicy::Start, &failureReasons)) {
    state = Status::LowMemory;
    return false;
  }
  if (!host().begin("CrossInk X4 Pro")) {
    LOG_ERR("BLE", "HID host initialization failed");
    logGuard("initialization failed", memorySnapshot(), BleMemoryPolicy::PostStart, &failureReasons);
    state = Status::Failed;
    failureReasons |= Initialization;
    return false;
  }
  // The pinned SDK doesn't check xTaskCreate's result. Refuse connection work
  // unless its verified task exists, so OOM cannot strand a pending connect.
  if (!xTaskGetHandle("ble-conn")) {
    LOG_ERR("BLE", "HID connection task allocation failed");
    logGuard("task allocation failed", memorySnapshot(), BleMemoryPolicy::PostStart, &failureReasons);
    stop();
    state = Status::Failed;
    failureReasons |= Initialization;
    return false;
  }
  // No background reconnect to arbitrary saved bonds. Pairing is explicit.
  host().disconnect();
  optedIn = true;
  state = Status::Ready;
  pairingPasskey = 0;
  filter.reset();
  if (!logGuard("after start", memorySnapshot(), BleMemoryPolicy::PostStart, &failureReasons)) {
    LOG_ERR("BLE", "Rolling back BLE start to preserve reader heap");
    stop();
    state = Status::LowMemory;
    return false;
  }
  return true;
}

bool HalBlePageTurner::stop(uint32_t timeoutMs) {
  const bool wasResident = resident();
  optedIn = false;
  pairingPasskey = 0;
  scanPending = false;
  count = 0;
  filter.reset();
  // Also covers calls from sleep/USB handoff; end() may need later retries.
  powerManager.setPowerSaving(false);
  if (!host().end(timeoutMs)) {
    state = Status::Stopping;
    return false;
  }
  if (wasResident) logGuard("after shutdown", memorySnapshot(), BleMemoryPolicy::PostStart);
  state = Status::Off;
  return true;
}

bool HalBlePageTurner::scan() {
  if (!optedIn || host().isConnecting() || host().isConnected() || scanPending) return false;
  failureReasons = None;
  count = 0;
  pairingPasskey = 0;
  host().startScan(5000);
  scanPending = true;
  state = Status::Scanning;
  return true;
}

bool HalBlePageTurner::connect(uint8_t index) {
  if (!optedIn || index >= count || host().isConnecting() || host().isConnected()) return false;
  failureReasons = None;
  std::memcpy(selected, devices[index].address, sizeof(selected));
  pairingPasskey = 0;
  filter.reset();
  if (!host().connect(selected)) {
    LOG_ERR("BLE", "Connect request rejected");
    state = Status::Failed;
    failureReasons = Connection;
    return false;
  }
  state = Status::Connecting;
  return true;
}

void HalBlePageTurner::forget() {
  if (!optedIn || host().isConnecting()) return;
  failureReasons = None;
  host().disconnect();
  // This experiment exposes one keyboard; forget all its stored host bonds.
  while (host().pairedCount()) {
    char address[18];
    std::memcpy(address, host().paired(0).addr, sizeof(address));
    host().forget(address);
  }
  selected[0] = '\0';
  pairingPasskey = 0;
  filter.reset();
  state = Status::Ready;
}

int8_t HalBlePageTurner::poll() {
  if (!optedIn) {
    if (resident()) stop();
    return 0;
  }
  const auto runningHeap = memorySnapshot();
  if (BleMemoryPolicy::evaluate(runningHeap, BleMemoryPolicy::Running).any()) {
    LOG_ERR("BLE", "Stopping BLE for Wi-Fi or low reader heap");
    logGuard("runtime refusal", runningHeap, BleMemoryPolicy::Running, &failureReasons);
    stop();
    return 0;
  }
  if (!host().isConnected() && !host().isConnecting()) host().disconnect();
  host().poll();
  if (scanPending && !host().isScanning()) {
    scanPending = false;
    count = 0;
    for (uint8_t i = 0; i < host().deviceCount() && count < 24; ++i) {
      const auto& found = host().device(i);
      if (!found.connectable) continue;
      std::memcpy(devices[count].address, found.addr, sizeof(Device::address));
      std::memcpy(devices[count].name, found.name, sizeof(Device::name));
      ++count;
    }
    state = Status::Ready;
  }
  char failure[48];
  if (host().takeConnectFailure(failure, sizeof(failure))) {
    LOG_ERR("BLE", "Connect failed: %s", failure);
    state = Status::Failed;
    failureReasons = Connection;
  }
  uint32_t code;
  if (host().takePairingPasskey(code)) {
    pairingPasskey = code;
    LOG_INF("BLE", "Pairing passkey: %06lu", static_cast<unsigned long>(code));
  }
  if (host().isConnected()) {
    pairingPasskey = 0;
    if (state != Status::Connected) {
      LOG_INF("BLE", "Connected to %s", host().connectedName());
      host().releaseScanResults();
    }
    state = Status::Connected;
  } else if (state == Status::Connected) {
    LOG_INF("BLE", "Disconnected; reconnect explicitly from Bluetooth settings");
    filter.reset();
    state = Status::Ready;
  }
  // Drain the translated queue too; only raw press edges drive page turns.
  freeink::KeyEvent key;
  while (host().popKey(key)) {}
  freeink::RawButtonEvent raw;
  while (host().popRawButton(raw)) {
    const int8_t direction = filter.accept(raw.reportId, raw.byteIndex, raw.value, raw.pressed, raw.keycode, raw.mods,
                                           raw.wasRest);
    // Never replay an old settings/overlay key after a slow render or transition.
    if (direction && millis() - raw.atMs <= 250 && host().isConnected() &&
        std::strcmp(selected, host().connectedAddr()) == 0) {
      LOG_INF("BLE", "HID 0x%02X -> %s", raw.keycode, direction > 0 ? "next" : "previous");
      return direction;
    }
  }
  return 0;
}
#endif
