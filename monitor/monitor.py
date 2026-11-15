"""Read UART CSV from imu_reader. No commands are sent to the device."""
import argparse
import csv
import datetime
import json
import math
from pathlib import Path
import time
import serial
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parent
FIELDS = ['ms','ax_g','ay_g','az_g','gx_dps','gy_dps','gz_dps','acc_norm_g','roll_acc_deg','pitch_acc_deg']

def parse_sample(line):
    parts = line.strip().split(',')
    if len(parts) != len(FIELDS):
        return None
    try:
        values = [float(x) for x in parts]
    except ValueError:
        return None
    if not all(math.isfinite(x) for x in values[:8]):
        return None
    return dict(zip(FIELDS, values))

class Reader:
    def __init__(self, port):
        self.serial = serial.Serial(port=None, baudrate=115200, timeout=0)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()
        self.buffer = b''
        logs = ROOT / 'logs'
        logs.mkdir(exist_ok=True)
        self.path = logs / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.log')
        self.log = self.path.open('w', encoding='utf-8')

    def poll(self):
        self.buffer += self.serial.read(min(self.serial.in_waiting, 8192))
        lines = []
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            text = line.decode('utf-8', errors='replace').strip()
            self.log.write(text+'\n')
            lines.append(text)
        if len(self.buffer) > 16384:
            self.buffer = b''
        self.log.flush()
        return lines

    def close(self):
        self.serial.close()
        self.log.close()

def capture(port, seconds):
    reader = Reader(port)
    samples = []
    try:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            for line in reader.poll():
                print(line, flush=True)
                sample = parse_sample(line)
                if sample is not None:
                    samples.append(sample)
            time.sleep(.02)
    finally:
        reader.close()
    report = {'port':port, 'seconds':seconds, 'valid_samples':len(samples), 'log':str(reader.path)}
    if samples:
        report['first'] = samples[0]
        report['last'] = samples[-1]
        report['mean_acc_norm_g'] = sum(x['acc_norm_g'] for x in samples)/len(samples)
        report['timestamp_increased'] = all(b['ms'] > a['ms'] for a,b in zip(samples,samples[1:]))
    (ROOT / 'latest_capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if samples else 2

def gui(port):
    import tkinter as tk
    from tkinter import ttk
    win = tk.Tk()
    win.title('ESP32-S3 IMU 数据查看 — SDA=4 / SCL=5')
    win.geometry('760x660')
    reader = None
    last_received = 0.0
    last_ms = None
    port_var = tk.StringVar(value=port)
    status = tk.StringVar(value='未连接；只接 ESP32 和 IMU，保持舵机断电。')
    toolbar = ttk.Frame(win, padding=12); toolbar.pack(fill='x')
    ttk.Label(toolbar,text='串口').pack(side='left')
    ports = [p.device for p in list_ports.comports() if p.vid is not None]
    ttk.Combobox(toolbar,textvariable=port_var,values=ports,width=12).pack(side='left',padx=8)
    def disconnect():
        nonlocal reader, last_received, last_ms
        if reader:
            reader.close(); reader = None
        last_received = 0; last_ms = None
        status.set('已断开')
    def connect():
        nonlocal reader
        disconnect()
        try:
            reader = Reader(port_var.get())
            status.set('串口已打开，等待 IMU 数据；必要时按 ESP32 的 RST。')
        except Exception as exc:
            status.set(f'连接失败：{exc}')
    ttk.Button(toolbar,text='连接',command=connect).pack(side='left')
    ttk.Button(toolbar,text='断开',command=disconnect).pack(side='left',padx=8)
    ttk.Label(win,textvariable=status,wraplength=720,padding=12).pack(fill='x')
    grid = ttk.Frame(win,padding=12);grid.pack(fill='x')
    labels = ['时间 (ms)','加速度 X (g)','加速度 Y (g)','加速度 Z (g)',
              '角速度 X (°/s)','角速度 Y (°/s)','角速度 Z (°/s)',
              '加速度合量 (g)','静态 Roll (°)','静态 Pitch (°)']
    values = {}
    for i, (key,label) in enumerate(zip(FIELDS,labels)):
        row, col = divmod(i,2)
        ttk.Label(grid,text=label,width=22).grid(row=row,column=col*2,sticky='w',pady=6)
        value = tk.StringVar(value='—'); values[key] = value
        ttk.Label(grid,textvariable=value,width=12,font=('Consolas',14)).grid(row=row,column=col*2+1,sticky='w')
    ttk.Label(win,text='静止时合量应接近 1 g，角速度接近 0。倾角仅供静态检查，不是融合姿态；没有航向角。',wraplength=720,padding=12).pack(fill='x')
    output = tk.Text(win,height=13,font=('Consolas',10));output.pack(fill='both',expand=True,padx=12,pady=8)
    def tick():
        nonlocal last_received,last_ms
        if reader:
            try:
                for line in reader.poll():
                    sample = parse_sample(line)
                    if sample:
                        if sample['ms'] == last_ms:
                            continue
                        last_ms = sample['ms']; last_received=time.monotonic()
                        status.set('正在接收实时数据（原始测量，尚未标定）')
                        for key,value in sample.items(): values[key].set(f'{value:.3f}')
                    else:
                        output.insert('end',line+'\n');output.see('end')
                        if int(output.index('end-1c').split('.')[0]) > 300: output.delete('1.0','100.0')
                        if 'ERROR' in line or 'STOP' in line: status.set(line)
                if last_received and time.monotonic()-last_received > 1.5:
                    status.set('数据已过期：超过 1.5 秒没有新样本，请检查连接。')
                    for value in values.values(): value.set('—')
            except Exception as exc:
                disconnect(); status.set(f'读取失败：{exc}')
        win.after(50,tick)
    def close(): disconnect();win.destroy()
    win.protocol('WM_DELETE_WINDOW',close)
    connect();tick();win.mainloop()

if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',default='COM15')
    ap.add_argument('--seconds',type=float,default=0)
    args=ap.parse_args()
    if args.seconds > 0:
        raise SystemExit(capture(args.port,args.seconds))
    gui(args.port)
