# V5 pairing and cleanup investigation

Status: diagnostic checkpoint for a supervised v6 experiment; no hardware test.
Known v4/v5 images are unchanged. Button learning and all memory guards remain.

`pio run -e x4-pro-ble-diagnostic` succeeded: image 5,836,032 bytes,
717,568 bytes free in the 6,553,600-byte partition. Static RAM is 115,164 bytes,
unchanged from v5. No persistent buffer or added initialization allocation is
introduced by the lifecycle logger. Runtime NVS/serial effects remain unmeasured.

The user observed rapid blue blinking in Kobo's explicit pairing mode, versus
slower pulses in reconnection mode. Earlier attempts may have mixed these states,
and the remote has been paired with both Windows and X4 Pro. This is context,
not an established explanation for failure. Keep Windows Bluetooth Off.

## Established from source

- V4 `c1e4467c` and v5 `65ebb88e` pin SDK `f62bb097`. GAP connect,
  security policy, discovery, subscriptions and teardown are unchanged. V4 used
  diagnostic flags; v5 used normal `x4-pro`. V5 adds 152 bytes of static RAM and
  a read-only NVS mapping load before preflight. Forget now also writes the
  empty mapping table. Timing/heap effects are possible; neither establishes a
  pairing regression.
- Connection order is GAP, HID service discovery, synchronous security, HID
  subscriptions, then SDK remembered-peer persistence. A failure before HID
  setup can leave NimBLE security credentials without SDK remembered metadata.
- NimBLE synchronous security returns the encryption-event result through
  `getLastError()` and retries missing-key status once. Its authentication
  completion callback is not a universal failure callback: error status must be
  captured at the failed `secureConnection()` call. Disconnect reason is separate.
  Also retain NimBLE's `ble_gap_security_initiate: rc=...` line: an immediate
  initiation failure can be more specific than the synchronous wrapper's result.
- `Not a HID device` means `getService(0x1812)` returned null. GATT request errors,
  including a dropped link, also take that path. It does not prove Kobo lacks HID.
- SDK remembered metadata uses `freeink-hid` NVS; NimBLE owns separate security
  credentials; button assignments use `crossink-ble`. Four remembered slots and
  three configured security bonds are distinct limits. Live counts are needed.
- HAL Forget is legacy **all remembered peers**, not a selected-peer operation.
  It silently returns while off/connecting; storage failure can also stop it.
  Otherwise it clears all mappings, requests asynchronous disconnect, loops over
  remembered addresses/types, and sets Ready without confirmation. Disconnected
  peers follow the same loop. An unremembered failed-pairing peer is not covered.
- SDK Forget ignores the boolean `deleteBond` result, removes remembered metadata
  and does not check Preferences writes. Thus apparent success may leave security
  records behind. `rc=5` at unpair means no matching security record; it is not
  proof of success, capacity exhaustion or the original security failure.
- Connection address/type lookup lets remembered metadata override scan type;
  identity/private-address and stale-type mismatches are hypotheses to test.
- Failed connection paths request disconnect and return the worker to idle;
  client/services are retained for reuse until next connection or shutdown.
  Shutdown waits for worker exit from NimBLE calls and finalized disconnect,
  deletes worker and client, then deinitializes NimBLE. It does not check the
  client-delete result; diagnostics now record it and remaining client count.

## Heap interpretation

132496/81908 versus 132088/45044 is 408 fewer total bytes but 36864 fewer
contiguous bytes. This proves a layout change, not the owner or size of a leak.
A small live allocation can split a much larger region. NVS caches, security
storage and application allocations remain candidates. No EPUB is required.
Worker stack reclamation can lag `vTaskDelete`; compare immediate and settled
samples before attributing ownership. A clean client count does not prove every
controller/NVS allocation was released.

The prebuilt S3 sdkconfig disables standalone heap tracing and task tracking.
Do not enable header flags against that binary. Region-level heap information
is available without replacing the core. If it narrows the split but cannot
identify its owner, allocation hooks/JTAG or a separately reviewed tracing-core
build are a subsequent step, not part of this change.

## Diagnostic changes

