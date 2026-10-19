# X4 Pro V10 Bluetooth Lab

Baseline: V9a f11f8ecc, SDK 9f660022a0a338253fb964126558084e72a04ae5.
Diagnostic-only, physical X4 Pro, basic Lyra. No SDK/core/board/dependency changes,
no new service/task, no pairing/forget/mapping changes, no fragmentation fix.
The exact identity comes from AppVersion::versionLabel() and the clean Git build.
Upstream 1.6.1-x4-pro remains update/API metadata. Previous artifacts stay intact.

## V9a activation defect and correction

Hardware showed selection without execution. Source confirmed bleLab.tick() was
inside dispatchButtonShortcut(), but absent after the ordinary main-loop
activityManager.loop(). A normal tap could queue work without servicing it.
V10 services that ordinary path too, outside RenderLock, guarded against sleep.
The shortcut path remains serviced for early-return shortcut dispatches. Both
paths skip exclusive storage/USB mode. Pending initialization or new connection
work is cancelled if Home is no longer current; existing orderly shutdown still
progresses. This prevents a queued start racing an activity handoff.

BleLabInput separates focus-only down from tap/Confirm activation; tap wins when
both are present. A fixed pending UI slot retains activation while rendering owns
the lock. It is consumed once under RenderLock; callbacks only queue controller
work. Restart Cancel never queues a restart; confirmed restart reaches ESP.restart()
after checked saves, complete BLE teardown, and parking/unlocking the renderer.
No physical reset/power sequence is simulated. Serial BLELAB records input focus,
UI queued/refused, requested/accepted/refused, result, and final confirmed restart.
An accepted request is not a success indication. Radio status is read from the HAL.

## Panel and input

Collapsed: a focusable header/chevron, actual BT/Wi-Fi state, compiled identity,
RAM/largest block/Kobo link, persistent concise result. Normal Home remains usable.
Expanded: two native button rows, Bluetooth/Kobo/Wi-Fi then Logs/Update/Restart.
Existing monochrome radio/book/network/file/upload/history icons are reused.
No new UI dependency or generated icon edit. Selected controls invert; every
state has an outline. Physical Up/Down cycles header plus six controls, Confirm
activates, Back or the header collapses. Touch uses the existing registry.
There are no new swipe bindings. Global gestures retain their existing routing.
The expanded panel hides trailing Home rows with an obvious collapse control;
hidden hit targets are removed. On leaving Home it resets to collapsed.

Portrait geometry (panel 800x480, logical Home 480x800):

| Region | Bounds |
| --- | --- |
| Book card | y=34..276; image top/left=42 |
| Seven ordinary Home rows | y=276..594 |
| Collapsed Lab | y=644..748 |
| Expanded Lab | y=506..728 (snapped to whole menu-row boundary) |
| Expanded header | y=506..538 |
| Grid row 1 / 2 | y=542..594 / 600..652 |
| Identity / memory / feedback | y=656..680 / 680..704 / 704..728 |
| Existing hints | y=760..800 |

Content spans x=20..460; cells 142x52 with six-pixel gaps, 24px icons and bounded
single-line labels. Small font advance=20, text bands=24 for ink descenders.
No animations or polling redraws; memory is sampled on interactions/lifecycle
boundaries. Local bitmap-font previews approximate layout, not physical or full
simulator verification (kerning, actual covers and interaction differ).

## Wi-Fi and firmware staging

Wi-Fi waits for the existing orderly BLE stop, including pending teardown, then
opens the existing File Transfer activity. It does not call WiFi.mode() or create
a second server. Choose Join Network or Hotspot there. Existing transfer-mode
entry/exit may restart to clean network heap; Bluetooth stays Off. After exit,
Home shows actual Off states. A restart resets transient Lab feedback, not SD
exports or saved mappings. Exit/cancel remains the native File Transfer workflow.

