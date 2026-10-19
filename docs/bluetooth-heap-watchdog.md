# V8a: correct the V8 diagnostic interrupt-watchdog crash

V8 (`45b464b7`) remains archived for backtrace decoding. Do not use its full-dump
diagnostic path for further hardware experiments. V8a changes diagnostics only;
the underlying Bluetooth restart fragmentation issue remains unproven.

## Confirmed failure

Both CPU1 panic traces in `device-monitor-261019-092949.log` decode with the
archived V8 `firmware.elf` to this chain (addresses are V8-specific):

| Address | Decoded frame |
| --- | --- |
| `0x421a50c3` | `BleSettingsActivity::loop()` / FreeInkUI input route |
| `0x421a4ded` | `BleSettingsActivity::activate()` |
| `0x42055b65` | `HalBlePageTurner::enable()`, line 180 |
| `0x42055547` | `HeapDiagnostics::blocks()`, line 36 |
| `0x4221d577` | `heap_caps_dump()`, packaged IDF heap_caps.c:450 |
| `0x4230ec3d` | `multi_heap_dump()`, packaged IDF multi_heap.c:376 |
| `0x4230edc9` | `tlsf_walk_pool()` |
| `0x4230ebb1` | `multi_heap_dump_tlsf()` calling `esp_rom_printf` |

The leading `0x4004...` PCs are ROM printing frames without names in the app ELF;
the matching ELF's disassembly explicitly identifies the call to `esp_rom_printf`.
CPU0 decodes to its idle task. Complete decoded output and the original serial
log are preserved with the corrected artifact. The X4 Pro SD card was not mounted
in the host filesystem during inspection, so `crash_report.txt` was not read;
both complete serial backtraces independently identify the same path.

The packaged ELF shows `multi_heap_internal_lock` before ROM printing and the
pool walk, with `multi_heap_internal_unlock` only afterward. IDF's
[heap lock macros](https://github.com/espressif/esp-idf/blob/v5.5.2/components/heap/multi_heap_platform.h)
use a portMUX critical section. Its
[full dump implementation](https://github.com/espressif/esp-idf/blob/v5.5.2/components/heap/multi_heap.c)
prints each block before releasing that lock. Long/polling serial output extends
the interrupt-masked critical section, preventing normal CPU1 tick/interrupt
service and triggering the **interrupt** watchdog. The pinned dio_opi header
enables `CONFIG_ESP_INT_WDT` with a **300 ms** timeout. This is not the task watchdog;
yielding before/after the dump would not fix the critical section inside it.

The repeated last printed block `0x3fcbd87c` is not evidence of a corrupt block.
The panic occurs in printing, with no reported heap-integrity assertion. Free
RAM/largest block were above the startup requirements, and execution had not
reached the normal preflight or NimBLE initialization.

## Narrow correction

- Remove `HeapDiagnostics::blocks()` and all four calls: preflight, completed
  teardown, before font reclamation and after font reclamation.
- Retain free/largest/allocated-byte and block-count measurements, PSRAM free,
  named cache/theme allocation addresses and lightweight region summaries.
  IDF's [summary implementation](https://github.com/espressif/esp-idf/blob/v5.5.2/components/heap/heap_caps.c)
  obtains region information before printing, after the heap lock is released.
- Retain the manually selected, rendering-locked, Bluetooth-Off font-cache
  reclamation experiment and before/after-repaint measurements. No automatic
  cache reclamation or Bluetooth start is added.
- No watchdog settings, memory budgets, pairing, forgetting, mappings, board,
  dio_opi, TinyUSB, SDK pin, dependencies or sleep/USB policy change.

Regression tests reject full dumps/locked walkers and watchdog-bypass calls in
the diagnostic paths. Existing memory-policy, arrow, binding, forgetting and
build-identity tests still apply. These source-policy checks cannot simulate
hardware interrupt timing. The firmware must pass the smoke test below.

## Minimal supervised hardware smoke test

1. Start serial capture on **COM3, 115200** before a fresh boot. Keep Windows
   Bluetooth Off. Dismiss the prior crash screen normally if shown; preserve
   the old report. Do not open an EPUB, Forget devices or run reclamation yet.
2. Open **Settings → System → Bluetooth**, then select **Enable Bluetooth once**.
3. Expect the lightweight `BLE before preflight` summary, normal `preflight`
   guard, `after start` guard and `BLE initialization complete`. The radio toggle
   should turn On. There must be no `BEGIN internal block dump`, panic or reboot.
   Wait at least 30 seconds and verify ordinary screen/button responsiveness.
4. Stop and preserve the log if a panic occurs or the guard refuses startup;
   do not retry repeatedly or bypass the guard. If successful, disable once and
   verify the teardown summary and Off state without a crash. Save this smoke log.
5. Only after this passes, return to the controlled no-EPUB and EPUB runs in
   [the revised fragmentation procedure](bluetooth-heap-diagnostic.md).

No installation, flashing or hardware testing was performed by the agent.

## Corrected build verification

One `pio run -e x4-pro` build succeeded. Binary: **5,843,248 bytes**, **480 bytes
smaller than V8**, leaving **710,352 bytes** in the unchanged 6,553,600-byte app
partition. Static RAM is **115,116 bytes**, unchanged. No new diagnostic heap
buffers, persistent state or tasks are added.

Two diagnostic safety policy tests, three build-identity Python tests, and four
target-compiler constexpr BLE suites passed. Default-Off diagnostics still
preprocess to no code/state. The final ELF contains the retained lifecycle/cache
markers and has no defined full-dump/helper symbols or old BEGIN dump marker.
Hardware interrupt timing remains untested; the smoke test is required.

The corrected archive includes the binary, matching ELF, checksums, manifest,
local opt-in build configuration, build log, original V8 crash log, decoded V8
backtrace and V8 lock/printing disassembly. V7/V8 checksums were reverified.
