#include "../../src/util/BleLabLayout.h"
using namespace BleLabLayout;
constexpr int SmallLine = 20;
constexpr int CoverY = coverTop(20, 9);
constexpr int MenuY = CoverY + 242 + CoverGap;
constexpr int LabY = top(800, 3, 40, SmallLine);
constexpr int ExpandedY = top(800, 3, 40, SmallLine, true);
static_assert(CoverY == 34 && MenuY == 288);
static_assert(MenuRow >= 48);
static_assert(ExpandedY == 550);
static_assert(MenuY + menuHeight(5) + CoverGap <= ExpandedY);
constexpr int Available = ExpandedY - CoverGap - MenuY;
static_assert(menuPageRows(Available) == 5);
static_assert(menuRowHeight(Available, 5) == 48);
static_assert(menuRowHeight(Available, 7) == 48);
static_assert(menuRowHeight(LabY - CoverGap - MenuY, 5) > 48);
static_assert(MenuY + 5 * menuRowHeight(Available, 5) + 4 * MenuGap <= ExpandedY - CoverGap);
static_assert(ExpandedY + height(SmallLine, true) == 748);
static_assert(LabY + height(SmallLine) == 748);
static_assert(GridRows == 2 && Controls == 6);
static_assert((440 - 2 * ButtonGap) / 3 - 12 - 24 - 4 == 102);
static_assert(top(800, 60, 40, SmallLine) + height(SmallLine) == 728);

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
