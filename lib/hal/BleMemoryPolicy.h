#pragma once

#include <cstddef>

namespace BleMemoryPolicy {
struct Budget {
  size_t freeInternal;
  size_t largestInternal;
};

constexpr Budget PostStart{64 * 1024, 32 * 1024};
constexpr Budget Running{48 * 1024, 24 * 1024};
// CrossPoint X4 Pro measurement with NimBLE host allocations in PSRAM:
// internal free 124752 -> 78244 (46508 consumed), largest 81908 -> 36852
// (45056 drop). Source: lib/BlePageTurner/src/RadioPolicy.h at
// 2c09b8ce8748463c603205aa815a527cd01f0a29, measured 2026-10-13.
// Keep CrossInk's stricter 32 KiB post-start reserve (upstream uses 24 KiB),
// plus the measured drop and a 2 KiB margin. This is a provisional budget,
// not a promise about fragmentation: always enforce the post-start check.
constexpr size_t MeasuredLargestDrop = 45056;
constexpr size_t LargestMargin = 2048;
constexpr Budget Start{128 * 1024, PostStart.largestInternal + MeasuredLargestDrop + LargestMargin};
static_assert(Start.largestInternal == 79872);
static_assert(Start.freeInternal >= 46508 + 4096 + PostStart.freeInternal);

struct Snapshot {
  size_t freeInternal;
  size_t largestInternal;
  size_t freePsram;
  int wifiMode;  // WIFI_MODE_NULL is 0; checked against the SDK in the HAL.
  bool psramAvailable;
};

struct Failures {
  bool wifi;
  bool freeInternal;
  bool largestInternal;
  bool psram;
  constexpr bool any() const { return wifi || freeInternal || largestInternal || psram; }
};

constexpr Failures evaluate(const Snapshot& heap, const Budget& budget) {
  // Evaluate every check; diagnostic output must not hide additional failures.
  return {heap.wifiMode != 0, heap.freeInternal < budget.freeInternal,
          heap.largestInternal < budget.largestInternal, !heap.psramAvailable || heap.freePsram == 0};
}
}  // namespace BleMemoryPolicy
