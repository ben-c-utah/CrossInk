#pragma once
#include <BleLabConfig.h>
#if CROSSINK_BLE_LAB
#include <BleLabPolicy.h>
#include <I18n.h>

class BleLab {
 public:
  enum class Radio : uint8_t { Off, Starting, On, Stopping, Error };
  enum class Link : uint8_t { NotSelected, Disconnected, Connecting, Connected, Other };
  struct View {
    Radio radio = Radio::Off;
    Link link = Link::NotSelected;
    StrId result = StrId::STR_NONE_OPT;
    uint32_t free = 0, largest = 0, revision = 0;
    bool busy = false, restarting = false, wifi = false, enabled = false;
  };
  void enterHome();
  bool request(BleLabPolicy::Command command);
  void tick(); // main loop only, outside Activity::loop and RenderLock
  View view() const;
  bool selectConnected();
  bool clearSelection(bool all, const char* address, uint8_t type);
  bool restarting() const { return BleLabPolicy::restarting(phase) || pending == BleLabPolicy::Command::Restart; }
 private:
  BleLabPolicy::Selection selection{};
  bool loaded = false, selected = false;
  BleLabPolicy::Command pending = BleLabPolicy::Command::None;
  BleLabPolicy::Phase phase = BleLabPolicy::Phase::Idle;
  StrId result = StrId::STR_NONE_OPT;
  uint32_t since = 0, free = 0, largest = 0, revision = 0;
  bool connectAfterEnable = false;
  int previousStatus = -1;
  BleLabPolicy::Command toolAction = BleLabPolicy::Command::None;
  struct Event { uint32_t at, free, largest, psram; uint8_t phase, status; };
  Event events[8]{}; // 160 bytes, fixed; no allocation/logging hook or background writer
  uint8_t eventHead = 0, eventCount = 0;
  bool exportDiagnostics();
  bool load();
  void sample();
  void finish(StrId message);
};
extern BleLab bleLab;
#endif
