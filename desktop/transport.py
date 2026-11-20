import queue
import threading
import time
import serial
from data import Identity, parse

ALLOWED={'START','PAUSE','ZERO','CAL','STATUS','STOP','HOLD','TEST1','TEST2','POLICY','GETUP'}

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
        port.port=self.port_name;port.dtr=False;port.rts=False
        try:
            port.open();port.reset_input_buffer();port.rts=True;time.sleep(.15);port.rts=False
            self.emit('opened',self.port_name)
            heartbeat=0;started=time.monotonic();buffer=bytearray()
            while not self.stop_event.is_set():
                now=time.monotonic()
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
                    if self.identity.verified and not self.verified:
                        self.verified=True;self.emit('verified',self.port_name)
                    try:row=parse(line,firmware=self.identity.firmware_name) if self.verified else None
                    except ValueError as exc:
                        port.write(b'STOP\n');raise RuntimeError(str(exc)) from exc
                    self.emit('line',(line,row))
                if not self.verified and now-started>10:raise RuntimeError('未收到匹配的记录固件，请确认串口和已烧录程序')
        except Exception as exc:self.emit('error',str(exc))
        finally:
            if port.is_open:
                try:
                    if self.verified:port.write(b'STOP\n');port.flush()
                except serial.SerialException:pass
                port.close()
            self.verified=False;self.emit('closed',self.port_name)
