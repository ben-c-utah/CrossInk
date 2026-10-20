"""PC-only selection and confirmation tests; no device or build tools used."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import stage_latest as h


class StageLatestTest(unittest.TestCase):
    def artifact(self, root, name='build', **changes):
        folder = root / name
        folder.mkdir()
        binary = folder / 'firmware.bin'
        binary.write_bytes(b'firmware')
        meta = dict(target='x4-pro', buildResult='SUCCESS', buildSourceDirty=False,
                    archivedUtc='2026-10-19T20:00:00+00:00', binary=binary.name,
                    sizeBytes=8, sha256=hashlib.sha256(b'firmware').hexdigest(),
                    displayIdentity='CrossInk test v11')
        meta.update(changes)
        manifest = folder / 'manifest.json'
        manifest.write_text(json.dumps(meta), encoding='utf-8')
        return manifest

    def test_timestamp_selection_ignores_mtime_and_invalid_newer(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            old = self.artifact(root, 'old', archivedUtc='2026-10-18T20:00:00Z')
            latest = self.artifact(root, 'latest')
            self.artifact(root, 'dirty', buildSourceDirty=True, archivedUtc='2027-01-01T00:00:00Z')
            os.utime(latest, (1, 1))
            os.utime(old, (2000000000, 2000000000))
            self.assertEqual(h.select_latest(root)[1], latest)

    def test_rejects_unsafe_or_incomplete_manifests(self):
        cases = [dict(target='default'), dict(buildResult='FAILED'),
                 dict(buildSourceDirty=True), dict(buildSourceDirty='false'),
                 dict(sdkDirtyAtBuild=True), dict(archivedUtc='bad'),
                 dict(archivedUtc='2026-10-19T00:00:00'), dict(binary='../fw.bin'),
                 dict(binary='missing.bin'), dict(sizeBytes=9), dict(sizeBytes=True),
                 dict(sha256='0' * 64), dict(sha256='bad')]
        for changes in cases:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                self.artifact(root, **changes)
                with self.assertRaises(ValueError):
                    h.select_latest(root)

    def test_malformed_and_missing_required_metadata_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = self.artifact(root)
            for content in ['{', '[]', '{}']:
                manifest.write_text(content)
                with self.assertRaises(ValueError):
                    h.select_latest(root)

    def test_confirmation_success_and_remembered_address(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = self.artifact(root)
            state = root / 'local' / 'ip.txt'
            output = io.StringIO()
            with patch('builtins.input', side_effect=['192.168.0.20', 'yes']), \
                    patch.object(h.ble_lab_pc, 'stage', return_value={'result': 'ALREADY STAGED AND READ-BACK VERIFIED'}) as stage, \
                    contextlib.redirect_stdout(output):
                h.run(root, state)
            stage.assert_called_once_with('http://192.168.0.20', manifest.parent / 'firmware.bin', manifest, None)
            self.assertEqual(state.read_text().strip(), '192.168.0.20')
            self.assertIn('ALREADY STAGED AND READ-BACK VERIFIED', output.getvalue())
            self.assertIn('SD firmware picker filename for a new upload: CrossInk-BLE-X4Pro-V11-', output.getvalue())
            for value in ['CrossInk test v11', 'firmware.bin', 'X4 Pro', '192.168.0.20']:
                self.assertIn(value, output.getvalue())
            with patch('builtins.input', side_effect=['', 'no']), patch.object(h.ble_lab_pc, 'stage') as stage:
                h.run(root, state)
                stage.assert_not_called()

    def test_failure_does_not_save_ip(self):
        for error in [urllib.error.URLError('connection refused'), ValueError('read-back mismatch')]:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                self.artifact(root)
                state = root / 'ip.txt'
                with patch('builtins.input', side_effect=['192.168.0.20', 'yes']), \
                        patch.object(h.ble_lab_pc, 'stage', side_effect=error):
                    with self.assertRaises(ValueError) as caught:
                        h.run(root, state)
                if isinstance(error, urllib.error.URLError):
                    self.assertIn('File Transfer server unavailable', str(caught.exception))
                self.assertFalse(state.exists())

    def test_http_rejection_is_not_reported_as_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.artifact(root)
            error = urllib.error.HTTPError('http://192.168.0.20/upload', 400, 'Bad Request',
                                           {}, io.BytesIO(b'destination already exists'))
            with patch('builtins.input', side_effect=['192.168.0.20', 'yes']), \
                    patch.object(h.ble_lab_pc, 'stage', side_effect=error):
                with self.assertRaises(ValueError) as caught:
                    h.run(root, root / 'ip.txt')
            self.assertIn('HTTP 400', str(caught.exception))
            self.assertIn('destination already exists', str(caught.exception))
            self.assertNotIn('unavailable', str(caught.exception))
            self.assertFalse((root / 'ip.txt').exists())

    def test_invalid_ip_never_uploads(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.artifact(root)
            with patch('builtins.input', return_value='example.com/update'), patch.object(h.ble_lab_pc, 'stage') as stage:
                with self.assertRaises(ValueError):
                    h.run(root, root / 'ip.txt')
                stage.assert_not_called()

    def test_change_during_confirmation_never_uploads(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = self.artifact(root)

            def answer(prompt):
                if 'IP address' in prompt:
                    return '192.168.0.20'
                (manifest.parent / 'firmware.bin').write_bytes(b'changed!')
                return 'yes'

            with patch('builtins.input', side_effect=answer), patch.object(h.ble_lab_pc, 'stage') as stage:
                with self.assertRaises(ValueError):
                    h.run(root, root / 'ip.txt')
                stage.assert_not_called()


if __name__ == '__main__':
    unittest.main()
