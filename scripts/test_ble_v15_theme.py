"""Execute production theme lifecycle methods; preserve the single-variable scope."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "8acf8fed34d2c90c4960613ff5966afbe0a7ae99"


class ThemeReuseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        path = Path(cls.directory.name)
        source = (ROOT / "src/components/UITheme.cpp").read_text(encoding="utf-8")
        header = (ROOT / "src/components/UITheme.h").read_text(encoding="utf-8")
        # Actual constructor, reload, fallback/selection and metrics-cache code.
        methods = source[source.index("UITheme::UITheme()"):source.index("int UITheme::getNumberOfItemsPerPage")]
        declarations = "\n".join(re.findall(r"  void (?:reload|setTheme)\([^;]+;", header))
        settings_header = (ROOT / "src/CrossPointSettings.h").read_text(encoding="utf-8")
        theme_enum = re.search(r"enum UI_THEME \{.*?\};", settings_header, re.S).group()
        program = r'''
#include <cassert>
#include <cstdlib>
#include <memory>
#include <new>
int allocated=0, constructed=0, destroyed=0, snapshots=0, observations=0;
const void* oldObserved=nullptr; const void* newObserved=nullptr;
void* operator new(size_t n) { ++allocated; return std::malloc(n); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, size_t) noexcept { std::free(p); }
#define LOG_DBG(...) ((void)0)
#define LOG_ERR(...) ((void)0)
#define CROSSINK_HEAP_DIAGNOSTICS 1
namespace HeapDiagnostics {
void snapshot(const char*) { ++snapshots; }
void allocation(const char*, const void* p, size_t) {
 if(observations++ % 2 == 0) oldObserved=p; else newObserved=p;
}
}
struct CrossPointSettings {
''' + theme_enum + r'''
 int uiTheme=1;
} SETTINGS;
bool psram=true;
bool psramHeapAvailable() { return psram; }
struct { bool touch=false; bool hasTouch() { return touch; } } gpio;
struct ThemeMetrics { int kind; int buttonHintsHeight; };
struct BaseTheme {
 BaseTheme() { ++constructed; } virtual ~BaseTheme() { ++destroyed; }
 virtual int kind() const { return 0; }
};
struct BaseMetrics { static constexpr ThemeMetrics values{0,20}; };
constexpr ThemeMetrics BaseMetrics::values;
#define THEME(Name, ID) \
 struct Name##Theme: BaseTheme { int kind() const override { return ID; } }; \
 struct Name##Metrics { static constexpr ThemeMetrics values{ID,20+ID}; }; \
 constexpr ThemeMetrics Name##Metrics::values;
THEME(Lyra,1) THEME(RoundedRaff,3) THEME(Lyra3Covers,2)
THEME(LyraCarousel,4) THEME(Minimal,5) THEME(Dashboard,6)
class UITheme {
 public:
 UITheme();
 const ThemeMetrics& getMetrics() const;
 const BaseTheme& getTheme() const { return *currentTheme; }
 static bool supportsCoverGrid();
 static bool hasCoverGridHome();
''' + declarations + r'''
 // Deliberately expose the cache flag only in the native harness.
 const ThemeMetrics* currentMetrics;
 std::unique_ptr<BaseTheme> currentTheme;
 mutable ThemeMetrics adjustedMetrics;
 mutable bool metricsValid=false;
 mutable bool metricsForTouch=false;
};
''' + methods + r'''
using Kind=CrossPointSettings::UI_THEME;
void select(UITheme& theme,int kind) { SETTINGS.uiTheme=kind; theme.reload(true); }
int main(int argc,char** argv) {
 assert(argc==2); const int scenario=std::atoi(argv[1]); UITheme theme;
 if(scenario==0) { // Default boot/direct APIs still construct before destroying.
  for(int i=0;i<20;++i) {
   const auto* old=&theme.getTheme(); const int before=constructed, dead=destroyed;
   theme.reload();
   assert(&theme.getTheme()!=old && constructed==before+1 && destroyed==dead+1);
   assert(oldObserved==old && newObserved==&theme.getTheme());
  }
  const int before=constructed; theme.setTheme(Kind::LYRA);
  assert(constructed==before+1);
 }
 if(scenario==1) { // Same implementation: no new/delete and stable storage.
  for(int kind=0;kind<7;++kind) {
   select(theme,kind); const auto* old=&theme.getTheme();
   const int count=allocated, live=constructed, dead=destroyed;
   for(int i=0;i<100;++i) {
    theme.getMetrics(); assert(theme.metricsValid);
    theme.reload(true);
    assert(!theme.metricsValid && &theme.getTheme()==old);
    assert(oldObserved==old && newObserved==old);
   }
   assert(allocated==count && constructed==live && destroyed==dead);
  }
 }
 if(scenario==2) { // Every pair of genuine implementations.
  for(int from=0;from<7;++from) for(int to=0;to<7;++to) {
   select(theme,from); const auto* old=&theme.getTheme();
   const int before=constructed, dead=destroyed; select(theme,to);
   assert(theme.getTheme().kind()==to && theme.getMetrics().kind==to);
   assert(constructed==before+(from!=to) && destroyed==dead+(from!=to));
   assert((&theme.getTheme()==old)==(from==to));
  }
 }
 if(scenario==3) { // Cover Grid and Lyra share an implementation, even on fallback.
  select(theme,1); const auto* old=&theme.getTheme(); const int before=constructed;
  for(bool available: {false,true}) {
   psram=available; select(theme,7);
   assert(&theme.getTheme()==old && constructed==before);
   assert(UITheme::hasCoverGridHome()==available);
  }
  select(theme,0); psram=false; select(theme,7);
  assert(theme.getTheme().kind()==1 && theme.getMetrics().kind==1);
 }
 if(scenario==4) { // Invalid values retain Classic fallback and refresh metrics.
  select(theme,999); assert(theme.getTheme().kind()==0);
  const auto* old=&theme.getTheme(); const int before=constructed;
  select(theme,-1);
  assert(&theme.getTheme()==old && constructed==before && !theme.metricsValid);
  assert(theme.getMetrics().kind==0);
  select(theme,1); assert(theme.getTheme().kind()==1);
 }
 if(scenario==5) { // Reuse still invalidates/recomputes touch-sensitive metrics.
  theme.getMetrics(); const auto* old=&theme.getTheme();
  theme.adjustedMetrics.buttonHintsHeight=-999;
  theme.reload(true); assert(!theme.metricsValid);
  assert(theme.getMetrics().buttonHintsHeight==21);
  gpio.touch=true; theme.reload(true);
#if CROSSINK_APP_CAP_TOUCH
  assert(theme.getMetrics().buttonHintsHeight==0);
#else
  assert(theme.getMetrics().buttonHintsHeight==21);
#endif
  gpio.touch=false; theme.reload(true);
  assert(theme.getMetrics().buttonHintsHeight==21 && &theme.getTheme()==old);
 }
 assert(snapshots==observations && snapshots>0);
 assert(constructed==destroyed+1);
}
'''
        (path / "theme.cpp").write_text(program, encoding="utf-8")
        compiler = ROOT / ".pio/native-tools/toolchain-gccmingw32/bin/g++.exe"
        env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get("PATH", ""))
        cls.executables = []
        for touch in (0, 1):
            exe = path / f"theme-{touch}.exe"
            result = subprocess.run(
                [str(compiler), "-std=c++17", "-static", "-fno-exceptions",
                 f"-DCROSSINK_APP_CAP_TOUCH={touch}", str(path / "theme.cpp"), "-o", str(exe)],
                capture_output=True, text=True, env=env)
            if result.returncode:
                raise AssertionError(result.stderr)
            cls.executables.append(exe)

    def run_scenario(self, number):
        for exe in self.executables:
            with self.subTest(target=exe.name):
                run = subprocess.run([str(exe), str(number)], capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_boot_and_default_set_theme_still_replace(self):
        self.run_scenario(0)

    def test_repeated_same_theme_reuses_storage_without_allocating(self):
        self.run_scenario(1)

    def test_all_genuine_theme_transitions(self):
        self.run_scenario(2)

    def test_cover_grid_effective_implementation_and_capability_fallback(self):
        self.run_scenario(3)

    def test_unknown_theme_classic_fallback_and_recovery(self):
        self.run_scenario(4)

    def test_metric_invalidation_and_touch_cache_refresh(self):
        self.run_scenario(5)

    def test_only_settings_exit_opts_in_under_existing_lifecycle_lock(self):
        settings = (ROOT / "src/activities/settings/SettingsActivity.cpp").read_text(encoding="utf-8")
        before = subprocess.check_output(
            ["git", "show", f"{BASELINE}:src/activities/settings/SettingsActivity.cpp"], cwd=ROOT
        ).decode("utf-8")
        expected = before.replace(
            "UITheme::getInstance().reload();  // Re-apply theme in case it was changed",
            "UITheme::getInstance().reload(true);  // Re-apply changes, but retain an unchanged theme's storage.")
        self.assertEqual(settings, expected)
        for name in ("src/main.cpp", "src/activities/ActivityManager.cpp",
                     "src/activities/home/HomeActivity.cpp", "src/activities/home/HomeActivity.h"):
            with self.subTest(file=name):
                original = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT).decode("utf-8")
                self.assertEqual((ROOT / name).read_text(encoding="utf-8"), original)

    def test_diagnostic_records_and_existing_theme_storage_members_preserved(self):
        for name in ("src/components/UITheme.cpp", "src/activities/settings/SettingsActivity.cpp"):
            before = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT).decode("utf-8")
            after = (ROOT / name).read_text(encoding="utf-8")
            pattern = r"#if CROSSINK_HEAP_DIAGNOSTICS\n.*?#endif"
            self.assertEqual(re.findall(pattern, before, re.S), re.findall(pattern, after, re.S))
        name = "src/components/UITheme.h"
        before = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT).decode("utf-8")
        after = (ROOT / name).read_text(encoding="utf-8")
        self.assertEqual(before.split(" private:")[1], after.split(" private:")[1])


if __name__ == "__main__":
    unittest.main()
