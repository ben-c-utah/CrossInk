#include <BleForget.h>
#include <BleButtonBindings.h>

using namespace freeink::bleforget;

namespace {
// Mocks storage responses, not NimBLE/NVS. The production transaction template
// must order real operations identically and stop on every failed stage.
struct Storage {
  bool security[3]{true, true, true};
  bool metadataRecords[3]{true, true, true};
  bool mapping[3]{true, true, true};
  int target = 1;
  int connected = 1;
  bool all = false;
  bool credentialFailure = false;
  bool metadataFailure = false;
  bool mappingFailure = false;
  Code ready = Code::Done;
  unsigned metadataCalls = 0;
  constexpr Code prepare() {
    if (ready == Code::Done && (all || connected == target)) connected = -1;
    return ready;
  }
  constexpr Step credentials() {
    if (credentialFailure) return {false, false};
    bool changed = false;
    for (int i = 0; i < 3; ++i) if ((all || i == target) && security[i]) { security[i] = false; changed = true; }
    return {true, changed};
  }
  constexpr Step metadata() {
    ++metadataCalls;
    if (metadataFailure) return {false, false};
    bool changed = false;
    for (int i = 0; i < 3; ++i) if ((all || i == target) && metadataRecords[i]) { metadataRecords[i] = false; changed = true; }
    return {true, changed};
  }
  constexpr Result execute() {
    auto result = run(*this);
    if (!result.ok()) return result;
    bool changed = false;
    for (int i = 0; i < 3; ++i) if ((all || i == target) && mapping[i]) changed = true;
    result = mappings(result, changed, !mappingFailure);
    if (result.ok()) for (int i = 0; i < 3; ++i) if (all || i == target) mapping[i] = false;
    return result;
  }
};
constexpr bool targeted() {
  Storage s;
  if (s.execute().code != Code::Done || s.connected != -1) return false;
  if (s.security[1] || s.metadataRecords[1] || s.mapping[1]) return false;
  for (int i : {0, 2}) if (!s.security[i] || !s.metadataRecords[i] || !s.mapping[i]) return false;
  if (s.execute().code != Code::Absent) return false;
  Storage disconnected;
  disconnected.connected = 0;
  return disconnected.execute().ok() && disconnected.connected == 0;
}
constexpr bool inconsistent() {
  Storage s;
  s.security[1] = false; // Metadata only.
  if (s.execute().code != Code::Done || s.metadataRecords[1] || s.mapping[1]) return false;
  Storage orphan;
  orphan.metadataRecords[1] = false; // Security only.
  return orphan.execute().code == Code::Done && !orphan.security[1] && !orphan.mapping[1];
}
constexpr bool failures() {
  Storage s;
  s.credentialFailure = true;
  if (s.execute().code != Code::Credentials || s.metadataCalls || !s.metadataRecords[1] || !s.mapping[1]) return false;
  s.credentialFailure = false;
  s.metadataFailure = true;
  if (s.execute().code != Code::Metadata || s.security[1] || !s.mapping[1]) return false;
  s.metadataFailure = false;
  s.mappingFailure = true;
  if (s.execute().code != Code::Mappings || !s.mapping[1]) return false;
  s.mappingFailure = false;
  return s.execute().code == Code::Done && s.execute().code == Code::Absent;
}
constexpr bool allDevices() {
  Storage s;
  s.all = true;
  s.security[0] = false;
  s.metadataRecords[2] = false;
  if (s.execute().code != Code::Done || s.connected != -1) return false;
  for (int i = 0; i < 3; ++i) if (s.security[i] || s.metadataRecords[i] || s.mapping[i]) return false;
  return s.execute().code == Code::Absent;
}
constexpr bool busyAndOff() {
  for (auto reason : {Code::Busy, Code::RadioOff, Code::Identity}) {
    Storage s;
    s.ready = reason;
    if (s.execute().code != reason || s.metadataCalls || !s.security[1] || !s.mapping[1]) return false;
  }
  return true;
}
constexpr bool allFailurePreservesRecovery() {
  Storage s;
  s.all = true;
  s.credentialFailure = true;
  if (s.execute().code != Code::Credentials || s.metadataCalls) return false;
  for (int i = 0; i < 3; ++i) if (!s.metadataRecords[i] || !s.mapping[i]) return false;
  s.credentialFailure = false;
  s.metadataFailure = true;
  if (s.execute().code != Code::Metadata) return false;
  for (int i = 0; i < 3; ++i) if (s.security[i] || !s.metadataRecords[i] || !s.mapping[i]) return false;
  s.metadataFailure = false;
  return s.execute().code == Code::Done;
}
constexpr bool actualMappingIsolation() {
  BleBindings::Store store;
  const BleBindings::Peer kobo{"a4:3c:d7:9c:93:b1", 0};
  const BleBindings::Peer windows{"01:02:03:04:05:06", 1};
  store.assign(kobo, BleBindings::Action::Next, 0x010251);
  store.assign(windows, BleBindings::Action::Next, 0x01024f);
  store.reset(kobo);
  BleBindings::Store restored;
  return BleBindings::decode(BleBindings::encode(store), restored) &&
         !restored.get(kobo, BleBindings::Action::Next) && restored.get(windows, BleBindings::Action::Next) == 0x01024f;
}
static_assert(targeted(), "Target only one device and preserve others, including an unrelated live connection");
static_assert(inconsistent(), "Handle metadata-only and security-only peers");
static_assert(failures(), "Credential/metadata/mapping failures must remain failures with retry state");
static_assert(allDevices(), "All-device recovery covers inconsistent stores and repeats as a no-op");
static_assert(busyAndOff(), "Busy/off/identity failures must never delete storage");
static_assert(allFailurePreservesRecovery(), "All-device partial failures preserve recovery state and report failure");
static_assert(actualMappingIsolation(), "Actual mapping codec preserves unrelated device assignments");
}  // namespace
