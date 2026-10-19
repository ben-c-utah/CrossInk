# Bluetooth forgetting checkpoint

This change preserves V6 (`ad13c822`, SDK `71ac350`) and its archived firmware.
It does not claim to fix intermittent security failures or heap fragmentation.

The final `pio run -e x4-pro` passed: 5,837,408-byte image, 716,192 bytes free
in the 6,553,600-byte application partition. Static RAM is 115,116 bytes (48
bytes below V6). This is distinct from the increased settings-screen heap cost.

## User flow

Bluetooth settings has separate Forget Device and Forget All Devices actions.
Forget Device opens a native list of remembered peers, security-only peers when
the host is running, and mapping-only peers. Names are display-only. Each row
shows the address and address type; confirmation copies that exact identity.
The connected peer's identity address is resolved before disconnecting it.
Unresolved private addresses require connecting the device first, rather than
guessing which bond to remove. An exact persisted credential identity is accepted
even if its bits look like a private address (as in the observed Windows records).
A different connected device is left connected.

Both confirmations use OptionPopup with Cancel selected initially, supporting
touch and physical buttons. Completion appears in the existing wrapped status
area, names the selected device, and remains through redraws/status changes and
selection movement until the next relevant action or leaving the screen.
Failures identify the unfinished stage and give a retry/recovery instruction.
The list refreshes after the actual result. No success is shown just for clicking.
An unreadable store is never presented as an empty store.

## Ordering, storage and recovery

Shared SDK transaction logic orders quiescence, credentials, then metadata.
CrossInk clears mappings only after those steps succeed. Credential failure
keeps metadata and mappings. Metadata failure keeps mappings. Mapping-write
failure keeps the old active mapping table. A later-stage failure can mean partial
cleanup; the screen says so, and retained records permit retry. There is no
cross-namespace atomic transaction and no automatic erasure after an error.
Malformed mapping records block single-device deletion/learning rather than
overwriting unknown assignments; explicitly confirmed Forget All can clear them.

Single-device Forget requires Bluetooth On and an idle connection worker. It
stops scanning, disables automatic reconnect and waits up to one second for the
selected live connection's disconnect callback and finalized state. Busy/stopping
or unverifiable identity is an explicit result. It removes credentials through
NimBLE and checks both its RAM store and typed NVS security records afterward.
Already-absent credentials are allowed; actual read/delete failures stop cleanup.
SDK metadata and mappings match address **and** type, including a live resolved
identity alias. No device is deleted by name or mutable list index.

Forget All turns Bluetooth Off, waits for completed SDK teardown (up to two
seconds per request), then clears only NimBLE's `nimble_bond` namespace. This
also works from a fresh boot or after a memory-guard refusal, without initializing
BLE. The pinned backend's `ble_store_config_init()` resets RAM counters and reloads
NVS on next initialization. No stale host store is accessed while Off. Pending
teardown causes a visible Busy result and storage is left untouched; retry later.
All-deletion checks NVS erase/commit results and verifies zero remaining entries.
The namespace includes the local IRK, so the next session can generate a new BLE
privacy identity. Local-IRK-only storage is not counted as a saved device.

The SDK's `freeink-hid` metadata moves from legacy `n`/`b` keys to one versioned
206-byte `peers-v1` blob (version, count, four 51-byte records). Reads accept legacy
records only if V1 is absent. Writes check set/commit and read back the record;
legacy keys are removed. An empty V1 record prevents resurrecting legacy peers.
Failed writes retain the in-memory recovery records. V6 rollback does not read
V1 metadata; security bonds and the unchanged CrossInk mapping format still
exist, and explicit scanning/reconnection can repopulate V6 metadata.

Only `nimble_bond`, SDK pairing keys in `freeink-hid`, and `crossink-ble/buttons`
are touched. No NVS partition erase, application reset, Wi-Fi credential deletion,
book/progress deletion or memory-guard changes are introduced. SDK metadata's
four slots and NimBLE's three security bonds remain unchanged; all-device cleanup
works independently of those counts and includes security-only records.

Resource cost is bounded: a 14-entry saved-device snapshot lives in the settings
activity, not a new global allocation. Existing scan-name buffers hold identity
subtitles. Native popup allocations are cold-path UI allocations. Metadata helpers
reuse a 206-byte stack record; nested calls can hold two such records (candidate
list and write/readback buffer), avoiding a new persistent heap buffer. NVS and
popup internals may allocate; existing guards remain authoritative.
Compiler debug information reports the settings activity at 4,924 bytes versus
3,756 in V6: 1,168 additional heap payload bytes while that screen exists,
excluding allocator overhead and native popup strings/NVS internals. This cost
is separate from the linker-reported static RAM figure. Verify actual startup
free/largest values on hardware; no headroom threshold has been weakened.

## Automated coverage and limits

Target-compiler constexpr tests exercise the production shared transaction engine
with mocked storage outcomes: one/all removal, connected/disconnected targets,
unrelated peers, security-only/metadata-only states, credential/metadata/mapping
failures, recovery retries, Busy/Off/identity rejection, and empty/repeated clears.
The actual mapping codec's reset/isolation tests and existing Windows arrow,
press/release, persistence and memory-policy assertions also run.

These mocks do not prove NimBLE's flash deletion, real privacy resolution, NVS
power-loss behavior or physical UI rendering. Native list/popup compilation and
review cover the input path; visible feedback and refresh require hardware tests.
Actual NVS fault injection was not performed. A persisted-store verification
failure must remain an error even if RAM no longer contains that credential.

## Supervised hardware validation (do not use production data casually)

1. Fresh boot, Windows Bluetooth Off, Kobo in rapid-blinking pairing mode.
   Enable Bluetooth, connect Kobo and verify the existing learned buttons first.
   Note saved device names/addresses and any second device's assignments.
2. Open Forget Device. Verify each row's name/address/type. Cancel using touch,
   then using Back/physical navigation; bonds and buttons must remain intact.
3. Forget Kobo while connected. Expect "Kobo Remote forgotten" only after
   completion; wait at least 30 seconds and navigate selection to confirm the
   message persists. The list must refresh. Verify another saved device and its
   mappings remain, reconnect it and check Windows Left/Right defaults.
4. Re-enter explicit Kobo pairing mode, scan/reconnect and verify its assignments
   are Not Set. Relearn Next/Previous; verify one turn per press and none on release.
5. Repeat single-device deletion while disconnected but Bluetooth On. For an
   unresolved private identity, expect the connect-first message, not guessed
   deletion. If a metadata-only or security-only row exists, test it separately;
   names may be unavailable for security-only rows. Verify absence after reboot.
6. With several saved devices, choose Forget All Devices and Cancel first.
   Confirm again using the other input method. Expect "All Bluetooth devices
   forgotten" and "Bluetooth is Off"; verify saved list empty, then repeat:
   expect "No saved Bluetooth devices". All assignments must be cleared.
7. Repeat Forget All while already Off, including after any naturally occurring
   guard refusal. There must be no BLE initialization. Reboot, enable and pair
   afresh; ensure old security-only records do not reappear. No threshold changes.
8. Verify Wi-Fi configuration, books/progress, physical buttons, Home, sleep/wake
   and USB Drive are intact. Preserve COM3/115200 logs and screen observations.
   Real storage-error feedback/failure preservation needs controlled fault injection
   on a disposable setup; do not corrupt live NVS to simulate it casually.

Stop on partial failure, unexpected device removal, unreadable feedback or a
memory refusal. Do not repeatedly retry pairing or relax guards. Long-term
heap behavior and the separate failure/fragmentation issue remain unresolved.
