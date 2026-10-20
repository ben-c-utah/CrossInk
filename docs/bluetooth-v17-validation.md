# V17: controlled Home recent-book record placement

Baseline: V16 d830338e418530b9c68cd77dfcee60ef47978894.
SDK: 9f660022a0a338253fb964126558084e72a04ae5 (unchanged).
This candidate tests record-array placement; it is not a proven fragmentation fix.

## Scope and consumer map

Only the existing V16 root Settings-return Home factory selects external record
storage. ActivityManager route selection, construction timing, replacement,
render locks, path handoff and failure restoration remain unchanged.
Boot and other Home routes retain an ordinary std::vector<RecentBook>.
The target compiler asserts the original 1252-byte Home controller size.
The external-mode boolean occupies existing padding; the union occupies exactly
one vector's footprint. Global recent-book ownership and persistence are unchanged.

Home loadRecentBooks still copies the global record to a temporary, filters
missing files, normalizes the cover reference, then copies into Home storage.
There is no move substitution, string allocator change or render-time vector copy.
Selection restoration and book swapping rotate the same mutable records.
Cover loading can update cover metadata as before.

All rendering consumers use RecentBookView, an allocation-free pointer/count
view with const record access: BaseTheme, DashboardTheme, LyraTheme,
Lyra3CoversTheme, LyraCarouselTheme, MinimalTheme, RoundedRaffTheme and
CoverGridHomeUi. Their drawing bodies are mechanically unchanged; CoverGrid's
retained collection pointer becomes a retained view. The view contains two words
rather than one; cover-grid bookkeeping can therefore grow by a word. It is not
instantiated in the controlled classic-Home experiment. Other theme histories
require later hardware regression testing.

## Ownership and failure

Before constructing Home or consuming the selected path, the factory obtains
both controller storage and aligned MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT record
storage. Seven slots (700 target bytes, before allocator overhead) cover the
largest supported Home layout, including cover grid. Preallocation precedes
Settings exit because a genuine theme change may become effective during exit.
No records or strings are populated until the original Home initialization point.
Only two records are constructed in the controlled test; capacity seven is expected.

Either PSRAM allocation failure leaves Settings usable through the existing V16
failure path. Temporary raw storage is RAII-owned; no internal fallback occurs.
Successful construction hands the record block to Home. Each record is placement
constructed normally; the constructed count advances only after success.
Clear destroys constructed records, and destruction releases the block once with
heap_caps_free. No live C++ object is relocated with memcpy or fabricated vector
internals. Home resets CoverGridHomeUi before destroying record storage; the
normal onExit already does so under ActivityManager's lifecycle lock. The destructor
releases initialBookPath storage before records, matching the original member
destruction order; its later automatic string destructor sees an empty string.

Long std::string buffers retain their ordinary allocator. The existing target's
exception-free std::string allocation-failure behavior is not changed. Native
exception injection checks cleanup of a partially copied record and prior live
records; it does not establish recovery from target string OOM.

## Validation requirements

Retain every one of the 77 V16 tests, plus current PC-tooling checks. Execute the
actual factory/navigation code with both first- and second-PSRAM-allocation
failures, native production storage/view/load methods, six ordinary string
allocations, alignment, filtering, rotation, updates and destruction. Historical
source assertions gate exact reviewed V17 file hashes before comparing V16 with
older checkpoints; independent checks require mechanically unchanged theme bodies
and byte-identical protected sources. Run all 12 prior production syntax targets,
all seven additional affected rendering translation units and all six BLE
compile-time checks. Preserve diagnostics and the 1252-byte target ABI assertion.

Early native harness checks required explicit static_assert messages for the
installed GCC 5.1 compiler and corrected expected free counts for non-Lab variants.
A historical diagnostic assertion also required the new view-accessor spelling.
A subsequent run passed all 98 test methods but Windows temporarily denied cleanup
of a native test executable; the complete suite was rerun. These were validation
compatibility/environment issues, not firmware build failures.

## First hardware experiment: clean Test E

Do not install automatically. After owner-approved installation:
1. Start continuous capture, software restart, confirm v17-dev identity and direct
   Boot -> Home without EPUB activity or SD fonts. If needed, use normal Sleep
   from Home, wake, then Lab Restart; never edit session/progress/NVS files.
2. Home -> Settings -> System -> Bluetooth -> On. Wait 30 seconds.
3. Back to System -> Back to category bar -> Back to Home, keeping BLE active.
4. Home Bluetooth Lab -> Off. Wait 30 seconds. On. Wait 30 seconds.
5. Collect the complete serial log before another restart or Wi-Fi/SD export.

Verify boot Home/controller and record array external=0; replacement controller
and record array external=1; two records/capacity seven; all six long strings
external=0; inline authors external=1; unchanged selected path and theme reuse.
Initial BLE preflight should closely match free=167700, largest=118772; active
BLE free=121156, largest=77812. Metadata should add six internal blocks, not
seven. Saving is only the former record allocation's charge, not all 652 bytes.
Do not infer exact allocation charge from vector capacity or string capacity.

Largest recovery near 118772 after normal shutdown, with successful restart,
supports this intervention without proving physical adjacency or sole causation.
An unchanged 77812 demonstrates only that record placement alone is insufficient.
Partial recovery or a marginal pass above 79872 is not release acceptance.
Further acceptance requires repeated navigation/cycling, reading histories,
Kobo page turns/reconnection, covers and all protected workflows. All BLE guards,
PSRAM/Wi-Fi restrictions, SDK/security/partitions remain unchanged.
