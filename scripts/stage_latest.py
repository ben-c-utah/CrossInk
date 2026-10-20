"""Select a validated X4 Pro artifact and stage it only after confirmation."""
import datetime as dt
import ipaddress
import json
from pathlib import Path
import re
import sys
import urllib.error

import ble_lab_pc

ARTIFACTS = Path(__file__).resolve().parents[1] / 'artifacts'
STATE = Path.home() / '.crossink' / 'stage-latest-ip.txt'


def validate(manifest):
    meta = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if not isinstance(meta, dict):
        raise ValueError('Manifest must be an object')
    if (meta.get('target') != 'x4-pro' or meta.get('buildResult') != 'SUCCESS'
            or meta.get('buildSourceDirty') is not False
            or meta.get('sdkDirtyAtBuild', False) is not False):
        raise ValueError('Requires a successful, clean X4 Pro build')
    # Existing artifact manifests record the build archive timestamp here.
    timestamp = dt.datetime.fromisoformat(meta['archivedUtc'].replace('Z', '+00:00'))
    if timestamp.utcoffset() is None:
        raise ValueError('Build timestamp must include a timezone')
    name = meta['binary']
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*\.bin', name):
        raise ValueError('Binary must be a simple .bin filename')
    binary = (manifest.parent / name).resolve()
    if binary.parent != manifest.parent.resolve():
        raise ValueError('Binary must remain in its artifact directory')
    size = meta['sizeBytes']
    if type(size) is not int or not 0 < size <= 6553600:
        raise ValueError('Invalid binary size')
    digest = meta['sha256']
    if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise ValueError('Invalid SHA-256')
    if binary.stat().st_size != size:
        raise ValueError('Binary size mismatch')
    import hashlib
    if hashlib.sha256(binary.read_bytes()).hexdigest() != digest.lower():
        raise ValueError('Binary SHA-256 mismatch')
    return timestamp, binary, meta


def select_latest(artifacts):
    candidates = []
    for manifest in sorted(artifacts.rglob('manifest.json')):
        try:
            if not manifest.resolve().is_relative_to(artifacts.resolve()):
                raise ValueError('Manifest outside artifacts')
            stamp, binary, meta = validate(manifest)
            candidates.append((stamp, manifest, binary, meta))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            print(f'Skipping {manifest}: {exc}')
    if not candidates:
        raise ValueError('No validated successful, clean X4 Pro builds in artifacts')
    return max(candidates, key=lambda item: (item[0], str(item[1])))


def run(artifacts=ARTIFACTS, state=STATE):
    stamp, manifest, binary, meta = select_latest(artifacts)
    try:
        previous = state.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        previous = ''
    address = input(f"X4 Pro Wi-Fi IP address{f' [{previous}]' if previous else ''}: ").strip() or previous
    ip = ipaddress.ip_address(address)
    url = 'http://' + (f'[{ip}]' if ip.version == 6 else str(ip))
    print(f"Version: {meta.get('displayIdentity') or meta.get('revision') or meta.get('upstreamVersion') or 'unspecified'}")
    print(f'File: {binary.name}\nTarget: X4 Pro (x4-pro)\nIP: {ip}\nBuild timestamp: {stamp.isoformat()}')
    print('SD firmware picker filename for a new upload:', ble_lab_pc.staging_names(meta)[0])
    print('Previously staged hash-only files are verified and reused; their existing name is reported below.')
    if input('Stage to SD and verify only? Type yes to confirm: ').strip().lower() != 'yes':
        print('Cancelled; no upload requested.')
        return
    # Revalidate after the prompt, then retain all existing transfer safety checks.
    if validate(manifest) != (stamp, binary, meta):
        raise ValueError('Selected build changed; run Stage Latest again')
    try:
        result = ble_lab_pc.stage(url, binary, manifest, None)
    except urllib.error.HTTPError as exc:
        raise ValueError(ble_lab_pc.http_error_details(exc)) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ValueError(f'X4 Pro File Transfer server unavailable or transfer interrupted at {url}: {exc}. '
                         'Open File Transfer on the X4 Pro and check its Wi-Fi IP. Staging was not verified.') from exc
    print(json.dumps(result, indent=2))
    try:
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(str(ip) + '\n', encoding='utf-8')
    except OSError as exc:
        print(f'WARNING: staging verified, but could not remember IP: {exc}')


def main():
    try:
        run()
    except (OSError, ValueError, KeyError, TypeError, EOFError, KeyboardInterrupt) as exc:
        print(f'ERROR: {exc}\nNo firmware installation was requested.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
