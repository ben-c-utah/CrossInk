# V16: controlled Home controller placement experiment

Baseline: V15 `51e21a7eb6e17c523d717354b92b442f451ef49a`.
SDK remains `9f660022a0a338253fb964126558084e72a04ae5`.
This is an experimental candidate, not a demonstrated fragmentation fix.

## Controlled change

Only the physical X4 Pro Bluetooth Lab root Settings return opts into external
storage for the Home controller. Selection requires the existing retained Home
return context, a current activity named Settings, and an empty parent stack.
Boot Home, unrelated navigation and frontlight-panel Home replacement continue
using their original global allocation paths. There is no new per-object field.

Home remains constructed before Settings cleanup. Generic replacement processing,
render locking, onExit/destruction/onEnter ordering and path move semantics on
success are unchanged. Recent-book vectors, strings, cover buffers and renderer
allocations keep their existing allocation policies. V15 theme reuse remains.

The factory requests `sizeof(HomeActivity)` bytes with `alignof(HomeActivity)`
alignment and `MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT`. It checks the allocation
before evaluating the moving constructor argument. RAII owns raw storage until
placement construction completes, then unique_ptr owns the constructed object.
Virtual destruction selects Home's matching class delete. On ESP32, both the
original global-new/malloc storage and capability storage use heap_caps_free;
native builds retain global delete. No live object is relocated or copied.

Allocation failure queues nothing, preserves Settings, restores the moved path
and Home-return flag, logs the failure and permits retry. No internal fallback.
An initial tagged-new implementation failed the injected native OOM/path test;
the explicit allocation-before-construction factory corrects that ordering.
The failed implementation was never built as firmware.

## Source and native validation

Retain all 67 distinct V15 PC/native tests, all 12 production syntax targets and
all six BLE compile-time checks. Add ten V16 tests, including execution of the
actual allocator/factory, goHome, replaceActivity, exitActivity and replacement
processing source against native stand-ins. Exercise physical-target, non-Lab,
non-PSRAM and simulator branches; forced allocation failure; unchanged boot and
other routes; alignment; polymorphic destruction; selected path backing storage;
selection/refresh restoration; and repeated transitions.

Historical whole-source preservation checks reverse only the exact V16 delta
before comparing against their prior checkpoints. They still reject unrelated
changes. Keep all V14 diagnostic regions, no additional object fields, and exact
BLE policy source. Native models do not establish ESP32 allocation placement or
hardware rendering correctness.

## First physical test: clean Test E

Do not install automatically. After owner-authorized installation:

1. Start continuous serial capture. Software restart and confirm
   `CrossInk BLE · v16-dev <candidate commit>`.
2. Verify Boot goes directly to Home with no Reader/EpubReader activity or SD
   fonts. If necessary, use ordinary Sleep from Home, wake, then Bluetooth Lab
   Restart. Do not manually edit state.json, NVS, progress or books.
3. Home -> Settings -> System -> Bluetooth. Turn On; wait about 30 seconds.
4. Back to System, Back to category bar, Back to Home. Keep Bluetooth on.
5. Home Bluetooth Lab -> Off. Wait 30 seconds.
6. Home Bluetooth Lab -> On. Wait 30 seconds.
7. Collect the complete device-monitor log before another restart. Do not use
   Wi-Fi or SD diagnostic export before completing the memory sequence.

Check boot Home external=0; targeted replacement Home external=1; unchanged
theme pointer; retained long path buffer; and all existing lifecycle boundaries.

| V15 boundary | Free internal | Largest internal |
| --- | ---: | ---: |
| First BLE preflight | 167700 | 118772 |
| BLE running | 121156 | 77812 |
| Settings reconstructed | 97292 | 51188 |
| Settings cleaned, before Home metadata | 119872 | 73716 |
| BLE stopped on Home | 165500 | 73716 |

Before the selected return, V16 should closely match V15. A changed initial
baseline makes a direct comparison questionable. After cleanup, removal of the
one Home block should reduce internal allocation by about 1268 allocator bytes
(1284 total free bytes including overhead), but largest-block recovery is the
measurement of interest. Subsequent metadata addresses may change as a result.

Full recovery near 118772 and successful restart supports this intervention,
without proving physical adjacency or sole causation. Unchanged 73716 with an
external Home shows the object-only change is insufficient. Recovery only to
77812 still fails the 79872 guard; a marginal passing value is not acceptance.
Compare the pre-metadata boundary with the post-metadata and shutdown boundaries
before considering a separate metadata experiment. Never move both owners in
this candidate or weaken guards.

## Later acceptance, only after the initial evidence is reviewed

Require repeatable recovery with no progressive deterioration during Home-only
cycling, Settings navigation and ordinary reading histories. Verify selected
book and cover rendering; touchscreen/buttons; Kobo designation, secure manual
reconnect and 0x51/0x52 page turns; restart/cancel; logs; Wi-Fi transfer; native
updater selection/cancel; and file browsing. No automatic reconnect or Wi-Fi/BLE
concurrency is introduced.

Unchanged guards (free/largest): startup 131072/79872; post-start 65536/32768;
runtime 49152/24576. PSRAM and Wi-Fi restrictions remain unchanged. The archive
manifest records the actual build identity, SHA-256, partition headroom,
validation outcomes and warnings. No hardware success is claimed by this file.
