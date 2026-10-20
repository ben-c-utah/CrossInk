# BLE v13-dev: Settings parent placement

## Evidence before implementation

Baseline: V12 `83d66103883832957cdc55a4f800e6db2d3f37f8`, SDK
`9f660022a0a338253fb964126558084e72a04ae5`.
Log: `C:\Users\chrbe\logs\ble-sessions\ble-session-20261019-215351-490753\device-monitor-261019-213740-full.log`.
Line numbers below refer to the decoded full capture (including blank lines).

- Lines 850/913: initial Settings parent `0x3fccaddc`, 1,728 actual internal
  bytes. After menu/catalog release, first preflight has largest 118,772.
- Lines 958–962: Bluetooth child destruction releases PSRAM, not internal
  heap. Its result callback reconstructs Settings menus while BLE runs.
  The temporary outer allSettings vector is already external memory; its
  nested copies and category vectors use internal heap.
- Lines 1009–1029: Home is constructed before Settings destruction. Then
  replacement Settings is constructed before Home destruction, while BLE
  still runs. Its address is now `0x3fcd5fe0`, 1,716 actual internal bytes.
- Lines 1086–1094: all category vectors and dictionary catalog are released;
  this replacement Settings parent remains alive. Largest recovers from
  47,092 to 73,716 to 77,812. The child is external (`0x3c5ac42c`).
- Lines 1121–1154: shutdown deletes worker/client, leaves zero clients and
  workers, and recovers free internal bytes from 119,436 to 165,720.
  Largest stays 77,812. After 40 seconds, preflight still fails only largest.
- Home-only control in this capture recovers largest 118,772 on shutdown.
  Previous V11 captures also recover 118,772 when the Settings parent is
  completely destroyed, without rebooting.

Confirmed ownership: ActivityManager constructs replacements before exiting
the previous screen and retains pushed parents in unique_ptrs. Releasing menu
vectors does not destroy the enclosing Settings controller (including its
fixed FreeInkApp interaction state). The Bluetooth callback restores menus
and the dictionary catalog when returning, preserving normal editing.

Strong inference: the replacement parent's internal allocation pins part of
the former BLE allocation region after shutdown. Its changed address and
survival distinguish it from the initial successful parent. Total recovery
and zero worker/client counts support an allocation-placement problem rather
than a large teardown leak. Region summaries cannot prove that this is the
only remaining pin. No individual-block dump or new tracing buffer is used.

V11 removed retained menu owners; V12 removed a catalog owner (hardware
improvement of 4,096 bytes). Neither can free the live parent object. Moving
that object addresses its lifetime/placement, rather than trimming another
2 KB to barely pass the guard.

## Implementation and safety

SettingsActivity has a checked nothrow allocator using the existing PSRAM
buffer helper on real ESP32 targets with PSRAM framebuffer and BLE capability.
It transfers ownership to the existing unique_ptr activity owner. Matching
class-specific delete returns the allocation through HeapByteBufferDeleter;
Activity's virtual destructor preserves correct deletion through the base
pointer. Other targets and simulators retain default-heap placement.
PSRAM failure has no internal fallback. All three creation sites handle null;
ordinary throwing new is disallowed for this class.

The existing approximately 1.7 KB foreground controller is moved, not copied
or newly retained. It contains UI state and references, no DMA buffers, task
stacks or ISR data. Its lifetime must span callbacks, so stack/static storage
cannot replace independent ActivityManager ownership. This does not relocate
nested allocations; existing menu/catalog release and restoration remain.
No threshold, BLE lifecycle/security, SDK, reader/font, updater, PC workflow
or VS Code changes are made. Existing lightweight object-address and boundary
summaries remain sufficient to check the hypothesis.

Native tests execute the production allocator/deallocator against fake heaps,
including PSRAM failure without fallback and virtual base-pointer deletion.
Repeated ownership/menu simulations check release counts, not actual ESP heap
coalescing. Existing tests cover the menu/catalog handoff, BLE lifecycle guards,
Kobo state and Home controls. Only hardware can establish reliable recovery.

## Ordered physical tests

Do not use Wi-Fi or export diagnostics before controlled memory tests. Capture
serial output; no cache reset is required. Confirm `CrossInk BLE · v13-dev`
and the manifest commit, normal Settings rows, touch and physical controls.

1. **A, separate fresh boot:** Home BLE On → Off → On. Require the V12 control
   behavior to remain working. Record free/largest before start, running and
   after shutdown.
2. **B, separate fresh boot:** Settings → Bluetooth On → Settings → Home →
   Settings → Bluetooth Off → wait 30 seconds → On. Require successful guarded
   restart without reboot. Check both Settings.object/retained-parent records
   say `external=1`, before/after menu/catalog release, shutdown complete and
   next preflight. Startup minima remain free 131,072 / largest 79,872;
   post-start minima remain 65,536 / 32,768. Expect recovery toward the
   Home-only baseline (~118,772), not a single marginal threshold pass.
3. **C:** Repeat B's navigation/off/on cycle at least five times without reboot.
   Record every shutdown and preflight. Require no downward trend. Visit all
   four Settings categories, dictionary and font options after child return;
   verify current selections, scrolling and touch/button navigation survive.
   Do not accept success based only on total free bytes.
4. **D:** Return Home, reconnect the designated bonded Kobo manually, open an
   EPUB, verify next/previous turns (0x51/0x52). Then check Restart cancellation,
   SD Logs, Wi-Fi File Transfer and Update picker cancellation. Do not install
   firmware as part of this test.

If parent placement is external but largest remains ~77,812, the parent was
not the only pin: stop and retain the complete capture. Next experiment is
bounded address/size logging of remaining Settings-owned popup/callback
allocations before child entry and after parent destruction, outside allocator
locks. Do not lower guards, add a reboot workaround or claim the fix passed.

Status: source-level candidate; physical fragmentation recovery unverified.
