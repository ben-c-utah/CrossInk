# BLE page button assignments

## Behavior and scope

With a compatible HID device connected, Bluetooth settings offers Configure
Buttons. Select Next Page or Previous Page, then press **and release** the
desired remote button within 15 seconds. Back cancels capture. Learning
suppresses page delivery, ignores pre-capture queued input and modified keys,
and rejects rest-frame corrections. The matching release confirms the capture;
release reports never turn pages. Repeated presses while a mapped button is
held are suppressed until its release.

Assignments are keyed by the SDK's bonded peer address and address type, with
four device slots and two fingerprints each. A fingerprint contains report
ID, payload byte index and value, as in CrossPoint's bounded BleKeyBinding
policy. No new remote profile, hold action or global Up/Down mapping is added.
Learned assignments take precedence for that device; ordinary Windows
Left/Right remains the fallback for unassigned input. Each event takes one route.
The existing freshness, foreground-reader, sleep and USB policies remain in use.

A button already assigned to the other action is rejected without replacing
either assignment. Reset Buttons clears only the connected device's assignments,
allowing a swap. Successful writes show Saved; timeout, disconnect, full storage
and persistence errors have inline feedback. There are no repeated popups or
countdown redraws. The existing Disconnect and Forget Device operation still
forgets all SDK bonds; their assignments are cleared as part of that operation.

## Persistence and resource budget

The SDK already keeps bonds in NVS. Button assignments use a separate
`crossink-ble` namespace, key `buttons`; BLE opt-in itself is never persisted.
Loading occurs before BLE's unchanged startup memory check. A fixed 112-byte
in-memory table and bounded capture/router state avoid per-event allocations.
The codec and storage adapter use stack buffers under 128 bytes each, rather
than allocating a settings JSON document while BLE runs. NVS internals may
allocate; actual heap behavior still needs supervised hardware verification.

The format is an explicitly encoded 116-byte blob:

- Header: `B`, `M`, version 1, fixed capacity 4.
- Four records: 18-byte terminated address, 1-byte address type, two
  little-endian 32-bit fingerprints. Zero means unassigned; empty records are zeroed.
- A little-endian FNV-1a checksum covers the preceding bytes.

Length, version, addresses, fingerprint bits, duplicate identities and duplicate
assignments are validated. Invalid data is logged and ignored; it cannot become
a page action. Writes occur only on changed, confirmed assignments, reset, or
forget. One NVS blob is written and committed; the active table changes only
after storage reports success. An error means persistence is unconfirmed and
the previous in-memory table remains active. Relearning the same assignment
does not write flash. The SDK revision and dependencies remain pinned.

## Supervised physical test

1. After supervised installation, start from a fresh boot. Enable Bluetooth and
   connect the Kobo Remote. Open Configure Buttons using touch, then also check
   selection and confirmation using physical buttons.
2. Select Next Page; press/release the **large main button**. Expect Saved and
   Assigned. Select Previous Page and press/release the large button again:
   expect the duplicate warning, with Next unchanged. Select Previous Page
   again and press/release the **smaller page button**; expect Saved.
3. Return to an EPUB. Press large three times, slowly: exactly three next-page
   actions. Press smaller three times: exactly three previous-page actions.
   Hold each for two seconds: at most one action per press, none on release.
4. Restart the reader. Bluetooth must be Off. Enable, scan and reconnect the
   Kobo; both assignments must still show Assigned and work without relearning.
5. Select an assignment and wait 15 seconds: expect timeout with the old mapping
   intact. Test Back cancellation. In a separate capture, turn the remote off:
   expect disconnected feedback and no new assignment. Confirm physical page
   controls, Home, sleep/wake and USB Drive still work.
6. From a separate fresh boot, connect Windows BLE HID. `key right` and
   `key left` must still turn once without learning. `key down` and `key up`
   must not inherit the Kobo assignments. Optionally assign/reset Windows
   buttons and verify that the Kobo's saved assignments remain unchanged.
7. Use Reset Buttons on Kobo only if desired; both assignments should become
   Not Set and stay cleared after restart. Relearn using steps 1–2.

The connection-cycle fragmentation issue remains separately tracked. If the
unchanged guard refuses re-enable, retain the logs and use a fresh boot for the
next mapping test; do not relax thresholds. Bonded address stability across
reconnects must be confirmed on hardware; rotating/private identities may need
SDK identity-resolution work in a later, evidence-driven change.

## Automated verification

Compile-time tests exercise codec restart round trips, corrupt/version-invalid
records, peer/address-type isolation, bounded capacity, duplicate rejection,
reset isolation, press/release and repeat suppression, modified/rest input,
capture timeout/cancellation/disconnect, timer wraparound, Windows arrow fallback
and single-route overrides. NVS flash survival and the UI require the physical
checks above; they are not claimed as automated hardware tests.
