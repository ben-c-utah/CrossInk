#pragma once

#include <AppCapabilities.h>
#if CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <FreeInkApp.h>
#include <FreeInkUIGfxRenderer.h>
#include <HalBlePageTurner.h>

#include "activities/Activity.h"
#include "util/ButtonNavigator.h"
#include "components/OptionPopup.h"

class BleSettingsActivity final : public Activity {
 public:
  BleSettingsActivity(GfxRenderer& renderer, MappedInputManager& mappedInput);
  void onEnter() override;
  void onExit() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  using UiApp = freeink::ui::FreeInkApp<32, 2>;
  freeink::ui::GfxRendererTarget target;
  UiApp app;
  freeink::ui::ListNav listNav;
  ButtonNavigator navigator;
  // Bounded storage lives with this heap-owned screen, not on the render stack.
  freeink::ui::ListItem items[29]{};
  char names[24][32]{};
  char connectedName[32]{};
  uint8_t found = 0;
  int selected = 0;
  bool enabled = false;
  uint8_t failureReasons = HalBlePageTurner::None;
  HalBlePageTurner::Status status = HalBlePageTurner::Status::Off;
  uint32_t passkey = 0;
  bool uiReady = false;
  bool configuring = false;
  bool managing = false;
  bool savedListOk = true;
  uint8_t savedCount = 0;
  HalBlePageTurner::SavedDevice saved[HalBlePageTurner::MaxSavedDevices]{};
  HalBlePageTurner::SavedDevice pendingDevice{};
  OptionPopup confirmation;
  bool confirming = false;
  bool pendingAll = false;
  bool hasForgetResult = false;
  HalBlePageTurner::ForgetResult forgetResult{};
  char resultName[32]{};
  void refreshSaved();
  void confirmForget(bool all);
  void performForget();
  bool nextAssigned = false;
  bool previousAssigned = false;
  BleBindings::Learning learning = BleBindings::Learning::Idle;
  bool connected() const { return status == HalBlePageTurner::Status::Connected; }
  int deviceStart() const { return connected() ? 3 : 2; }
  int rowCount() const { return configuring ? 3 : managing ? (savedCount ? savedCount : 1) : deviceStart() + found + 2; }
  void activate();
  void snapshot();
  static void screen(UiApp::ScreenType& screen, void* user);
  static void rowEvent(const freeink::ui::ActionEvent& event, void* user);
};
#endif
