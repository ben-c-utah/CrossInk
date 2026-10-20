# V15: unchanged-theme reuse experiment

Baseline: V14 `8acf8fed34d2c90c4960613ff5966afbe0a7ae99`.
FreeInk SDK: `9f660022a0a338253fb964126558084e72a04ae5`, unchanged.
The archive manifest records the exact clean source commit, build identity,
BIN/ELF hashes, size and partition headroom. Identity is
`CrossInk BLE · v15-dev <commit>`.

## Hypothesis and single behavior change

The V14 clean Test E log (`device-monitor-261020-114511.log`) shows:

| Boundary | Internal free | Largest block |
| --- | ---: | ---: |
| First preflight | 167700 | 118772 |
| BLE initialized | 121156 | 77812 |
| Parent Settings rebuilt | 97292 | 51188 |
| Settings cleanup, before theme reload | 119872 | 73716 |
| Theme replacement | 119872 | 73716 |
| Home recent-book copies | 119220 | 73716 |
| BLE shutdown and refused restart | 165500 | 73716 |

Theme replacement from `0x3fcc4380` to `0x3fcd58f0` changes placement with
no net allocation increase. The new Home object is a strong independent
candidate: before theme replacement, its allocation accounts for the extra
1268 allocated bytes, one allocated block and 1284 fewer free bytes.
Home metadata later occupies storage previously used by Settings. Addresses
and aggregate counters do not prove physical adjacency or identify the final
obstructing block. Successful V13 D reconstructs Settings but does not visit
Home; it restores largest=118772 after teardown.

V15 tests whether unnecessary theme replacement on Settings exit is a necessary
contributor. `SettingsActivity::onExit()` now calls `reload(true)`.
`reload()` and `setTheme()` default to replacement, preserving boot and all
other callers. Only Settings exit opts into reuse.

`currentMetrics` already identifies the concrete implementation paired with
`currentTheme`. Each switch case skips replacement only when reuse was
requested and that metrics identity matches. No stored enum, new field,
allocation, custom allocator, or activity layout change is introduced.

- Cover Grid and Lyra share the Lyra implementation/metrics; unsupported Cover
  Grid still resolves to Lyra.
- Unknown values still resolve to Classic and retain the existing error log.
- Genuine changes still construct the appropriate concrete implementation and
  replace the old unique owner before updating its paired metrics pointer.
- Every path still sets `metricsValid=false`. Touch-sensitive metric refresh,
  normal logging and all V14 before/after pointer/heap records remain.
- Settings cleanup, orientation restoration and font-registry release remain
  in their original order under the existing ActivityManager render lock.
  Immediate theme changes in Settings retain their original reload/font logic.
- Constructor, boot reload, Home construction/metadata, path moves, category
  lists, BLE lifecycle, reader, updater, Wi-Fi and PC tooling remain unchanged.

This is not a claimed fragmentation fix. Matching storage does not require
matching numeric addresses across builds, but old/new theme pointers within
the same unchanged-theme Settings exit must match.

## Source validation

Run the complete prior 59 PC/native tests, including `test_build_identity.py`
and `test_heap_diagnostic_safety.py`, plus eight V15 tests.
The new native harness executes production constructor/reload/selection/cache
method bodies and the real theme enum, with minimal theme/heap/logger fixtures.
It runs both touch and non-touch variants:

- Boot/default replacement, including construction before destruction.
- Stable storage and zero new allocations across 100 same-theme cycles for each
  of seven concrete implementations.
- All 49 implementation-to-implementation transitions.
- Cover Grid capability fallback and shared Lyra identity.
- Invalid-value Classic fallback and subsequent recovery.
- Metric invalidation and touch/non-touch cache recomputation.
- Only Settings exit opts in; full Settings body otherwise matches V14.
- V14 diagnostic blocks and theme storage members remain unchanged.

The V14 whole-source preservation test reverses only the explicit V15 delta
before comparing diagnostic-stripped sources to V13. Protected BLE lifecycle,
guards, Home navigation, dictionary/recent store, File Browser and build
configuration remain under existing byte-for-byte checks.

Retain all 12 production target syntax checks and six BLE compile-time checks,
using the V14 target flags with only the Lab identity changed to 15.
Run Python syntax, diff/whitespace and changed-hunk format review.
Native fixtures cannot prove physical allocator placement or real render-task
timing; those remain hardware acceptance conditions.

Build once with `pio run -e x4-pro` from a clean committed detached checkout.
Use the same isolated diagnostic configuration, with
`custom_ble_lab_version = 15`. Archive actual test/build results, configuration,
source patch, BIN, ELF, partitions, manifest and validation notes separately.
Do not modify earlier archives or install/upload the candidate.

## First hardware experiment: clean Test E

After owner-approved installation:

1. Start/retain continuous serial capture. Use Home Lab software Restart.
   Confirm `CrossInk BLE · v15-dev <manifest commit>`.
2. Record whether boot enters an EPUB or Home. An EPUB resume is not the clean
   comparison; retain its log and report the changed history.
3. Home → Settings → System → Bluetooth → On. Wait approximately 30 seconds.
4. Back to System → Back to category bar → Back to Home.
   Allow Home's first render to finish; leave BLE running throughout.
5. Home Bluetooth Lab → Off. Wait approximately 30 seconds after shutdown.
6. Home Bluetooth Lab → On. Wait approximately 30 seconds.
7. Collect the full serial-monitor log before any further restart. Keep Wi-Fi
   and SD diagnostic export out of the controlled memory sequence.

Check the initial preflight and BLE-active baselines against V14. Inspect theme
old/new pointers, Home object/path/recents, Settings-release boundaries, and
shutdown free/largest/block counts. All startup, post-start and runtime guards
remain respectively 131072/79872, 65536/32768 and 49152/24576 bytes.
PSRAM requirements and Wi-Fi exclusion remain unchanged.

## Interpretation

- Full recovery near 118772 and successful restart supports the intervention.
  It does not prove the old theme physically separated two BLE free regions:
  later allocations can move as a consequence. Repetition and broader reading,
  navigation and actual theme-change tests are required before accepting a fix.
- Stable theme pointer with approximately 73716 and failure falsifies theme
  replacement being necessary for this failure under a comparable baseline.
  Investigate Home construction/placement next; do not automatically change it.
- Partial recovery or a marginal guard pass suggests interacting causes.
  Never lower a guard or combine another memory correction into this experiment.
- A changed initial baseline or unexpected theme replacement makes the
  comparison inconclusive until the cause is understood.

V14 diagnostics can perturb timing; V15 retains them for comparison.
No physical recovery is claimed by source tests or successful compilation.
