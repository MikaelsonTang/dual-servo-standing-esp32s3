import queue
import threading
import time
import serial
from data import Identity, parse, FW

ALLOWED={'START','PAUSE','ZERO','CAL','STATUS','STOP','HOLD','TEST1','TEST2','POLICY','GETUP','IMURESET','JOINTZERO'}

def require_current_firmware(line,identity):
    if '# FW=' in line and identity.firmware_name != FW:
        raise RuntimeError(f'固件版本不匹配：本窗口需要 {FW}，设备报告 {line}。请使用同一最新版文件夹里的 01_flash.cmd 和 02_open_demo.cmd')

class Link(threading.Thread):
    def __init__(self,port,ui_required=False):
        super().__init__(daemon=True)
        self.port_name=port;self.events=queue.Queue(maxsize=10000);self.commands=queue.Queue()
        self.stop_event=threading.Event();self.identity=Identity();self.verified=False
        self.emergency=threading.Event();self.ui_required=ui_required;self.last_ui=time.monotonic()
    def touch(self):self.last_ui=time.monotonic()
    def send(self,command):
        if command not in ALLOWED:raise ValueError('Unsupported command')
        if command in ('STOP','PAUSE'):
            with self.commands.mutex:self.commands.queue.clear()
            self.emergency.set();return
        self.commands.put(command)
    def emit(self,kind,value):
        # GUI falls behind: stop rather than silently drop the recorded stream.
        try:self.events.put((kind,value),timeout=.05)
        except queue.Full:self.stop_event.set()
    def run(self):
        port=serial.Serial(port=None,baudrate=230400,timeout=.03,write_timeout=.2)
        port.port=self.port_name;port.dtr=True;port.rts=False
        try:
            port.open();port.reset_input_buffer();port.write(b'STATUS\n')
            self.emit('opened',self.port_name)
            heartbeat=0;started=time.monotonic();last_status=started;buffer=bytearray()
            while not self.stop_event.is_set():
                now=time.monotonic()
                if not self.verified and now-last_status>2:
                    port.write(b'STATUS\n');last_status=now
                if self.emergency.is_set() and self.verified:
                    port.write(b'STOP\n');self.emergency.clear();self.emit('sent','STOP')
                ui_alive=not self.ui_required or now-self.last_ui<.3
                if self.verified and ui_alive and now-heartbeat>.1:
                    port.write(b'HEARTBEAT\n');heartbeat=now
                while not self.commands.empty():
                    cmd=self.commands.get_nowait()
                    if self.verified and ui_alive:port.write((cmd+'\n').encode('ascii'));self.emit('sent',cmd)
                    else:self.emit('notice','固件身份尚未确认，指令未发送')
                buffer.extend(port.read(min(port.in_waiting or 1,8192)))
                if len(buffer)>32768:raise RuntimeError('串口数据行过长')
                while b'\n' in buffer:
                    line,_,tail=buffer.partition(b'\n');buffer[:]=tail
                    line=line.decode('utf-8',errors='replace').strip()
                    if not line:continue
                    if '# FW=' in line and self.verified:
                        self.verified=False;started=time.monotonic()
                        self.emit('restart','设备重新报告固件身份，重新核对版本')
                    self.identity.feed(line)
                    require_current_firmware(line,self.identity)
                    if self.identity.verified and not self.verified:
                        self.verified=True;self.emit('verified',self.port_name)
                    try:row=parse(line,firmware=self.identity.firmware_name) if self.verified else None
                    except ValueError as exc:
                        port.write(b'STOP\n');raise RuntimeError(str(exc)) from exc
                    self.emit('line',(line,row))
                if not self.verified and now-started>120:raise RuntimeError('未收到匹配的记录固件，请确认串口和已烧录程序')
        except Exception as exc:self.emit('error',str(exc))
        finally:
            if port.is_open:
                try:
                    if self.verified:port.write(b'STOP\n');port.flush()
                except serial.SerialException:pass
                port.close()
            self.verified=False;self.emit('closed',self.port_name)
