"""Verify and flash the ESP32-S3 V21 per-device-zero image; never start motors."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / 'firmware' / 'prebuilt' / 'v21'


def checked_images():
    manifest = json.loads((IMAGE_DIR / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['firmware'] != 'HD1910_RECOVERY_V21' or manifest['board'] != 'ESP32-S3 N16R8':
        raise ValueError('V21 image manifest does not match the expected ESP32-S3 board')
    for name, expected in manifest['files'].items():
        if hashlib.sha256((IMAGE_DIR / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Firmware checksum mismatch: ' + name)
    return manifest


def command(port, manifest):
    args = [sys.executable, '-m', 'esptool', '--chip', 'esp32s3', '--port', port,
            '--baud', '460800', '--before', 'default_reset', '--after', 'hard_reset',
            'write_flash', '-z', '--flash_size', '16MB']
    for name, offset in manifest['flash_offsets'].items():
        args.extend([offset, str(IMAGE_DIR / name)])
    return args


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--port')
    args = parser.parse_args()
    manifest = checked_images()
    print('V21 firmware checksums: PASS. Board: ESP32-S3 N16R8.')
    if args.check:
        return
    from serial.tools import list_ports
    usb = {p.device for p in list_ports.comports() if p.vid}
    if not usb:
        raise ValueError('No USB serial port found. Connect the ESP32 UART/COM USB.')
    print('USB serial ports:', ', '.join(sorted(usb)))
    port = args.port or input('ESP32 COM port (example COM3): ').strip()
    if not re.fullmatch(r'COM[1-9][0-9]*', port, re.IGNORECASE) or port.upper() not in usb:
        raise ValueError('Select the detected ESP32 USB COM port')
    print('Close FD and the demonstration window. Keep the base flat and joints upright.')
    print('Disconnect servo power for flashing. The saved joint zero in NVS is retained.')
    if input('Type FLASH to upload; anything else cancels: ').strip() != 'FLASH':
        print('Cancelled.')
        return
    subprocess.run(command(port, manifest), check=True)
    print('Upload completed. Reconnect servo power, open the UI, and capture upright joint zero if not saved.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print('ERROR:', exc)
        sys.exit(1)
