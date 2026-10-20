"""Collect diagnostics and reveal an immutable, full serial capture in Explorer."""
import argparse
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys

import ble_lab_pc

ADDRESS_FILE = Path.home() / '.crossink' / 'stage-latest-ip.txt'


def remembered_url(path=ADDRESS_FILE):
    try:
        ip = ipaddress.ip_address(path.read_text(encoding='utf-8').strip())
        return 'http://' + (f'[{ip}]' if ip.version == 6 else str(ip))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        print(f'WARNING: remembered File Transfer IP unavailable: {exc}')
        return None


def full_serial_copy(source, destination):
    before = source.stat()
    temporary = destination.with_suffix('.part')
    created = False
    try:
        with ble_lab_pc.shared_read(source) as stream, temporary.open('xb') as output:
            created = True
            remaining = before.st_size
            while remaining:
                block = stream.read(min(65536, remaining))
                if not block:
                    raise ValueError('Serial log shrank during capture; no complete copy produced')
                output.write(block)
                remaining -= len(block)
        # Session directories are unique. Never replace a pre-existing attachment.
        if destination.exists():
            raise ValueError('Full capture destination already exists')
        temporary.rename(destination)
    finally:
        if created:
            temporary.unlink(missing_ok=True)
    after = source.stat()
    return {'path': str(destination.resolve()), 'bytes': before.st_size,
            'capturedThroughUtc': dt.datetime.fromtimestamp(before.st_mtime, dt.timezone.utc).isoformat(),
            'sourceChangedDuringRead': (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns),
            'note': 'Complete byte-for-byte log prefix as of capture start; not tail-limited. Monitor may continue appending.'}


def reveal(path):
    if os.name != 'nt':
        print('Explorer reveal is available on Windows; attach:', path)
        return
    subprocess.Popen(['explorer.exe', '/select,', str(path.resolve())])


def run(args):
    if not args.url and not args.no_wifi:
        args.url = remembered_url()
    if args.no_wifi:
        args.url = None
    args.tolerate_download_errors = True
    args.download_timeout = 5
    folder = ble_lab_pc.collect(args)
    receipt_path = folder / 'session.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    attachment = None
    if receipt.get('source'):
        source = Path(receipt['source'])
        attachment = folder / (source.stem + '-full.log')
        receipt['fullSerialCapture'] = full_serial_copy(source, attachment)
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print('\nDiagnostic session:', folder.resolve())
    print('Collected files:')
    for file in sorted(folder.iterdir()):
        if file.is_file():
            print(f'  {file.name}: {file.stat().st_size:,} bytes')
    downloads = receipt.get('deviceDownloads')
    if downloads is None:
        print('Wi-Fi diagnostics: not requested (no address, or --no-wifi).')
    else:
        print('Wi-Fi diagnostics from', args.url)
        for name, result in downloads.items():
            if isinstance(result, int):
                print(f'  {name}: DOWNLOADED ({result:,} bytes)')
            elif isinstance(result, dict):
                print(f"  {name}: NOT DOWNLOADED — {result['error']}")
            else:
                print(f'  {name}: {result}')
        print('Downloaded diagnostics are saved device exports; they may predate this serial capture.')
    if attachment:
        print('ATTACH TO CHATGPT:', attachment.resolve())
        print(receipt['fullSerialCapture']['note'])
        if not args.no_reveal:
            try:
                reveal(attachment)
            except OSError as exc:
                print(f'WARNING: capture saved, but Explorer could not open: {exc}')
    else:
        print('No serial log found; no full serial attachment available.')
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--logs-dir', type=Path, default=Path.home() / 'logs')
    parser.add_argument('--output', type=Path, default=Path.home() / 'logs' / 'ble-sessions')
    parser.add_argument('--artifact', type=Path)
    parser.add_argument('--url', help='File Transfer URL; otherwise use the last successfully staged IP')
    parser.add_argument('--no-wifi', action='store_true')
    parser.add_argument('--no-reveal', action='store_true')
    try:
        run(parser.parse_args())
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f'ERROR: {exc}\nSerial monitor and device were not stopped.\n')


if __name__ == '__main__':
    main()
