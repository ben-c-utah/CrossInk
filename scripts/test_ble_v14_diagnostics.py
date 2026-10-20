"""V14 diagnostics: safe storage observations and V13 behavior preservation."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "a626db46af2bb039478e6691521be4fb8bba0b9e"


def without_diagnostics(text):
    """Remove only opt-in diagnostic regions, preserving other preprocessor code."""
    result = []
    depth = 0
    for line in text.splitlines():
        if not depth and line.strip() == "#if CROSSINK_HEAP_DIAGNOSTICS":
            depth = 1
        elif depth:
            if re.match(r"\s*#if", line):
                depth += 1
            elif line.strip() == "#endif":
                depth -= 1
        elif line != "#include <HeapDiagnostics.h>":
            result.append(line)
    assert depth == 0
    return "\n".join(result)


class DiagnosticsTest(unittest.TestCase):
    def test_observers_do_not_allocate_or_query_string_allocation_size(self):
        compiler = ROOT / ".pio/native-tools/toolchain-gccmingw32/bin/g++.exe"
        program = r'''
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <string>
#include <vector>
size_t allocations=0, queries=0, lines=0;
char last[256];
void* operator new(size_t n) { ++allocations; return std::malloc(n); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, size_t) noexcept { std::free(p); }
void record(const char*, const char* format, ...) {
 ++lines; va_list args; va_start(args,format);
 std::vsnprintf(last,sizeof(last),format,args); va_end(args);
}
#include "HeapDiagnostics.h"
int main() {
 std::string small="short", large(160,'x'), empty;
 std::string moved=std::move(large);
 std::vector<int> values(3,7), none;
 const auto before=allocations;
 for (int i=0;i<20;++i) {
  HeapDiagnostics::stringStorage("SSO",small);
  HeapDiagnostics::stringStorage("long",moved);
  HeapDiagnostics::stringStorage("moved-from",large);
  HeapDiagnostics::stringStorage("empty",empty);
  HeapDiagnostics::vectorStorage("empty",none.data(),none.size(),none.capacity(),sizeof(int));
  HeapDiagnostics::vectorStorage("owned",values.data(),values.size(),values.capacity(),sizeof(int));
  HeapDiagnostics::snapshot("boundary");
 }
 assert(allocations==before && queries==0 && lines==140);
 assert(std::string(last).find("blocks=4/3")!=std::string::npos);
 HeapDiagnostics::allocation("null",nullptr,0); assert(queries==0);
 HeapDiagnostics::allocation("exact owned base",values.data(),values.capacity()*sizeof(int));
 assert(queries==1);
}
'''
        stubs = {
            "Logging.h": "#define LOG_INF(...) record(__VA_ARGS__)\n",
            "esp_memory_utils.h": "inline bool esp_ptr_external_ram(const void*) { return false; }\n",
            "esp_heap_caps.h": r'''
#include <cstdint>
#include <cstddef>
constexpr uint32_t MALLOC_CAP_INTERNAL=1, MALLOC_CAP_8BIT=2, MALLOC_CAP_SPIRAM=4;
struct multi_heap_info_t {
 size_t total_free_bytes,largest_free_block,total_allocated_bytes,allocated_blocks,free_blocks;
};
inline void heap_caps_get_info(multi_heap_info_t* p,uint32_t) { *p={100,80,20,4,3}; }
inline size_t heap_caps_get_free_size(uint32_t) { return 1000; }
inline size_t heap_caps_get_allocated_size(void*) { ++queries; return 16; }
inline void heap_caps_print_heap_info(uint32_t) { assert(false); }
''',
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name, content in stubs.items():
                (path / name).write_text(content)
            (path / "test.cpp").write_text(program)
            env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get("PATH", ""))
            run = subprocess.run(
                [str(compiler), "-std=c++17", "-static", "-fno-exceptions",
                 "-DCROSSINK_HEAP_DIAGNOSTICS=1", "-DFREEINK_DEVICE_X4PRO=1",
                 "-I" + str(path), "-I" + str(ROOT / "lib/Memory"), str(path / "test.cpp"),
                 "-o", str(path / "test.exe")], capture_output=True, text=True, env=env)
            self.assertEqual(run.returncode, 0, run.stderr)
            run = subprocess.run([str(path / "test.exe")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            # With diagnostics disabled no ESP headers, observers or state exist.
            (path / "disabled.cpp").write_text('#include "HeapDiagnostics.h"\nint main() {}\n')
            run = subprocess.run(
                [str(compiler), "-std=c++17", "-fsyntax-only", "-I" + str(ROOT / "lib/Memory"),
                 str(path / "disabled.cpp")], capture_output=True, text=True, env=env)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_non_diagnostic_behavior_matches_v13(self):
        files = [
            "src/activities/ActivityManager.cpp", "src/activities/home/HomeActivity.cpp",
            "src/activities/home/HomeActivity.h", "src/activities/settings/SettingsActivity.cpp",
            "src/components/UITheme.cpp",
        ]
        for name in files:
            with self.subTest(file=name):
                before = subprocess.check_output(
                    ["git", "show", f"{BASELINE}:{name}"], cwd=ROOT).decode("utf-8")
                after = (ROOT / name).read_text(encoding="utf-8")
                before, after = without_diagnostics(before), without_diagnostics(after)
                # Sole non-diagnostic refactor: name the same unique_ptr to observe
                # it before replaceActivity. Construction still precedes onExit.
                after = re.sub(
                    r"auto home = (std::make_unique<HomeActivity>\(.*?std::move\(initialBookPath\)\));"
                    r"\s*replaceActivity\(std::move\(home\)\);",
                    r"replaceActivity(\1);", after, flags=re.S)
                # V15's sole authorized behavior change is tested dynamically in
                # test_ble_v15_theme. Reverse only that explicit delta here so
                # the original whole-source V13 preservation check remains useful.
                after = after.replace(
                    "UITheme::getInstance().reload(true);  // Re-apply changes, but retain an unchanged theme's storage.",
                    "UITheme::getInstance().reload();  // Re-apply theme in case it was changed")
                after = after.replace("reload(const bool reuseUnchanged)", "reload()")
                after = after.replace(
                    "setTheme(CrossPointSettings::UI_THEME type, const bool reuseUnchanged)",
                    "setTheme(CrossPointSettings::UI_THEME type)")
                after = after.replace("setTheme(themeType, reuseUnchanged);", "setTheme(themeType);")
                after = re.sub(
                    r"if \(!reuseUnchanged \|\| currentMetrics != &\w+Metrics::values\) \{\s*"
                    r"(currentTheme = std::make_unique<\w+Theme>\(\);)\s*\}", r"\1", after)
                self.assertEqual(re.sub(r"\s+", "", before), re.sub(r"\s+", "", after))

    def test_ble_lifecycle_guards_and_navigation_dependencies_unchanged(self):
        for name in [
            "lib/hal/HalBlePageTurner.cpp", "lib/hal/BleMemoryPolicy.h",
            "src/activities/settings/BleSettingsActivity.cpp", "src/util/BleLab.cpp",
            "src/activities/home/FileBrowserActivity.cpp", "src/RecentBooksStore.cpp",
            "src/util/DictionaryRegistry.cpp", "platformio.ini",
        ]:
            with self.subTest(file=name):
                before = subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=ROOT)
                self.assertEqual(before.decode().replace("\r\n", "\n"),
                                 (ROOT / name).read_text(encoding="utf-8"))

    def test_home_observation_is_bounded_and_has_no_new_members(self):
        text = (ROOT / "src/activities/home/HomeActivity.cpp").read_text(encoding="utf-8")
        observer = text.split("void HomeActivity::logDiagnosticHome(", 1)[1].split("\n#endif", 1)[0]
        self.assertIn("std::min(recentBooks.size(), size_t{3})", observer)
        self.assertIn("const auto& book = recentBooks[i]", observer)
        self.assertNotIn("heap_caps_get_allocated_size", observer)
        self.assertNotIn("getCurrentBookPath", observer)  # Would copy the string.
        self.assertNotIn("std::vector", observer)
        self.assertNotIn("std::string ", observer)


if __name__ == "__main__":
    unittest.main()
