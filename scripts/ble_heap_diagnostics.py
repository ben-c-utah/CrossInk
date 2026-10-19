"""Explicit local opt-in; archive platformio.local.ini alongside the test binary."""
Import("env")
if env["PIOENV"] != "x4-pro":
    raise RuntimeError("Heap experiment is restricted to x4-pro")
env.Append(CPPDEFINES=[("CROSSINK_HEAP_DIAGNOSTICS", 1), ("FREEINK_BLE_HID_LIFECYCLE_DEBUG", 1)])

lab_version = env.GetProjectOption("custom_ble_lab_version", "")
if lab_version:
    if not str(lab_version).isdigit() or int(lab_version) <= 0:
        raise RuntimeError("custom_ble_lab_version must be a positive development revision")
    env.Append(CPPDEFINES=[("CROSSINK_BLE_LAB", 1), ("CROSSINK_BLE_LAB_VERSION", int(lab_version))])
