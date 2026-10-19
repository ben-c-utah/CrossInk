#pragma once
#include "BleButtonBindings.h"

namespace BleLabPolicy {
enum class Command : uint8_t { None, Toggle, Connect, Restart };
enum class Phase : uint8_t { Idle, Enable, Connect, AwaitConnection, Stop, RestartStop, RestartReady };
constexpr uint32_t ConnectionTimeout = 45000;
constexpr uint32_t StopTimeout = 15000;
constexpr bool expired(uint32_t now, uint32_t since, uint32_t limit) { return now - since >= limit; }
constexpr bool restarting(Phase p) { return p == Phase::RestartStop || p == Phase::RestartReady; }
constexpr bool canRequest(Phase p, Command pending, Command next) {
  if (next == Command::None) return false;
  return next == Command::Restart ? !restarting(p) && pending != Command::Restart
                                 : p == Phase::Idle && pending == Command::None;
}
// NVS supplies integrity checking. Fixed version/size rejects incompatible records.
struct Selection {
  uint8_t version = 1;
  BleBindings::Peer peer{};
  char name[32]{};
};
static_assert(sizeof(Selection) == 52);
constexpr bool valid(const Selection& s) {
  return s.version == 1 && BleBindings::valid(s.peer) && s.name[31] == '\0';
}
}  // namespace BleLabPolicy