Only `x4-pro-ble-diagnostic` enables `FREEINK_BLE_HID_LIFECYCLE_DEBUG`.
Cold-path logs include attempt address/type, remembered/security counts and
security identities; security/GATT failure codes; authenticated/encrypted/bonded
state and key length; disconnect reasons; worker idle/deletion, client deletion,
completed teardown, free internal/largest/PSRAM and per-region heap totals.
Forget logs each requested address/type, deletion result and metadata write sizes.
No key material, new trace buffers, mapping or connection policy is introduced.
The diagnostic SDK checkpoint is `71ac350`; its parent remains `f62bb097`.
Bond inventories include the underlying enumeration return code; failed reads
are marked unknown rather than zero. Before requesting security, log OTA and
identity address lookup results plus current encrypted/authenticated/bonded state.
An identity-resolution callback and authentication completion callback add context.
Credential availability only establishes whether key reuse is possible. These
APIs do not reliably identify fresh SMP pairing versus accepted stored-key reuse.
The firmware cannot observe the remote's LED mode; record it in the test notes.
No secret keys or credentials are printed; existing serial passkey values are
also omitted while on-screen passkey handling stays unchanged.

Validation: both edited C++ units passed target-compiler syntax checks using the
diagnostic compilation database. Existing mapping, arrow-filter and memory-policy
constexpr assertions passed, as did three Python build-identity tests. Parent/SDK
diff checks passed. The v6 artifact manifest records compilation, size, hash and
checkpoint. No flash or push; v4/v5 checksums were reverified.

The added logger has no global trace buffer or state. Its 192-byte stack buffer
uses Serial.write instead of Arduino printf's long-line heap allocation. Address
inventories use a fixed three-entry stack array. Log strings live in flash;
runtime serial/NVS costs and timing effects still require hardware observation.
The target object reports a 272-byte logger stack frame including compiler and
varargs overhead. This bounded cold-path cost avoids heap churn; the connection
worker's existing 4096-byte stack is unchanged. Stack high-water behavior remains
a hardware check, including callbacks on the NimBLE task.

## Approved first controlled hardware procedure

1. Start serial capture on COM3 at 115200 **before** Bluetooth initialization,
   from a fresh X4 Pro boot. Keep Windows Bluetooth Off. Do not clear NVS or use
   Disconnect and Forget Device.
2. Hold the Kobo tip pairing button until **rapid blue blinking**. Record that
   state; slower pulses indicate the reconnection state used in some earlier tests.
3. Enable Bluetooth, scan, select Kobo and attempt exactly one connection. Preserve
   all output: target/type, metadata/security counts, lookup return codes, identity,
   security initiation/result codes, authentication callback and disconnect reason.
4. If connected, stop the experiment and preserve the logs. Optionally verify the
   existing learned page assignments; do not relearn or change bond state here.
5. If pairing fails, disable Bluetooth once. Preserve worker/client teardown status,
   internal free/largest/PSRAM and per-region heap information.
6. Wait approximately 30 seconds, then attempt to re-enable once. Preserve preflight
   thresholds and individual failed checks. Do not repeatedly retry or use Forget.
7. Save the complete raw log and note build v6, remote LED state, timing and outcome.
   Review this evidence before changing pairing, Forget or memory policy.

## Later comparisons, only after reviewing the first experiment

1. Save COM3 at 115200 baud from boot through completed shutdown. Record remote
   pairing mode, reader build, and whether other paired devices are nearby.
   Do not erase NVS, reset Kobo bonds or press legacy Forget as an initial step.
2. Fresh boot, stay in Settings (no EPUB), enable, scan, attempt Kobo once.
   Keep complete output including `security failed`, authentication, disconnect,
   worker idle and bond inventory. If successful, press/release both page buttons.
3. Switch Bluetooth off once. Capture worker/client deletion and region report.
   Wait 30 seconds, then attempt enable once to capture the unchanged preflight.
   If refused, stop; do not keep retrying or weaken guards.
4. From a fresh boot repeat without connecting, then separately with one failed
   connection and with one successful connection if possible. Compare identical
   lifecycle boundaries, client counts and region addresses/free/largest values.
5. Repeat with preserved v4 under otherwise identical remote/bond conditions.
   V4 lacks the new detailed logs, but its existing security debug code is enabled.
   Avoid repeated writes/forget operations between comparisons.
6. Defer destructive Forget testing until a reviewed single-peer correction.
   Then test only the intended Kobo identity: capture inventories before/after,
   explicit operation result and reboot persistence; verify other bonds and
   assignments survive. Test connecting and disconnected states separately.

## Smallest correction recommended for review

Implement one explicit peer-targeted forget operation with an observable result.
Resolve the security identity/type, stop scanning and finish/cancel connection
work before unpairing; distinguish absent credentials from actual failure.
Check security and metadata persistence results; clear only that peer's mapping
after the operation is reconciled. Keep other peers intact and report partial
failure. Do not automatically forget/re-pair on authentication failure.
Pairing/heap corrections must wait for the recorded codes and lifecycle samples.
