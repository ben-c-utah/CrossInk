#include "BleArrowFilter.h"

constexpr bool tapAndRepeat() {
  BleArrowFilter filter;
  if (filter.accept(1, 2, 0x4f, true, 0x4f, 0, false) != 1) return false;
  if (filter.accept(1, 2, 0x4f, true, 0x4f, 0, false) != 0) return false;
  if (filter.accept(1, 2, 0x4f, false, 0, 0, false) != 0) return false;
  if (filter.accept(1, 2, 0x4f, true, 0x4f, 0, false) != 1) return false;
  filter.accept(1, 2, 0x4f, false, 0, 0, false);
  return filter.accept(1, 2, 0x50, true, 0x50, 0, false) == -1;
}

constexpr bool unrelatedReports() {
  BleArrowFilter filter;
  if (filter.accept(2, 2, 0x4f, true, 0x4f, 0, false) != 0) return false;
  if (filter.accept(1, 3, 0x4f, true, 0x4f, 0, false) != 0) return false;
  if (filter.accept(1, 2, 0x28, true, 0x28, 0, false) != 0) return false;
  filter.reset();
  if (filter.accept(1, 2, 0x4f, true, 0x4f, 2, false) != 0) return false;
  // Releasing Shift while the arrow stays held must not create a page turn.
  if (filter.accept(1, 2, 0x4f, true, 0x4f, 0, false) != 0) return false;
  filter.reset();
  if (filter.accept(1, 2, 0x4f, true, 0x50, 0, false) != 0) return false;
  filter.reset();
  if (filter.accept(1, 2, 0x4f, true, 0x4f, 0, true) != 0) return false;
  filter.reset();
  return filter.accept(1, 2, 0x4f, true, 0x4f, 0, false) == 1;
}

static_assert(tapAndRepeat(), "One arrow press must turn once; release permits the next press");
static_assert(unrelatedReports(), "Mouse, modifiers, other keys and false rest edges must not turn pages");
