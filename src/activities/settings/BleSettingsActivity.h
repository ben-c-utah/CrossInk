#pragma once

#include <AppCapabilities.h>
#if CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <FreeInkApp.h>
#include <FreeInkUIGfxRenderer.h>
#include <HalBlePageTurner.h>

#include "activities/Activity.h"
#include "util/ButtonNavigator.h"

class BleSettingsActivity final : public Activity {
 public:
  BleSettingsActivity(GfxRenderer& renderer, MappedInputManager& mappedInput);
  void onEnter() override;
  void loop() override;
  void render(RenderLock&&) override;

 private:
  using UiApp = freeink::ui::FreeInkApp<32, 2>;
  freeink::ui::GfxRendererTarget target;
  UiApp app;
  ButtonNavigator navigator;
  // Bounded storage lives with this heap-owned screen, not on the render stack.
  freeink::ui::ListItem items[27]{};
  char names[24][32]{};
  uint8_t found = 0;
  int selected = 0;
  int top = 0;
  int rows = 1;
  bool enabled = false;
  HalBlePageTurner::Status status = HalBlePageTurner::Status::Off;
  uint32_t passkey = 0;
  bool uiReady = false;
  void activate();
  void snapshot();
  static void screen(UiApp::ScreenType& screen, void* user);
  static void rowEvent(const freeink::ui::ActionEvent& event, void* user);
};
#endif
