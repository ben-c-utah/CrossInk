import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import collect_logs as h


class CollectTest(unittest.TestCase):
    def args(self, root, url=None):
        return argparse.Namespace(logs_dir=root, output=root / 'sessions', artifact=None,
                                  url=url, no_wifi=url is None, no_reveal=False)

    def test_latest_full_copy_receipt_and_explorer_selection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            old = root / 'device-monitor-old.log'
            old.write_bytes(b'old')
            os.utime(old, (1, 1))
            source = root / 'device-monitor-live.log'
            payload = b'A' * (h.ble_lab_pc.LIMIT + 100) + b'\nidentity=CrossInk BLE v12-dev test\n'
            with source.open('wb') as writer:
                writer.write(payload)
                writer.flush()
                with patch.object(h, 'reveal') as reveal, contextlib.redirect_stdout(io.StringIO()) as output:
                    folder = h.run(self.args(root))
            receipt = json.loads((folder / 'session.json').read_text())
            attachment = Path(receipt['fullSerialCapture']['path'])
            self.assertEqual(attachment.read_bytes(), payload)
            self.assertTrue(receipt['tailLimited'])
            reveal.assert_called_once_with(attachment)
            self.assertIn('ATTACH TO CHATGPT:', output.getvalue())
            self.assertIn('Wi-Fi diagnostics: not requested', output.getvalue())
            self.assertEqual(source.read_bytes(), payload)

    def test_wifi_receipt_and_unavailable_wifi_keeps_serial(self):
        for online in [True, False]:
            with self.subTest(online=online), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                (root / 'device-monitor-live.log').write_text('identity=CrossInk BLE v12-dev test')

                def download(url, remote, path, **kwargs):
                    if not online:
                        path.write_bytes(b'partial')
                        raise urllib.error.URLError('server unavailable')
                    path.write_text('identity=CrossInk BLE v12-dev test\n')
                    return path.stat().st_size

                with patch.object(h.ble_lab_pc, 'download', side_effect=download), \
                        patch.object(h, 'reveal'), contextlib.redirect_stdout(io.StringIO()) as output:
                    folder = h.run(self.args(root, 'http://192.168.0.20'))
                self.assertTrue((folder / 'device-monitor-live-full.log').exists())
                self.assertIn('DOWNLOADED' if online else 'NOT DOWNLOADED', output.getvalue())
                self.assertEqual((folder / 'ble-lab-diagnostics.txt').exists(), online)

    def test_explorer_uses_argument_list_and_no_terminal(self):
        with patch.object(h.os, 'name', 'nt'), patch.object(h.subprocess, 'Popen') as popen:
            path = Path('path with spaces/log.log')
            h.reveal(path)
        popen.assert_called_once_with(['explorer.exe', '/select,', str(path.resolve())])

    def test_remembered_ip_and_invalid_ip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'ip.txt'
            self.assertIsNone(h.remembered_url(path))
            path.write_text('192.168.0.20')
            self.assertEqual(h.remembered_url(path), 'http://192.168.0.20')
            path.write_text('http://host/untrusted')
            self.assertIsNone(h.remembered_url(path))

    def test_existing_partial_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / 'source.log'
            source.write_bytes(b'log')
            target = root / 'capture.log'
            target.with_suffix('.part').write_bytes(b'existing work')
            with self.assertRaises(FileExistsError):
                h.full_serial_copy(source, target)
            self.assertEqual(target.with_suffix('.part').read_bytes(), b'existing work')


if __name__ == '__main__':
    unittest.main()
