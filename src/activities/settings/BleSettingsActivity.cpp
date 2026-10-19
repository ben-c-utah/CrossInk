#include "BleSettingsActivity.h"

#if CROSSINK_APP_CAP_BLE_PAGE_TURNER
#include <I18n.h>
#include <FontCacheManager.h>
#include <FontDecompressor.h>

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
  listNav.reset(selected);
  requestUpdate();
}

void BleSettingsActivity::snapshot() {
  status = blePageTurner.status();
  enabled = blePageTurner.enabled();
  failureReasons = blePageTurner.failure();
  learning = blePageTurner.learning();
  nextAssigned = blePageTurner.hasBinding(BleBindings::Action::Next);
  previousAssigned = blePageTurner.hasBinding(BleBindings::Action::Previous);
  passkey = blePageTurner.passkey();
  found = blePageTurner.deviceCount();
  std::snprintf(connectedName, sizeof(connectedName), "%s", blePageTurner.connectedName());
  for (uint8_t i = 0; i < found; ++i) std::memcpy(names[i], blePageTurner.device(i).name, sizeof(names[i]));
  if (managing) for (uint8_t i = 0; i < savedCount; ++i)
    std::snprintf(names[i], sizeof(names[i]), "%s / %u", saved[i].addr, saved[i].addrType);
  if (selected >= rowCount()) selected = 0;
}

void BleSettingsActivity::onExit() {
  blePageTurner.cancelLearning();
  Activity::onExit();
}

void BleSettingsActivity::refreshSaved() {
  savedCount = 0;
  savedListOk = blePageTurner.listSaved(saved, HalBlePageTurner::MaxSavedDevices, savedCount);
  if (!savedListOk) savedCount = 0;
  if (selected >= rowCount()) selected = 0;
  for (uint8_t i = 0; i < savedCount; ++i)
    std::snprintf(names[i], sizeof(names[i]), "%s / %u", saved[i].addr, saved[i].addrType);
  listNav.reset(selected);
}

void BleSettingsActivity::confirmForget(bool all) {
  pendingAll = all;
  hasForgetResult = false;
  char title[192];
  if (all) std::snprintf(title, sizeof(title), "%s", tr(STR_BLE_FORGET_ALL_PROMPT));
  else {
    pendingDevice = saved[selected]; // Copy address/type, never delete by a later list index.
    std::snprintf(title, sizeof(title), tr(STR_BLE_FORGET_ONE_PROMPT),
                  pendingDevice.name[0] ? pendingDevice.name : pendingDevice.addr, pendingDevice.addr, pendingDevice.addrType);
  }
  const char* options[] = {tr(STR_CANCEL), all ? tr(STR_BLE_FORGET_ALL_BUTTON) : tr(STR_BLE_FORGET_BUTTON)};
  confirmation.show(title, options, 2, 0, [this](int index) {
    confirming = false;
    if (index == 1) performForget();
    requestUpdate();
  });
  confirmation.setPrimaryOptionIndex(1);
  confirming = true;
}

void BleSettingsActivity::performForget() {
  std::snprintf(resultName, sizeof(resultName), "%s", pendingDevice.name[0] ? pendingDevice.name : pendingDevice.addr);
  forgetResult = pendingAll ? blePageTurner.forgetAll() : blePageTurner.forget(pendingDevice);
  hasForgetResult = true; // Kept until the user's next relevant action, not a timer.
  snapshot();
  if (managing) refreshSaved();
}

#if CROSSINK_HEAP_DIAGNOSTICS
void BleSettingsActivity::reclaimDiagnosticCaches() {
  // activate() runs under loop's RenderLock; also reject a paused reader on the stack.
  auto* cache = renderer.getFontCacheManager();
  if (blePageTurner.resident() || !activityManager.diagnosticCanReclaimFonts() || !cache || cache->isScanning()) {
    LOG_ERR("HDBG", "Cache experiment refused: BLE must be fully Off, no retained reader, font scan inactive");
    return;
  }
  HeapDiagnostics::snapshot("reclaim before", "", true);
  renderer.logHeapAllocations();
  cache->logAllocations();
  if (auto* decompressor = cache->getDecompressor()) decompressor->clearCache();
  HeapDiagnostics::snapshot("reclaim after built-in fonts");
  cache->releaseSdFontCaches();
  HeapDiagnostics::snapshot("reclaim after all fonts BEFORE repaint", "", true);
  cache->logAllocations();
  diagnosticRepaint = true;
  // No radio start, settings writes, font unload or framebuffer changes here.
}
#endif