Update similarly stops BLE and opens SdFirmwareUpdateActivity, not upstream OTA
release discovery. First transfer the custom binary with the PC helper or normal
web upload. Exit File Transfer (expect restart), reopen Lab, select Update, choose
the staged .bin. Existing code checks destination partition size, ESP chip/board
marker, segment structure, XOR checksum and appended SHA when present. It asks
for explicit confirmation and revalidates before writing the alternate partition.
The helper checks the entire binary SHA against the explicit local manifest,
uploads via /upload?path=/, and independently hashes /download?path=/filename.
It never installs or changes otadata. Name collisions are refused by the existing
server; choose a new --name or remove the old staged file manually in File Transfer.

The prebuilt dio_opi SDK header has CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=1,
but this alone does not verify the installed physical bootloader or a complete
application health/rollback contract. The raw OtaBootSwitch path writes a new
slot entry; no new rollback/health acknowledgement is added. Do not rely on
automatic rollback. Keep known-good SD/USB recovery available. App-based SD
recovery still requires its startup/storage/display code to run; a firmware
that cannot reach recovery may need ESP ROM USB recovery. No physical recovery
buttons, bootloader, partitions or watchdog configuration changed. Software
restart is not a power cycle. This assignment never installs firmware.

## Logs: deliberately bounded first step

Logs requires BLE fully Off; otherwise its visible result requests that first.
It records up to eight most recent Lab main-loop samples (uptime, free internal,
largest internal, free PSRAM, numeric phase/status), firmware identity/base, and
crash availability. It is NOT a complete serial/HID/security session capture.
No logger hook or new serial ring is added. Existing Logging retains only sixteen
recent 256-byte messages; directly collecting that unsynchronized global ring
would neither capture the entire session nor improve SDK direct-serial coverage.
Use the PC serial snapshot for complete available serial logs.

On explicit export, the main loop acquires RenderLock only to park an inactive
renderer, then releases it BEFORE opening files. It refuses a retained reader,
pending navigation, active radio/Wi-Fi, and waits boundedly for font scanning.
All handles are explicitly closed; writes, sync/close and rename are checked.
No SD writes occur during active BLE tests or in callbacks/IRQs/heap locks/render
critical sections. A 192-byte stack buffer streams data. Output:

- /ble-lab-diagnostics.txt: small bounded snapshot, latest export replaces it.
- /ble-lab-crash.txt: copy of /crash_report.txt capped at 8192 bytes, if present;
  truncation is declared, original preserved. Stale exported crash is removed
  when the source is absent. Export failure never reports success.

These files survive Wi-Fi transition reboots and are downloadable in normal
File Transfer or with the helper. There is no push-to-PC endpoint or always-on
server. Export AFTER recording the guard failure, not during the measured A/B
sequence: SD/file-wrapper/font allocation history can itself affect heap layout.
Before/after tool heap measurements remain on serial. Eight fixed records add
160 bytes plus small queue/control fields; final static RAM and stack figures
are in the artifact manifest. No new serial-text ring or large transient buffer.

## PC helper

Use Python 3.12 from the repository root. Serial monitor may remain open; Windows
CreateFile requests read/write/delete sharing. Snapshot is a bounded 8MiB tail
at the initial file size, decoded to UTF-8; metadata reports timestamps, age,
concurrent growth and truncation. Newest file is chosen by mtime, not filename.
A stale log gets a warning. Observed serial identity is separate from candidate
manifest metadata; the helper never assumes a local build is flashed. Without
--artifact, the newest local artifact manifest is included as a candidate only.
A downloaded export identity is labeled separately because it may predate a reboot.

    python scripts/ble_lab_pc.py collect --logs-dir C:\Users\chrbe\logs --artifact artifacts/ble-x4-pro-bluetooth-lab-v10-20261019

After Logs export, use the Wi-Fi control and the root URL displayed by File Transfer:

    python scripts/ble_lab_pc.py collect --url http://192.168.1.50 --artifact artifacts/ble-x4-pro-bluetooth-lab-v10-20261019
    python scripts/ble_lab_pc.py stage --url http://192.168.1.50 --binary <firmware.bin> --manifest <manifest.json>

