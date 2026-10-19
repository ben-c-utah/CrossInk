"""Regression policy: runtime heap diagnostics must not print under heap locks.

These checks prevent reintroducing the V8 interrupt-watchdog path. They do not
simulate interrupt timing or prove serial-driver behavior on physical hardware.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_PATHS = (
    "lib/Memory/HeapDiagnostics.h",
    "lib/hal/HalBlePageTurner.cpp",
    "src/activities/settings/BleSettingsActivity.cpp",
    "src/util/BleLab.cpp",
    "src/util/BleLabExport.cpp",
)


class HeapDiagnosticSafetyTest(unittest.TestCase):
    def test_no_full_dump_or_locked_walker_in_runtime_diagnostics(self):
        # A future bounded, copy-only walker needs separate review; printing in
        # any callback while the allocator holds its critical section is unsafe.
        forbidden = re.compile(
            r"\b(?:heap_caps_dump(?:_all)?|heap_caps_walk(?:_all)?|"
            r"multi_heap_dump|multi_heap_walk|tlsf_walk_pool)\s*\("
        )
        for relative in DIAGNOSTIC_PATHS:
            with self.subTest(path=relative):
                self.assertIsNone(forbidden.search((ROOT / relative).read_text(encoding="utf-8")))

    def test_no_watchdog_or_interrupt_bypass(self):
        forbidden = re.compile(
            r"\b(?:esp_task_wdt_(?:deinit|delete|reconfigure|reset)|"
            r"esp_int_wdt_init|wdt_hal_\w+|portDISABLE_INTERRUPTS|"
            r"disableLoopWDT|disableCore[01]WDT)\s*\("
        )
        for relative in DIAGNOSTIC_PATHS:
            with self.subTest(path=relative):
                self.assertIsNone(forbidden.search((ROOT / relative).read_text(encoding="utf-8")))

    def test_lab_has_no_delay_loop_or_second_ble_stack(self):
        text = (ROOT / "src/util/BleLab.cpp").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b(?:delay|vTaskDelay|vTaskDelayUntil|xTaskCreate|xTaskCreatePinnedToCore|while)\s*\(", text))
        self.assertNotIn("#include <NimBLE", text)
        self.assertNotIn("#include <BleKeyboardHost", text)


if __name__ == "__main__":
    unittest.main()
