"""Execute production Home allocation and navigation methods with bounded fake heaps."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

from v16_source_contract import without_v16
from v17_source_contract import without_v17

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "51e21a7eb6e17c523d717354b92b442f451ef49a"


class HomePlacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        path = Path(cls.directory.name)
        source = (ROOT / "src/activities/home/HomeActivity.cpp").read_text()
        header = (ROOT / "src/activities/home/HomeActivity.h").read_text()
        manager = (ROOT / "src/activities/ActivityManager.cpp").read_text()
        allocation = source[source.index("std::unique_ptr<HomeActivity> HomeActivity::createForSettingsReturn"):source.index("namespace {")]
        declarations = header[header.index("  // Allocate storage before consuming"):
                              header.index("  explicit HomeActivity(")]
        go_home = manager[manager.index("void ActivityManager::goHome("):
                          manager.index("void ActivityManager::goToCrashReport()")]
        replace = manager[manager.index("void ActivityManager::replaceActivity("):
                          manager.index("void ActivityManager::goToFileTransfer(")]
        exit_activity = manager[manager.index("void ActivityManager::exitActivity("):
                                manager.index("void ActivityManager::replaceActivity(")]
        drain = manager[manager.index("      if (pendingAction == PendingAction::Replace) {"):
                        manager.index("      if (pendingAction == PendingAction::None && pendingReaderMenuAction")]
        destruction = header.split("  ~HomeActivity() override {", 1)[1].split("\n  }", 1)[0]
        program = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <new>
#include <string>
#include <vector>
#define LOG_ERR(...) (++errors)
int errors=0, psramCalls=0, freed=0, constructed=0, destroyed=0, failAt=0;
void* allocated[128]{};
int exits=0, entered=0, events=0;
char trace[128]{};
bool fail=false;
void* external=nullptr;
constexpr unsigned MALLOC_CAP_SPIRAM=4, MALLOC_CAP_8BIT=2;
void* heap_caps_aligned_alloc(size_t alignment, size_t size, unsigned caps) {
 ++psramCalls; assert(caps==(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
 assert(alignment>=alignof(void*) && (alignment&(alignment-1))==0);
 external=(fail || psramCalls==failAt) ? nullptr : std::malloc(size);
 allocated[psramCalls-1]=external;
 assert(!external || reinterpret_cast<uintptr_t>(external)%alignment==0);
 return external;
}
struct HeapByteBufferDeleter { void operator()(uint8_t* p) const {
 if(p) { ++freed; std::free(p); }
}};
using HeapByteBuffer=std::unique_ptr<uint8_t[],HeapByteBufferDeleter>;
#include "HomeRecentBooks.h"
struct CoverGridHomeUi { static constexpr size_t MAX_BOOKS=7; };
using GfxRenderer=int;
using MappedInputManager=int;
struct RenderLock { void unlock() {} };
struct TouchRegistry {
 static TouchRegistry& getInstance() { static TouchRegistry r; return r; }
 void clear() {}
};
enum class HomeMenuItem { NONE,FILE_BROWSER,LIBRARY,OPDS_BROWSER,FILE_TRANSFER,SETTINGS_MENU };
struct HalDisplay { enum RefreshMode { FAST_REFRESH,FULL_REFRESH }; };
struct Activity {
 std::string name;
 explicit Activity(std::string n):name(std::move(n)){}
 virtual ~Activity() {}
 virtual void onExit() { ++exits; trace[events++]='X'; }
 virtual void onEnter() { ++entered; trace[events++]='E'; }
};
struct HomeActivity final:Activity {
''' + declarations + r'''
 HomeMenuItem menu; HalDisplay::RefreshMode refresh; std::string initialBookPath;
 std::unique_ptr<int> coverGridUi;
 std::vector<std::string> recents;
 HomeRecentBooks recentBookStorage; bool externalRecentBooks=false;
 static constexpr int kMaxCachedBooks=3;
 HomeActivity(int&,int&,HomeMenuItem m,HalDisplay::RefreshMode r,std::string p)
 :Activity("Home"),menu(m),refresh(r),initialBookPath(std::move(p)) {
  ++constructed;trace[events++]='C';
 }
 ~HomeActivity() override {
''' + destruction + r'''
 ++destroyed;trace[events++]='D'; }
};
''' + allocation + r'''
struct ActivityManager {
 int renderer=0,mappedInput=0;
 std::unique_ptr<Activity> currentActivity,pendingActivity;
 std::vector<std::unique_ptr<Activity>> stackActivities;
 enum class PendingAction { None,Push,Pop,Replace };
 PendingAction pendingAction=PendingAction::None;
 Activity* pendingHomeReaderTarget=nullptr;
 std::string preferredHomeBookPath;
 bool returningHomeThroughSettings=false;
 void goHome(HomeMenuItem=HomeMenuItem::NONE,HalDisplay::RefreshMode=HalDisplay::FAST_REFRESH);
 void replaceActivity(std::unique_ptr<Activity>&&);
 void exitActivity(const RenderLock&);
 void drain() { RenderLock lock;
''' + drain + r'''
 }
};
''' + exit_activity + replace + go_home + r'''
int main(int argc,char** argv) {
 assert(argc==2); const int scenario=std::atoi(argv[1]);
 ActivityManager manager;
 if(scenario==0) { // Boot: ordinary allocation, immediate entry with no current activity.
  manager.goHome(); assert(psramCalls==0 && entered==1 && constructed==1);
  assert(manager.currentActivity && manager.pendingAction==ActivityManager::PendingAction::None);
 } else if(scenario==1) { // Unrelated routes and non-root Settings never opt in.
  for(int route=0;route<4;++route) {
   manager.currentActivity=std::make_unique<Activity>(route==0?"Reader":"Settings");
   manager.returningHomeThroughSettings=route!=1;
   if(route==2) manager.stackActivities.push_back(std::make_unique<Activity>("Reader"));
   if(route==3) manager.currentActivity->name="FileBrowser";
   manager.goHome(); assert(psramCalls==0); manager.drain(); manager.stackActivities.clear();
  }
 } else if(scenario==2 || scenario==3 || scenario==4 || scenario==5 || scenario==8) {
  manager.currentActivity=std::make_unique<Activity>("Settings");
  Activity* settings=manager.currentActivity.get();
  manager.returningHomeThroughSettings=true;
  manager.preferredHomeBookPath=std::string(90,'b');
  const char* backing=manager.preferredHomeBookPath.data();
  fail=scenario==3; failAt=scenario==8 ? 2 : 0;
  manager.goHome(HomeMenuItem::NONE,HalDisplay::FULL_REFRESH);
#if defined(ARDUINO_ARCH_ESP32) && !defined(SIMULATOR) && CROSSINK_BLE_LAB && FREEINK_FB_PSRAM
  assert(psramCalls==(fail?1:2));
  if(fail || scenario==8) {
   assert(!manager.pendingActivity && manager.currentActivity.get()==settings);
   assert(manager.pendingAction==ActivityManager::PendingAction::None);
   assert(constructed==0 && destroyed==0 && exits==0 && errors==1);
   assert(manager.returningHomeThroughSettings && manager.preferredHomeBookPath.data()==backing);
   assert(manager.preferredHomeBookPath==std::string(90,'b'));
   fail=false; failAt=0; manager.goHome(); assert(psramCalls==(scenario==8?4:3)); // Screen remains navigable.
  }
  assert(manager.pendingActivity.get()==allocated[psramCalls-2]);
#else
  assert(psramCalls==0);
#endif
  assert(manager.currentActivity.get()==settings && exits==0 && entered==0);
  auto* home=static_cast<HomeActivity*>(manager.pendingActivity.get());
  assert(home->initialBookPath.data()==backing && home->initialBookPath==std::string(90,'b'));
  assert(home->menu==HomeMenuItem::SETTINGS_MENU);
  if(!fail && scenario!=3 && scenario!=8) assert(home->refresh==HalDisplay::FULL_REFRESH);
  assert(!manager.returningHomeThroughSettings && manager.preferredHomeBookPath.empty());
  assert(events==1 && trace[0]=='C');
  manager.drain(); assert(trace[1]=='X' && trace[2]=='E');
  assert(manager.currentActivity.get()==home);
  if(scenario==5) {
   home->recents.emplace_back(80,'r');
   assert(home->recents.data()!=external && home->recents[0].data()!=external);
  }
  manager.currentActivity.reset(); assert(destroyed==1);
#if defined(ARDUINO_ARCH_ESP32) && !defined(SIMULATOR)
  assert(freed==(CROSSINK_BLE_LAB && FREEINK_FB_PSRAM ? (scenario==8?3:2) : 1));
#endif
 } else if(scenario==6) {
  for(int i=0;i<20;++i) {
   manager.currentActivity=std::make_unique<Activity>("Settings");
   manager.returningHomeThroughSettings=true;
   manager.preferredHomeBookPath=std::string(90,'c');
   manager.goHome(); manager.drain(); manager.currentActivity.reset();
  }
  assert(constructed==20 && destroyed==20 && exits==20 && entered==20);
#if defined(ARDUINO_ARCH_ESP32) && !defined(SIMULATOR)
  assert(freed==(CROSSINK_BLE_LAB && FREEINK_FB_PSRAM ? 40 : 20));
#endif
 } else if(scenario==7) {
  std::unique_ptr<Activity> home(new(std::nothrow) HomeActivity(manager.renderer,manager.mappedInput,
       HomeMenuItem::NONE,HalDisplay::FAST_REFRESH,{}));
  assert(home && psramCalls==0); home.reset(); assert(destroyed==1);
 }
}
'''
        (path / "Memory.h").write_text("#pragma once\n")
        record = (ROOT / "src/RecentBooksStore.h").read_text().split("struct RecentBook {")[1].split("class RecentBooksStore")[0]
        (path / "RecentBooksStore.h").write_text("#pragma once\n#include <string>\n#include <cstdint>\nstruct RecentBook {" + record)
        (path / "home.cpp").write_text(program)
        compiler = ROOT / ".pio/native-tools/toolchain-gccmingw32/bin/g++.exe"
        env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get("PATH", ""))
        variants = [[], ["-DARDUINO_ARCH_ESP32=1", "-DCROSSINK_BLE_LAB=1", "-DFREEINK_FB_PSRAM=1"],
                    ["-DARDUINO_ARCH_ESP32=1", "-DCROSSINK_BLE_LAB=0", "-DFREEINK_FB_PSRAM=0"],
                    ["-DARDUINO_ARCH_ESP32=1", "-DCROSSINK_BLE_LAB=0", "-DSIMULATOR=1"]]
        cls.executables = []
        for index, flags in enumerate(variants):
            exe = path / f"home-{index}.exe"
            run = subprocess.run([str(compiler), "-std=c++17", "-static", "-fno-exceptions", *flags,
                                  "-I"+str(path), "-I"+str(ROOT / "src"), "-I"+str(ROOT / "src/activities/home"),
                                  str(path / "home.cpp"), "-o", str(exe)], env=env, capture_output=True, text=True)
            if run.returncode:
                raise AssertionError(run.stderr)
            cls.executables.append(exe)

    def scenario(self, value):
        for exe in self.executables:
            with self.subTest(variant=exe.name):
                run = subprocess.run([str(exe), str(value)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_boot_allocation_and_immediate_entry_unchanged(self):
        self.scenario(0)

    def test_only_root_settings_home_return_opts_in(self):
        self.scenario(1)

    def test_psram_alignment_and_virtual_deallocation(self):
        self.scenario(2)

    def test_allocation_failure_preserves_settings_path_and_retry(self):
        self.scenario(3)

    def test_record_preflight_failure_preserves_settings_path_and_retry(self):
        self.scenario(8)

    def test_path_move_selection_refresh_and_lifecycle_order(self):
        self.scenario(4)

    def test_secondary_allocations_keep_ordinary_allocator(self):
        self.scenario(5)

    def test_repeated_returns_destroy_exactly_once(self):
        self.scenario(6)

    def test_other_nothrow_home_construction_unchanged(self):
        self.scenario(7)

    def test_no_other_production_behavior_changed(self):
        for name in ("src/activities/ActivityManager.cpp", "src/activities/home/HomeActivity.cpp",
                     "src/activities/home/HomeActivity.h", "src/activities/settings/SettingsActivity.cpp",
                     "src/components/UITheme.cpp", "lib/hal/BleMemoryPolicy.h", "src/main.cpp"):
            before = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT).decode()
            self.assertEqual(without_v16(name, (ROOT / name).read_text()), before, name)

    def test_diagnostics_and_inline_object_layout_preserved(self):
        for name in ("src/activities/ActivityManager.cpp", "src/activities/home/HomeActivity.cpp"):
            before = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT).decode()
            after = without_v17(name, (ROOT / name).read_text())
            pattern = r"#if CROSSINK_HEAP_DIAGNOSTICS\n.*?#endif"
            self.assertEqual(re.findall(pattern, before, re.S), re.findall(pattern, after, re.S))
        source = (ROOT / "src/activities/home/HomeActivity.cpp").read_text()
        self.assertIn('HeapDiagnostics::allocation("Home object", this, sizeof(*this))', source)


if __name__ == "__main__":
    unittest.main()
