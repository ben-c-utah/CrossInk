"""Bounded Lyra Lab text checks and dependency-free geometry/font preview.

This is a layout preview, not a simulator or physical rendering verification.
Uses firmware bitmap glyphs; kerning/icons/cover artwork are not simulated.
"""
from pathlib import Path
import itertools
import re
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]

class Font:
    def __init__(self, name):
        source = (ROOT / 'lib/EpdFont/builtinFonts' / (name + '.h')).read_text()
        data = source.split(name + 'Bitmaps', 1)[1].split('{', 1)[1].split('}', 1)[0]
        self.bitmap = bytes(int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]+)', data))
        glyph_source = source.split(name + 'Glyphs[] = {', 1)[1].split('};', 1)[0]
        self.glyphs = {cp: tuple(map(int, values.split(','))) for cp, values in enumerate(
            re.findall(r'\{\s*([\d, \-]+)\s*\}', glyph_source)) if cp < 128}
        metrics = source.split('EpdFontData ' + name + ' = {', 1)[1]
        self.line, self.asc, self.desc = map(int, re.search(r'Intervals,\s*\d+,\s*(\d+),\s*(\d+),\s*(-?\d+)', metrics).groups())

    def width(self, text):
        return sum((self.glyphs[ord(c)][2] + 8) // 16 for c in text)

    def draw(self, canvas, x, y, text, color=0):
        for c in text:
            w, h, advance, left, top, length, offset = self.glyphs[ord(c)]
            for gy in range(h):
                for gx in range(w):
                    bit = gy * w + gx
                    if self.bitmap[offset + bit // 8] & (0x80 >> (bit % 8)):
                        px, py = x + left + gx, y + self.asc - top + gy
                        assert 0 <= px < 480 and 0 <= py < 800, (text, px, py)
                        canvas[py * 480 + px] = color
            x += (advance + 8) // 16

SMALL = Font('inter_8_regular')
BODY = Font('inter_12_regular')
BOLD = Font('inter_12_bold')
UI10 = Font('inter_10_regular')
STRINGS = dict(re.findall(r'^(STR_\w+): "(.*)"$', (ROOT / 'lib/I18n/translations/english.yaml').read_text(encoding='utf-8'), re.M))
HOME = (ROOT / 'src/activities/home/HomeActivity.cpp').read_text(encoding='utf-8')
KEYS = set(re.findall(r'StrId::(STR_BLE_LAB_BRIEF_\w+)', HOME))
KEYS.update('STR_BLE_LAB_' + s for s in ['ON', 'OFF', 'CONNECTED', 'WORKING', 'BUSY', 'TIMEOUT', 'CLOSE_WIFI', 'LOGS_OFF', 'TOOL_FAILED', 'LOGS_SAVED', 'WIFI_OPEN', 'UPDATE_OPEN', 'WIFI_RETURN', 'UPDATE_RETURN'])

class LayoutTest(unittest.TestCase):
    def test_button_labels_fit_without_wrapping(self):
        for key in ['STR_BLE_LAB_BLUETOOTH', 'STR_BLE_LAB_KOBO', 'STR_BLE_LAB_WIFI', 'STR_BLE_LAB_LOGS', 'STR_BLE_LAB_UPDATE', 'STR_BLE_LAB_RESTART']:
            self.assertLessEqual(SMALL.width(STRINGS[key]), 102, key)

    def test_every_home_feedback_fits_one_line(self):
        for key in KEYS:
            self.assertLessEqual(SMALL.width(STRINGS[key]), 440, key)

    def test_worst_state_and_memory_lines_fit(self):
        for radio, link in itertools.product(['Off', 'Starting', 'On', 'Stopping', 'Error'],
                                             ['Not Set', 'Disconnected', 'Connecting', 'Connected', 'Other Device']):
            self.assertLessEqual(SMALL.width(STRINGS['STR_BLE_LAB_V10_MEMORY'] % (999999, 999999, link)), 440)
        self.assertLessEqual(SMALL.width(STRINGS['STR_BLE_LAB_MEMORY'] % (999999, 999999)), 440)

    def test_header_fits_with_chevron(self):
        for radio in ['Off','On','Starting','Stopping','Error']:
            self.assertLessEqual(SMALL.width(STRINGS['STR_BLE_LAB_HEADER'] % ('Bluetooth Lab',radio,'Off')), 400)

    def test_ink_bounds_and_long_title_progress_card(self):
        self.assertEqual(SMALL.line, 20)
        self.assertLessEqual(SMALL.asc - SMALL.desc, 24)
        self.assertLessEqual(BOLD.asc - BOLD.desc + (42 - BOLD.line) // 2, 42)
        # Existing full card contract: three title lines, author, two statistics
        # lines, and progress label/bar. V9a never shrinks this 242-pixel card.
        total = 3 * BODY.line + UI10.line * 3 // 2 + 2 * SMALL.line + 6 + UI10.line + 12
        self.assertLessEqual(total, 242)
        self.assertIn('int homeCoverTileHeight = metrics.homeCoverTileHeight;', HOME)
        self.assertNotIn('homeCoverTileHeight = std::max(0, std::min', HOME)


def preview(path, expanded=False):
    canvas = bytearray([255]) * (480 * 800)
    def box(x,y,w,h,fill=255,border=0):
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                canvas[yy*480+xx]=border if yy in (y,y+h-1) or xx in (x,x+w-1) else fill
    def icon(name,x,y,color):
        source=(ROOT/'src/components/icons/listIcons.h').read_text()
        data=source.split('icon_'+name+'_24_bits[] = {',1)[1].split('}',1)[0]
        bits=bytes(int(v,16) for v in re.findall(r'0x([0-9A-Fa-f]+)',data))
        for yy in range(24):
            for xx in range(24):
                bit=yy*24+xx
                if not bits[bit//8]&(0x80>>(bit%8)):canvas[(y+yy)*480+x+xx]=color
    SMALL.draw(canvas,20,12,'12:34                                         85%')
    box(42,42,150,226,230)
    for i,text in enumerate(['A Long Book','Title Across Three','Lines With Stats']):BOLD.draw(canvas,208,50+i*30,text)
    UI10.draw(canvas,208,152,'Example Author')
    SMALL.draw(canvas,208,184,'Total time: 12h 34m')
    SMALL.draw(canvas,208,204,'Avg session: 24m')
    UI10.draw(canvas,208,232,'100%');box(208,260,238,4)
    for i,text in enumerate(['Browse Files','Library','OPDS Browser','Reading Stats','Saved Items','File Transfer','Settings']):
        BODY.draw(canvas,36,276+i*46+6,text)
    top=506 if expanded else 644
    height=222 if expanded else 104
    box(20,top,440,height,255,255)
    box(20,top,440,32)
    header=STRINGS['STR_BLE_LAB_HEADER']%('Bluetooth Lab','Off','Off')
    SMALL.draw(canvas,30,top+6,header)
    icon('chevron_up' if expanded else 'chevron_down',426,top+4,0)
    info=top+32
    if expanded:
        info+=4
        names=['radio_tower','book','wifi','file_text','arrow_up','history']
        labels=['Bluetooth','Kobo','Wi-Fi','Logs','Update','Restart']
        for i,label in enumerate(labels):
            x=20+(i%3)*148;y=info+(i//3)*58;selected=i==0
            box(x,y,142,52,0 if selected else 255)
            ink=255 if selected else 0
            group=24+4+SMALL.width(label);left=x+(142-group)//2
            icon(names[i],left,y+14,ink)
            SMALL.draw(canvas,left+28,y+16,label,ink)
        info+=114
    SMALL.draw(canvas,20,info+2,'CrossInk BLE v10-dev <build-id>')
    SMALL.draw(canvas,20,info+26,'Max 47092 B | Free 142656 B | Kobo Off')
    SMALL.draw(canvas,20,info+50,'Not enough memory')
    SMALL.draw(canvas,20,768,'Read        Select             Up        Down')
    raw=b''.join(b'\0'+canvas[y*480:(y+1)*480] for y in range(800))
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',480,800,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] in ('--preview','--expanded-preview'):
        preview(sys.argv[2], sys.argv[1] == '--expanded-preview')
    else:
        unittest.main()
