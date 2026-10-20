"""Run real BleLab.cpp + Home input router with fake hardware, not a rendering model."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import re
import os
ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / '.pio/native-tools/toolchain-gccmingw32/bin/g++.exe'
class RuntimeTest(unittest.TestCase):
    def test_normal_loop_services_controller(self):
        text=(ROOT/'src/main.cpp').read_text(encoding='utf-8').split('const unsigned long activityStartTime = millis();',1)[1]
        self.assertRegex(text,r'activityManager.loop\(\);\s*#if CROSSINK_BLE_LAB\s*if \(!deepSleepInProgress && !activityManager.requiresExclusiveStorageLoop\(\)\) bleLab.tick\(\);')
        home=(ROOT/'src/activities/home/HomeActivity.cpp').read_text(encoding='utf-8')
        self.assertIn('BleLabInput::route(',home)
        self.assertIn('bleLab.request(BleLabInput::command(index))',home)
    def test_actual_dispatch_and_execution(self):
        self.assertTrue(COMPILER.exists(),'Install project-local native toolchain per docs')
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            def write(name,text):
                p=folder/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#pragma once\n'+text)
            # PlatformIO's portable host compiler is GCC 5. Keep runtime bodies
            # identical; remove only constexpr function qualifiers unsupported by
            # its older std::array. Modern target compiler checks originals too.
            for name in ['BleLabPolicy.h','BleButtonBindings.h']:
                header=(ROOT/'lib/hal'/name).read_text(encoding='utf-8')
                header=re.sub(r'\bconstexpr(?=\s+(?:bool|void|Blob|Result|uint32_t)\s+\w+\s*\()', 'inline', header)
                header=header.replace('static_assert(sizeof(Selection) == 52);','static_assert(sizeof(Selection) == 52, "record layout");')
                (folder/name).write_text(header)
            ids=sorted(set(re.findall(r'StrId::(STR_\w+)',(ROOT/'src/util/BleLab.cpp').read_text()+(ROOT/'src/util/BleLab.h').read_text())))
            write('I18n.h','enum class StrId {'+','.join(ids)+'};\nstruct Labels { const char* get(StrId){return "test";} };extern Labels I18N;')
            write('Arduino.h','#include <cstdint>\n#include <cstdio>\nextern uint32_t nowMs;inline uint32_t millis(){return nowMs;}\nstruct Esp{int resets=0;void restart(){++resets;}};extern Esp ESP;')
            write('Logging.h','#define LOG_INF(...) ((void)0)\n#define LOG_DBG(...) ((void)0)\n#define LOG_ERR(...) ((void)0)')
            write('HeapDiagnostics.h','namespace HeapDiagnostics{constexpr int Internal=1;inline void snapshot(const char*){}}')
            write('esp_heap_caps.h','#define MALLOC_CAP_SPIRAM 2\ninline unsigned heap_caps_get_free_size(int){return 140000;}\ninline unsigned heap_caps_get_largest_free_block(int){return 94000;}')
            write('HalStorage.h',r'''
#include <map>
#include <string>
#include <cstring>
#include <algorithm>
extern std::map<std::string,std::string> files;
extern bool exportOk,syncOk,renameOk; extern int exports;
struct HalFile {
 std::string name;size_t pos=0;
 size_t fileSize(){return files[name].size();}
 int read(void* b,size_t n){n=std::min(n,files[name].size()-pos);std::memcpy(b,files[name].data()+pos,n);pos+=n;return int(n);}
 size_t write(const void* b,size_t n){files[name].append((const char*)b,n);return n;}
 bool sync(){return syncOk;} bool close(){return true;}
};
struct Disk {
 bool exists(const char* p){return files.count(p)!=0;}
 bool remove(const char* p){return files.erase(p)!=0;}
 bool rename(const char* from,const char* to){if(!renameOk)return false;files[to]=files[from];files.erase(from);return true;}
 bool openFileForRead(const char*,const char* p,HalFile& f){if(!exists(p))return false;f.name=p;f.pos=0;return true;}
 bool openFileForWrite(const char*,const char* p,HalFile& f){if(std::string(p)=="/ble-lab-diagnostics.tmp")++exports;if(!exportOk)return false;files[p]="";f.name=p;f.pos=0;return true;}
};extern Disk Storage;
''')
            write('AppVersion.h','namespace AppVersion{inline const char* versionLabel(){return "test";}inline const char* version(){return "base";}}')
            write('activities/Activity.h','''
extern bool lockReady;
struct RenderLock{enum class Mode{Try};RenderLock(Mode){}bool ownsLock(){return lockReady;}};
struct Manager{
 int park=0,resume=0,wifi=0,update=0,restart=0,ready=1;bool home=true;
 bool isHomeActivity(){return home;}
 int prepareBleLabStorage(){++park;return ready;} void finishBleLabStorage(){++resume;}
 bool goToBleLabTransfer(){++wifi;return true;} bool goToBleLabUpdate(){++update;return true;}
 int prepareBleLabRestart(){++restart;return ready;}
};extern Manager activityManager;
''')
            write('HalBlePageTurner.h','''
#include <BleLabPolicy.h>
class HalBlePageTurner{public:
 enum class Status{Off,Ready,Scanning,Connecting,Connected,Stopping,Failed,LowMemory};enum{Memory=1,Wifi=2};
 Status state=Status::Off;bool on=false,held=false,enableOk=true,stopOk=true,saved=true,wifi=false;
 int starts=0,stops=0,connects=0,saves=0;unsigned fail=0;
 bool enabled()const{return on;} bool resident()const{return held;} Status status()const{return state;} unsigned failure()const{return fail;}
 bool enable(){++starts;on=held=enableOk;state=enableOk?Status::Ready:Status::LowMemory;fail=enableOk?0:Memory;return enableOk;}
 bool stop(unsigned){++stops;if(stopOk){on=held=false;state=Status::Off;}else state=Status::Stopping;return stopOk;}
 bool labWifiActive()const{return wifi;}
 bool labPeerConnected(const BleBindings::Peer&)const{return state==Status::Connected;}
 bool labConnectSaved(const BleBindings::Peer&){++connects;state=Status::Connecting;return true;}
 bool labLoadSelection(BleLabPolicy::Selection& s,bool& present){present=saved;std::snprintf(s.peer.address,sizeof(s.peer.address),"a4:3c:d7:9c:93:b1");s.peer.type=0;return true;}
 bool labSaveSelection(const BleLabPolicy::Selection&){++saves;saved=true;return true;} bool labClearSelection(){return true;}
 bool labConnectedPeer(BleLabPolicy::Selection& s){bool p;return labLoadSelection(s,p)&&p;}
};extern HalBlePageTurner blePageTurner;
''')
            case=r'''
#include <cassert>
#include "Arduino.h"
#include "I18n.h"
#include "HalBlePageTurner.h"
#include "activities/Activity.h"
#include "BleLab.h"
#include "BleLabInput.h"
#include "HalStorage.h"
using namespace BleLabPolicy;
uint32_t nowMs=0;bool lockReady=true;Esp ESP;Labels I18N;
HalBlePageTurner blePageTurner;Manager activityManager;int exports=0;bool exportOk=true,syncOk=true,renameOk=true;
std::map<std::string,std::string> files;Disk Storage;
void reset(){bleLab=BleLab{};blePageTurner=HalBlePageTurner{};activityManager=Manager{};ESP=Esp{};nowMs=0;lockReady=true;exports=0;exportOk=syncOk=renameOk=true;files.clear();}
void ticks(int n){for(int i=0;i<n;++i)bleLab.tick();}
int main(){
 BleLabInput::Pending queued;
 assert(queued.offer(0));assert(!queued.offer(0)); // no double activation while renderer busy
 assert(queued.take()==0&&queued.action==-2);assert(queued.take()==-2);
 reset();auto down=BleLabInput::route(-1,1,false,false,true,0);
 assert(down.handled&&down.action==-2&&blePageTurner.starts==0);
 auto tap=BleLabInput::route(1,1,true,false,true,0);assert(tap.action==0&&tap.focus==1);
 assert(bleLab.request(BleLabInput::command(tap.action)));assert(!bleLab.request(Command::Toggle));
 ticks(4);assert(blePageTurner.starts==1&&bleLab.view().radio==BleLab::Radio::On);
 ticks(4);assert(blePageTurner.starts==1);
 auto confirm=BleLabInput::route(-1,-1,true,false,true,1);assert(confirm.action==0);
 assert(bleLab.request(BleLabInput::command(confirm.action)));ticks(4);assert(blePageTurner.stops==1&&!blePageTurner.enabled());
 reset();assert(bleLab.request(Command::Toggle));ticks(1);activityManager.home=false;ticks(3);
 assert(blePageTurner.starts==0); // leave Home/USB handoff cannot start radio
 reset();assert(bleLab.request(Command::Connect));ticks(2);activityManager.home=false;ticks(2);
 assert(blePageTurner.connects==0); // no new client after leaving Home
 reset();blePageTurner.enableOk=false;assert(bleLab.request(Command::Toggle));ticks(3);
 assert(blePageTurner.starts==1&&!blePageTurner.enabled());assert(bleLab.view().result==StrId::STR_BLE_LOW_MEMORY&&bleLab.view().radio==BleLab::Radio::Error);
 reset();lockReady=false;assert(bleLab.request(Command::Toggle));ticks(3);assert(blePageTurner.starts==0);lockReady=true;ticks(2);assert(blePageTurner.starts==1);
 reset();assert(bleLab.request(Command::Connect));ticks(4);assert(blePageTurner.starts==1&&blePageTurner.connects==1);
 blePageTurner.state=HalBlePageTurner::Status::Connected;ticks(2);assert(bleLab.view().link==BleLab::Link::Connected);
 assert(bleLab.request(Command::Connect));ticks(3);assert(blePageTurner.connects==1);
 reset();blePageTurner.saved=false;assert(bleLab.request(Command::Connect));ticks(3);assert(blePageTurner.starts==0);
 reset();blePageTurner.saved=false;ticks(1);assert(bleLab.view().link==BleLab::Link::NotSelected);
 blePageTurner.saved=true;blePageTurner.on=blePageTurner.held=true;blePageTurner.state=HalBlePageTurner::Status::Connected;
 assert(bleLab.selectConnected());assert(blePageTurner.saves==1);
 assert(bleLab.selectConnected());assert(blePageTurner.saves==1); // repeat designation avoids NVS writes
 bleLab=BleLab{};blePageTurner.state=HalBlePageTurner::Status::Ready;bleLab.enterHome();
 assert(bleLab.view().link==BleLab::Link::Disconnected&&bleLab.view().enabled);
 assert(bleLab.request(Command::Connect));assert(bleLab.view().link==BleLab::Link::Connecting);
 ticks(4);assert(blePageTurner.connects==1);assert(!bleLab.request(Command::Connect));
 blePageTurner.state=HalBlePageTurner::Status::Failed;ticks(2);
 assert(bleLab.view().result==StrId::STR_BLE_CONNECT_FAILED);ticks(10);assert(blePageTurner.connects==1);
 reset();assert(!bleLab.view().enabled);assert(bleLab.request(Command::Toggle));
 assert(!bleLab.view().enabled);ticks(3);assert(bleLab.view().enabled);
 reset();ticks(2);assert(ESP.resets==0);assert(BleLabInput::route(-1,-1,false,true,true,6).action==-1);
 blePageTurner.on=blePageTurner.held=true;blePageTurner.stopOk=false;assert(bleLab.request(BleLabInput::command(5)));ticks(3);assert(ESP.resets==0);
 blePageTurner.stopOk=true;ticks(2);assert(ESP.resets==1&&activityManager.restart==1);
 reset();blePageTurner.on=blePageTurner.held=true;blePageTurner.stopOk=false;assert(bleLab.request(Command::Wifi));ticks(4);assert(activityManager.wifi==0);
 blePageTurner.stopOk=true;ticks(2);assert(activityManager.wifi==1&&!blePageTurner.held);assert(activityManager.park==activityManager.resume);
 reset();assert(bleLab.request(Command::Update));ticks(4);assert(activityManager.update==1);
 reset();blePageTurner.held=true;assert(bleLab.request(Command::Logs));ticks(3);assert(exports==0);
 reset();assert(bleLab.request(Command::Logs));ticks(3);assert(exports==1&&activityManager.resume==1);assert(bleLab.view().result==StrId::STR_BLE_LAB_LOGS_SAVED);
 reset();exportOk=false;assert(bleLab.request(Command::Logs));ticks(3);assert(bleLab.view().result==StrId::STR_BLE_LAB_TOOL_FAILED&&activityManager.resume==1);
 reset();files["/crash_report.txt"]=std::string(12000,'X');assert(bleLab.request(Command::Logs));ticks(3);
 assert(files["/ble-lab-crash.txt"].size()==8192);
 assert(files["/ble-lab-diagnostics.txt"].find("crash_copy_truncated=1")!=std::string::npos);
 assert(files["/ble-lab-diagnostics.txt"].size()<2048);
 reset();syncOk=false;assert(bleLab.request(Command::Logs));ticks(3);
 assert(bleLab.view().result==StrId::STR_BLE_LAB_TOOL_FAILED&&files.count("/ble-lab-diagnostics.txt")==0);
 reset();renameOk=false;assert(bleLab.request(Command::Logs));ticks(3);
 assert(bleLab.view().result==StrId::STR_BLE_LAB_TOOL_FAILED);
 return 0;
}
'''
            (folder/'case.cpp').write_text(case)
            exe=folder/'runtime.exe'
            args=[str(COMPILER),'-std=c++14','-static','-DCROSSINK_BLE_LAB=1','-DCROSSINK_HEAP_DIAGNOSTICS=1','-DFREEINK_DEVICE_X4PRO=1','-I'+str(folder),'-I'+str(ROOT/'src/util'),'-I'+str(ROOT/'include'),'-I'+str(ROOT/'lib/hal'),str(ROOT/'src/util/BleLab.cpp'),str(ROOT/'src/util/BleLabExport.cpp'),str(folder/'case.cpp'),'-o',str(exe)]
            env=dict(os.environ, PATH=str(COMPILER.parent)+os.pathsep+os.environ.get("PATH", ""))
            result=subprocess.run(args,capture_output=True,text=True,env=env)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
