"""Flash the checked, bundled C3 image. Does not enable servo motion."""
import hashlib,json,subprocess,sys
from pathlib import Path
from serial.tools import list_ports
ROOT=Path(__file__).resolve().parent
def checked_images(root=ROOT):
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['flash_files'].items():
        if hashlib.sha256((root/'release'/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('File checksum mismatch: '+name)
    for name,digest in manifest['source_text_sha256'].items():
        if hashlib.sha256((root/name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()!=digest:
            raise ValueError('Custom source detected: '+name+'. Compile/upload your source with Arduino; do not overwrite custom calibration with the original binary.')
    return root/'release'

def command(port,directory):
    cmd=[sys.executable,'-m','esptool','--chip','esp32c3','--port',port,'--baud','460800',
     '--before','usb_reset','--after','watchdog_reset','write_flash','--flash_mode','dio',
     '--flash_freq','80m','--flash_size','4MB']
    for offset,name in [('0x0','bootloader.bin'),('0x8000','partitions.bin'),('0xe000','boot_app0.bin'),('0x10000','application.bin')]:
        cmd.extend([offset,str(directory/name)])
    return cmd

def main():
    directory=checked_images()
    ports=list(list_ports.comports())
    for p in ports:print(p.device,p.description)
    print('关闭窗口，底座平放、两轴直立静止。首次烧录先断开舵机独立电源。仅适用于 ESP32-C3。')
    port=input('输入 C3 的 COM 端口（例如 COM18），按回车开始烧录：').strip().upper()
    if port not in {p.device.upper() for p in ports}:raise ValueError('端口不存在，未烧录。')
    subprocess.run(command(port,directory),check=True)
    print('烧录完成。平放静止约 40 秒。若停留在下载模式，轻按右侧 RST，再打开窗口连接。')

if __name__=='__main__':
    try:main()
    except Exception as exc:print('ERROR:',exc);sys.exit(1)
