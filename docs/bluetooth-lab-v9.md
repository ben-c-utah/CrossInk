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

## V9a presentation correction

BLE orchestration, identity storage, guards and diagnostic measurements are
unchanged. Only diagnostic basic Lyra uses compact 42-pixel menu rows with
4-pixel gaps; other themes and production Lyra retain their existing metrics.
Native FreeInkUI buttons now explicitly set borders in all states, black/white
selected focus, six-pixel padding and one-line short labels. The main-loop
selection/activation and touch routing are unchanged.

For the X4 Pro's 800x480 panel in portrait Home coordinates (480x800):

| Region | Vertical bounds (exclusive bottom) |
| --- | --- |
| Full book card | 24?266 (image top 32, left 28) |
| Seven menu rows, including Settings | 270?588 |
| Bluetooth Lab heading | 600?624 |
| Three 142x44 buttons with 6-pixel gaps | 628?672 |
| Bluetooth/Kobo state | 676?700 |
| Internal RAM / largest block | 700?724 |
| One-line result, including low memory | 724?748 |
| Reserved gap | 748?760 |
| Existing button hints | 760?800 |

All Lab bands use the renderer's actual small-font line advance plus four
pixels for ink/descender safety. Horizontal content spans x=20..460. Compact
English feedback and labels are measured against firmware glyph advances in
`scripts/test_ble_lab_layout.py`; future longer translations still use native
single-line ellipsis rather than overflowing. Full original messages remain
in source/Settings and existing BLE failure logs. The displayed build remains
`v9-dev <new Git SHA>`; V9a is identified by that exact source SHA and its archive,
without changing update metadata or BLE build flags.

The full 242-pixel card is deliberately retained: Lyra's 226-pixel cover image,
up-to-three-line title, author, statistics and progress do not honor shrinking
just the nominal card height. No allocation API or new heap owner was added.
The existing optional cover cache now follows the full card region: 14520 bytes
in portrait, rather than V9's incorrectly shortened region (6840?14520 depending
on optional rows). This geometry can affect allocation history; use the SAME
V9a binary for the memory investigation and do not compare it as a heap fix.

The dependency-free local PNG preview uses firmware bitmap glyphs and the same
portrait geometry, with seven rows, a long title, statistics, 100% progress,
selected/unselected buttons and a low-memory error. It is a layout approximation,
not an app simulator: icons, kerning, real covers and interaction are not modeled.
No physical visual verification is claimed. Both changed source units compile;
constexpr geometry checks cover menu separation and larger bottom insets.

After supervised installation: verify the on-screen Git ID, then use physical
Up/Down/Confirm through the ordinary items and all three Lab buttons. Check visible
focus/borders and Restart Cancel, long titles and progress/statistics variants,
then BT enable/Connect Kobo/Off and any guarded low-memory refusal. Nothing may
encroach on the hint strip. Check touch separately if used. Continue the existing
A/B fragmentation protocol only once layout is accepted. Do not flash automatically.
