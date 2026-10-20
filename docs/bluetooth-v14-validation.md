# V14 diagnostic candidate: Home transition allocation lifetimes

## Scope and evidence

Baseline: V13 `a626db46af2bb039478e6691521be4fb8bba0b9e`.
FreeInk SDK remains `9f660022a0a338253fb964126558084e72a04ae5`.
Candidate identity is `CrossInk BLE · v14-dev <source commit>`.
The archive manifest records the exact committed source and binary identity.
This is instrumentation, **not a corrective release**.

The complete clean Test E capture was read:
`C:\Users\chrbe\logs\ble-sessions\ble-session-20261020-100903-313524\device-monitor-261020-100535-full.log`.
Segment after the software reset (line 16); disregard the earlier prefix.
Boot enters Home directly, with no Reader/EPUB activity; renderer reports three
built-in fonts and zero SD fonts. The relevant boundaries are:

| Boundary | Internal free | Largest internal block |
| --- | ---: | ---: |
| First BLE preflight (line 169) | 167700 | 118772 |
| BLE initialized (line 176) | 121156 | 77812 |
| Parent allSettings construction (line 187) | 114252 | 73716 |
| Home initialized | 119220 | 73716 |
| Shutdown complete (line 293) | 165500 | 73716 |
| Refused restart (line 380) | 165500 | 73716 |

The parent is in PSRAM. The new Home object is internal at `0x3fcd70d0`,
actual size 1268 bytes. Theme changes from `0x3fcc4380` to `0x3fcd58f0`,
actual size 4 bytes. These are observed addresses, **not proof of adjacency
to a BLE allocation or responsibility for the blocked coalescing**.

The earlier A/B failures visited Home; C stayed inside Bluetooth; D rebuilt
parent Settings without visiting Home and recovered its 118772-byte block.
Clean E rules out EPUB history and a second Home-to-Settings visit as necessary
conditions. Parent reconstruction alone remains insufficient under tested D.
Surviving Home/theme/metadata allocations interleaved with BLE allocations are
the leading mechanism; the exact obstructing owner remains unproven.

## Instrumentation map

All new observations are gated by `CROSSINK_HEAP_DIAGNOSTICS`, restricted to
physical X4 Pro. No fields are added to any activity or persistent store.

| Boundary / log label | Observation and purpose |
| --- | --- |
| `goHome before path handoff` | Heap and manager path object/data/length/capacity before moving it. |
| `manager path after Home move`, `goHome local path` | Distinguish transferring an existing backing buffer from copying it. |
| `before Home construction` / `after Home construction` | Heap, outgoing activity allocation, new Home allocation/size and received path. Home is still constructed before outgoing Settings exits. |
| `Bluetooth child returned before/after Settings rebuild` | Heap/block counts and still-live parent address around the existing result callback; existing `allSettings constructed` captures temporary peak. |
| `Settings before child menu release`, existing menus/catalog released logs | Separate menu storage and dictionary catalog release before child construction. |
| `Settings before cleanup`, `Settings exit menus/catalog/font registry released` | Separate outgoing Settings cleanup stages, including dictionary vector backing identity. |
| `theme before/after reload`, `theme old/new` | Heap and exact theme allocation addresses around the unchanged replacement. Old pointer is inspected before replacement only. |
| `before activity exit`, `before activity destruction`, `after activity destruction` | Separate onExit cleanup from destructor cleanup. No destroyed owner is dereferenced or queried afterward. |
| `Home before initialization` | Object, received path and initially empty Home metadata. |
| `Home before/after recent store load` | Separate persistent recent-store loading from per-Home copies; global vector backing identity after the existing load. |
| `Home after recent copies` | Home recent vector data/size/capacity/element size; at most three records' path/title/author/cover string backing identities. Omitted count is explicit. |
| `Home before/after selection restoration` | Heap around the existing selection/rotation and input path identity; focus/selection behavior is unchanged. |
| `Home after initialization`, `Home after first render`, `Home before exit` | Retained owners after initialization/render and before cleanup, including chapter title, cover/grid/carousel buffers. First-render inspection respects the existing render lock. |
| Existing `BLE before shutdown` / `BLE teardown complete` | Heap/block counts and per-region summaries across unchanged SDK teardown; existing worker/client lifecycle output is preserved. |
| Existing first-render renderer/font-cache diagnostics | Renderer buffer owners and font cache/decompressor/SD-font owners when present; no reader or font code changed. |

Snapshots report total free/allocated internal bytes, largest block,
allocated/free block counts, and PSRAM free bytes. Vector diagnostics report
backing address, size, capacity and element size without walking allocations.
String diagnostics report object and data addresses, length, capacity and PSRAM
classification, never contents or allocator allocation-size queries.

