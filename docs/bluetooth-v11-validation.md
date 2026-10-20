# BLE V11 candidate: ownership, shortcut and Home layout

V11 is a supervised X4 Pro experiment, not a hardware-verified fragmentation fix.
SDK remains 9f660022a0a338253fb964126558084e72a04ae5. No memory budgets,
security policy, partition or board configuration changes are intended.

## Evidence and bounded change

V10 logs: `device-monitor-261019-153628.log` (Home control) and
`device-monitor-261019-154149.log` (Settings failure), under the user's `logs`.
The failure log records 115,988 internal bytes / 55,284 largest before rebuilding
Settings, then 93,756 / 47,092 after construction and destruction of the temporary
catalog. The temporary `allSettings` buffer is already in PSRAM (31,220 actual
bytes), while the retained category/submenu vectors and nested enum storage are
internal. The parent Settings remains on ActivityManager's stack while Bluetooth
Settings runs. Its menu allocations survive radio teardown: 141,828 free bytes
but still only 47,092 contiguous. Home-only teardown restores 118,772 contiguous.

This supports an allocation-lifetime/placement problem, not a large teardown
leak. It does not identify every internal allocation or prove that the parent
menus are the only cause. V11 releases **all** parent menu vectors, including
their capacities and nested enum/string owners, before constructing the Bluetooth
child. It rebuilds them when the child returns, including the allocation-failure
path. The parent's rendering is suspended while its menu pointers are absent;
release and restoration use RenderLock. Menu state/category/selection is retained.
No extra arena, allocator, PSRAM assumption, cache-clearing experiment or heap
walker is introduced. The existing metadata is dynamic and too large for stack
storage; this change shortens its lifetime rather than adding another allocation.

Lightweight before/after menu handoff and normal BLE preflight/start/shutdown
summaries remain. Startup stays 131,072 free / 79,872 largest; post-start stays
65,536 / 32,768. Runtime and PSRAM guards remain unchanged.

## Kobo and input

The V10 designation action existed after every discovered device, Forget/Forget
All and the diagnostic cache action. It is now the first connected-device action,
immediately after Enable and Scan, before button configuration and discovered
devices. It still calls the same typed bonded-peer identity and NVS commit/readback
path. No guessing by device name, forgetting or re-pairing is needed. The Home
shortcut makes one explicitly requested connection attempt; no reconnect loop.
Connection errors remain visible separately from radio state.

Bluetooth lists previously drew a scrollbar without applying vertical swipe
events to ListNav. They now scroll their viewport and reserve vertical swipes
from the bottom-edge Home shortcut; Back and the physical Home key remain.

Home previously reset the touch registry when expanding the Lab and swallowed
all input while expanded. V11 keeps normal targets and routes ordinary taps to
the normal dispatcher. Physical navigation exits the Lab at its first/last
control. Focus highlights do not determine the displayed radio or link state.

## Portrait geometry and tradeoff

At 480x800 with the existing 242-pixel book card, cover top is 34, card bottom
276, and menu top 288. With 20-pixel small-font lines, expanded Lab top is 550
and bottom 748, before the 760 hint strip. The menu ends at 538. Five rows are
48 pixels high with 2-pixel gaps, leaving 12 pixels at the top and 14 pixels at
the bottom. This preserves font/icon sizes while increasing the former 42-pixel
targets. The identity moves into the 32-pixel gray header to recover one text
band. Additional optional Home actions use bounded menu pagination instead of
overlapping the Lab. Collapsed mode can give the rows more space. Other viewport
sizes compute their capacity from actual dimensions; the full book card remains.
Hardware touch accuracy, gray appearance and partial-refresh ghosting remain
unverified. Python previews are geometry/font illustrations, not full UI renders.

## Ordered hardware test (no automatic installation)

Keep serial logging active. Install only through the existing confirmed native
SD updater, then start with a **fresh boot for each memory experiment**. Do not
open EPUB, Wi-Fi or export diagnostics until the memory tests finish. No cache
reset is needed for these Settings/UI changes.

1. **A — Identity/layout:** confirm `v11-dev` and the manifest's source SHA.
   Expand Lab: cover/title stays intact, all five normal actions remain visible
   and independently tappable, Settings and Lab never share a target. Check
   touch-down, tap, Back, Confirm and physical Up/Down through both regions.
2. **B — Home control, fresh boot:** without Kobo/EPUB, BLE On → Off → On.
   Record preflight, post-start and teardown free/largest internal bytes. Both
   starts must pass unchanged guards; preserve the V10 118,772 teardown largest
   and 77,812 running largest as comparison, not promised exact V11 values.
3. **C — Settings experiment, fresh boot:** Settings → Bluetooth On → Home →
   Settings → Bluetooth Off → wait → On. Record before/after menu construction,
   `Settings menus released before Bluetooth child`, shutdown, and second
   preflight. Verify the menu-release summary recovers the parent allocations.
   The second start must pass 131,072 / 79,872, then the existing post-start
   checks. Repeat once. If refused, do not relax guards: retain logs and compare
   largest/free at menu release, shutdown and preflight. Next diagnostic is a
   bounded comparison of live parent object/dictionary/UI-owner addresses and
   sizes at those three boundaries, with BLE Off summaries and no locked walker.
4. **D — Kobo:** connect the already-bonded Kobo in Bluetooth Settings; choose
   `Use as Kobo for Home Lab` near the top. Back/Home, confirm connected state;
   restart, enable Bluetooth, press Home Kobo once and confirm one connection
   attempt. Check not-configured/error feedback where applicable without erasing
   the working bond. Scroll discovered/saved lists with swipes and buttons.
5. **E — Reading:** open a known EPUB after memory tests; encrypted Kobo link,
   0x51 Next / 0x52 Previous, repeated taps, disconnect/reconnect, touch and
   physical reader controls and SD access remain functional.
6. **F — Regressions:** Restart Cancel must do nothing; confirmed Restart must
   restart with Bluetooth Off and bond/designation retained. With BLE fully Off,
   Logs exports the bounded snapshot. Wi-Fi opens native File Transfer only
   after teardown; retrieve diagnostics and stage firmware/read back SHA through
   unchanged PC tools, without installing. Verify native exit/restart behavior.
   Update opens the native SD selector; cancel without installing.

Do not call the fragmentation issue fixed until C passes on the actual device.
