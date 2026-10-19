#pragma once
#ifndef CROSSINK_BLE_LAB
#define CROSSINK_BLE_LAB 0
#endif
#if CROSSINK_BLE_LAB && (!defined(FREEINK_DEVICE_X4PRO) || !FREEINK_DEVICE_X4PRO || defined(SIMULATOR) || !CROSSINK_HEAP_DIAGNOSTICS)
#error "Bluetooth Lab requires the physical X4 Pro heap-diagnostic build"
#endif
