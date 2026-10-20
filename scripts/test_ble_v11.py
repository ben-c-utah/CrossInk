"""V11 ownership/dispatch contracts and executable menu-destruction test."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding='utf-8')


class V11Test(unittest.TestCase):
    def test_every_owned_settings_list_is_released_including_nested_storage(self):
        header = source('src/activities/settings/SettingsActivity.h')
        implementation = source('src/activities/settings/SettingsActivity.cpp')
        names = re.findall(r'  std::vector<SettingInfo> (\w+);', header)
        body = implementation.split('void SettingsActivity::releaseSettingsLists() {', 1)[1].split('\n}', 1)[0]
        self.assertEqual(set(names), set(re.findall(r'\.swap\((\w+)\)', body)))
        # Execute the exact production cleanup body with tracked nested owners.
        # Validates capacity release and destruction, rather than clear-only size.
        program = '''#include <vector>
#include <cassert>
struct SettingInfo { std::vector<int> nested{1,2,3}; };
struct Settings {
 const std::vector<SettingInfo>* currentSettings = nullptr;
 int settingsCount = 99;
'''
        program += ''.join(' std::vector<SettingInfo> ' + n + ';\n' for n in names)
        program += ' void release() {' + body + '\n}\n};\nint main(){Settings s;\n'
        program += ''.join('s.' + n + '.resize(3);\n' for n in names)
        program += 's.release(); assert(!s.currentSettings && !s.settingsCount);\n'
        program += ''.join('assert(s.' + n + '.capacity()==0);\n' for n in names) + '}\n'
        compiler = ROOT / '.pio/native-tools/toolchain-gccmingw32/bin/g++.exe'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / 'test.cpp').write_text(program)
            env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get('PATH', ''))
            build = subprocess.run([str(compiler), '-std=c++14', '-static', str(path / 'test.cpp'),
                                    '-o', str(path / 'test.exe')], capture_output=True, text=True, env=env)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(path / 'test.exe')], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_child_handoff_releases_before_allocation_and_restores_on_result(self):
        text = source('src/activities/settings/SettingsActivity.cpp')
        handoff = text.split('case SettingAction::Bluetooth:', 1)[1].split('case SettingAction::Network:', 1)[0]
        self.assertLess(handoff.index('releaseSettingsLists()'), handoff.index('makeUniqueNoThrow<BleSettingsActivity>'))
        self.assertEqual(handoff.count('rebuildSettingsLists()'), 2)  # OOM and normal return
        self.assertIn('RenderLock lock(*this)', handoff)
        self.assertIn('if (menusSuspended) return;', text)

    def test_kobo_designation_visible_before_discovered_and_forget_rows(self):
        text = source('src/activities/settings/BleSettingsActivity.cpp')
        self.assertIn('selected == 2)', text)
        self.assertIn('self.items[2].label = tr(STR_BLE_LAB_USE_CONNECTED)', text)
        self.assertIn('bleLab.selectConnected()', text)
        self.assertIn('listNav.scrollBy(', text)
        self.assertIn('allowGlobalHomeSwipeGesture() const override { return false; }',
                      source('src/activities/settings/BleSettingsActivity.h'))

    def test_typed_persistent_identity_uses_existing_nvs_commit_and_readback(self):
        text = source('lib/hal/HalBlePageTurner.cpp')
        save = text.split('bool HalBlePageTurner::labSaveSelection', 1)[1].split('bool HalBlePageTurner::labClearSelection', 1)[0]
        self.assertIn('nvs_commit(handle)', save)
        self.assertIn('nvs_get_blob(handle, "lab-peer"', save)
        self.assertIn('BleBindings::same(peer, known)', text)
        self.assertIn('bond.type = host().paired(i).addrType', text)

    def test_home_keeps_normal_targets_and_dispatch_while_expanded(self):
        text = source('src/activities/home/HomeActivity.cpp')
        lab = text.split('void HomeActivity::labRender(int top)', 1)[1]
        self.assertNotIn('beginFrame()', lab)
        input_code = text.split('bool HomeActivity::labInput()', 1)[1].split('void HomeActivity::labActivate', 1)[0]
        self.assertNotIn('return expanded;', input_code)
        self.assertIn('selectorIndex == getMenuItemCount() - 1', input_code)
        self.assertIn('if (labUi.focus == 0) --selectorIndex', input_code)
        self.assertIn('if (labUi.focus == 6) selectorIndex = 0', input_code)
        self.assertIn('labUi.view.enabled ? StrId::STR_BLE_LAB_ON_STATE', lab)
        self.assertIn('labUi.view.wifi ? StrId::STR_BLE_LAB_ON_STATE', lab)
        self.assertIn('props.styles.normal.background = fui::Paint::solid(fui::Color::LightGray)', lab)


if __name__ == '__main__':
    unittest.main()
