"""Flash the published, hash-checked V20 image. No motor commands."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def checked_images():
    directory=ROOT/'firmware/prebuilt/v20'
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest['files'].items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Firmware checksum mismatch: '+name)
    for name,expected in manifest['source_text_sha256'].items():
        actual=hashlib.sha256((ROOT/name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        if actual!=expected:
            raise ValueError('Custom firmware source detected: '+name+'. Compile/upload with Arduino IDE instead of the original prebuilt image.')
    # Do not overwrite custom joint calibration with the original prebuilt image.
    source=(ROOT/'firmware/policy_shadow/joint_limits.h').read_text(encoding='utf-8')
    desktop=(ROOT/'desktop/data.py').read_text(encoding='utf-8')
    if not re.search(r'ZERO\[2\]\s*=\s*\{337,2872\}',source) or not re.search(r'JOINT_ZEROS\s*=\s*\{1:337,2:2872\}',desktop):
        raise ValueError('Custom joint zeros detected. Compile/upload your source with Arduino IDE; do not use the original prebuilt image.')
    return directory,manifest

def command(port,directory,manifest):
    args=[sys.executable,'-m','esptool','--chip','esp32s3','--port',port,'--baud','460800',
          '--before','default_reset','--after','hard_reset','write_flash','-z','--flash_size','16MB']
    for name,offset in manifest['flash_offsets'].items():args.extend([offset,str(directory/name)])
    return args

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--port');args=parser.parse_args()
    directory,manifest=checked_images()
    print('V20 firmware checksums: PASS. Board: ESP32-S3 N16R8, UART/COM USB.')
    if args.check:return
    from serial.tools import list_ports
    ports=list(list_ports.comports())
    for p in ports:print(f'  {p.device}: {p.description}')
    port=args.port or input('ESP32 COM port (example COM3): ').strip()
    if not re.fullmatch(r'COM[1-9][0-9]*',port,re.IGNORECASE):raise ValueError('Use a Windows COM port, e.g. COM3.')
    print('Close FD, Arduino Serial Monitor and the demonstration window.')
    print('Disconnect servo power. Keep base flat and joints upright. Connect ESP32 UART/COM USB only.')
    print('This overwrites the ESP32 application. Original external flash backups are NOT included.')
    if input('Type FLASH to upload; anything else cancels: ').strip()!='FLASH':
        print('Cancelled.');return
    subprocess.run(command(port,directory,manifest),check=True)
    print('Upload completed. Now follow docs/05-first-run.md; keep base flat while zero is captured.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        print('ERROR:',exc);sys.exit(1)
