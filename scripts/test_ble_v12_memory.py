"""Execute the real dictionary catalog lifecycle with a fake, bounded SD backend."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CatalogTest(unittest.TestCase):
    def test_discovery_release_and_dirty_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            for name in ['DictionaryRegistry.cpp', 'DictionaryRegistry.h']:
                shutil.copyfile(ROOT / 'src/util' / name, folder / name)
            (folder / 'Logging.h').write_text('#define LOG_DBG(...) ((void)0)\n#define LOG_ERR(...) ((void)0)\n#define LOG_INF(...) ((void)0)\n')
            (folder / 'FsHelpers.h').write_text('''#pragma once
#include <cstring>
extern bool rootExists;
namespace FsHelpers { inline bool resolveRootDirectoryIgnoreCase(const char* p,char* out,unsigned n) {
 if (!rootExists) return false; std::strncpy(out,p,n); return true;
}}
''')
            (folder / 'HalStorage.h').write_text('''#pragma once
#include <cstddef>
extern bool validDirectory; extern int closes;
struct HalFile {
 bool present=false;
 explicit operator bool() const {return present;}
 bool isDirectory()const{return validDirectory;}
 void close(){++closes;present=false;}
 void rewindDirectory(){}
 HalFile openNextFile(){return {};}
 void getName(char*,size_t){}
};
struct Disk {HalFile open(const char*) {HalFile f; f.present=true;return f;}}; extern Disk Storage;
''')
            (folder / 'Dictionary.h').write_text('''#pragma once
#include <string>
extern int saves;
namespace Dictionary {
 inline std::string readConfiguredDictPath(){return "working-dictionary";}
 inline bool hasGlobalDictPathFile(){return true;}
 inline void saveGlobalDictPath(const char*){++saves;}
}
''')
            (folder / 'case.cpp').write_text('''#include <cassert>
#include "DictionaryRegistry.h"
#include "HalStorage.h"
bool rootExists=false,validDirectory=true;int closes=0,saves=0;Disk Storage;
int main(){
 DictionaryRegistry r;
 assert(!r.discover() && r.getEntries().capacity()==0);
 rootExists=true;assert(!r.discover() && r.getEntries().capacity()>=16);
 auto& entries=const_cast<std::vector<DictionaryEntry>&>(r.getEntries());
 entries.push_back({"English","test","/.dictionaries/English/test"});
 assert(r.count()==1);
 r.clear();r.markDirty();assert(r.getEntries().capacity()==0 && r.root().empty() && saves==0);
 r.refreshIfDirty();assert(r.getEntries().capacity()>=16); // catalog can be restored before menu rows
 rootExists=false;r.markDirty();r.refreshIfDirty();assert(r.getEntries().capacity()==0);
 rootExists=true;r.discover();validDirectory=false;int before=closes;
 assert(!r.discover() && r.getEntries().capacity()==0 && r.root().empty());
 assert(closes==before+1 && saves==0);
}
''')
            compiler = ROOT / '.pio/native-tools/toolchain-gccmingw32/bin/g++.exe'
            env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get('PATH', ''))
            result = subprocess.run([str(compiler), '-std=c++14', '-static', '-I' + str(folder),
                                     str(folder / 'DictionaryRegistry.cpp'), str(folder / 'case.cpp'),
                                     '-o', str(folder / 'case.exe')], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(folder / 'case.exe')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_catalog_handoff_and_restore_precede_bluetooth_allocation(self):
        text = (ROOT / 'src/activities/settings/SettingsActivity.cpp').read_text(encoding='utf-8')
        handoff = text.split('case SettingAction::Bluetooth:', 1)[1].split('case SettingAction::Network:', 1)[0]
        self.assertLess(handoff.index('dictionaryRegistry.clear()'), handoff.index('makeUniqueNoThrow<BleSettingsActivity>'))
        self.assertLess(handoff.index('dictionaryRegistry.markDirty()'), handoff.index('makeUniqueNoThrow<BleSettingsActivity>'))
        self.assertIn('RenderLock lock(*this)', handoff)
        self.assertEqual(handoff.count('rebuildSettingsLists()'), 2)
        self.assertIn('dictionaryRegistry.refreshIfDirty()', text.split('void SettingsActivity::rebuildSettingsLists()', 1)[1])


if __name__ == '__main__':
    unittest.main()
