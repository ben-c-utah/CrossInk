"""CrossInk BLE Lab: live serial snapshots and existing File Transfer routes.

No firmware installation, serial-port access, guessed endpoint or monitor shutdown.
"""
import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

LIMIT = 8 * 1024 * 1024

def shared_read(path):
    if os.name != 'nt':
        return path.open('rb')
    # Monitor may still hold the file. Request sharing for reads/writes/deletion;
    # never close its port or assume the writer has stopped.
    import msvcrt
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                              ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    api.CreateFileW.restype = ctypes.c_void_p
    handle = api.CreateFileW(str(path.resolve()), 0x80000000, 7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except Exception:
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        api.CloseHandle(handle)
        raise
    return os.fdopen(fd, 'rb')

def decode(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16', errors='replace')
    if data[:1024].count(b'\0') > len(data[:1024]) // 4:
        return data.decode('utf-16-le', errors='replace')
    return data.decode('utf-8-sig', errors='replace')

def snapshot(path, destination):
    before = path.stat()
    with shared_read(path) as source:
        source.seek(max(0, before.st_size - LIMIT))
        raw = source.read(min(before.st_size, LIMIT))
    destination.write_text(decode(raw), encoding='utf-8')
    after = path.stat()
    text = destination.read_text(encoding='utf-8')
    identities = re.findall(r'identity=(CrossInk BLE[^\r\n]+)', text)
    return {'source': str(path.resolve()), 'sourceBytes': before.st_size,
            'snapshotBytes': len(raw), 'tailLimited': before.st_size > LIMIT,
            'modifiedUtc': dt.datetime.fromtimestamp(before.st_mtime, dt.timezone.utc).isoformat(),
            'ageSeconds': round(dt.datetime.now().timestamp() - before.st_mtime, 1),
            'changedDuringRead': (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns),
            'observedFirmwareIdentity': identities[-1] if identities else 'unverified; no identity marker in snapshot'}

def base_url(value):
    u = urllib.parse.urlsplit(value)
    if u.scheme not in ('http', 'https') or not u.hostname or u.query or u.fragment or u.path not in ('', '/'):
        raise ValueError('Use the File Transfer root URL shown on the device, e.g. http://192.168.1.50')
    return value.rstrip('/')

def download(url, remote, destination, limit=16384, timeout=30):
    address = base_url(url) + '/download?' + urllib.parse.urlencode({'path': remote})
    with urllib.request.urlopen(address, timeout=timeout) as response, destination.open('wb') as output:
        total = 0
        for block in iter(lambda: response.read(65536), b''):
            total += len(block)
            if total > limit:
                raise ValueError('Download exceeds expected size limit')
            output.write(block)
    return total

def http_error_details(exc):
    with exc:
        detail = exc.read(4096).decode('utf-8', errors='replace').strip()
    return f'HTTP {exc.code} {exc.reason} at {exc.url}' + (f': {detail}' if detail else '')


def verify_staged(url, remote, size, expected):
    """Return False only for an explicit 404; all other failures stop staging."""
    address = base_url(url) + '/download?' + urllib.parse.urlencode({'path': '/' + remote})
    try:
        response = urllib.request.urlopen(address, timeout=180)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            exc.close()
            return False
        raise ValueError(http_error_details(exc)) from exc
    hasher, total = hashlib.sha256(), 0
    with response:
        for block in iter(lambda: response.read(65536), b''):
            total += len(block)
            if total > size:
                raise ValueError(f'Remote /{remote} size mismatch; refusing to overwrite or delete')
            hasher.update(block)
    if total != size or hasher.hexdigest() != expected:
        raise ValueError(f'Remote /{remote} size/SHA-256 mismatch; refusing to overwrite or delete')
    return True


def staging_names(meta, remote=None):
    """New picker name first; retain the historic SHA-only name as a read-only alias."""
    if remote is not None:
        names = (remote,)
    else:
        digest = str(meta['sha256']).lower()
        if not re.fullmatch(r'[0-9a-f]{64}', digest) or meta.get('target') != 'x4-pro':
            raise ValueError('Staging names require an X4 Pro manifest and full SHA-256')
        version = meta.get('revision')
        if not version:
            match = re.search(r'\bv(\d+(?:\.\d+)*)', str(meta.get('displayIdentity', '')), re.I)
            version = 'V' + match.group(1) if match else meta.get('upstreamVersion', 'Unversioned')
        if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,47}', version):
            raise ValueError('Manifest version must be a simple readable version token')
        names = (f'CrossInk-BLE-X4Pro-{version}-{digest[:8]}.bin', f'CrossInk-{digest[:12]}.bin')
    if any(not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*\.bin', name) for name in names):
        raise ValueError('--name must be a simple root .bin filename')
    return names


def stage(url, binary, manifest, remote):
    meta = json.loads(manifest.read_text(encoding='utf-8-sig'))
    expected = str(meta['sha256']).lower()
    payload = binary.read_bytes()
    if len(payload) > 6553600 or len(payload) != meta['sizeBytes'] or hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError('Binary size/hash does not match the supplied build manifest')
    if meta.get('target') != 'x4-pro':
        raise ValueError('Manifest target must be x4-pro')
    names = staging_names(meta, remote)
    remote = names[0]
    result = {'remotePath': '/' + remote, 'bytes': len(payload), 'sha256': expected,
              'result': 'ALREADY STAGED AND READ-BACK VERIFIED'}
    for name in names:
        if verify_staged(url, name, len(payload), expected):
            result['remotePath'] = '/' + name
            return result
    # Existing multipart /upload?path=/ route. No update/install endpoint.
    boundary = 'CrossInkBleLabFileTransferBoundary'
    body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="' + remote +
            '"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() + payload + ('\r\n--' + boundary + '--\r\n').encode()
    request = urllib.request.Request(base_url(url) + '/upload?path=%2F', data=body, method='POST',
                                    headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response.read(16384)
    except urllib.error.HTTPError as exc:
        code = exc.code
        details = http_error_details(exc)
        # Another uploader may have created the file after our initial 404.
        if code in (400, 409):
            try:
                if verify_staged(url, remote, len(payload), expected):
                    return result
            except (OSError, ValueError) as verification:
                raise ValueError(f'{details}; collision verification failed: {verification}') from verification
        raise ValueError(details) from exc
    # Independently verify what the server stored. Never trust just HTTP 200.
    if not verify_staged(url, remote, len(payload), expected):
        raise ValueError('Staging verification FAILED: remote file missing; do not install this file')
    result['result'] = 'STAGED AND READ-BACK VERIFIED ONLY; installation requires device confirmation'
    return result

def collect(args):
    logs = sorted(args.logs_dir.glob('device-monitor*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs and not args.url: raise ValueError('No device-monitor*.log in ' + str(args.logs_dir))
    stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder = args.output / ('ble-session-' + stamp)
    folder.mkdir(parents=True, exist_ok=False)
    info = snapshot(logs[0], folder / 'serial-snapshot.txt') if logs else {'source': None, 'ageSeconds': None, 'observedFirmwareIdentity': 'unverified; no serial log'}
    candidate = args.artifact / 'manifest.json' if args.artifact else None
    if candidate is None:
        available = list((Path(__file__).resolve().parents[1] / 'artifacts').glob('*/manifest.json'))
        if available: candidate = max(available, key=lambda p: p.stat().st_mtime)
    if candidate:
        shutil.copyfile(candidate, folder / 'candidate-build-manifest.json')
        info['manifestNote'] = 'Candidate build metadata; observed serial identity is independent and may differ.'
    if args.url:
        info['deviceDownloads'] = {}
        for remote in ['ble-lab-diagnostics.txt', 'ble-lab-crash.txt']:
            try:
                info['deviceDownloads'][remote] = download(args.url, '/' + remote, folder / remote,
                                                         timeout=getattr(args, 'download_timeout', 30))
                if remote == 'ble-lab-diagnostics.txt':
                    exported = re.search(r'^identity=(.+)$', (folder / remote).read_text(encoding='utf-8', errors='replace'), re.M)
                    info['savedExportIdentity'] = exported.group(1) if exported else 'unverified'
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and remote == 'ble-lab-crash.txt':
                    exc.close()
                    info['deviceDownloads'][remote] = 'absent'
                elif getattr(args, 'tolerate_download_errors', False):
                    info['deviceDownloads'][remote] = {'error': http_error_details(exc)}
                    (folder / remote).unlink(missing_ok=True)
                else:
                    raise
            except (OSError, ValueError, urllib.error.URLError) as exc:
                if not getattr(args, 'tolerate_download_errors', False):
                    raise
                info['deviceDownloads'][remote] = {'error': str(exc)}
                (folder / remote).unlink(missing_ok=True)
    (folder / 'session.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    print(folder)
    print('Log age:', info['ageSeconds'], 'seconds; identity:', info['observedFirmwareIdentity'])
    if info['ageSeconds'] is not None and info['ageSeconds'] > 120: print('WARNING: newest log is stale; verify serial capture is running.')
    return folder

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('collect', help='snapshot newest serial log; optionally fetch saved device export')
    c.add_argument('--logs-dir', type=Path, default=Path.home() / 'logs')
    c.add_argument('--output', type=Path, default=Path.home() / 'logs' / 'ble-sessions')
    c.add_argument('--artifact', type=Path, help='candidate artifact directory containing manifest.json')
    c.add_argument('--url', help='explicit existing File Transfer root URL')
    s = sub.add_parser('stage', help='upload firmware to SD and verify read-back; NEVER install')
    s.add_argument('--url', required=True)
    s.add_argument('--binary', type=Path, required=True)
    s.add_argument('--manifest', type=Path, required=True)
    s.add_argument('--name', help='optional root .bin filename; default includes device, version and SHA prefix')
    args = parser.parse_args()
    try:
        if args.command == 'collect': collect(args)
        else: print(json.dumps(stage(args.url, args.binary, args.manifest, args.name), indent=2))
    except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
        parser.exit(1, 'ERROR: ' + str(exc) + '\nNo firmware installation was requested.\n')

if __name__ == '__main__': main()
