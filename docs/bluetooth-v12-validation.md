# BLE V12: remaining Settings ownership and PC workflow

This is a candidate fix. V11 hardware proved partial improvement, not completed
Settings recovery. V12 retains SDK 9f660022a0a338253fb964126558084e72a04ae5,
the same board/partitions/security policy, manual Kobo reconnect, and every BLE
memory guard. No updater or EPUB/font implementation changes are included.

## Supported mechanism and bounded fix

Evidence is in `device-monitor-261019-190403.log` and
`device-monitor-261019-194501.log`, under the user's `logs`. The session
`ble-session-20261019-205412-975586/session.json` confirms observed V11 identity
and successful saved Wi-Fi diagnostic downloads; those exports are separate
from the live serial record.

In the controlled sequence, V11 releases menu vectors before entering Bluetooth.
On reentry this recovers the largest block from 47,092 to 73,716. Shutdown returns
164,072 internal bytes, but largest remains 73,716, below the unchanged 79,872
preflight guard. Destroying the Bluetooth child does not recover it. Destroying
the remaining Settings state and returning Home recovers 118,772, without reboot.

The parent Settings object remains live on the activity stack. Its menu release
did not release the global dictionary **catalog**, discovered on Settings entry
and cleared only on Settings exit. This is UI metadata, separate from active
dictionary lookup objects and the persisted dictionary selection. Discovery
reserved 16 entries before checking whether a dictionary root even existed.
The target compiler measures that reservation at 1,152 payload bytes, before
allocator overhead and any strings. A small retained block can split a much
larger free region; the bytes retained do not equal the lost contiguous capacity.
Menus reconstructed when returning from Bluetooth also run while BLE is live,
changing subsequent allocation placement. The parent object and other live
owners cannot be ruled out solely from the V11 summaries.

V12 retains V11's menu release and additionally clears the unused dictionary
catalog before allocating the Bluetooth child, then marks it dirty. Both normal
return and child-allocation failure rebuild through `refreshIfDirty()` before
constructing dictionary rows. The persisted selection is untouched. Missing or
invalid dictionary roots now retain no vector capacity. Valid dictionaries and
all Settings options retain their discovery behavior.

This is a concrete ownership correction with hardware-unverified heap effects.
It is not proof that every remaining splitter was identified. No broad activity
allocator or PSRAM migration is justified yet: the large temporary settings list
already lives in PSRAM in the logs, while the newly identified catalog need not
exist at all during Bluetooth. The parent object remains in its normal heap.
V12 logs the catalog pointer/capacity and parent pointer before release, then a
lightweight after-release summary. No heap walker, block dump, guard reduction,
forced Home route, restart, font clearing or background service is introduced.

## EPUB finding: defer font ownership changes

V11 reader cleanup explicitly releases grayscale/image scratch, SD-font caches,
section/Epub ownership, and registry data. In the second log, cleanup at 611488
raises free internal memory to 105,388 and largest to 55,284. After destruction,
largest stays 55,284. Later BLE shutdown returns 159,568 free but still 55,284
largest. Another reading session shows the same shape.

The named allocation records still show renderer-owned SD font object
`0x3fcd7988` and coverage indexes (`sd.fullIntervals`, actual 1,140 and 916 bytes)
after cache release. `FontCacheManager::releaseSdFontCaches()` calls
`SdCardFont::releaseForLowMemory(false)`, which intentionally retains font objects
and coverage metadata while freeing rebuildable caches. This supports retained
renderer state and placement fragmentation; it does not prove an EPUB ownership
leak or account for every retained byte. Unloading shared fonts needs a separate
audit of renderer/font references, including paused readers and overlays.
Next experiment: fresh boot, same book/font, capture existing named font-owner
summaries before reading, after reader destruction, and after BLE Off; compare a
second pass through the same book before changing font ownership. No speculative
EPUB cleanup is included in V12.

## PC behavior

Stage Latest prints the source image and exact **new-upload SD picker name**
before confirmation, for example `CrossInk-BLE-X4Pro-V12-379f229f.bin`. The suffix
is the first eight SHA-256 characters, not the source commit. Full SHA-256 and
size are still checked locally and through streamed remote read-back. An
identical existing readable or legacy `CrossInk-<12 SHA chars>.bin` file is reused
and its actual existing path reported. A mismatch fails without overwrite or
deletion. Upload collisions are verified without retrying the upload. Installation
remains a separate native device confirmation.

`scripts/collect_logs.py` reuses `ble_lab_pc.collect()` and its existing download
routes. It makes an immutable full byte-for-byte serial copy in the unique
session directory, in addition to the bounded quick snapshot. It reads through
the source size recorded at copy start; the monitor may continue appending.
This is a complete point-in-time prefix, not a claim that an ongoing session has
ended. Explorer selects the full copy, so it is stable to drag into ChatGPT.
The receipt identifies source/session/files, bytes and Wi-Fi outcomes. Partial
failed Wi-Fi downloads are removed from that new session, leaving the serial
capture intact. Saved exports may predate the serial capture. No monitor, port
or terminal is stopped or created.

Without `--url`, collection uses the IP remembered by the last successful stage,
if available, with bounded download timeouts. `--no-wifi` is available for memory
experiments; `--no-reveal` supports headless checks. Explorer-launch failure does
not invalidate the saved capture. The local, Git-ignored VS Code configuration
changes only Collect Logs' command to the installed Python executable plus
`scripts/collect_logs.py`; terminal name, layout, other buttons and colors remain.
The now-tracked staging helpers/tests preserve the previously local duplicate-
upload fix as part of this requested PC workflow work.

## Ordered physical validation

Do not open Wi-Fi or export diagnostics until controlled memory experiments
finish. Keep live serial capture running. No EPUB cache reset is needed.

1. Confirm `v12-dev` and manifest SHA identity; check normal Home/Settings UI.
2. Fresh boot, no Kobo/book: Home BLE On → Off → On; record free/largest.
3. Fresh boot, no Kobo/book: Settings → Bluetooth On → Home → Settings →
   Bluetooth Off → wait → On. Capture the named parent/catalog owners and
   `Settings catalog released before Bluetooth child`. Second startup must pass
   131,072 free / 79,872 largest, followed by 65,536 / 32,768 post-start guards.
   Repeat with installed dictionaries if present; verify selection/options on
   Back. If still refused, retain the log and compare catalog release versus
   full parent exit; investigate the remaining named parent/UI owners next.
4. Reuse the existing Kobo bond/designation; software restart, enable Bluetooth,
   reconnect once using Home Kobo. No re-pairing or automatic retry loop.
5. Turn EPUB pages using 0x51 Next / 0x52 Previous, then leave the book and record
   reader cleanup, Home and BLE-Off summaries. Treat the retained-font finding
   separately from the Settings result.
6. Check Update picker/cancel, Restart/cancel, Logs snapshot and native File
   Transfer exit/restart. Stage/read back V12 twice: readable filename on first
   upload, already-verified result on second; retain legacy files. Collect Logs
   should select the full serial attachment and show Wi-Fi success/failure.

Only hardware results can establish whether Settings recovery is complete.
