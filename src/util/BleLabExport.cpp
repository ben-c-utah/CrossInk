#include "BleLab.h"
#if CROSSINK_BLE_LAB
#include <AppVersion.h>
#include <HalStorage.h>
#include <Logging.h>
#include <cstring>
#include <cstdio>
#include <algorithm>

// Called once on user request, radio Off, renderer parked, no RenderLock held.
// Eight fixed main-loop snapshots, not a capture of all USB/NimBLE serial output.
bool BleLab::exportDiagnostics() {
  constexpr const char* crash = "/ble-lab-crash.txt";
  constexpr const char* output = "/ble-lab-diagnostics.txt";
  char buffer[192]; // shared bounded streaming/format scratch
  bool crashPresent = Storage.exists("/crash_report.txt");
  bool truncated = false;
  if (crashPresent) {
    HalFile input, copy;
    if (!Storage.openFileForRead("BLELAB", "/crash_report.txt", input)) return false;
    if (!Storage.openFileForWrite("BLELAB", "/ble-lab-crash.tmp", copy)) { input.close(); return false; }
    const size_t bytes = std::min<size_t>(8192, input.fileSize());
    truncated = input.fileSize() > bytes;
    bool ok = true;
    for (size_t offset = 0; offset < bytes;) {
      const size_t want = std::min(sizeof(buffer), bytes - offset);
      const int n = input.read(buffer, want);
      if (n != int(want) || copy.write(buffer, want) != want) { ok = false; break; }
      offset += want;
    }
    ok = copy.sync() && ok;
    ok = copy.close() && ok;
    ok = input.close() && ok;
    if (!ok || (Storage.exists(crash) && !Storage.remove(crash)) || !Storage.rename("/ble-lab-crash.tmp", crash)) return false;
  } else if (Storage.exists(crash) && !Storage.remove(crash)) return false;
  HalFile file;
  if (!Storage.openFileForWrite("BLELAB", "/ble-lab-diagnostics.tmp", file)) return false;
  bool ok = true;
  const auto line = [&](const char* text) { if (file.write(text, std::strlen(text)) != std::strlen(text)) ok = false; };
  std::snprintf(buffer, sizeof(buffer), "identity=%s\nbase=%s\n", AppVersion::versionLabel(), AppVersion::version());
  line(buffer);
  line("Bounded Lab main-loop snapshots; NOT complete USB serial logs. PC helper captures full logs.\n");
  std::snprintf(buffer, sizeof(buffer), "crash_present=%u crash_copy_truncated=%u cap=8192\n", crashPresent, truncated);
  line(buffer);
  line("ms,free_internal,largest_internal,free_psram,phase,ble_status\n");
  for (uint8_t i = 0; i < eventCount; ++i) {
    const auto& e = events[(eventHead + 8 - eventCount + i) % 8];
    std::snprintf(buffer, sizeof(buffer), "%lu,%lu,%lu,%lu,%u,%u\n", (unsigned long)e.at,
                  (unsigned long)e.free, (unsigned long)e.largest, (unsigned long)e.psram, e.phase, e.status);
    line(buffer);
  }
  ok = file.sync() && ok;
  ok = file.close() && ok;
  if (!ok || (Storage.exists(output) && !Storage.remove(output)) || !Storage.rename("/ble-lab-diagnostics.tmp", output)) {
    LOG_ERR("BLELAB", "Diagnostic export failed; previous files may be incomplete/stale");
    return false;
  }
  LOG_INF("BLELAB", "Exported %s (crash present=%u truncated=%u); retrieve in File Transfer", output, crashPresent, truncated);
  return true;
}
#endif
