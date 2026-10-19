"""Check diagnostic opt-in/version propagation without running PlatformIO."""
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Env(dict):
    def __init__(self, version="", target="x4-pro"):
        super().__init__(PIOENV=target)
        self.version, self.defines = version, []

    def GetProjectOption(self, key, default=None):
        return self.version if key == "custom_ble_lab_version" else default

    def Append(self, **kwargs):
        self.defines.extend(kwargs.get("CPPDEFINES", []))


def configure(env):
    runpy.run_path(str(ROOT / "scripts/ble_heap_diagnostics.py"),
                   init_globals={"env": env, "Import": lambda _: None})


class BleLabBuildTest(unittest.TestCase):
    def test_heap_diagnostics_do_not_implicitly_enable_lab(self):
        env = Env()
        configure(env)
        self.assertNotIn("CROSSINK_BLE_LAB", dict(env.defines))

    def test_explicit_version_reaches_compile_definitions(self):
        env = Env("9")
        configure(env)
        self.assertEqual(dict(env.defines)["CROSSINK_BLE_LAB"], 1)
        self.assertEqual(dict(env.defines)["CROSSINK_BLE_LAB_VERSION"], 9)

    def test_invalid_revision_is_rejected(self):
        for value in ("0", "-1", "v9", "9-dev"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                configure(Env(value))

    def test_other_hardware_is_rejected(self):
        with self.assertRaises(RuntimeError):
            configure(Env("9", "default"))


if __name__ == "__main__":
    unittest.main()
