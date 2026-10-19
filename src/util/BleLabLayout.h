#pragma once
#include <algorithm>

// Presentation only. Basic Lyra diagnostic Home; no Bluetooth policy here.
namespace BleLabLayout {
constexpr int MenuRow = 42;
constexpr int MenuGap = 4;
constexpr int CoverGap = 0;
constexpr int ButtonHeight = 52;
constexpr int HeaderHeight = 32;
constexpr int Controls = 6;
constexpr int GridRows = 2;
constexpr int Gap = 4;
constexpr int BottomGap = 12;
constexpr int ButtonGap = 6;
constexpr int band(int lineHeight) { return lineHeight + 4; } // ink descenders, not just line advance
constexpr int height(int lineHeight, bool expanded = false) {
  return HeaderHeight + 3 * band(lineHeight) + (expanded ? 2 * ButtonHeight + ButtonGap + 2 * Gap : 0);
}
constexpr int top(int screenHeight, int bottomInset, int hintsHeight, int lineHeight, bool expanded = false, int menuY = 0) {
  const int raw = screenHeight - std::max(bottomInset, hintsHeight) - BottomGap - height(lineHeight, expanded);
  // Expanded panel replaces complete trailing menu rows, never half a label.
  return expanded && menuY > 0 ? menuY + std::max(0, (raw - menuY) / (MenuRow + MenuGap)) * (MenuRow + MenuGap) : raw;
}
constexpr int coverTop(int sidePadding, int topInset) { return std::max(sidePadding + 14, topInset); }
constexpr int menuHeight(int rows) { return rows * MenuRow + std::max(0, rows - 1) * MenuGap; }
} // namespace BleLabLayout
