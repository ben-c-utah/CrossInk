# X4 Pro Bluetooth development

## First wireless hardware milestone — 2026-10-18

Verified by supervised hardware testing of checkpoint `ea19179b` and the
preserved `ble-x4-pro-memory-v2-20261018` experimental firmware:

- Windows BLE HID emulator paired and connected to the physical X4 Pro.
- Without USB connected, HID Right Arrow (`0x4F`) advanced exactly one EPUB
  page and Left Arrow (`0x50`) returned exactly one page.
- Ordinary page turns appeared effectively instantaneous. Image-heavy chapter
  transitions appeared comparable to physical-button navigation.
- Physical controls, Home, Sleep and Wake worked normally.
- PSRAM-assisted NimBLE initialization succeeded and the observed memory
  checks passed. This is an observed test result, not a long-term heap guarantee.

Still unverified: sustained battery usage, repeated connection cycles,
long-term heap stability, and third-party remote compatibility. The Kobo Remote
had **not** been tested at that milestone. Later connection-only testing is
recorded in [Kobo diagnostics](bluetooth-kobo-diagnostics.md).

## Windows pairing identity

The SDK already calls `NimBLEDevice::init("CrossInk X4 Pro")` through
`HalBlePageTurner::enable()`. NimBLE sets the local GAP Device Name; this does
not itself publish an advertisement or instruct Windows how to label a pairing
request. CrossInk is the scanning/connecting central and Windows is the HID
peripheral. The current SDK flow creates a GATT client, not an advertising
identity-discovery flow for Windows.

Microsoft documents the display name as Windows' `DeviceInformation.Name`;
its pairing API does not provide a peer-supplied dialog-title override:

- [DeviceInformation.Name](https://learn.microsoft.com/en-us/uwp/api/windows.devices.enumeration.deviceinformation.name)
- [DeviceInformationPairing.PairAsync](https://learn.microsoft.com/en-us/uwp/api/windows.devices.enumeration.deviceinformationpairing.pairasync)

No documented, reliable minimal change was found that makes Windows resolve
this central's name before showing the incoming request. The generic “your
device” prompt is therefore left unchanged. This is a limitation of the
currently verified discovery/pairing flow, not a claim that Windows can never
name a BLE central. Advertising or adding services would expand the working
flow and require separate validation.

## UI verification

Check Settings → System → Bluetooth with touch and physical buttons. The
Enable Bluetooth row uses the same FreeInkUI list toggle as the frontlight
settings. Its checked value requires both successful opt-in and a running SDK
host; failed startup remains Off. Session-only/default-Off behavior is unchanged.

Failures stay in the screen rather than opening repeated dialogs. Memory and
Wi-Fi refusals can appear together; initialization and connection failures have
separate explanations. Text uses the SDK's measured multiline layout. Numeric
heap diagnostics remain in serial logs, and all memory limits are unchanged.

After supervised installation, verify enable/connect, wireless `key right` and
`key left`, disable, sleep/wake, restart-to-Off and USB Drive. Check failed
connection text with the Windows peripheral unavailable, and Wi-Fi refusal
where the existing flow permits it. Inspect long messages at the largest UI
scale and both orientations. Do not deliberately exhaust memory on the device
to test the memory message.
