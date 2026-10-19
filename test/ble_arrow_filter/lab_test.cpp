#include "BleLabPolicy.h"
using namespace BleLabPolicy;

static_assert(canRequest(Phase::Idle, Command::None, Command::Connect));
static_assert(!canRequest(Phase::Idle, Command::Connect, Command::Connect));
static_assert(!canRequest(Phase::Enable, Command::None, Command::Toggle));
static_assert(!canRequest(Phase::AwaitConnection, Command::None, Command::Connect));
static_assert(canRequest(Phase::AwaitConnection, Command::None, Command::Restart));
static_assert(!canRequest(Phase::RestartStop, Command::None, Command::Restart));
static_assert(!canRequest(Phase::RestartReady, Command::None, Command::Restart));
static_assert(!canRequest(Phase::Idle, Command::Restart, Command::Toggle));
static_assert(!canRequest(Phase::Idle, Command::None, Command::None));
static_assert(!expired(101, 100, ConnectionTimeout));
static_assert(expired(45100, 100, ConnectionTimeout));
static_assert(expired(8, 0xfffffff0u, 24)); // millis wrap

constexpr Selection Kobo{1, {"a4:3c:d7:9c:93:b1", 0}, "Kobo Remote"};
constexpr Selection SameNameOtherDevice{1, {"a4:3c:d7:9c:93:b2", 0}, "Kobo Remote"};
constexpr Selection SameAddressOtherType{1, {"a4:3c:d7:9c:93:b1", 1}, "Kobo Remote"};
static_assert(valid(Kobo) && valid(SameNameOtherDevice));
static_assert(!BleBindings::same(Kobo.peer, SameNameOtherDevice.peer));
static_assert(!BleBindings::same(Kobo.peer, SameAddressOtherType.peer));
static_assert(!valid(Selection{}));
static_assert(!valid(Selection{2, Kobo.peer, "Kobo Remote"}));
constexpr bool selectionRoundTrip() {
  const auto stored = Kobo;
  return valid(stored) && BleBindings::same(stored.peer, Kobo.peer) && stored.name[0] == 'K';
}
static_assert(selectionRoundTrip()); // fixed record has no borrowed string pointers
