# X4 Pro Bluetooth Lab v9

Diagnostic controls exist only on basic Lyra, in physical X4 Pro builds with
`CROSSINK_BLE_LAB=1` and heap diagnostics enabled. The local build option
`custom_ble_lab_version = 9` in the existing heap-diagnostic pre-script sets this.
Production defaults remain off. Carousel and other Home layouts are unchanged.
Native buttons join the normal logical Up/Down/Confirm navigation and touch registry.

## Identity and storage

The visible version is `CrossInk BLE ? v9-dev <Git SHA>` (asterisk for dirty
sources). Commit sources before building. Upstream `1.6.1-x4-pro` remains the
update/API version. The archive manifest records the exact flags and identity.
The SDK, dio_opi core, TinyUSB, and all BLE guards are unchanged.

Connect Kobo uses an explicitly selected, verified address AND address type,
never a name match. After normal pairing, select **Use as Kobo for Home Lab**
in Bluetooth settings. A fixed 52-byte versioned record in `crossink-ble/lab-peer`
is checked on write/read. Forgetting that device clears its Lab role; Forget All
clears the role too. Unrelated devices and learned mappings remain unaffected.

The controller queues work on the main loop and advances by actual HAL state;
there are no delay loops, additional tasks, or BLE clients. Existing HAL startup
itself remains synchronous. Connection/teardown deadlines report failure rather
than retrying initialization. Restart requires confirmation, completed BLE
teardown, checked settings/session saves, and an inactive renderer. It runs from
the main loop after releasing RenderLock. Cancel changes nothing. Software restart
is not a full power cycle and USB Serial may briefly disconnect.

## Allocation evidence and limits

Reference: device-monitor-261019-105525.log. No EPUB was opened. Initial guard:
internal free 142920, largest 94196. Connected largest 53236. Second Settings
entry after Home destruction: free 116788, largest 53236, allocated 138008,
394 allocated blocks. Before its first render: free 94692, largest 47092,
allocated 158280, 508 allocated blocks. Thus Settings initialization adds 114
blocks and reduces largest by 6144. Completed teardown: free 142656, largest
47092. The 264-byte net free difference does not explain which allocation pins
that region. Previous font reclamation did not recover it.

Settings was allocated at 0x3fcc31e4 (1716 usable bytes) on both entries.
SettingInfo is 144 bytes on this target. Dictionary discovery and retained
category/enum vectors are suspects, not proven causes. The 6144-byte largest-block
change does not establish a 6144-byte allocation. New bounded logs separate
construction, dictionary discovery, menu rebuild, first render, and destruction;
owned vector pointers/capacities and aggregate nested enum sizes are printed.
Hidden string/function allocations remain a limitation. No permanent allocation
fix or heap-block walk/dump is included.

The Lab uses fixed static controller/UI state, no new Home member payload, and
bounded render-stack scratch. Rendering/fonts and confirmation dialogs can still
allocate; compare the SAME V9 binary from fresh boots. Measurements are sampled
only at interaction/state boundaries, not polled with continuous e-ink refresh.
Region summaries copy allocator statistics before serial printing. Cache reclaim
retains its existing safety/locking contract and now reports refusal or largest
block before/after, including unchanged/decreased results.

## Hardware protocol (do not flash automatically)

1. Capture COM3 at 115200 from before boot. Windows Bluetooth Off. Use basic Lyra.
   Pair Kobo normally in rapid-blue-blinking pairing mode if necessary, learn
   buttons, and select **Use as Kobo for Home Lab** once. Restart via Home Lab.
   Do not select/write the role again during measured runs.
2. Smoke test Restart Cancel (nothing changes), then confirmed Restart. Verify
   visible v9-dev identity matches manifest, saved role/mappings survive, BLE Off.
3. Workflow A, fresh boot: Home ? Settings ? Bluetooth ? enable ? connect Kobo.
   Return Home, wait 15 seconds, return Settings ? Bluetooth. Disable, wait
   30 seconds, enable ONCE. Save the complete log and screen result.
4. Workflow B, fresh boot: remain Home; **Connect Kobo**. Wake the selected remote
   if needed. Wait for Connected, wait 15 seconds; **Bluetooth On/Off** to stop.
   Wait 30 seconds; toggle On once. Do not visit Settings or open a book during
   this connected session. Compare preflight, teardown, Home repaint and Settings
   allocation boundaries against A. Never weaken the unchanged 131072/79872 guard.
5. Separate checks: absent role directs normal pairing; asleep remote gives a
   failure/timeout; duplicate actions do not duplicate clients. Restart while
   connecting must finish teardown or report failure without forcing reset.
6. Separately verify padded long errors, persistent reclaim ran/refused and exact
   before/after numbers; no improvement must say so. Verify physical and touch
   navigation, Kobo learned presses and Windows Left/Right defaults, sleep/USB
   shutdown, and targeted/all forgetting including Lab-role removal.

Preserve logs and screen outcomes. No cache reset or bond deletion is required
for A/B. Do not infer a permanent correction until the pointer/capacity evidence
identifies the retained allocation. Binary size, RAM, partition headroom, SHA-256,
ELF and build log are recorded in the separate immutable test artifact archive.