void BleSettingsActivity::activate() {
  app.clearTapFlash();
  if (managing) {
    if (savedListOk && savedCount) confirmForget(false);
    requestUpdate();
    return;
  }
  hasForgetResult = false;
  if (configuring) {
    if (learning == BleBindings::Learning::Waiting) return;
    if (selected < 2) blePageTurner.beginLearning(static_cast<BleBindings::Action>(selected));
    else blePageTurner.resetButtons();
  } else if (selected == 0) {
    if (blePageTurner.resident()) blePageTurner.stop();
    else blePageTurner.enable();
  } else if (selected == 1) {
    blePageTurner.scan();
  } else if (connected() && selected == 2) {
    configuring = true;
    selected = 0;
    listNav.reset();
    blePageTurner.cancelLearning();
  } else if (selected == deviceStart() + found) {
    managing = true;
    selected = 0;
    refreshSaved();
#if CROSSINK_HEAP_DIAGNOSTICS
  } else if (selected == deviceStart() + found + 2) {
    reclaimDiagnosticCaches();
#endif
  } else if (selected == deviceStart() + found + 1) {
    confirmForget(true);
  } else {
    blePageTurner.connect(static_cast<uint8_t>(selected - deviceStart()));
  }
  snapshot();
  requestUpdate();
}

void BleSettingsActivity::rowEvent(const fui::ActionEvent& event, void* user) {
  auto& self = *static_cast<BleSettingsActivity*>(user);
  if (event.value < 0 || event.value >= self.rowCount()) return;
  self.selected = event.value;
  self.activate();
}

