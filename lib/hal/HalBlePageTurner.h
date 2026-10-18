#pragma once

#include <AppCapabilities.h>
#if CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <cstdint>

#include "BleArrowFilter.h"

// Main-loop-only facade. BLE callbacks and bonding remain owned by the SDK.
class HalBlePageTurner {
 public:
  struct Device {
    char address[18]{};
    char name[32]{};
  };
  enum class Status { Off, Ready, Scanning, Connecting, Connected, Stopping, Failed, LowMemory };
  bool enable();
  bool stop(uint32_t timeoutMs = 0);
  bool resident() const;
  bool enabled() const { return optedIn; }
  bool scan();
  bool connect(uint8_t index);
  void forget();
  int8_t poll();
  Status status() const { return state; }
  uint8_t deviceCount() const { return count; }
  const Device& device(uint8_t index) const { return devices[index]; }
  uint32_t passkey() const { return pairingPasskey; }

 private:
  // Fixed scan snapshot: render never reads the SDK's callback-owned scan list.
  Device devices[24]{};
  uint8_t count = 0;
  bool optedIn = false;
  bool scanPending = false;
  Status state = Status::Off;
  uint32_t pairingPasskey = 0;
  char selected[18]{};
  BleArrowFilter filter;
};

extern HalBlePageTurner blePageTurner;
#endif
