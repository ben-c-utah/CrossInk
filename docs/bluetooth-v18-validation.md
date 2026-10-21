# V18: zero private recent-book copies experiment

Baseline: V17 `a65801555dc210e443e317e0909420933404fd28`.
SDK: `9f660022a0a338253fb964126558084e72a04ae5`, unchanged.
This is a diagnostic candidate, not a release-ready fragmentation correction.

## One controlled change

HomeActivity::onEnter skips loadRecentBooks only when externalRecentBooks is
true. Only createForSettingsReturn sets that existing flag, on the existing
root Settings-to-Home route. Boot and unrelated Homes still load their private
records. No class fields, controller footprint, allocator, construction order,
render locks or navigation interfaces change.

The V17 factory still preflights the external Home controller and seven aligned
external RecentBook slots (700 target bytes before allocator overhead) before
moving the selected path or replacing Settings. The array is adopted normally
but its constructed count stays zero. No temporary RecentBook or private string
copy is made. Allocation failure still preserves Settings and the retained path;
the old executable factory/failure tests remain applicable. Destruction frees
the array once, with zero record/string destructors to run. CoverGridHomeUi is
released before its collection owner as before.

RECENT_BOOKS.ensureLoaded and the global-store diagnostics stay in their original
positions. Global history, APP_STATE, book files and persistence code are not
modified. Selection restoration still executes and keeps the initial path
buffer, but naturally finds no private entry to highlight on this diagnostic
Home. Browse Files, Library, Settings and Bluetooth Lab remain available.
Recent-book cards, cover and Continue Reading are intentionally absent only on
this replacement Home. They return on ordinary Home construction.

## Empty-list feasibility review

- onEnter excludes Continue Reading when empty, uses a guarded front() for the
  grid, and leaves a valid ordinary-menu selection. getHighlightedBookIndex
  returns -1; path/title accessors return empty strings; swapping is disabled.
- onContinueReading returns immediately. Grid activation maps menu indices
  after a zero-size book range. No record is dereferenced for those actions.
- Recent cover, thumbnail and statistics loading iterate over the private
  count, so empty data cannot generate new book-specific work. Carousel cache
  validation rejects index -1 before constructing a key; frame warmup returns
  before allocation for zero books.
- CoverGridHomeUi does not allocate its cover cache for an empty view; draw
  takes its existing empty branch. HomeCoverCache::prepare only invalidates
  existing metadata. The view remains valid until the UI is released.
- Base, Lyra, RoundedRaff, Lyra3Covers, Carousel, Dashboard and Minimal already
  guard empty records. Their bodies remain byte-identical to V17. The tested Lab
  is Lyra; it renders its existing empty-recents message. Minimal's existing
  empty-state quote uses temporary wrapped-text storage. Normal renderer/font
  activity is not claimed allocation-free, and other themes need hardware
  regression checks. No new fallback allocation mechanism is introduced.

The executable native fixture runs the actual onEnter, loadRecentBooks and
selection/accessor methods with production storage/view/record types. It counts
ordinary allocations, checks zero targeted copies (including temporaries),
retained external capacity, selection/path/global-state invariants, empty grid
and carousel initialization, repeated initialization and destruction. Its UI,
filesystem and statistics collaborators are bounded stubs, not an e-ink or
ESP32 allocator emulator. Separate source contracts require exactly the one
reviewed production gate and unchanged protected files; older V17 hash gates
still reject any other production change.

## Coverage and archive

Retain all 98 prior PC/native tests, all 19 production translation-unit syntax
checks and all six BLE compile-time checks. Add ten V18 checks. Run Python
syntax and git diff validation before one isolated clean x4-pro build. The
archive's validation-results.json and BUILD-NOTES.md record actual results,
compiler warnings, source identity, SDK, BIN/ELF checksums and partition headroom.
The Workbench improvements remain outside the firmware source change.

## First physical experiment: clean Test E

Only after owner-approved installation:

1. Start continuous serial capture. Software restart, verify `v18-dev` and
   direct Boot -> Home with no Reader/EPUB activity or SD-font history. If
   necessary use normal Sleep from Home, wake, then Lab Restart. Do not edit
   state, reading progress or NVS.
2. Home -> Settings -> System -> Bluetooth -> On. Wait 30 seconds.
3. Back to System -> Back to category bar -> Back to Home with BLE still on.
4. Verify replacement Home/controller external=1 and recents data external=1,
   size=0, capacity=7. There should be no private recent-string records. Boot
   Home must still show ordinary records; selected input and theme reuse remain.
5. Home Bluetooth Lab -> Off. Wait 30 seconds. On. Wait 30 seconds.
6. Collect the complete serial log before restarting. Keep Wi-Fi/SD export
   after the memory observations, not between the controlled steps.

Initial BLE preflight should closely match free=167700 / largest=118772, and
active BLE free=121156 / largest=77812. Distinguish the earlier diagnostic
snapshot from the actual guard measurement: V17's snapshot was free=167916,
while its later guard baseline was 167700. Compare like-for-like boundaries.
Compared with V17, private-copy initialization should not consume the observed
432 internal bytes/six blocks. After shutdown, free near 167436 is an expected
comparison, not a guaranteed exact measurement. Use block counts and all
existing snapshots to detect other layout changes, including empty rendering.

Recovery toward largest=118772 with normal shutdown and successful restart
would support eliminating the private records as a sufficient intervention for
this controlled history. It would not identify which string blocked coalescing.
An unchanged 77812 would establish that this intervention alone is insufficient;
investigate other surviving owners/heap regions rather than relocate blindly.
Quantify partial recovery; a marginal pass over 79872 is not release acceptance.
All startup/post-start/runtime, PSRAM and Wi-Fi restrictions stay unchanged.
Repeatability, ordinary reading histories, Kobo controls and other navigation
remain future acceptance work. V18 intentionally lacks recents on the targeted
Home and is not intended as the permanent UX solution.

No automatic staging, installation, flashing, push or publication is authorized.
