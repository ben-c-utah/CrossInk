#pragma once
#include <algorithm>

// Presentation only. Basic Lyra diagnostic Home; no Bluetooth policy here.
namespace BleLabLayout {
constexpr int MenuRow = 48;
constexpr int MenuGap = 2;
constexpr int CoverGap = 12;
constexpr int ButtonHeight = 52;
constexpr int HeaderHeight = 32;
constexpr int Controls = 6;
constexpr int GridRows = 2;
constexpr int Gap = 4;
constexpr int BottomGap = 12;
constexpr int ButtonGap = 6;
constexpr int band(int lineHeight) { return lineHeight + 4; } // ink descenders, not just line advance
constexpr int height(int lineHeight, bool expanded = false) {
  // Identity is in the header. Two lines below hold heap/link and action feedback.
  return HeaderHeight + 2 * band(lineHeight) + (expanded ? 2 * ButtonHeight + ButtonGap + 2 * Gap : 0);
}
constexpr int top(int screenHeight, int bottomInset, int hintsHeight, int lineHeight, bool expanded = false) {
  const int raw = screenHeight - std::max(bottomInset, hintsHeight) - BottomGap - height(lineHeight, expanded);
  return raw;
}
constexpr int coverTop(int sidePadding, int topInset) { return std::max(sidePadding + 14, topInset); }
constexpr int menuHeight(int rows) { return rows * MenuRow + std::max(0, rows - 1) * MenuGap; }
constexpr int menuPageRows(int availableHeight) {
  return std::max(1, std::min(7, (availableHeight + MenuGap) / (MenuRow + MenuGap)));
}
constexpr int menuRowHeight(int availableHeight, int count) {
  const int visible = std::max(1, std::min(count, menuPageRows(availableHeight)));
  return std::max(MenuRow, (availableHeight - (visible - 1) * MenuGap) / visible);
}
} // namespace BleLabLayout
