# X4 Pro Bluetooth restart heap experiment (V8)

Baseline: CrossInk `4c85de55`, FreeInk SDK `9f66002`. This experiment changes
neither allocation policy nor Bluetooth memory thresholds. It is not a permanent
fragmentation fix. Preserve the V7 artifact and learned button assignments.

## Evidence and suspects

- V7 log `device-monitor-261019-011245.log`: largest internal block is 94,196
  before BLE, 53,236 after connection, 53,236 immediately after reader font-cache
  release, then 40,948 after Home/menu navigation. Completed teardown and Forget
  All do not recover that block. The additional menu-stage reduction is 12,288
  bytes; that difference alone does not identify an allocation size or owner.
- Healthy V6 `device-monitor-261019-001058.log` restores 90,100 after connection
  and shutdown without reading. V6 `device-monitor-261019-003319.log` reproduces
  the 40,948 result after reading. Similar total free memory with different
  largest blocks supports fragmentation or small retained allocations, rather
  than a missing 40–50 KB BLE buffer. A small leak is still possible.
- `lib/EpdFont/FontDecompressor.cpp`: the singleton's hot-group/hot-glyph malloc
  buffers grow without shrinking until `clearCache()`. Page/prewarm buffers also
  use ordinary malloc. Default allocation does not guarantee PSRAM. These buffers
  are reconstructible and menus can repopulate them after reader cleanup.
  The pinned dio_opi SDK config prefers internal RAM for default allocations
  up to 4,096 bytes; allocation location must still be checked at runtime. A
  small retained buffer can split a much larger free span.
- `lib/GfxRenderer/FontCacheManager.cpp`: `releaseSdFontCaches()` clears that
  decompressor plus each SD font's `releaseForLowMemory(false)`.
  `lib/EpdFont/SdCardFont.cpp`: ordinary `clearCache()` deliberately retains
  mini/advance storage; the stronger release frees it, kerning and ligatures.
  Loaded font identity and full interval tables remain resident by design.
- `src/activities/reader/EpubReaderActivity.cpp::onExit()` already invokes the
  stronger release. Its existing "reader exit after caches" log occurs BEFORE
  section/EPUB reset and activity destruction. The new destruction checkpoint
  separates those lifetimes. EPUB vectors/index data owned by `Epub` are released
  with the object; persisted SD indexing is a different resource.
- `src/activities/home/HomeActivity.cpp`: carousel frames prefer explicit PSRAM,
  and `onExit()` releases cover/frame buffers. Recent-book strings, activity/UI
  objects and containers can still occupy internal blocks. Settings discovers a
  dictionary registry and retains lists while its Bluetooth child is displayed.
  Activities are allocated before the outgoing activity is destroyed, so even
  small surviving allocations can pin holes in a previously large free region.
- `src/components/UITheme.cpp::setTheme()` replaces the resident theme object
  on Settings exit even when the theme is unchanged. The replacement is allocated
  before the old object is freed. This is a specific possible small pinning
  allocation; first-render diagnostics identify its address. Metrics are fixed
  data. FreeInkUI's GfxRenderer adapter uses local wrapped-text strings and
  vectors, not a persistent wrapped-subtitle cache. Renderer font registrations,
  fallback maps, and BW-buffer vector capacity are other resident candidates.
- `lib/ScalableFont/HalScalableFont.cpp`: large scalable-font workspace/pixel
  arenas explicitly use PSRAM on hardware. They are not released by this
  experiment. Do not unload live faces or borrowed glyphs to test a hypothesis.

No source inspection alone establishes which surviving block prevents coalescing.
The strongest first test is retained/repopulated font storage followed by the
Home/Settings activity and registry allocation layout.

## Opt-in build and instrumentation

Normal builds default `CROSSINK_HEAP_DIAGNOSTICS` to zero. For this diagnostic
artifact only, use the following ignored `platformio.local.ini`:

```ini
[env:x4-pro]
extra_scripts =
  ${base.extra_scripts}
  pre:scripts/ble_heap_diagnostics.py
```

Then run `pio run -e x4-pro`. The script enables heap diagnostics and the SDK's
existing lifecycle logs. Raw HID/scan verbosity remains Off. SDK, dependencies,
dio_opi, TinyUSB and PSRAM allocation policy are unchanged. Remove this local
override to return to normal builds. Archive it with the binary for reproducibility.

`HDBG` records internal free/largest/allocated bytes, allocated/free block counts,
PSRAM free, first activity renders, activity destruction, reader cleanup and BLE
boundaries. Font logs name exact owned allocation addresses, capacities and actual
allocated sizes; capacity zero means unavailable, not an empty allocation.
`external=1` means PSRAM. Renderer logs also identify retained BW storage.

Region summaries and full INTERNAL|8BIT heap dumps occur only at BLE preflight,
completed teardown and the manually requested reclamation experiment. Dumps
contain addresses/sizes/free-state, never memory contents or keys. These use
the installed IDF heap API and its ROM console; capture COM3/115200. No heap
tracing build option is enabled against the prebuilt Arduino core.

