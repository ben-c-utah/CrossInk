#include "BleArrowFilter.h"
#include "BleButtonBindings.h"

using namespace BleBindings;
constexpr Peer Kobo{"aa:bb:cc:dd:ee:01", 1};
constexpr Peer Windows{"aa:bb:cc:dd:ee:02", 0};
constexpr uint32_t Down = 0x010251;
constexpr uint32_t Up = 0x010252;

constexpr bool persistenceAndIsolation() {
  Store store;
  if (store.assign(Kobo, Action::Next, Down) != Result::Saved ||
      store.assign(Kobo, Action::Previous, Up) != Result::Saved) return false;
  if (store.assign(Kobo, Action::Previous, Down) != Result::Duplicate || store.get(Kobo, Action::Previous) != Up)
    return false;
  if (store.assign(Kobo, Action::Next, Down) != Result::Unchanged) return false;
  Store loaded;
  const auto blob = encode(store);
  if (!decode(blob, loaded) || encode(loaded) != blob) return false;
  if (loaded.get(Kobo, Action::Next) != Down || loaded.get(Kobo, Action::Previous) != Up ||
      loaded.get(Windows, Action::Next)) return false;
  if (loaded.get(Peer{"AA:BB:CC:DD:EE:01", 1}, Action::Next) != Down ||
      loaded.get(Peer{"aa:bb:cc:dd:ee:01", 0}, Action::Next)) return false;
  auto bad = blob;
  bad[12] ^= 1;
  if (decode(bad, loaded) || encode(loaded) != blob) return false;
  bad = blob;
  bad[2] = 2;
  put32(bad, bad.size() - 4, checksum(bad));
  if (decode(bad, loaded)) return false;
  bad = blob;
  put32(bad, 27, Down);  // Duplicate Next/Previous in a checksum-valid record.
  put32(bad, bad.size() - 4, checksum(bad));
  if (decode(bad, loaded)) return false;
  bad = blob;
  put32(bad, 23, 0xff010251);
  put32(bad, bad.size() - 4, checksum(bad));
  if (decode(bad, loaded)) return false;
  if (loaded.assign(Windows, Action::Next, 0x01024f) != Result::Saved) return false;
  if (!loaded.reset(Kobo) || loaded.get(Kobo, Action::Next)) return false;
  return decode(encode(loaded), store) && !store.get(Kobo, Action::Previous) &&
         store.get(Windows, Action::Next) == 0x01024f;
}

constexpr bool capacityAndValidation() {
  Store store;
  if (store.assign(Peer{"not an address", 0}, Action::Next, Down) != Result::Invalid ||
      store.assign(Kobo, Action::Next, 0x010200) != Result::Invalid ||
      store.assign(Kobo, Action::Next, 0xff010251) != Result::Invalid) return false;
  for (unsigned i = 0; i < MaxPeers; ++i) {
    auto peer = Kobo;
    peer.address[16] = '0' + i;
    if (store.assign(peer, Action::Next, Down) != Result::Saved) return false;
  }
  auto extra = Kobo;
  extra.address[16] = '9';
  return store.assign(extra, Action::Next, Down) == Result::Full;
}

constexpr bool pressEdgesAndArrows() {
  Store store;
  store.assign(Kobo, Action::Next, Down);
  store.assign(Kobo, Action::Previous, Up);
  Router router;
  if (router.accept(store, Kobo, Down, true, false, 0, 0) != 1 ||
      router.accept(store, Kobo, Down, true, false, 0, 0) != 0 ||
      router.accept(store, Kobo, Down, false, false, 0, 1) != 0 ||
      router.accept(store, Kobo, Down, true, false, 0, 0) != 1) return false;
  router.reset();
  if (router.accept(store, Windows, Down, true, false, 0, 0) != 0) return false;
  if (router.accept(store, Kobo, Up, true, false, 2, 0) != 0 ||
      router.accept(store, Kobo, Up, true, false, 0, 0) != 0) return false;
  router.accept(store, Kobo, Up, false, false, 0, 0);
  if (router.accept(store, Kobo, Up, true, false, 0, 0) != -1) return false;
  BleArrowFilter arrows;
  if (router.accept(store, Windows, 0x01024f, true, false, 0,
                    arrows.accept(1, 2, 0x4f, true, 0x4f, 0, false)) != 1) return false;
  arrows.accept(1, 2, 0x4f, false, 0, 0, false);
  if (router.accept(store, Windows, 0x010250, true, false, 0,
                    arrows.accept(1, 2, 0x50, true, 0x50, 0, false)) != -1) return false;
  // A learned override produces one action, rather than both it and fallback.
  store.assign(Kobo, Action::Next, 0x010250);
  router.reset();
  return router.accept(store, Kobo, 0x010250, true, false, 0, -1) == 1;
}

constexpr bool learningLifecycle() {
  Learner learner;
  learner.start(Kobo, Action::Next, 100);
  if (learner.feed(Down, false, false, 0, 101, 101) ||
      learner.feed(Down, true, false, 0, 99, 101) ||
      learner.feed(Down, true, false, 2, 102, 102)) return false;
  if (learner.candidate || learner.feed(Down, true, false, 0, 103, 103)) return false;
  if (learner.feed(Down, false, true, 0, 104, 104) || learner.candidate) return false;
  learner.feed(Down, true, false, 0, 105, 105);
  if (!learner.feed(Down, false, false, 0, 106, 106) || learner.state != Learning::Captured) return false;
  learner.start(Kobo, Action::Previous, 200);
  learner.tick(15200, true);
  if (learner.state != Learning::Timeout) return false;
  learner.start(Kobo, Action::Previous, 200);
  learner.tick(201, false);
  if (learner.state != Learning::Disconnected) return false;
  learner.cancel();
  if (learner.state != Learning::Idle) return false;
  learner.start(Kobo, Action::Next, 0xfffffff0u);
  learner.feed(Down, true, false, 0, 2, 2);
  return learner.feed(Down, false, false, 0, 3, 3);
}

static_assert(sizeof(Store) <= 128 && sizeof(Blob) == 116);
static_assert(persistenceAndIsolation(), "Binding persistence, corruption rejection and device isolation");
static_assert(capacityAndValidation(), "Bounded peer capacity and validated fingerprints");
static_assert(pressEdgesAndArrows(), "One press action, no releases/repeats, Windows arrows and per-peer overrides");
static_assert(learningLifecycle(), "Learn only fresh paired edges; handle rest, modifiers, timeout, cancel and disconnect");
