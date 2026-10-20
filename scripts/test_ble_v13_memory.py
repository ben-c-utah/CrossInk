"""Settings controller placement, polymorphic ownership and handoff contracts."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SettingsMemoryTest(unittest.TestCase):
    def test_production_allocator_and_virtual_destruction(self):
        source = (ROOT / 'src/activities/settings/SettingsActivity.cpp').read_text(encoding='utf-8')
        methods = source.split('void* SettingsActivity::operator new(', 1)[1].split(
            'SettingsActivity::SettingsActivity(', 1)[0]
        methods = 'void* SettingsActivity::operator new(' + methods
        # Compile the exact allocation/deallocation implementations with fake
        # capability heaps. Exercise deletion through the real ownership shape.
        program = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <new>
#include <vector>
#define LOG_ERR(...) ((void)0)
int psramCalls=0, defaultCalls=0, frees=0, constructed=0, destroyed=0;
bool fail=false;
struct HeapByteBufferDeleter { void operator()(uint8_t* p) const {
 if(p) { ++frees; std::free(p); }
}};
using Buffer=std::unique_ptr<uint8_t[],HeapByteBufferDeleter>;
Buffer makePsramByteBufferNoThrow(size_t n) {
 ++psramCalls; return Buffer(fail ? nullptr : static_cast<uint8_t*>(std::malloc(n)));
}
Buffer makeHeapByteBufferNoThrow(size_t n) {
 ++defaultCalls; return Buffer(fail ? nullptr : static_cast<uint8_t*>(std::malloc(n)));
}
struct Activity { virtual ~Activity() {} };
struct SettingsActivity final: Activity {
 static void* operator new(size_t,const std::nothrow_t&) noexcept;
 static void* operator new(size_t)=delete;
 static void operator delete(void*) noexcept;
 static void operator delete(void*,const std::nothrow_t&) noexcept;
 std::vector<int> menu;
 SettingsActivity() { ++constructed; }
 ~SettingsActivity() { ++destroyed; }
};
''' + methods + r'''
int main() {
 for(int navigation=0; navigation<20; ++navigation) {
  std::unique_ptr<SettingsActivity> parent(new(std::nothrow) SettingsActivity);
  assert(parent); parent->menu.assign(40,7);
  std::unique_ptr<Activity> retainedParent(std::move(parent));
  for(int child=0; child<5; ++child) {
   auto* settings=static_cast<SettingsActivity*>(retainedParent.get());
   std::vector<int>().swap(settings->menu);
   assert(settings->menu.capacity()==0 && destroyed==navigation);
   settings->menu.assign(40,7);
   assert(settings->menu.size()==40);
  }
  retainedParent.reset(); assert(destroyed==navigation+1 && frees==destroyed);
 }
 fail=true;
 std::unique_ptr<Activity> missing(new(std::nothrow) SettingsActivity);
 assert(!missing && constructed==20 && destroyed==20 && frees==20);
#if defined(ARDUINO_ARCH_ESP32) && !defined(SIMULATOR) && FREEINK_FB_PSRAM && CROSSINK_APP_CAP_BLE_PAGE_TURNER
 assert(psramCalls==21 && defaultCalls==0); // No internal fallback on PSRAM OOM.
#else
 assert(psramCalls==0 && defaultCalls==21);
#endif
}
'''
        compiler = ROOT / '.pio/native-tools/toolchain-gccmingw32/bin/g++.exe'
        variants = [[], ['-DARDUINO_ARCH_ESP32=1', '-DFREEINK_FB_PSRAM=1',
                         '-DCROSSINK_APP_CAP_BLE_PAGE_TURNER=1'],
                    ['-DARDUINO_ARCH_ESP32=1', '-DFREEINK_FB_PSRAM=0',
                     '-DCROSSINK_APP_CAP_BLE_PAGE_TURNER=1'],
                    ['-DARDUINO_ARCH_ESP32=1', '-DFREEINK_FB_PSRAM=1',
                     '-DCROSSINK_APP_CAP_BLE_PAGE_TURNER=1', '-DSIMULATOR=1']]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.cpp').write_text(program)
            env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get('PATH', ''))
            for flags in variants:
                with self.subTest(flags=flags):
                    result = subprocess.run([str(compiler), '-std=c++14', '-static', '-fno-exceptions',
                                             *flags, str(path / 'test.cpp'), '-o', str(path / 'test.exe')],
                                            env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(path / 'test.exe')], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_settings_entry_paths_are_fallible_and_checked(self):
        paths = list((ROOT / 'src').rglob('*.cpp'))
        callers = []
        for path in paths:
            source = path.read_text(encoding='utf-8')
            self.assertNotIn('std::make_unique<SettingsActivity>', source)
            for match in re.finditer(r'auto settings =\s*makeUniqueNoThrow<SettingsActivity>.*?;', source):
                callers.append(path)
                tail = source[match.end():match.end() + 350]
                self.assertRegex(tail, r'if \(!settings\) \{')
                self.assertIn('return;', tail)
        self.assertEqual(len(callers), 3)

    def test_parent_is_retained_and_restored_through_existing_result_flow(self):
        source = (ROOT / 'src/activities/ActivityManager.cpp').read_text(encoding='utf-8')
        self.assertIn('stackActivities.push_back(std::move(currentActivity))', source)
        self.assertIn('currentActivity = std::move(stackActivities.back())', source)
        self.assertIn('handler(pendingResult)', source)
        settings = (ROOT / 'src/activities/settings/SettingsActivity.cpp').read_text(encoding='utf-8')
        handoff = settings.split('case SettingAction::Bluetooth:', 1)[1].split('case SettingAction::Network:', 1)[0]
        self.assertEqual(handoff.count('rebuildSettingsLists()'), 2)
        self.assertIn('dictionaryRegistry.markDirty()', handoff)
        self.assertIn('menusSuspended = false', handoff)


if __name__ == '__main__':
    unittest.main()