Instrumentation allocates no new diagnostic heap buffers or global trace arrays.
It adds a first-render flag per activity and one native diagnostic list row/flag
to the Bluetooth activity. Serial output changes timing and those small object
size changes can affect layout (Bluetooth activity payload: 4,984 bytes versus
V7 4,924, a 60-byte increase): compare within this build, not absolute addresses
across firmware versions. Underlying allocator dumps are not a whole-system
atomic snapshot; unrelated RTOS allocations can change between measurements.

## Controlled hardware procedure (supervised installation separately)

1. Capture COM3 at 115200 from boot, Windows Bluetooth Off. Keep the same theme,
   language, reader font, book and ordinary SD caches across both runs. Record
   those choices. Do not Forget devices or change assignments during the test.
2. **Control run, fresh boot:** enable BLE, connect Kobo, do not open EPUB.
   Return to Bluetooth and disable once. Wait for `BLE teardown complete` and
   its END dump marker. Wait 30 seconds, then enable once. Save the whole log.
3. **Reading run, fresh boot:** enable/connect Kobo, open the usual EPUB, turn
   several pages (including the previously tested image chapter), return Home,
   then Settings → System → Bluetooth. Disable once; await completed teardown.
   Wait 30 seconds, attempt enable once. Preserve the refusal and preflight dump.
4. While Bluetooth is fully Off, select **Reclaim Font Caches (Diagnostic)**.
   It is unavailable while BLE is resident or a reader remains on the activity
   stack. The action holds the existing RenderLock and refuses active font scans.
   It first clears built-in font caches, then the existing SD-font release API.
   It never unloads font faces, changes settings/progress, or starts Bluetooth.
5. Preserve `reclaim before`, `reclaim after built-in fonts`, `reclaim after all
   fonts BEFORE repaint`, both block dumps, and `reclaim after normal repaint`.
   The panel content remains until the ordinary redraw; glyph pointers are not
   retained across that locked, completed draw. After repaint, manually enable
   once. The existing 131,072/79,872 startup checks still decide whether it starts.
6. If enabled, reconnect and verify learned Kobo Next/Previous, physical buttons,
   reading position, Home, sleep/wake and USB Drive handoff. If refused, stop;
   do not repeatedly retry or relax guards. Preserve both complete logs.

## Interpretation and permanent correction gate

- Recovery after the built-in-only step identifies the decompressor cache group;
  recovery only after the SD-font step identifies optional SD-font caches.
  Match allocation addresses to the intervening used blocks in the dump.
  The IDF dump prints block-header addresses; user pointers are offset by the
  allocator/debug header, so do not require literal address equality.
- Recovery before repaint followed by loss after repaint identifies reconstruction
  as a contributor. A future locked, just-in-time cache release before BLE start
  is only a candidate: first validate post-start/render headroom and redraw cost.
- No recovery: compare used-block addresses/sizes in control teardown versus
  fragmented teardown and before/after reclamation. Cross-reference named font,
  renderer, theme and activity allocations; investigate the remaining pinning owner.
  Dumps do not supply allocation call sites. Add tracking only at the newly
  identified owner's allocation boundary if required, not speculative heap hooks.
- Stable residual allocation across cycles suggests retention/layout; growing
  allocated bytes/block counts at the same settled checkpoint suggest a leak.
  Neither total free memory nor one successful restart proves long-term safety.

If the named theme allocation is the pin, a candidate correction is to reuse the
existing object when reapplying the same theme, preserving required metrics
invalidation. This is a hypothesis to validate, not a change in this build.

Only after hardware evidence, correct the specific cache lifetime or consider
explicit PSRAM placement for a suitable identified buffer. Keep the current BLE
guards and all pairing/forgetting/mapping behavior unchanged.

## Build verification

`pio run -e x4-pro` succeeded (one full build, one incremental build to include
explicit theme-address logging). Final image: **5,843,728 bytes**, leaving
**709,872 bytes** in the unchanged 6,553,600-byte partition. Increase over V7:
**6,320 bytes**. Static RAM: **115,116 bytes**, unchanged from V7.

Build-identity Python tests: 3 passed. Target-compiler constexpr suites for arrow
filtering, device bindings/persistence, forgetting and memory policy passed,
including the exact V7 fragmented-state refusal and healthy V6 acceptance.
Diagnostics preprocess to no code/state by default. All modified compilation
units built; final ELF contains the diagnostic markers and theme-address log.
The compiled NimBLE malloc/calloc still request `0x404` (SPIRAM | 8BIT).
No CTest/native compiler environment was installed; real reclamation/repaint,
restart, watchdog/serial timing and UI interaction still require hardware.

The archive manifest records checksums, exact local build override, baseline,
checkpoint and modified files. Previous artifacts remain untouched. No hardware
was flashed and no commits were pushed.
