#include "BleSettingsActivity.h"

#if CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <I18n.h>

#include <cstdio>
#include <cstring>

#include "components/TouchHeaderBackButton.h"
#include "components/UITheme.h"
#include "components/UiAppHelpers.h"

namespace fui = freeink::ui;

BleSettingsActivity::BleSettingsActivity(GfxRenderer& renderer, MappedInputManager& mappedInput)
    : Activity("BleSettings", renderer, mappedInput), target(makeUiTarget(renderer)),
      app(target, target.deviceContext()) {}

void BleSettingsActivity::onEnter() {
  Activity::onEnter();
  applySharedUiTheme(app, target);
  app.on(1, rowEvent, this);
  app.setScreen(screen, this);
  snapshot();
  requestUpdate();
}

void BleSettingsActivity::snapshot() {
  status = blePageTurner.status();
  enabled = blePageTurner.enabled();
  passkey = blePageTurner.passkey();
  found = blePageTurner.deviceCount();
  for (uint8_t i = 0; i < found; ++i) std::memcpy(names[i], blePageTurner.device(i).name, sizeof(names[i]));
  if (selected >= 3 + found) selected = 0;
}

void BleSettingsActivity::activate() {
  app.clearTapFlash();
  if (selected == 0) {
    if (blePageTurner.resident()) blePageTurner.stop();
    else blePageTurner.enable();
  } else if (selected == 1) {
    blePageTurner.scan();
  } else if (selected == 2) {
    blePageTurner.forget();
  } else {
    blePageTurner.connect(static_cast<uint8_t>(selected - 3));
  }
  snapshot();
  requestUpdate();
}

void BleSettingsActivity::rowEvent(const fui::ActionEvent& event, void* user) {
  auto& self = *static_cast<BleSettingsActivity*>(user);
  if (event.value < 0 || event.value >= 3 + self.found) return;
  self.selected = event.value;
  self.activate();
}

void BleSettingsActivity::loop() {
  // Rendering reads only this screen's snapshot. Never race app.route()/render().
  RenderLock lock(*this, RenderLock::Mode::Try);
  if (!lock.ownsLock()) return;
  if (status != blePageTurner.status() || found != blePageTurner.deviceCount() ||
      enabled != blePageTurner.enabled() || passkey != blePageTurner.passkey()) {
    snapshot();
    requestUpdate();
  }
  if (TouchHeaderBackButton::wasTapped(mappedInput, renderer) ||
      mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    finish();
    return;
  }
  if (uiReady) {
    const auto snap = touchSnapshotFrom(mappedInput);
    if (snap.touchPressed || snap.touchReleased) {
      const auto event = app.route(snap);
      if (app.invalidated()) requestUpdate();
      if (event) return;
    }
  }
  if (mappedInput.wasReleased(MappedInputManager::Button::Confirm)) {
    activate();
    return;
  }
  navigator.onNext([this] {
    selected = (selected + 1) % (3 + found);
    requestUpdate();
  });
  navigator.onPrevious([this] {
    selected = (selected + 2 + found) % (3 + found);
    requestUpdate();
  });
}

void BleSettingsActivity::screen(UiApp::ScreenType& screen, void* user) {
  auto& self = *static_cast<BleSettingsActivity*>(user);
  const auto& metrics = UITheme::getInstance().getMetrics();
  screen.setContentMargin(fui::Insets{
      static_cast<int16_t>(metrics.topPadding + TouchHeaderBackButton::height(metrics, self.mappedInput)), 0,
      static_cast<int16_t>(metrics.buttonHintsHeight), 0});
  const StrId statusText[] = {StrId::STR_DISABLED, StrId::STR_BLE_READY, StrId::STR_BLE_SCANNING,
                             StrId::STR_CONNECTING, StrId::STR_CONNECTED, StrId::STR_BLE_STOPPING,
                             StrId::STR_CONNECTION_FAILED, StrId::STR_BLE_LOW_MEMORY};
  char hint[96];
  if (self.passkey) {
    std::snprintf(hint, sizeof(hint), tr(STR_BLE_PASSKEY), static_cast<unsigned long>(self.passkey));
  } else {
    std::snprintf(hint, sizeof(hint), "%s", I18N.get(statusText[static_cast<unsigned>(self.status)]));
  }
  screen.target().text(screen.takeTop(static_cast<int16_t>(metrics.tabBarHeight)), hint, screen.theme().smallText);
  screen.target().text(screen.takeTop(static_cast<int16_t>(metrics.tabBarHeight)), tr(STR_BLE_SESSION_HINT),
                       screen.theme().smallText);
  self.items[0].label = tr(STR_BLE_ENABLE);
  self.items[0].value = self.enabled ? tr(STR_ENABLED) : tr(STR_DISABLED);
  self.items[1].label = tr(STR_BLE_SCAN);
  self.items[2].label = tr(STR_BLE_FORGET);
  for (int i = 0; i < 3 + self.found; ++i) {
    if (i >= 3) self.items[i].label = self.names[i - 3];
    self.items[i].actionValue = static_cast<int16_t>(i);
  }
  fui::ListProps props;
  props.items = self.items;
  props.count = 3 + self.found;
  props.selectedIndex = self.selected;
  props.action = 1;
  props.inputMask = fui::InputTouch;
  self.rows = configureUiList(props, screen.theme(), screen.body());
  if (self.rows < 1) self.rows = 1;
  if (self.selected < self.top) self.top = self.selected;
  if (self.selected >= self.top + self.rows) self.top = self.selected - self.rows + 1;
  self.top = scrollListBy(self.top, 0, self.rows, props.count);
  props.topIndex = self.top;
  screen.list(props);
}

void BleSettingsActivity::render(RenderLock&&) {
  renderer.clearScreen();
  const Rect header = TouchHeaderBackButton::headerRect(renderer, mappedInput);
  TouchHeaderBackButton::draw(renderer, target, header, tr(STR_BLE_PAGE_TURNER), false);
  uiReady = false;
  app.render();
  uiReady = true;
  const auto labels = mappedInput.mapLabels(mappedInput.withBackArrow(tr(STR_BACK)), tr(STR_SELECT), tr(STR_DIR_UP),
                                           tr(STR_DIR_DOWN));
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
  renderer.displayBuffer();
}
#endif
