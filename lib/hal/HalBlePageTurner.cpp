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

HalBlePageTurner blePageTurner;

namespace {
auto& host() { return freeink::BleKeyboardHost::getInstance(); }
bool hasHeadroom(size_t freeBytes, size_t largest) {
  return heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT) >= freeBytes &&
         heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT) >= largest;
}
void logHeap(const char* stage) {
  LOG_INF("BLE", "%s: internal free=%u largest=%u PSRAM free=%u", stage,
          heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
          heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
          heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}
}  // namespace

bool HalBlePageTurner::resident() const { return host().isRunning() || host().isStopping(); }

bool HalBlePageTurner::enable() {
  if (resident()) return optedIn;
  // BLE needs controller RAM and task stacks even on PSRAM-equipped boards.
  if (WiFi.getMode() != WIFI_MODE_NULL || !hasHeadroom(128 * 1024, 80 * 1024)) {
    LOG_ERR("BLE", "Start refused: Wi-Fi active or insufficient internal heap");
    logHeap("refused");
    state = Status::LowMemory;
    return false;
  }
  HalPowerManager::Lock powerLock;
  logHeap("before start");
  if (!host().begin("CrossInk X4 Pro")) {
    LOG_ERR("BLE", "HID host initialization failed");
    state = Status::Failed;
    return false;
  }
  // The pinned SDK doesn't check xTaskCreate's result. Refuse connection work
  // unless its verified task exists, so OOM cannot strand a pending connect.
  if (!xTaskGetHandle("ble-conn")) {
    LOG_ERR("BLE", "HID connection task allocation failed");
    stop();
    state = Status::Failed;
    return false;
  }
  // No background reconnect to arbitrary saved bonds. Pairing is explicit.
  host().disconnect();
  optedIn = true;
  state = Status::Ready;
  pairingPasskey = 0;
  filter.reset();
  logHeap("after start");
  if (!hasHeadroom(64 * 1024, 32 * 1024)) {
    LOG_ERR("BLE", "Rolling back BLE start to preserve reader heap");
    stop();
    state = Status::LowMemory;
    return false;
  }
  return true;
}

bool HalBlePageTurner::stop(uint32_t timeoutMs) {
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
  if (state != Status::Off) logHeap("stopped");
  state = Status::Off;
  return true;
}

bool HalBlePageTurner::scan() {
  if (!optedIn || host().isConnecting() || host().isConnected() || scanPending) return false;
  count = 0;
  pairingPasskey = 0;
  host().startScan(5000);
  scanPending = true;
  state = Status::Scanning;
  return true;
}

bool HalBlePageTurner::connect(uint8_t index) {
  if (!optedIn || index >= count || host().isConnecting() || host().isConnected()) return false;
  std::memcpy(selected, devices[index].address, sizeof(selected));
  pairingPasskey = 0;
  filter.reset();
  if (!host().connect(selected)) {
    LOG_ERR("BLE", "Connect request rejected");
    state = Status::Failed;
    return false;
  }
  state = Status::Connecting;
  return true;
}

void HalBlePageTurner::forget() {
  if (!optedIn || host().isConnecting()) return;
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
  if (WiFi.getMode() != WIFI_MODE_NULL || !hasHeadroom(48 * 1024, 24 * 1024)) {
    LOG_ERR("BLE", "Stopping BLE for Wi-Fi or low reader heap");
    logHeap("low headroom");
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
