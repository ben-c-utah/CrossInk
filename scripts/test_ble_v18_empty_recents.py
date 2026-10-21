"""Run production Home initialization/storage with bounded native collaborators.

These checks establish ownership, copy suppression and empty selection safety;
they do not emulate ESP32 heap placement or physical e-ink rendering.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from v18_source_contract import BASELINE, EXPERIMENT, HOME, without_v18

ROOT = Path(__file__).resolve().parents[1]


def fn(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    for end in range(opening + 1, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError('Unclosed production function: ' + signature)


class EmptyRecentHomeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name)
        record = (ROOT / 'src/RecentBooksStore.h').read_text().split('struct RecentBook {')[1].split('class RecentBooksStore')[0]
        (path / 'RecentBooksStore.h').write_text('#pragma once\n#include <string>\n#include <cstdint>\nstruct RecentBook {' + record)
        (path / 'Memory.h').write_text(r'''
#pragma once
#include <memory>
#include <cstdint>
constexpr unsigned MALLOC_CAP_SPIRAM=4, MALLOC_CAP_8BIT=2;
int psramCalls=0, psramFrees=0; bool failPsram=false; void* external=nullptr;
void* heap_caps_aligned_alloc(size_t alignment,size_t bytes,unsigned caps) {
 ++psramCalls; assert(caps==(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
 external=failPsram?nullptr:std::malloc(bytes);
 assert(!external || reinterpret_cast<uintptr_t>(external)%alignment==0);return external;
}
struct HeapByteBufferDeleter {void operator()(uint8_t* p) const {
 if(p) {assert(p==external);++psramFrees;std::free(p);external=nullptr;}
}};
using HeapByteBuffer=std::unique_ptr<uint8_t[],HeapByteBufferDeleter>;
template<class T,class... Args> std::unique_ptr<T> makeUniqueNoThrow(Args&&... args) {
 return std::unique_ptr<T>(new(std::nothrow) T(std::forward<Args>(args)...));
}
''')
        source = (ROOT / HOME).read_text()
        methods = '\n'.join(fn(source, name) for name in [
            'void HomeActivity::loadRecentBooks(', 'void HomeActivity::onEnter()',
            'int HomeActivity::getHighlightedBookIndex()', 'int HomeActivity::getVisibleRecentBookCount()',
            'bool HomeActivity::canSwapHomeBook()', 'void HomeActivity::showNextRecentBookOnHome()',
            'int HomeActivity::getMenuItemCount()', 'void HomeActivity::activateCoverGridSelection()',
            'void HomeActivity::onContinueReading()',
            'std::string HomeActivity::getCurrentBookPath()', 'std::string HomeActivity::getCurrentBookTitle()'])
        program = r'''
#include <cassert>
#include <cstdlib>
#include <new>
#include <string>
#include <vector>
#include <array>
#include <algorithm>
int live=0,calls=0;
void* operator new(size_t n) {void* p=std::malloc(n);if(!p) throw std::bad_alloc();++live;++calls;return p;}
void* operator new(size_t n,const std::nothrow_t&) noexcept {return ::operator new(n);}
void operator delete(void* p) noexcept {if(p) {--live;std::free(p);}}
void operator delete(void* p,size_t) noexcept {if(p) {--live;std::free(p);}}
void operator delete(void* p,const std::nothrow_t&) noexcept {::operator delete(p);}
namespace std {template<class T> T clamp(T x,T lo,T hi) {return min(max(x,lo),hi);}}
#include "HomeRecentBooks.h"
#define LOG_ERR(...) ((void)0)
struct Store {
 std::vector<RecentBook> books;int ensures=0;
 void ensureLoaded() {++ensures;}
 const std::vector<RecentBook>& getBooks() const {return books;}
} store;
#define RECENT_BOOKS store
struct RecentBooksStore {static bool isMissing(const RecentBook& b) {return b.path=="missing";}};
void ensureReusableCoverPath(RecentBook&) {}
struct CrossPointSettings {enum UI_THEME {LYRA,LYRA_CAROUSEL};};
struct Settings {int uiTheme=0;} settings;
#define SETTINGS settings
struct State {std::string openEpubPath;} appState;
#define APP_STATE appState
struct Metrics {int homeRecentBooksCount=1;bool homeContinueReadingInMenu=false;};
struct UITheme {
 static bool grid;Metrics metrics;
 static UITheme& getInstance() {static UITheme t;return t;}
 static bool hasCoverGridHome() {return grid;}
 const Metrics& getMetrics() const {return metrics;}
};
bool UITheme::grid=false;
struct Opds {bool enabled=false;bool hasServers() const {return enabled;}} opds;
#define OPDS_STORE opds
struct BookmarkStore {static bool hasAnyBookmarks() {return false;}};
struct ClippingStore {static bool hasAnyClippings() {return false;}};
struct GlobalReadingStats {
 static int load() {return 0;} static bool hasSyncedStats() {return false;}
 static int loadAggregated(int n) {return n;}
};
struct CoverGridHomeUi {
 static constexpr int MAX_BOOKS=7;RecentBookView books;bool hasBook=false;float progress=0;
 explicit CoverGridHomeUi(int&) {}
 void begin(RecentBookView b,bool,bool has,float p) {books=b;hasBook=has;progress=p;}
};
enum class HomeMenuItem {NONE,FILE_BROWSER,LIBRARY,OPDS_BROWSER,FILE_TRANSFER,SETTINGS_MENU};
std::array<int,5> buildSelectableHomeMenuItems(bool,bool,bool,bool,bool) {return {{0,1,2,3,4}};}
int homeActionForInitialMenuItem(HomeMenuItem n) {return static_cast<int>(n)-1;}
int findMenuActionIndex(const std::array<int,5>&,int n) {return n;}
int getVisibleRecentBookCount(RecentBookView b) {
 return std::min(static_cast<int>(b.size()),UITheme::getInstance().metrics.homeRecentBooksCount);
}
int getHomeMenuSelectionOffset(RecentBookView b) {return getVisibleRecentBookCount(b);}
bool hasValidCarouselDiskCache(RecentBookView b,int&,int idx) {
 if(b.empty()) assert(idx==-1);return false;
}
int progressCalls=0,contextCalls=0;
float loadRecentBookProgress(const RecentBook&) {++progressCalls;return 50;}
struct Activity {int enters=0;void onEnter() {++enters;}};
struct HomeActivity:Activity {
 HomeRecentBooks recentBookStorage;bool externalRecentBooks=false;
 std::unique_ptr<CoverGridHomeUi> coverGridUi;std::string initialBookPath;
 static constexpr int kMaxCachedBooks=7,HOME_BOOK_SWAP_RECENT_COUNT=2;
 int renderer=0,selectorIndex=0,lastCarouselBookIndex=0,carouselCoverTouchDownIndex=0;
 int carouselMenuTouchDownIndex=0,minimalMenuIndex=0,minimalHomeNavIndex=0;
 bool carouselCoverTouchDownWasSelected=false,minimalMenuOpen=false,minimalSuppressInitialFrontRelease=false;
 bool backPressSeen=false,carouselFramesReady=false,carouselWarmupPending=false,bookStatsCached=false;
 bool hasOpdsServers=false,hasBookmarks=false,hasClippings=false,hasReadingStats=false,gridHasContinueReading=false;
 bool showAllDevicesStats=false;int globalStats=0,allDevicesGlobalStats=0,updates=0;
 HomeMenuItem initialMenuItem=HomeMenuItem::NONE;
 struct Lab {void enterHome() {} int view() {return 0;}} bleLab;
 struct LabUi {int view=0;} labUi;
 struct RenderLock {explicit RenderLock(HomeActivity&) {}};
 bool labEnabled() const {return true;}
 bool usesMinimalHomeInteraction() const {return false;}
 void loadAllBookStats() {}
 void updateHighlightedBookContext(bool=false) {++contextCalls;}
 void preRenderCarouselFrames() {assert(false);}
 void requestUpdate() {++updates;}
 void invalidateCoverCache() {}
 int action=-1;
 void onSelectBook(const std::string&) {action=99;}
 void onFileBrowserOpen() {action=0;}
 void onLibraryOpen() {action=1;}
 void onOpdsBrowserOpen() {action=2;}
 void onFileTransferOpen() {action=3;}
 void onSettingsOpen() {action=4;}
 MutableRecentBookView recentBooks() {return recentBookStorage.view(externalRecentBooks);}
 RecentBookView recentBooks() const {return recentBookStorage.view(externalRecentBooks);}
 bool prepare() {
  auto storage=HomeRecentBooks::allocateExternal(7);if(!storage) return false;
  recentBookStorage.adoptExternal(std::move(storage),7);externalRecentBooks=true;return true;
 }
 ~HomeActivity() {coverGridUi.reset();recentBookStorage.destroy(externalRecentBooks);}
 void loadRecentBooks(int);void onEnter();int getHighlightedBookIndex() const;
 int getVisibleRecentBookCount() const;bool canSwapHomeBook() const;void showNextRecentBookOnHome();
 std::string getCurrentBookPath() const;std::string getCurrentBookTitle() const;
 int getMenuItemCount() const;void activateCoverGridSelection();void onContinueReading();
};
constexpr int HomeActivity::kMaxCachedBooks;
constexpr int HomeActivity::HOME_BOOK_SWAP_RECENT_COUNT;
''' + methods + r'''
int main(int argc,char** argv) {
 assert(argc==2);const int test=std::atoi(argv[1]);
 store.books.push_back({std::string(75,'p'),std::string(18,'t'),"author",std::string(64,'c')});
 store.books.push_back({std::string(80,'q'),std::string(18,'u'),"author",std::string(65,'d')});
 appState.openEpubPath=store.books[0].path;
 const auto* globalData=store.books.data();const auto* globalPath=store.books[0].path.data();
 const int baseline=live;
 {
  HomeActivity home;home.initialBookPath=store.books[1].path;
  const auto* selected=home.initialBookPath.data();
  const bool targeted=test!=0 && test!=6;
  if(targeted) assert(home.prepare());
  void* records=external;
  if(test==2 || test==3) {UITheme::grid=true;opds.enabled=test==3;home.initialMenuItem=HomeMenuItem::SETTINGS_MENU;}
  if(test==4) settings.uiTheme=CrossPointSettings::LYRA_CAROUSEL;
  const int before=live,allocBefore=calls;
  home.onEnter();
  assert(home.enters==1 && home.updates==1 && store.ensures==1 && contextCalls==1);
  assert(home.initialBookPath.data()==selected && home.initialBookPath==store.books[1].path);
  assert(store.books.data()==globalData && store.books[0].path.data()==globalPath);
  assert(store.books.size()==2 && store.books[0].path[0]=='p' && store.books[1].path[0]=='q');
  assert(appState.openEpubPath==store.books[0].path);
  if(!targeted) {
   assert(home.recentBooks().size()==2 && psramCalls==0 && live==before+7);
   assert(home.getCurrentBookPath()==store.books[1].path && home.canSwapHomeBook());
  } else {
   assert(home.recentBooks().empty() && home.recentBooks().data()==records);
   assert(home.recentBookStorage.capacity(true)==7 && psramCalls==1);
   assert(!home.gridHasContinueReading && home.getHighlightedBookIndex()==-1);
   assert(home.getVisibleRecentBookCount()==0 && !home.canSwapHomeBook());
   assert(home.getCurrentBookPath().empty() && home.getCurrentBookTitle().empty());
   assert(progressCalls==0);
   const int expectedGridAlloc=UITheme::grid?1:0;
   assert(live==before+expectedGridAlloc && calls==allocBefore+expectedGridAlloc);
   home.showNextRecentBookOnHome();assert(home.updates==1);
   home.onContinueReading();assert(home.action==-1);
   if(UITheme::grid) {
    assert(home.coverGridUi->books.empty() && !home.coverGridUi->hasBook && home.coverGridUi->progress==-1);
    assert(home.selectorIndex==(opds.enabled?4:3));
    const int count=opds.enabled?5:4;assert(home.getMenuItemCount()==count);
    for(int i=0;i<count;++i) {
     home.selectorIndex=i;home.activateCoverGridSelection();
     assert(home.action==(opds.enabled || i<2?i:i+1));
    }
   } else {
    assert(home.getMenuItemCount()==5); // Four normal actions plus Bluetooth Lab.
   }
   if(test==5) {
    for(int i=0;i<20;++i) home.onEnter();
    assert(home.recentBooks().empty() && calls==allocBefore && home.initialBookPath.data()==selected);
   }
  }
 }
 assert(live==baseline && psramFrees==(test!=0 && test!=6?1:0));
}
'''
        (path / 'empty.cpp').write_text(program)
        compiler = ROOT / '.pio/native-tools/toolchain-gccmingw32/bin/g++.exe'
        cls.exe = path / 'empty.exe'
        env = dict(os.environ, PATH=str(compiler.parent) + os.pathsep + os.environ.get('PATH', ''))
        run = subprocess.run([str(compiler), '-std=c++17', '-static', '-DARDUINO_ARCH_ESP32=1',
                              '-DCROSSINK_BLE_LAB=1', '-DFREEINK_FB_PSRAM=1', '-I'+str(path),
                              '-I'+str(ROOT/'src'), '-I'+str(ROOT/'src/activities/home'),
                              str(path/'empty.cpp'), '-o', str(cls.exe)], env=env, capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(run.stderr)

    def scenario(self, number):
        run = subprocess.run([str(self.exe), str(number)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_boot_home_loads_private_books_and_restores_selection(self): self.scenario(0)
    def test_target_has_zero_copies_or_temporary_allocations(self): self.scenario(1)
    def test_empty_cover_grid_keeps_settings_selection_safe(self): self.scenario(2)
    def test_empty_cover_grid_with_opds_keeps_selection_safe(self): self.scenario(3)
    def test_empty_carousel_skips_cache_and_book_access(self): self.scenario(4)
    def test_repeated_empty_initialization_and_destruction(self): self.scenario(5)
    def test_unrelated_internal_home_still_loads_books(self): self.scenario(6)

    def test_only_production_delta_is_copy_call_gate(self):
        actual = (ROOT/HOME).read_text()
        self.assertEqual(actual.count(EXPERIMENT), 1)
        expected = subprocess.check_output(['git', 'show', f'{BASELINE}:{HOME}'], cwd=ROOT).decode()
        self.assertEqual(without_v18(HOME, actual), expected)
        # Includes allocation failure/path restoration, ownership and all guards.
        changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--',
                                           'src', 'lib', 'include', 'platformio.ini', 'freeink-sdk'],
                                          cwd=ROOT, text=True).splitlines()
        self.assertEqual(changed, [HOME])

    def test_route_flag_and_preflight_are_unchanged(self):
        source = (ROOT/HOME).read_text()
        factory = fn(source, 'std::unique_ptr<HomeActivity> HomeActivity::createForSettingsReturn(')
        self.assertEqual(source.count('externalRecentBooks = true;'), 1)
        self.assertIn('externalRecentBooks = true;', factory)
        self.assertIn('HomeRecentBooks::allocateExternal', factory)
        self.assertIn('static_assert(sizeof(HomeActivity) == 1252', source)
        # Existing V16 executable factory tests inject both PSRAM failures and
        # check Settings/path preservation; these remain in the full test run.

    def test_empty_rendering_guards_and_diagnostics_remain(self):
        source = (ROOT/HOME).read_text()
        self.assertIn('logDiagnosticHome("Home after recent copies", true)', source)
        self.assertIn('const size_t count = std::min(recentBooks().size(), size_t{3});', source)
        self.assertIn('if (recentBooks().empty())', fn(source, 'void HomeActivity::onContinueReading('))
        self.assertIn('if (bookCount == 0)', fn(source, 'void HomeActivity::preRenderCarouselFrames('))
        grid = (ROOT/'src/components/CoverGridHomeUi.cpp').read_text()
        draw = fn(grid, 'void CoverGridHomeUi::draw(')
        self.assertLess(draw.index('if (books.empty())'), draw.index('drawCurrent('))
        begin = fn(grid, 'void CoverGridHomeUi::begin(')
        self.assertIn('if (!recent.empty()) coverCache.begin();', begin)
        lyra = (ROOT/'src/components/themes/lyra/LyraTheme.cpp').read_text()
        self.assertIn('drawEmptyRecents(renderer, rect);', lyra)


if __name__ == '__main__':
    unittest.main()
