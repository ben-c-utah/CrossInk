# X4 Pro Kobo Remote diagnostics

## Hardware evidence

The official Kobo Remote is discovered, pairs, and reaches Connected. Its
buttons have not yet produced page turns or recognized input in the existing
monitor output. Raw notification delivery and button codes remain unverified.
Windows keyboard Left/Right page turning remains the known-working behavior.

Independent Windows Raw Keyboard Input Viewer testing identifies the large
button as `VK_DOWN` (40, Windows scan code `0x50`) and the smaller button as
`VK_UP` (38, scan code `0x48`), with normal down/up edges. The tip button enters
pairing mode and produced no keyboard event in that test. These are Windows
observations, not measured X4 Pro BLE bytes. Standard HID keyboard usages
would be Down `0x51` and Up `0x52`; confirm them, their report IDs and byte
positions in this capture. Intended later Kobo defaults are Down → Next Page
and Up → Previous Page, scoped to that device and configurable. No global
Up/Down behavior is introduced.

## Diagnostic build

Build with `pio run -e x4-pro-ble-diagnostic`. This environment inherits the
ordinary X4 Pro board, `dio_opi`, TinyUSB, PSRAM allocation and memory guards.
Only it enables `FREEINK_BLE_HID_REPORT_DEBUG`, `FREEINK_BLE_HID_SCAN_DEBUG`,
and `CROSSINK_BLE_INPUT_DIAGNOSTICS`. Normal `x4-pro` builds do not enable them.

A small local SDK diagnostic commit is necessary: the pinned base
`699370183fa3a0e33c9cb83a36f701bbb6022095` logs payloads but omits report IDs,
characteristic handles and individual subscription outcomes. The added logging
is conditional; decoding, pairing and teardown are unchanged. Diagnostic
discovery additionally checks CCCD presence, using the same descriptor lookup
that subscription uses. A missing CCCD can otherwise return subscription success.
Other dependency versions remain unchanged. The artifact archive includes an
SDK Git bundle so the unpublished local SDK commit can be recovered.

Notification logging happens before decoding, including empty reports. It
captures at most 32 bytes per notification and 256 notifications per connection;
length and truncation/limit markers are explicit. Formatting uses bounded
97-byte and 192-byte stack buffers, with no formatting heap allocation. Raw
edge logging is limited to 256 events per enable session. Diagnostic serial
output can affect timing; this build is for slow, deliberate report capture.

## Supervised capture procedure

1. After supervised installation, start from a fresh boot. The known
   connection-cycle fragmentation can still prevent re-enable; guards remain
   active. Keep USB Serial/JTAG connected, and close other COM3 applications.
2. In PowerShell run PlatformIO monitor with COM3 at 115200 baud and logging:
   `pio device monitor --port COM3 --baud 115200 --filter log2file --dtr 0 --rts 0`.
   Save the full generated log, beginning before enabling Bluetooth.
3. Enable Bluetooth, put the Kobo Remote into pairing mode, select Scan for
   Devices, then select the Kobo under Discovered Devices. Retain the scan,
   HID discovery, Report Reference, CCCD and subscription lines through Connected.
4. With the screen idle, press and release the **large main button three times**, one second
   apart. Wait five seconds. Press and release the **smaller page button three times**, one
   second apart. Wait five seconds, then hold the large button for two seconds and
   release; wait five seconds and repeat with the smaller page button. Record these phases
   alongside the log. Page turns are not expected until reports are measured.
5. If useful, repeat single presses in an open EPUB. Capture Windows `key right`
   and `key left` separately after a fresh boot to verify the established path.
   Do not repeatedly toggle BLE to evade a memory refusal.

Interpret the layers in order:

- Advertisement `hid=0` alone does not exclude HID; confirm discovered service
  `0x1812` and characteristic metadata.
- Missing HID service, input candidates, CCCD, or successful subscriptions
  identifies discovery/subscription trouble. Indicate-only characteristics are
  logged but the existing host still subscribes only to notifications.
- Subscription success with no `notify` lines during button presses means no
  subscribed notification reached the SDK callback; it does not identify why.
- `notify` lines without HAL `raw` lines locate the issue in raw-event
  generation/normalization. Raw edges with `arrow=0` show rejection by the
  intentionally narrow Windows filter, not missing BLE transport.
- IDs come from Report Reference descriptors. ID zero can be a fallback when
  a descriptor/association is absent; correlate the handle with discovery logs.
  `rest` is the decoder's baseline classification, not proof of a physical press.

## Recommended later button learning — not implemented

Reuse CrossPoint's `BleKeyBinding.h` bounded per-peer tables and learning
semantics, not its entire Bluetooth runtime/UI:

The current SDK exposes `RawButtonEvent` and `popRawButton()`, but does not
contain the newer `BleRemoteProfiles.h` included by upstream's binding header.
Adapt its pure fingerprint/lookup/learning helpers without that profile-table
dependency; do not upgrade the SDK or import unmeasured remote defaults just
to compile the whole upstream header.

- Route SDK raw edges through the main-loop HAL. In a foreground learning
  screen, capture a deliberate press for Next Page or Previous Page with a
  timeout, cancellation on disconnect, and no simultaneous reader delivery.
- Store the measured fingerprint (report ID, byte index, value) and action in
  `SETTINGS`, keyed by the SDK's bonded peer address. Reuse the existing
  serialization/store boundary, save only on confirmed assignments, validate
  loaded records, and remove a device's assignments when it is forgotten.
- Start with two immediate press actions; omit hold/chapter/menu actions.
  Reuse CrossPoint's duplicate-assignment handling and release/repeat tests.
- Keep the existing Windows arrow filter as fallback for unassigned input and
  deliver each event through only one route. Preserve suppression of repeats,
  stale events, modifiers, overlays and busy readers.
- First verify that Kobo reports yield stable raw fingerprints. If they do
  not, fix only the measured decoding gap before adding learning. Address-based
  persistence also needs validation with the remote's bonded/private identity.

Sources reviewed:
[binding policy](https://github.com/crosspoint-reader/crosspoint-reader/blob/develop/lib/BlePageTurner/include/BleKeyBinding.h),
[BLE settings](https://github.com/crosspoint-reader/crosspoint-reader/blob/develop/src/activities/settings/BleSettingsActivity.cpp).
No Kobo codes, remote profiles or learned mappings are added by this build.
