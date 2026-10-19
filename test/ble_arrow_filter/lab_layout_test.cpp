#include "../../src/util/BleLabLayout.h"
using namespace BleLabLayout;
// X4 Pro panel is 800x480, displayed as portrait 480x800 on Home.
constexpr int SmallLine = 20;
constexpr int CoverY = coverTop(20, 9);
constexpr int MenuY = CoverY + 242 + CoverGap;
constexpr int LabY = top(800, 3, 40, SmallLine);
static_assert(CoverY == 34 && MenuY == 276);
static_assert(5 + 5 + 2 + 22 <= CoverY); // status origin/inset + small-font ink
static_assert(MenuY + menuHeight(7) == 594);
static_assert(LabY == 600 && LabY >= MenuY + menuHeight(7) + Gap);
static_assert(LabY + height(SmallLine) == 748);
static_assert(800 - (LabY + height(SmallLine)) == 52);
static_assert(band(SmallLine) >= 22); // built-in Inter 8 ink ascent + descent
static_assert((440 - 2 * ButtonGap) / 3 - 12 == 130); // text width after padding
static_assert(top(800, 60, 40, SmallLine) + height(SmallLine) == 728);
