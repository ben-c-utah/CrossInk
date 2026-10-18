#pragma once

#include <cstdint>

// Windows BLE HID v0.6.0: keyboard report 1, first key at byte 2.
// Mouse report 2, modified keys, repeated notifications and releases never turn.
class BleArrowFilter {
 public:
  constexpr int8_t accept(uint8_t report, uint8_t byte, uint8_t value, bool pressed, uint8_t usage, uint8_t mods,
                bool wasRest) {
    if (report != 1 || byte != 2) return 0;
    if (!pressed) {
      held = 0;
      return 0;
    }
    if (held == value) return 0;
    held = value;
    if (wasRest || mods != 0 || value != usage) return 0;
    return usage == 0x4f ? 1 : usage == 0x50 ? -1 : 0;
  }
  constexpr void reset() { held = 0; }

 private:
  uint8_t held = 0;
};
