#include "HalBlePageTurner.h"

#if CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <BleKeyboardHost.h>
#include <HalPowerManager.h>
#include <Logging.h>
#include <WiFi.h>
#include <esp_heap_caps.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <nvs.h>

#include <cstring>
#include <cstdio>

#include "BleMemoryPolicy.h"
#include <HeapDiagnostics.h>

#if !defined(CROSSINK_BLE_HOST_PSRAM) || !CONFIG_BT_NIMBLE_MEM_ALLOC_MODE_EXTERNAL
#error "X4 Pro BLE memory policy requires the PSRAM NimBLE host allocator"
#endif

HalBlePageTurner blePageTurner;

namespace {
static_assert(WIFI_MODE_NULL == 0);
static_assert(BleBindings::MaxPeers == freeink::BleKeyboardHost::kMaxBonds);
constexpr const char* BindingNamespace = "crossink-ble";
bool saveBindings(const BleBindings::Store& bindings) {
  // One small NVS blob avoids allocating an SD/JSON document while BLE runs.
  const auto blob = BleBindings::encode(bindings);
  nvs_handle_t handle;
  esp_err_t err = nvs_open(BindingNamespace, NVS_READWRITE, &handle);
  if (err == ESP_OK) {
    err = nvs_set_blob(handle, "buttons", blob.data(), blob.size());
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
  }
  if (err != ESP_OK) LOG_ERR("BLE", "Button assignment save failed: %s", esp_err_to_name(err));
  return err == ESP_OK;
}
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
const char* HalBlePageTurner::connectedName() const { return host().connectedName(); }

BleBindings::Peer HalBlePageTurner::pairedPeer() const {
  BleBindings::Peer peer{};
  if (!host().isConnected()) return peer;
  std::memcpy(peer.address, host().connectedAddr(), sizeof(peer.address));
  for (uint8_t i = 0; i < host().pairedCount(); ++i) {
    BleBindings::Peer bond{};
    std::memcpy(bond.address, host().paired(i).addr, sizeof(bond.address));
    bond.type = host().paired(i).addrType;
    peer.type = bond.type;
    if (BleBindings::same(peer, bond)) return peer;
  }
  return {};
}

bool HalBlePageTurner::loadBindings() {
  if (bindingsLoaded) return true;
  nvs_handle_t handle;
  esp_err_t err = nvs_open(BindingNamespace, NVS_READONLY, &handle);
  if (err == ESP_ERR_NVS_NOT_FOUND) { bindingsLoaded = true; return true; }
  if (err != ESP_OK) {
    LOG_ERR("BLE", "Button assignment open failed: %s", esp_err_to_name(err));
    return false;
  }
  BleBindings::Blob blob{};
  size_t size = blob.size();
  err = nvs_get_blob(handle, "buttons", blob.data(), &size);
  nvs_close(handle);
  if (err == ESP_ERR_NVS_NOT_FOUND) { bindingsLoaded = true; return true; }
  if (err != ESP_OK && err != ESP_ERR_NVS_INVALID_LENGTH) {
    LOG_ERR("BLE", "Button assignment read failed: %s", esp_err_to_name(err));
    return false;
  }
  if (err != ESP_OK || size != blob.size() || !BleBindings::decode(blob, bindings)) {
    LOG_ERR("BLE", "Invalid saved button assignments ignored (size=%u)", static_cast<unsigned>(size));
    bindingsInvalid = true;
    learner.state = BleBindings::Learning::StorageError;
  }
  bindingsLoaded = true;
  return true;
}

bool HalBlePageTurner::hasBinding(BleBindings::Action action) const { return bindings.get(pairedPeer(), action) != 0; }

bool HalBlePageTurner::beginLearning(BleBindings::Action action) {
  if (bindingsInvalid) { learner.state = BleBindings::Learning::StorageError; return false; }
  const auto peer = pairedPeer();
  if (!optedIn || !BleBindings::valid(peer)) {
    learner.state = BleBindings::Learning::Disconnected;
    return false;
  }
  discardInput();
  learner.start(peer, action, millis());
  return true;
}

void HalBlePageTurner::discardInput() {
  const auto peer = pairedPeer();
  // Drop old queued input before arming/leaving; preserve held-state tracking so a
  // cancelled capture cannot turn an already-held button into a fresh press.
  freeink::RawButtonEvent raw;
  while (host().popRawButton(raw)) {
    const auto fallback = filter.accept(raw.reportId, raw.byteIndex, raw.value, raw.pressed, raw.keycode, raw.mods, raw.wasRest);
    bindingRouter.accept(bindings, peer, raw.code(), raw.pressed, raw.wasRest, raw.mods, fallback);
  }
  freeink::KeyEvent key;
  while (host().popKey(key)) {}
}

void HalBlePageTurner::cancelLearning() {
  learner.cancel();
  discardInput();
}

void HalBlePageTurner::completeLearning() {
  auto next = bindings;
  const auto result = next.assign(learner.peer, learner.action, learner.candidate);
  if (result == BleBindings::Result::Duplicate) learner.state = BleBindings::Learning::Duplicate;
  else if (result == BleBindings::Result::Full || result == BleBindings::Result::Invalid)
    learner.state = BleBindings::Learning::Full;
  else if (result == BleBindings::Result::Unchanged) learner.state = BleBindings::Learning::Saved;
  else if (saveBindings(next)) {
    bindings = next;
    bindingRouter.reset();
    learner.state = BleBindings::Learning::Saved;
  } else learner.state = BleBindings::Learning::StorageError;
  if (learner.state == BleBindings::Learning::Saved) failureReasons &= ~ButtonStorage;
}

bool HalBlePageTurner::resetButtons() {
  if (bindingsInvalid) { learner.state = BleBindings::Learning::StorageError; return false; }
  const auto peer = pairedPeer();
  if (!optedIn || !BleBindings::valid(peer)) { learner.state = BleBindings::Learning::Disconnected; return false; }
  auto next = bindings;
  if (next.reset(peer) && !saveBindings(next)) { learner.state = BleBindings::Learning::StorageError; return false; }
  bindings = next;
  bindingRouter.reset();
  learner.state = BleBindings::Learning::Saved;
  failureReasons &= ~ButtonStorage;
  return true;
}

bool HalBlePageTurner::enable() {
  if (resident()) return optedIn;
  failureReasons = None;
  if (!loadBindings()) {
    state = Status::Failed;
    failureReasons = ButtonStorage;
    return false;
  }
#if CROSSINK_BLE_INPUT_DIAGNOSTICS
  diagnosticEdges = 0;
#endif
#if CROSSINK_HEAP_DIAGNOSTICS
  HeapDiagnostics::snapshot("BLE before preflight", "", true);
#endif
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
#if CROSSINK_HEAP_DIAGNOSTICS
  HeapDiagnostics::snapshot("BLE initialization complete");
#endif
  return true;
}

bool HalBlePageTurner::stop(uint32_t timeoutMs) {
  learner.tick(millis(), false);
  const bool wasResident = resident();
#if CROSSINK_HEAP_DIAGNOSTICS
  if (wasResident && !host().isStopping()) HeapDiagnostics::snapshot("BLE before shutdown", "", true);
#endif
  optedIn = false;
  pairingPasskey = 0;
  scanPending = false;
  count = 0;
  filter.reset();
  bindingRouter.reset();
  // Also covers calls from sleep/USB handoff; end() may need later retries.
  powerManager.setPowerSaving(false);
  if (!host().end(timeoutMs)) {
    state = Status::Stopping;
    return false;
  }
  if (wasResident) logGuard("after shutdown", memorySnapshot(), BleMemoryPolicy::PostStart);
#if CROSSINK_HEAP_DIAGNOSTICS
  if (wasResident) {
    HeapDiagnostics::snapshot("BLE teardown complete", "running=0 stopping=0", true);
  }
#endif
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
  return connectAddress(devices[index].address);
}

bool HalBlePageTurner::connectAddress(const char* address) {
  failureReasons = None;
  std::memcpy(selected, address, sizeof(selected));
  pairingPasskey = 0;
  filter.reset();
  bindingRouter.reset();
  learner.tick(millis(), false);
  if (!host().connect(selected)) {
    LOG_ERR("BLE", "Connect request rejected");
    state = Status::Failed;
    failureReasons = Connection;
    return false;
  }
  state = Status::Connecting;
  return true;
}

bool HalBlePageTurner::listSaved(SavedDevice* out, uint8_t capacity, uint8_t& savedCount) {
  if (!loadBindings() || bindingsInvalid || !host().listStored(out, capacity, savedCount)) return false;
  for (const auto& table : bindings.tables) {
    if (!BleBindings::valid(table.peer)) continue;
    bool found = false;
    for (uint8_t i = 0; i < savedCount; ++i)
      if (strcasecmp(out[i].addr, table.peer.address) == 0 && out[i].addrType == table.peer.type) found = true;
    if (found) continue;
    if (savedCount == capacity) return false;
    auto& device = out[savedCount++];
    device = {};
    memcpy(device.addr, table.peer.address, sizeof(device.addr));
    device.addrType = table.peer.type;
  }
  for (uint8_t i = 0; i < savedCount; ++i) {
    if (out[i].name[0]) continue;
    // Display-only name lookup; deletion still uses the copied address/type.
    for (uint8_t j = 0; j < count; ++j) if (strcasecmp(out[i].addr, devices[j].address) == 0)
      std::snprintf(out[i].name, sizeof(out[i].name), "%s", devices[j].name);
  }
  return true;
}

HalBlePageTurner::ForgetResult HalBlePageTurner::forget(const SavedDevice& target) {
  using namespace freeink::bleforget;
  if (!loadBindings() || bindingsInvalid) return {Code::Mappings, false};
  HalPowerManager::Lock powerLock;
  SavedDevice identity{};
  auto result = host().forgetPeer(target, identity);
  if (!result.ok()) return result;
  auto next = bindings;
  const auto remove = [&](const SavedDevice& device) {
    BleBindings::Peer peer{};
    memcpy(peer.address, device.addr, sizeof(peer.address));
    peer.type = device.addrType;
    return next.reset(peer);
  };
  const bool original = remove(target);
  const bool resolved = remove(identity);
  const bool changed = original || resolved;
  result = freeink::bleforget::mappings(result, changed, !changed || saveBindings(next));
  if (!result.ok()) return result;
  bindings = next;
  cancelLearning();
  bindingRouter.reset();
  count = 0;
  scanPending = false;
  host().releaseScanResults();
  failureReasons = None;
  state = host().isConnected() ? Status::Connected : Status::Ready;
  LOG_INF("BLE", "Forget one completed: address=%s type=%u changed=%u", target.addr, target.addrType, result.changed);
  return result;
}

HalBlePageTurner::ForgetResult HalBlePageTurner::forgetAll() {
  using namespace freeink::bleforget;
  if (!loadBindings()) return {Code::Mappings, false};
  // Complete teardown before touching the dedicated NimBLE namespace. This also
  // works when startup was refused: no init, guard bypass or stale host cache.
  HalPowerManager::Lock powerLock;
  if (!stop(2000)) return {Code::Busy, false};
  auto result = host().forgetAllStored();
  if (!result.ok()) return result;
  bool changed = bindingsInvalid;
  for (const auto& table : bindings.tables) if (table.peer.address[0]) changed = true;
  const BleBindings::Store empty{};
  result = freeink::bleforget::mappings(result, changed, saveBindings(empty));
  if (!result.ok()) return result;
  bindings = empty;
  bindingsInvalid = false;
  learner.cancel();
  bindingRouter.reset();
  selected[0] = '\0';
  failureReasons = None;
  LOG_INF("BLE", "Forget all completed: changed=%u (radio remains off)", result.changed);
  return result;
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
    LOG_INF("BLE", "Pairing passkey available on screen (value omitted)");
  }
  if (host().isConnected()) {
    pairingPasskey = 0;
    if (state != Status::Connected) {
      LOG_INF("BLE", "Connected to %s", host().connectedName());
      host().releaseScanResults();
#if CROSSINK_HEAP_DIAGNOSTICS
      HeapDiagnostics::snapshot("BLE connected scan released");
#endif
    }
    state = Status::Connected;
  } else if (state == Status::Connected) {
    LOG_INF("BLE", "Disconnected; reconnect explicitly from Bluetooth settings");
    filter.reset();
    bindingRouter.reset();
    state = Status::Ready;
  }
  const auto peer = pairedPeer();
  const bool capturing = learner.state == BleBindings::Learning::Waiting;
  learner.tick(millis(), BleBindings::valid(peer) && BleBindings::same(peer, learner.peer));
  // Drain the translated queue too; only raw press edges drive page turns.
  freeink::KeyEvent key;
  while (host().popKey(key)) {}
  freeink::RawButtonEvent raw;
  while (host().popRawButton(raw)) {
    const int8_t fallback = filter.accept(raw.reportId, raw.byteIndex, raw.value, raw.pressed, raw.keycode, raw.mods,
                                           raw.wasRest);
    const int8_t direction = bindingRouter.accept(bindings, peer, raw.code(), raw.pressed, raw.wasRest, raw.mods, fallback);
    if (capturing) {
      if (learner.feed(raw.code(), raw.pressed, raw.wasRest, raw.mods, raw.atMs, millis())) completeLearning();
      continue;
    }
#if CROSSINK_BLE_INPUT_DIAGNOSTICS
    if (diagnosticEdges < 256) {
      ++diagnosticEdges;
      LOG_INF("BLE", "raw id=%u byte=%u value=%02X pressed=%u usage=%02X mods=%02X rest=%u arrow=%d age=%lu",
              raw.reportId, raw.byteIndex, raw.value, raw.pressed, raw.keycode, raw.mods, raw.wasRest, direction,
              static_cast<unsigned long>(millis() - raw.atMs));
    }
#endif
    // Never replay an old settings/overlay key after a slow render or transition.
    if (direction && millis() - raw.atMs <= 250 && host().isConnected() &&
        std::strcmp(selected, host().connectedAddr()) == 0) {
      LOG_INF("BLE", "HID 0x%02X -> %s", raw.keycode, direction > 0 ? "next" : "previous");
      return direction;
    }
  }
  return 0;
}

