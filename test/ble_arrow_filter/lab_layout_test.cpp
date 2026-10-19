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
static_assert(LabY == 644 && LabY >= MenuY + menuHeight(7) + Gap);
static_assert(LabY + height(SmallLine) == 748);
static_assert(800 - (LabY + height(SmallLine)) == 52);
static_assert(band(SmallLine) >= 22); // built-in Inter 8 ink ascent + descent
static_assert((440 - 2 * ButtonGap) / 3 - 12 - 24 - 4 == 102); // label after padding/icon/gap // text width after padding
static_assert(top(800, 60, 40, SmallLine) + height(SmallLine) == 728);

constexpr int ExpandedY = top(800, 3, 40, SmallLine, true);
static_assert(ExpandedY == 526);
static_assert(ExpandedY + height(SmallLine, true) == 748);
static_assert(GridRows == 2 && Controls == 6);
static_assert(ExpandedY > CoverY + 242); // book stays visible

constexpr int SnappedExpandedY = top(800, 3, 40, SmallLine, true, MenuY);
static_assert(SnappedExpandedY == 506);
static_assert(SnappedExpandedY + height(SmallLine, true) == 728);
static_assert((SnappedExpandedY - MenuY) % (MenuRow + MenuGap) == 0);

#include "../../src/util/BleLabInput.h"
static_assert(BleLabInput::route(-1, 1, false, false, true, 0).action == -2);
static_assert(BleLabInput::route(1, 1, true, false, true, 0).action == 0);
static_assert(BleLabInput::route(-1, -1, true, false, true, 6).action == 5);
static_assert(BleLabInput::route(-1, -1, false, true, true, 6).action == -1);
static_assert(!BleLabInput::route(1, -1, false, false, false, 0).handled);
static_assert(BleLabInput::command(0) == BleLabPolicy::Command::Toggle);
static_assert(BleLabInput::command(1) == BleLabPolicy::Command::Connect);
static_assert(BleLabInput::command(2) == BleLabPolicy::Command::Wifi);
static_assert(BleLabInput::command(3) == BleLabPolicy::Command::Logs);
static_assert(BleLabInput::command(4) == BleLabPolicy::Command::Update);
static_assert(BleLabInput::command(5) == BleLabPolicy::Command::Restart);