void BleSettingsActivity::loop() {
  // Rendering reads only this screen's snapshot. Never race app.route()/render().
  RenderLock lock(*this, RenderLock::Mode::Try);
  if (!lock.ownsLock()) return;
  if (confirming) {
    if (confirmation.handleInput(mappedInput, [this] { requestUpdate(); })) return;
    confirming = false; // Back/outside dismissal never executes deletion.
    requestUpdate();
    return;
  }
  if (status != blePageTurner.status() || found != blePageTurner.deviceCount() ||
      enabled != blePageTurner.enabled() || passkey != blePageTurner.passkey() ||
      failureReasons != blePageTurner.failure() || learning != blePageTurner.learning()) {
    snapshot();
    requestUpdate();
  }
  if (TouchHeaderBackButton::wasTapped(mappedInput, renderer) ||
      mappedInput.wasReleased(MappedInputManager::Button::Back)) {
    if (managing) {
      managing = false;
      snapshot();
      selected = deviceStart() + found;
      listNav.reset(selected);
      requestUpdate();
    } else if (configuring) {
      if (learning != BleBindings::Learning::Waiting) {
        configuring = false;
        selected = connected() ? 2 : 0;
        listNav.reset(selected);
      }
      blePageTurner.cancelLearning();
      snapshot();
      requestUpdate();
    } else finish();
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
  if (configuring && learning == BleBindings::Learning::Waiting) return;
  navigator.onNext([this] {
    selected = (selected + 1) % rowCount();
    requestUpdate();
  });
  navigator.onPrevious([this] {
    selected = (selected + rowCount() - 1) % rowCount();
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
                             StrId::STR_BLE_INIT_FAILED, StrId::STR_BLE_LOW_MEMORY};
  char hint[96];
  if (self.passkey) {
    std::snprintf(hint, sizeof(hint), tr(STR_BLE_PASSKEY), static_cast<unsigned long>(self.passkey));
  } else {
    std::snprintf(hint, sizeof(hint), "%s", I18N.get(statusText[static_cast<unsigned>(self.status)]));
  }
  // Use the SDK's wrapped text layout and measured height, rather than a
  // fixed single-line band. Each independent refusal remains readable.
  const auto message = [&](const char* text) {
    auto style = screen.theme().smallText;
    style.maxLines = 8;
    const auto size = fui::measureWrappedText(screen.target(), text, style, screen.body().width);
    screen.target().text(screen.takeTop(size.height), text, style);
  };
  if (self.hasForgetResult) {
    using Code = freeink::bleforget::Code;
    char result[128];
    const bool all = self.pendingAll;
    const auto code = self.forgetResult.code;
    if (code == Code::Done || code == Code::Absent) {
      if (all) {
        message(code == Code::Done ? tr(STR_BLE_ALL_FORGOTTEN) : tr(STR_BLE_NONE_SAVED));
        message(tr(STR_BLE_ALL_RADIO_OFF));
      }
      else {
        std::snprintf(result, sizeof(result), code == Code::Done ? tr(STR_BLE_DEVICE_FORGOTTEN) : tr(STR_BLE_ALREADY_FORGOTTEN), self.resultName);
        message(result);
      }
    } else {
      if (all) message(tr(STR_BLE_FORGET_ALL_FAILED));
      else { std::snprintf(result, sizeof(result), tr(STR_BLE_FORGET_FAILED), self.resultName); message(result); }
      switch (code) {
        case Code::Busy: message(tr(STR_BLE_FORGET_BUSY)); break;
        case Code::RadioOff: message(tr(STR_BLE_FORGET_RADIO_OFF)); break;
        case Code::Identity: message(tr(STR_BLE_FORGET_IDENTITY)); break;
        case Code::Credentials: message(tr(STR_BLE_FORGET_SECURITY_ERROR)); break;
        case Code::Metadata: message(tr(STR_BLE_FORGET_METADATA_ERROR)); break;
        case Code::Mappings: message(tr(STR_BLE_FORGET_MAPPING_ERROR)); break;
        default: break;
      }
    }
  } else if (self.failureReasons) {
    if (self.failureReasons & HalBlePageTurner::Memory) message(tr(STR_BLE_LOW_MEMORY));
    if (self.failureReasons & HalBlePageTurner::Wifi) message(tr(STR_BLE_WIFI_ACTIVE));
    if (self.failureReasons & HalBlePageTurner::Initialization) message(tr(STR_BLE_INIT_FAILED));
    if (self.failureReasons & HalBlePageTurner::Connection) message(tr(STR_BLE_CONNECT_FAILED));
    if (self.failureReasons & HalBlePageTurner::ButtonStorage) message(tr(STR_BLE_BINDINGS_STORAGE_ERROR));
  } else {
    message(hint);
    if (self.status == HalBlePageTurner::Status::Connected) message(self.connectedName);
  }
  if (self.configuring) {
    const StrId notes[] = {StrId::STR_BLE_LEARN_READY, StrId::STR_BLE_LEARN_PROMPT, StrId::STR_BLE_LEARN_PROMPT,
                           StrId::STR_BLE_BINDINGS_SAVED, StrId::STR_BLE_BINDING_DUPLICATE, StrId::STR_BLE_LEARN_TIMEOUT,
                           StrId::STR_BLE_DEVICE_GONE, StrId::STR_BLE_BINDINGS_STORAGE_ERROR, StrId::STR_BLE_BINDINGS_FULL};
    message(self.connected() ? I18N.get(notes[static_cast<unsigned>(self.learning)]) : tr(STR_BLE_DEVICE_GONE));
  } else if (self.managing) {
    message(self.savedListOk ? tr(STR_BLE_SELECT_FORGET) : tr(STR_BLE_SAVED_READ_ERROR));
    if (!self.enabled) message(tr(STR_BLE_FORGET_RADIO_OFF));
  } else message(tr(STR_BLE_SESSION_HINT));
  for (int i = 0; i < self.rowCount(); ++i) self.items[i] = {};
  if (self.configuring) {
    self.items[0].label = tr(STR_NEXT_PAGE);
    self.items[1].label = tr(STR_PREV_PAGE);
    self.items[0].value = self.nextAssigned ? tr(STR_BLE_ASSIGNED) : tr(STR_NOT_SET);
    self.items[1].value = self.previousAssigned ? tr(STR_BLE_ASSIGNED) : tr(STR_NOT_SET);
    self.items[2].label = tr(STR_BLE_RESET_BUTTONS);
    for (int i = 0; i < 3; ++i) self.items[i].enabled = self.connected() && self.learning != BleBindings::Learning::Waiting;
  } else if (self.managing) {
    if (!self.savedCount) {
      // With the radio Off, hidden security-only records may still exist.
      // Do not confuse an unavailable inventory with a verified empty store.
      self.items[0].label = !self.savedListOk ? tr(STR_BLE_SAVED_READ_ERROR)
                                           : self.enabled ? tr(STR_BLE_NONE_SAVED) : tr(STR_DISABLED);
      self.items[0].enabled = false;
    }
    for (uint8_t i = 0; i < self.savedCount; ++i) {
      self.items[i].label = self.saved[i].name[0] ? self.saved[i].name : self.saved[i].addr;
      self.items[i].subtitle = self.names[i];
    }
  } else {
    self.items[0].label = tr(STR_BLE_ENABLE);
    self.items[0].toggle = true;
    self.items[0].toggleChecked = self.enabled;
    self.items[1].label = tr(STR_BLE_SCAN);
    if (self.connected()) self.items[2].label = tr(STR_BLE_CONFIGURE_BUTTONS);
    const int first = self.deviceStart();
    self.items[first + self.found].label = tr(STR_BLE_FORGET);
    self.items[first + self.found + 1].label = tr(STR_BLE_FORGET_ALL);
#if CROSSINK_HEAP_DIAGNOSTICS
    self.items[first + self.found + 2].label = tr(STR_BLE_DIAGNOSTIC_RECLAIM);
    self.items[first + self.found + 2].enabled = !blePageTurner.resident() && activityManager.diagnosticCanReclaimFonts();
#endif
    self.items[first + self.found].sectionHeading = tr(STR_BLE_DEVICE_ACTIONS);
    if (self.found) self.items[first].sectionHeading = tr(STR_BLE_DISCOVERED_DEVICES);
    for (int i = 0; i < self.found; ++i) self.items[first + i].label = self.names[i];
  }
  for (int i = 0; i < self.rowCount(); ++i) {
    self.items[i].actionValue = static_cast<int16_t>(i);
  }
  fui::ListProps props;
  props.items = self.items;
  props.count = self.rowCount();
  props.selectedIndex = self.selected;
  props.action = 1;
  props.inputMask = fui::InputTouch;
  props.valueInset = 8;
  props.labelText = screen.theme().bodyText;
  props.labelText.maxLines = 2;
  props.headerText = screen.theme().smallText;
  props.headerText.bold = true;
  configureUiList(props, screen.theme(), screen.body());
  if (self.listNav.selected.exchange(self.selected) != self.selected) self.listNav.followOnBuild.store(true);
  self.listNav.syncToProps(screen.body(), props.rowHeight, props.rowGap, props.count, props);
  screen.list(props);
}

void BleSettingsActivity::render(RenderLock&&) {
  if (confirming && confirmation.processRender(renderer, mappedInput)) return;
  uiReady = false;
  // Native viewport feedback accounts for wrapped rows and section headings.
  // A corrective layout pass happens in RAM, before the single e-ink refresh.
  for (int pass = 0; pass < 2; ++pass) {
    renderer.clearScreen();
    const Rect header = TouchHeaderBackButton::headerRect(renderer, mappedInput);
    TouchHeaderBackButton::draw(renderer, target, header,
                               configuring ? tr(STR_BLE_CONFIGURE_BUTTONS) : managing ? tr(STR_BLE_FORGET) : tr(STR_BLE_PAGE_TURNER), false);
    app.render();
    if (!listNav.consumeRebuildNeeded()) break;
  }
  uiReady = true;
  const auto labels = mappedInput.mapLabels(mappedInput.withBackArrow(tr(STR_BACK)), tr(STR_SELECT), tr(STR_DIR_UP),
                                           tr(STR_DIR_DOWN));
  GUI.drawButtonHints(renderer, labels.btn1, labels.btn2, labels.btn3, labels.btn4);
#if CROSSINK_HEAP_DIAGNOSTICS
  if (diagnosticRepaint) {
    HeapDiagnostics::snapshot("reclaim after normal repaint", "", true);
    if (auto* cache = renderer.getFontCacheManager()) cache->logAllocations();
    diagnosticRepaint = false;
  }
#endif
  renderer.displayBuffer();
}
#endif