#if CROSSINK_BLE_LAB
bool HalBlePageTurner::labWifiActive() const { return WiFi.getMode() != WIFI_MODE_NULL; }
bool HalBlePageTurner::labConnectedPeer(BleLabPolicy::Selection& out) const {
  if (!enabled() || host().isStopping() || host().isConnecting()) return false;
  const auto peer = pairedPeer();
  if (!BleBindings::valid(peer)) return false;
  out = {};
  out.peer = peer;
  std::snprintf(out.name, sizeof(out.name), "%s", connectedName());
  return true;
}
bool HalBlePageTurner::labPeerConnected(const BleBindings::Peer& peer) const {
  return BleBindings::same(peer, pairedPeer());
}
bool HalBlePageTurner::labConnectSaved(const BleBindings::Peer& peer) {
  if (!enabled() || host().isConnecting() || host().isConnected() || host().isScanning() || scanPending) return false;
  // Never trust a name, stale scan index, or a Lab record without SDK metadata.
  for (uint8_t i = 0; i < host().pairedCount(); ++i) {
    const auto& saved = host().paired(i);
    BleBindings::Peer known{};
    std::memcpy(known.address, saved.addr, sizeof(known.address));
    known.type = saved.addrType;
    if (BleBindings::same(peer, known)) return connectAddress(peer.address);
  }
  LOG_ERR("BLE", "Home Lab selection is no longer a remembered peer");
  return false;
}
bool HalBlePageTurner::labLoadSelection(BleLabPolicy::Selection& out, bool& present) {
  present = false;
  nvs_handle_t handle;
  auto err = nvs_open(BindingNamespace, NVS_READONLY, &handle);
  if (err == ESP_ERR_NVS_NOT_FOUND) return true;
  if (err == ESP_OK) {
    size_t size = sizeof(out);
    err = nvs_get_blob(handle, "lab-peer", &out, &size);
    nvs_close(handle);
    if (err == ESP_ERR_NVS_NOT_FOUND) return true;
    if (err == ESP_OK && size == sizeof(out) && BleLabPolicy::valid(out)) { present = true; return true; }
  }
  LOG_ERR("BLE", "Home Lab selection read failed: %s", esp_err_to_name(err));
  return false;
}
bool HalBlePageTurner::labSaveSelection(const BleLabPolicy::Selection& value) {
  if (!BleLabPolicy::valid(value)) return false;
  nvs_handle_t handle;
  auto err = nvs_open(BindingNamespace, NVS_READWRITE, &handle);
  if (err == ESP_OK) {
    err = nvs_set_blob(handle, "lab-peer", &value, sizeof(value));
    if (err == ESP_OK) err = nvs_commit(handle);
    BleLabPolicy::Selection check{};
    size_t size = sizeof(check);
    if (err == ESP_OK) err = nvs_get_blob(handle, "lab-peer", &check, &size);
    if (err == ESP_OK && (size != sizeof(value) || std::memcmp(&check, &value, sizeof(value)))) err = ESP_FAIL;
    nvs_close(handle);
  }
  if (err != ESP_OK) LOG_ERR("BLE", "Home Lab selection save failed: %s", esp_err_to_name(err));
  return err == ESP_OK;
}
bool HalBlePageTurner::labClearSelection() {
  nvs_handle_t handle;
  auto err = nvs_open(BindingNamespace, NVS_READONLY, &handle);
  if (err == ESP_ERR_NVS_NOT_FOUND) return true;
  if (err != ESP_OK) { LOG_ERR("BLE", "Lab clear open failed: %s", esp_err_to_name(err)); return false; }
  size_t probe = 0;
  err = nvs_get_blob(handle, "lab-peer", nullptr, &probe);
  nvs_close(handle);
  if (err == ESP_ERR_NVS_NOT_FOUND) return true;
  if (err != ESP_OK) { LOG_ERR("BLE", "Lab clear lookup failed: %s", esp_err_to_name(err)); return false; }
  err = nvs_open(BindingNamespace, NVS_READWRITE, &handle);
  if (err == ESP_OK) {
    err = nvs_erase_key(handle, "lab-peer");
    if (err == ESP_ERR_NVS_NOT_FOUND) err = ESP_OK;
    if (err == ESP_OK) err = nvs_commit(handle);
    size_t size = 0;
    if (err == ESP_OK && nvs_get_blob(handle, "lab-peer", nullptr, &size) != ESP_ERR_NVS_NOT_FOUND) err = ESP_FAIL;
    nvs_close(handle);
  }
  if (err != ESP_OK) LOG_ERR("BLE", "Home Lab selection clear failed: %s", esp_err_to_name(err));
  return err == ESP_OK;
}
#endif
#endif