## Safety and observer effects

- No allocator hooks, traversal, heap dumps, new diagnostic buffers, diagnostic
  vectors/strings, new tasks, sleeps, scheduling changes or persistence writes.
- Helpers use constant formats and scalar/const-reference arguments. The
  existing logger uses a 256-byte stack buffer and its existing RTC ring.
  Heap statistics are copied before logging; no output occurs under heap locks.
- Exact allocation-size queries remain limited to known live allocation bases:
  activities, themes and owned cover buffers. Never query string data, vector
  elements, interior pointers, empty storage, or destroyed owners.
- Home observations add no data members. Naming its existing unique_ptr permits
  observation between construction and handoff; allocation/destruction order,
  arguments and unique ownership remain the same.
- Recent strings are bounded to three records per detailed observation. No
  content copies or path/title output. Existing first-render diagnostics skip
  owner inspection if the activity's render method released its lock.
- The normal UI/render mutex may be held at existing protected boundaries.
  It is not an allocator spinlock. Extra serial output can still delay rendering
  or change timing: this candidate is not a zero-perturbation heap experiment.
  No claim is made that runtime placement will exactly match V13 addresses.
- Startup guards remain 131072/79872; post-start 65536/32768; runtime
  49152/24576 bytes (free/largest). PSRAM, Wi-Fi exclusion, security, bonds,
  manual reconnect, native updater, PC tools and SDK behavior are unchanged.

## Source validation and build

`scripts/test_ble_v14_diagnostics.py` executes the real observer helpers against
heap/log stubs using short, long, empty and moved-from strings and empty/nonempty
vectors. It checks zero new allocations and zero allocation-size queries for
storage observations, plus the disabled build path.

It also compares diagnostic-stripped production sources against V13, allowing
only naming the existing Home unique_ptr before the unchanged handoff. BLE
policy/lifecycle, child Settings, dictionary/recent store and other navigation
dependencies must remain byte-for-byte unchanged.

Run the V11-V14 ownership tests, existing Lab runtime/layout/build/PC tests and
staging/collection tests. Run X4 Pro target syntax checks and diff/format checks
before the single full build. Archive factual results, build log, local diagnostic
configuration and source patch alongside BIN/ELF and manifest.

Build from a clean committed detached checkout with the pinned SDK. Opt in using
`custom_ble_lab_version = 14` and `pre:scripts/ble_heap_diagnostics.py` in the
candidate's local configuration. No build/flash/staging from the device is
automatic. Stage Latest may discover the archive after verification; preparing
an archive does not authorize installing it.

## First physical experiment: clean Test E only

After owner-authorized manual installation:

1. Keep the existing continuous serial monitor running. Verify the Home header
   and boot log say `CrossInk BLE · v14-dev <matching manifest commit>`.
2. Use Home Lab software **Restart**, confirm, and wait for Home. Record whether
   a Reader/EPUB activity appears automatically. If it does, preserve that log
   and identify the run as confounded rather than calling it clean Test E.
3. **Home → Settings → System → Bluetooth → On**. Wait approximately 30 seconds.
4. **Back** to System, **Back** to the category bar, **Back** to Home. Leave
   Bluetooth running throughout; allow Home's first render to finish.
5. Expand Home Bluetooth Lab if needed; select Bluetooth **Off**. Wait
   approximately 30 seconds after shutdown completes.
6. Select Bluetooth **On**. Wait approximately 30 seconds. Record either the
   successful startup or the unchanged guard refusal.
7. Use existing **Collect Logs** and supply the complete device-monitor capture
   before any subsequent restart. Do not start Wi-Fi or export SD diagnostics
   during the controlled sequence. No initial A-D repetitions are required.

Read one restart-delimited epoch and align the new owner records with the
existing BLE preflight/initialized/shutdown summaries. Compare pointer identity,
storage capacity and block counts before/after each individual boundary.

## What this can establish

The first V14 log can establish which candidate owners are newly allocated,
moved unchanged, retained, or released, and which boundary changes aggregate
memory. It can rule out owners located in PSRAM or freed before the failed
preflight. It cannot prove a small live allocation is physically separating two
specific free regions from addresses/counters alone; nor does a V14 pass prove
the original defect fixed.

If several internal owners survive, the next step is owner review of one
controlled lifetime/placement change at a time, with the same clean E route.
Choose the owner whose address/lifetime and boundary evidence are strongest.
Confirm restoration of contiguous memory and repeatability, not a marginal
guard pass. If allocation/free adjacency evidence is still required, design a
separate bounded capture of explicitly identified allocation bases outside
allocator critical sections; do not infer neighbors from string addresses or
introduce a whole-heap dump. No corrective experiment is authorized by V14.
