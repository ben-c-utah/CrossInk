"""Exercise staging through a local File Transfer server; never install."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
from unittest.mock import patch
import urllib.error

import ble_lab_pc as h


class DuplicateStageTest(unittest.TestCase):
    def exercise(self, initial=None, collision=None, rejection=None, corrupt=False, legacy_only=False):
        payload = b'firmware-test' * 10000
        stored = initial
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                requests.append(('GET', self.path))
                self.assert_route()
                missing = stored is None or (legacy_only and 'CrossInk-BLE-' in self.path)
                self.send_response(404 if missing else 200)
                self.end_headers()
                if not missing:
                    self.wfile.write(stored)

            def assert_route(self):
                assert self.path.startswith('/download?path=%2FCrossInk-')

            def do_POST(self):
                nonlocal stored
                requests.append(('POST', self.path))
                assert self.path == '/upload?path=%2F'
                raw = self.rfile.read(int(self.headers['Content-Length']))
                if collision is not None or rejection:
                    stored = payload if collision == 'same' else collision
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'destination already exists' if collision else b'invalid upload request')
                else:
                    stored = raw.split(b'\r\n\r\n', 1)[1].rsplit(b'\r\n--', 1)[0]
                    if corrupt:
                        stored = b'wrong'
                    self.send_response(200)
                    self.end_headers()

        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                binary = Path(d) / 'firmware.bin'
                binary.write_bytes(payload)
                manifest = Path(d) / 'manifest.json'
                manifest.write_text(json.dumps(dict(target='x4-pro', sizeBytes=len(payload),
                                                    sha256=hashlib.sha256(payload).hexdigest())))
                try:
                    result = h.stage(f'http://127.0.0.1:{server.server_port}', binary, manifest, None)
                except ValueError as exc:
                    result = str(exc)
                return result, requests
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_already_staged_streams_and_never_posts(self):
        result, requests = self.exercise(initial=b'firmware-test' * 10000)
        self.assertEqual(result['result'], 'ALREADY STAGED AND READ-BACK VERIFIED')
        self.assertEqual([r[0] for r in requests], ['GET'])

    def test_missing_uploads_and_reads_back(self):
        result, requests = self.exercise()
        self.assertIn('STAGED AND READ-BACK VERIFIED ONLY', result['result'])
        self.assertEqual([r[0] for r in requests], ['GET', 'GET', 'POST', 'GET'])

    def test_mismatch_never_posts(self):
        for data in [b'wrong', b'x' * 130000, b'x' * 140000]:
            with self.subTest(size=len(data)):
                result, requests = self.exercise(initial=data)
                self.assertIn('refusing to overwrite or delete', result)
                self.assertEqual([r[0] for r in requests], ['GET'])

    def test_collision_verifies_without_retry(self):
        result, requests = self.exercise(collision='same')
        self.assertEqual(result['result'], 'ALREADY STAGED AND READ-BACK VERIFIED')
        self.assertEqual([r[0] for r in requests], ['GET', 'GET', 'POST', 'GET'])

    def test_collision_mismatch_stops_with_http_details(self):
        result, requests = self.exercise(collision=b'other firmware')
        self.assertIn('HTTP 400', result)
        self.assertIn('destination already exists', result)
        self.assertIn('refusing to overwrite or delete', result)
        self.assertEqual([r[0] for r in requests], ['GET', 'GET', 'POST', 'GET'])

    def test_other_400_preserves_response_details(self):
        result, _ = self.exercise(rejection=True)
        self.assertIn('HTTP 400', result)
        self.assertIn('invalid upload request', result)
        self.assertNotIn('unavailable', result)

    def test_corrupt_upload_fails_readback(self):
        result, _ = self.exercise(corrupt=True)
        self.assertIn('mismatch', result)

    def test_legacy_hash_only_file_is_verified_and_reused(self):
        result, requests = self.exercise(initial=b'firmware-test' * 10000, legacy_only=True)
        self.assertEqual(result['result'], 'ALREADY STAGED AND READ-BACK VERIFIED')
        self.assertNotIn('BLE', result['remotePath'])
        self.assertEqual([r[0] for r in requests], ['GET', 'GET'])

    def test_legacy_mismatch_is_not_overwritten(self):
        result, requests = self.exercise(initial=b'other firmware', legacy_only=True)
        self.assertIn('refusing to overwrite or delete', result)
        self.assertEqual([r[0] for r in requests], ['GET', 'GET'])

    def test_readable_name_and_version_validation(self):
        meta = dict(target='x4-pro', revision='V12', sha256='379f229f' + '0' * 56)
        self.assertEqual(h.staging_names(meta)[0], 'CrossInk-BLE-X4Pro-V12-379f229f.bin')
        self.assertEqual(h.staging_names(meta)[1], 'CrossInk-379f229f0000.bin')
        self.assertEqual(h.staging_names(meta, 'manual.bin'), ('manual.bin',))
        meta['revision'] = '../unsafe'
        with self.assertRaises(ValueError):
            h.staging_names(meta)

    def test_unavailable_server_never_uploads(self):
        with patch.object(h.urllib.request, 'urlopen', side_effect=urllib.error.URLError('connection refused')) as request:
            with self.assertRaises(urllib.error.URLError):
                h.verify_staged('http://127.0.0.1', 'fw.bin', 8, '0' * 64)
            self.assertEqual(request.call_count, 1)


if __name__ == '__main__':
    unittest.main()