The default staged filename includes the SHA prefix. --name permits a different
simple root .bin filename. These are existing /upload and /download routes, not
new diagnostic/update APIs. URLs are explicit; no network discovery or guessed
endpoints. A download-only collection also works without a local serial log.
Use only a trusted development network: the existing transfer server's security
model is unchanged. Upload completion plus matching read-back SHA is staging
success, not installation success. After supervised installation, verify the
new on-screen/serial compiled identity independently.

## Verification and hardware protocol

Build opt-in platformio.local.ini (archive it, never commit):

    [env:x4-pro]
    custom_ble_lab_version = 10
    extra_scripts =
      ${base.extra_scripts}
      pre:scripts/ble_heap_diagnostics.py

Python build-identity, memory/diagnostic policy, layout and PC helper tests plus
six target constexpr suites remain applicable. Native action tests compile the
REAL BleLab.cpp and export code, with fake HAL/ESP/storage only, and execute
input-to-action flows including failures, pending teardown, crash cap, sync and
rename errors. The portable host compiler is isolated in ignored .pio/native-tools:

    pio pkg install --global --storage-dir .pio/native-tools --tool platformio/toolchain-gccmingw32@1.50100.0 --no-save --skip-dependencies
    python scripts/test_ble_lab_runtime.py

Create that storage directory first. No global PATH or system toolchain changes.
The old portable GCC needs constexpr-function qualifiers adapted to inline in
TEMPORARY policy-header copies only; runtime bodies are unchanged, and target
compile-time suites check original headers. Mocks do not prove physical NimBLE,
SD timing, USB serial, Wi-Fi transfer, bootloader rollback or actual ESP restart.

Supervised test after review (do not flash automatically):

1. Capture COM3/115200 from boot. Confirm v10-dev Git ID, basic Lyra, collapsed
   panel, all normal items visible. Expand/collapse by touch and physical Confirm;
   physical Up/Down visits header and six controls, Back dismisses.
2. Tap Bluetooth once: serial must show one UI activation/request/accept and one
   actual startup or a readable failure. Focus alone must not start it. Compare
   actual Settings toggle. Repeat with physical Confirm. Never infer success
   from highlighting. Press during repaint and ensure a single queued activation.
3. Select/retain the known Kobo identity in normal Settings if not already saved.
   Kobo button reconnects only it, enabling BLE once if Off. Confirm wireless
   learned pages, no double turns, unchanged Left/Right keyboard defaults.
4. Restart Cancel: no reset/request. Confirm: stop completes, serial confirms
   software restart, identity returns and BLE Off; mappings/bonds persist.
5. Perform the unchanged A/B no-EPUB experiment from fresh boots. Do not press
   Logs, Wi-Fi or Update until after measured failure/success. Save serial first.
6. With BLE Off, Logs must show success only after sync/rename; inspect snapshot
   and optional bounded crash file. Test absent/unwritable SD: visible failure.
7. Wi-Fi while connected must fully stop BLE before existing mode selection;
   enter native transfer, retrieve exports, upload/read-back verify a custom
   firmware file with the helper. Exit returns/restarts normally with Wi-Fi Off.
8. Update opens the SD picker. Inspect staging and validation; CANCEL installation
   for the first suite test. Test wrong-board/corrupt/oversized files are rejected
   by existing validation. Firmware installation requires separate supervision.

Stop if input dispatch, teardown, memory guard or recovery behavior differs.
The connection-cycle allocation owner remains unproven; no thresholds are relaxed.
Reconnection retains the pinned SDK's existing secureConnection behavior. The Lab
never scans/pairs arbitrary devices, deletes/replaces credentials or changes
security policy; stale credentials still require normal Settings diagnostics.
A strict new "encryption-only, never renegotiate pairing" SDK mode is not added
in this assignment and is not claimed by the shortcut.
