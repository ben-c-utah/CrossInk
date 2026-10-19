#pragma once
#include <algorithm>

// Presentation only. Basic Lyra diagnostic Home; no Bluetooth policy here.
namespace BleLabLayout {
constexpr int MenuRow = 42;
constexpr int MenuGap = 4;
constexpr int CoverGap = 0;
constexpr int ButtonHeight = 44;
constexpr int Gap = 4;
constexpr int BottomGap = 12;
constexpr int ButtonGap = 6;
constexpr int band(int lineHeight) { return lineHeight + 4; } // ink descenders, not just line advance
constexpr int height(int lineHeight) { return 4 * band(lineHeight) + ButtonHeight + 2 * Gap; }
constexpr int top(int screenHeight, int bottomInset, int hintsHeight, int lineHeight) {
  return screenHeight - std::max(bottomInset, hintsHeight) - BottomGap - height(lineHeight);
}
constexpr int coverTop(int sidePadding, int topInset) { return std::max(sidePadding + 14, topInset); }
constexpr int menuHeight(int rows) { return rows * MenuRow + std::max(0, rows - 1) * MenuGap; }
} // namespace BleLabLayout
