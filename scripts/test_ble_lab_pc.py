"""PC capture tests use an open writer and a local mock of verified file routes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
spec=importlib.util.spec_from_file_location('helper',Path(__file__).with_name('ble_lab_pc.py'))
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
class HelperTest(unittest.TestCase):
    def test_read_live_log_and_decode_utf16(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'device-monitor-live.log';out=Path(d)/'snapshot.txt'
            with p.open('wb') as writer:
                writer.write('identity=CrossInk BLE v10-dev abc123\r\n[BLE] largest=94196\r\n'.encode('utf-16'));writer.flush()
                info=h.snapshot(p,out)
                self.assertIn('largest=94196',out.read_text())
                self.assertEqual(info['observedFirmwareIdentity'],'CrossInk BLE v10-dev abc123')
    def test_newest_log_and_manifest_not_assumed_flashed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'device-monitor-old.log';new=root/'device-monitor-new.log'
            old.write_text('old');new.write_text('identity=CrossInk BLE v10-dev actual')
            os.utime(old,(1,1));artifact=root/'artifact';artifact.mkdir();(artifact/'manifest.json').write_text('{"displayIdentity":"candidate"}')
            folder=h.collect(argparse.Namespace(logs_dir=root,output=root/'sessions',artifact=artifact,url=None))
            meta=json.loads((folder/'session.json').read_text())
            self.assertEqual(meta['observedFirmwareIdentity'],'CrossInk BLE v10-dev actual')
            self.assertTrue((folder/'candidate-build-manifest.json').exists())
    def test_bad_target_hash_name_and_url_refused(self):
        with self.assertRaises(ValueError):h.base_url('http://example.test/imaginary-api')
        with tempfile.TemporaryDirectory() as d:
            b=Path(d)/'fw.bin';b.write_bytes(b'firmware');m=Path(d)/'manifest.json'
            m.write_text(json.dumps({'target':'x4-pro','sizeBytes':8,'sha256':'bad'}))
            with self.assertRaises(ValueError):h.stage('http://127.0.0.1',b,m,'fw.bin')
    def test_stage_readback_and_corruption_detection(self):
        class Handler(BaseHTTPRequestHandler):
            payload=b'';corrupt=False
            def log_message(self,*args):pass
            def do_POST(self):
                assert self.path=='/upload?path=%2F'
                raw=self.rfile.read(int(self.headers['Content-Length']))
                Handler.payload=raw.split(b'\r\n\r\n',1)[1].rsplit(b'\r\n--',1)[0]
                self.send_response(200);self.end_headers();self.wfile.write(b'OK')
            def do_GET(self):
                assert self.path.startswith('/download?path=')
                if not Handler.payload:
                    self.send_response(404);self.end_headers();return
                self.send_response(200);self.end_headers();self.wfile.write(b'wrong' if Handler.corrupt else Handler.payload)
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                b=Path(d)/'fw.bin';b.write_bytes(b'firmware-test-data');m=Path(d)/'manifest.json'
                m.write_text(json.dumps({'target':'x4-pro','sizeBytes':b.stat().st_size,'sha256':hashlib.sha256(b.read_bytes()).hexdigest()}))
                result=h.stage('http://127.0.0.1:'+str(server.server_port),b,m,None)
                self.assertIn('VERIFIED ONLY',result['result']);self.assertEqual(Handler.payload,b.read_bytes())
                Handler.corrupt=True
                with self.assertRaises(ValueError):h.stage('http://127.0.0.1:'+str(server.server_port),b,m,'different.bin')
        finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
