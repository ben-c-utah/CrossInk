#pragma once

// Adapted from CrossPoint scripts/s3_nimble_psram.h at
// 2c09b8ce8748463c603205aa815a527cd01f0a29. Force-included only by x4-pro.
// Load the prebuilt config first so its header guard prevents later includes
// from restoring INTERNAL. Only source-built NimBLE host allocations change;
// prebuilt controller/TinyUSB code, DMA buffers and task stacks are unchanged.
#if defined(CROSSINK_APP_CAP_BLE_PAGE_TURNER) && CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <sdkconfig.h>
#if !defined(BOARD_HAS_PSRAM) || !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "BLE host PSRAM configuration requires the ESP32-S3 PSRAM board profile"
#endif
#undef CONFIG_BT_NIMBLE_MEM_ALLOC_MODE_INTERNAL
#define CONFIG_BT_NIMBLE_MEM_ALLOC_MODE_EXTERNAL 1
#define CROSSINK_BLE_HOST_PSRAM 1
#endif
