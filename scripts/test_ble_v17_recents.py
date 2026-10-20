"""Execute production record storage, collection views and Home loading on native PC."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from v17_source_contract import BASELINE, REVIEWED, without_v17

ROOT = Path(__file__).resolve().parents[1]


class RecentPlacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name)
        record = (ROOT / 'src/RecentBooksStore.h').read_text().split('struct RecentBook {')[1].split('class RecentBooksStore')[0]
        (path / 'RecentBooksStore.h').write_text('#pragma once\n#include <string>\n#include <cstdint>\nstruct RecentBook {' + record)
        (path / 'Memory.h').write_text(r'''
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <memory>
constexpr unsigned MALLOC_CAP_SPIRAM=4, MALLOC_CAP_8BIT=2;
int psramCalls=0, psramFrees=0; bool fail=false; void* external=nullptr; size_t externalBytes=0;
void* heap_caps_aligned_alloc(size_t alignment,size_t bytes,unsigned caps) {
 ++psramCalls; assert(caps==(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
 external=fail?nullptr:std::malloc(bytes);externalBytes=bytes;
 assert(!external || reinterpret_cast<uintptr_t>(external)%alignment==0); return external;
}
struct HeapByteBufferDeleter { void operator()(uint8_t* p) const {
 if(p) { assert(p==external); ++psramFrees; std::free(p); external=nullptr; }
}};
using HeapByteBuffer=std::unique_ptr<uint8_t[],HeapByteBufferDeleter>;
''')
        home = (ROOT / 'src/activities/home/HomeActivity.cpp').read_text()
        load = home[home.index('void HomeActivity::loadRecentBooks('):home.index('void HomeActivity::loadCoverGridThumbnails(')]
        program = r'''
#include <cassert>
#include <cstdlib>
#include <new>
#include <string>
#include <vector>
#include <algorithm>
int live=0, calls=0, failNew=-1;
void* operator new(size_t n) {
 if(failNew==calls++) throw std::bad_alloc();
 void* p=std::malloc(n); if(!p) throw std::bad_alloc(); ++live; return p;
}
void operator delete(void* p) noexcept { if(p) {--live;std::free(p);} }
void operator delete(void* p,size_t) noexcept { if(p) {--live;std::free(p);} }
#include "HomeRecentBooks.h"
int errors=0;
#define LOG_ERR(...) (++errors)
struct Store {
 std::vector<RecentBook> books;
 const std::vector<RecentBook>& getBooks() const { return books; }
} store;
#define RECENT_BOOKS store
struct RecentBooksStore { static bool isMissing(const RecentBook& b) { return b.path=="missing"; } };
void ensureReusableCoverPath(RecentBook& b) { if(b.coverBmpPath=="old") b.coverBmpPath="new"; }
struct HomeActivity {
 HomeRecentBooks recentBookStorage; bool externalRecentBooks=false,coverGridUi=false;
 MutableRecentBookView recentBooks() {return recentBookStorage.view(externalRecentBooks);}
 ~HomeActivity() {recentBookStorage.destroy(externalRecentBooks);}
 void loadRecentBooks(int);
 bool prepare(size_t cap=7) {
  auto storage=HomeRecentBooks::allocateExternal(cap); if(!storage) return false;
  recentBookStorage.adoptExternal(std::move(storage),cap);externalRecentBooks=true;return true;
 }
};
''' + load + r'''
bool isExternal(const void* p) {
 auto n=reinterpret_cast<uintptr_t>(p), first=reinterpret_cast<uintptr_t>(external);
 return external && n>=first && n<first+externalBytes;
}
int main(int argc,char** argv) {
 assert(argc==2);const int test=std::atoi(argv[1]);
 store.books.push_back({std::string(75,'p'),std::string(18,'t'),std::string(15,'a'),std::string(64,'c')});
 store.books.push_back({std::string(80,'q'),std::string(18,'u'),std::string(15,'b'),std::string(65,'d')});
 const int baseline=live;
 {
  HomeActivity home;
  if(test!=0) assert(home.prepare());
  if(test==0) {home.loadRecentBooks(2); assert(psramCalls==0 && home.recentBooks().size()==2 && live==baseline+7);}
  if(test==1 || test==2) {
   home.loadRecentBooks(2);auto books=home.recentBooks();
   assert(books.size()==2 && isExternal(books.data()) && live==baseline+6);
   assert(reinterpret_cast<uintptr_t>(books.data())%alignof(RecentBook)==0);
   for(const auto& b:books) {
    assert(!isExternal(b.path.data()) && !isExternal(b.title.data()) && !isExternal(b.coverBmpPath.data()));
    assert(isExternal(b.author.data()));
   }
   if(test==2) {int n=calls;RecentBookView read=books;assert(read.data()==books.data());
    assert(read.front().title==store.books.front().title);assert(calls==n);}
  }
  if(test==3) {
   home.loadRecentBooks(2);auto books=home.recentBooks();const auto* p=books[1].path.data();
   RecentBookView held=books;std::rotate(books.begin(),books.begin()+1,books.end());
   assert(held[0].path.data()==p && held[0].path==store.books[1].path);
   assert(store.books[0].path[0]=='p'); books[0].coverBmpPath="changed cover reference with ordinary storage";
   assert(held[0].coverBmpPath==books[0].coverBmpPath && !isExternal(books[0].coverBmpPath.data()));
  }
  if(test==4) {
   home.loadRecentBooks(1); assert(home.recentBooks().size()==1);
   const int before=live;failNew=calls+1;
   try {home.recentBookStorage.pushCopy(store.books[1],true);assert(false);} catch(const std::bad_alloc&) {}
   failNew=-1;assert(home.recentBooks().size()==1 && live==before);
   assert(home.recentBookStorage.pushCopy(store.books[1],true));
   home.recentBookStorage.clear(true);assert(live==baseline && home.recentBooks().empty());
  }
  if(test==5) {
   for(int i=0;i<30;++i) {home.loadRecentBooks(2);assert(live==baseline+6);}
   assert(psramCalls==1);
  }
  if(test==6) {
   store.books[0].path="missing";store.books[1].coverBmpPath="old";
   home.loadRecentBooks(2);assert(home.recentBooks().size()==1);
   assert(home.recentBooks()[0].coverBmpPath=="new" && store.books[1].coverBmpPath=="old");
  }
  if(test==7) {
   assert(!home.recentBookStorage.reserve(8,true));
   for(int i=0;i<7;++i) assert(home.recentBookStorage.pushCopy(store.books[0],true));
   assert(!home.recentBookStorage.pushCopy(store.books[0],true) && home.recentBooks().size()==7);
  }
 }
 if(test!=6) assert(live==baseline);
 assert(psramFrees==(test==0?0:1));
 if(test==8) {
  const int before=live; HomeActivity home;fail=true;
  assert(!home.prepare() && !home.externalRecentBooks && home.recentBooks().empty() && live==before);
 }
}
'''
        (path / 'recents.cpp').write_text(program)
        compiler = ROOT / '.pio/native-tools/toolchain-gccmingw32/bin/g++.exe'
        env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get('PATH', ''))
        cls.exe = path / 'recents.exe'
        run = subprocess.run([str(compiler), '-std=c++17', '-static', '-DARDUINO_ARCH_ESP32=1',
                              '-DCROSSINK_BLE_LAB=1', '-DFREEINK_FB_PSRAM=1', '-I'+str(path),
                              '-I'+str(ROOT/'src'), '-I'+str(ROOT/'src/activities/home'),
                              str(path/'recents.cpp'), '-o', str(cls.exe)], env=env, capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(run.stderr)

    def scenario(self, number):
        run = subprocess.run([str(self.exe), str(number)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_boot_vector_and_seven_ordinary_allocations(self): self.scenario(0)
    def test_external_alignment_and_six_ordinary_string_allocations(self): self.scenario(1)
    def test_read_only_view_does_not_allocate_or_copy(self): self.scenario(2)
    def test_rotation_mutation_and_global_independence(self): self.scenario(3)
    def test_partial_copy_cleanup_and_constructed_count(self): self.scenario(4)
    def test_repeated_load_and_destruction(self): self.scenario(5)
    def test_production_filtering_and_cover_normalization(self): self.scenario(6)
    def test_capacity_is_bounded_without_fallback(self): self.scenario(7)
    def test_psram_failure_keeps_empty_internal_owner(self): self.scenario(8)

    def test_rendering_changes_are_only_collection_interfaces(self):
        for name in REVIEWED:
            if not name.startswith('src/components/'):
                continue
            actual = (ROOT/name).read_text()
            expected = subprocess.check_output(['git', 'show', f'{BASELINE}:{name}'], cwd=ROOT).decode()
            expected = expected.replace('const std::vector<RecentBook>&', 'RecentBookView')
            if name.endswith(('BaseTheme.h', 'CoverGridHomeUi.h')):
                expected = expected.replace('#include <string>', '#include <string>\n#include "components/RecentBookView.h"')
            if name.endswith('CoverGridHomeUi.h'):
                expected = expected.replace('const std::vector<RecentBook>* books = nullptr;', 'RecentBookView books;')
            if name.endswith('CoverGridHomeUi.cpp'):
                expected = expected.replace('books = &recent;', 'books = recent;').replace('books->', 'books.').replace('(*books)[', 'books[')
            self.assertEqual(actual, expected, name)

    def test_protected_sources_and_controller_abi_gate(self):
        for name in ['src/activities/ActivityManager.cpp', 'src/RecentBooksStore.h', 'src/RecentBooksStore.cpp',
                     'src/components/UITheme.cpp', 'src/activities/settings/SettingsActivity.cpp',
                     'lib/hal/BleMemoryPolicy.h', 'lib/hal/HalBlePageTurner.cpp', 'src/main.cpp']:
            expected = subprocess.check_output(['git', 'show', f'{BASELINE}:{name}'], cwd=ROOT).decode()
            self.assertEqual((ROOT/name).read_text(), expected, name)
        source = (ROOT/'src/activities/home/HomeActivity.cpp').read_text()
        self.assertIn('static_assert(sizeof(HomeActivity) == 1252', source)
        self.assertIn('RecentBook book = storedBook;', source)
        self.assertIn('recentBookStorage.pushCopy(book, externalRecentBooks)', source)
        self.assertIn('coverGridUi.reset();', source)
        self.assertEqual(without_v17('src/activities/home/HomeActivity.cpp', source),
                         subprocess.check_output(['git', 'show', f'{BASELINE}:src/activities/home/HomeActivity.cpp'], cwd=ROOT).decode())


if __name__ == '__main__':
    unittest.main()
