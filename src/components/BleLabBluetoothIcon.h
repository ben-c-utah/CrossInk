#pragma once
#include <Icon.h>

// Small built-in monochrome Bluetooth rune. Compile-time vector rasterization:
// 72 flash bytes, no runtime allocation and no extra icon/font dependency.
namespace BleLabIcon {
struct Mask {
  uint8_t bits[72]{};
  constexpr Mask() {
    for (auto& byte : bits) byte = 0xff;
    line(12, 2, 12, 22);
    line(12, 2, 17, 7);
    line(17, 7, 7, 17);
    line(7, 7, 17, 17);
    line(17, 17, 12, 22);
  }
  constexpr void line(int x, int y, int endX, int endY) {
    const int dx = endX == x ? 0 : endX > x ? 1 : -1;
    const int dy = endY == y ? 0 : endY > y ? 1 : -1;
    for (;;) {
      // Two-pixel stroke; all points (and the adjacent pixel) stay in 24x24.
      for (int offset = 0; offset < 2; ++offset) {
        const int bit = y * 24 + x + offset;
        bits[bit / 8] &= uint8_t(~(0x80 >> (bit % 8)));
      }
      if (x == endX && y == endY) break;
      x += dx;
      y += dy;
    }
  }
};
static constexpr Mask bluetoothMask{};
static const freeink::Icon bluetooth{24, 24, 12, bluetoothMask.bits};
}  // namespace BleLabIcon
