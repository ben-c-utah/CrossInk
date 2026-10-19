#include <AppVersion.h>
#include <BleLabConfig.h>
#define BLE_STRING_INNER(x) #x
#define BLE_STRING(x) BLE_STRING_INNER(x)

// Only this translation unit receives the changing version and Git defines.
#ifndef CROSSINK_VERSION
#define CROSSINK_VERSION "dev"
#endif

#ifndef CROSSINK_GIT_SHA
#define CROSSINK_GIT_SHA "unknown"
#endif

#ifndef CROSSINK_GIT_DIRTY
#define CROSSINK_GIT_DIRTY "unknown"
#endif

namespace AppVersion {
const char* version() { return CROSSINK_VERSION; }
const char* versionLabel() {
#if CROSSINK_BLE_LAB
  return CROSSINK_GIT_DIRTY[0] == '0'
      ? "CrossInk BLE \xC2\xB7 v" BLE_STRING(CROSSINK_BLE_LAB_VERSION) "-dev " CROSSINK_GIT_SHA
      : "CrossInk BLE \xC2\xB7 v" BLE_STRING(CROSSINK_BLE_LAB_VERSION) "-dev " CROSSINK_GIT_SHA "*";
#else
  return "CrossInk " CROSSINK_VERSION;
#endif
}
const char* userAgent() { return "CrossInk-ESP32-" CROSSINK_VERSION; }
const char* gitSha() { return CROSSINK_GIT_SHA; }
const char* gitDirtyFlag() { return CROSSINK_GIT_DIRTY; }
}  // namespace AppVersion
