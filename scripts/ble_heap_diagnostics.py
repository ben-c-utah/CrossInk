"""Explicit local opt-in; archive platformio.local.ini alongside the test binary."""
Import("env")
if env["PIOENV"] != "x4-pro":
    raise RuntimeError("Heap experiment is restricted to x4-pro")
env.Append(CPPDEFINES=[("CROSSINK_HEAP_DIAGNOSTICS", 1), ("FREEINK_BLE_HID_LIFECYCLE_DEBUG", 1)])
