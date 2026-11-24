"""C3 identity handshake, STOP, stable position readings. No motion or zero writes."""
import json,sys,time
from pathlib import Path
import serial
from serial.tools import list_ports
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
from data import Identity,parse,FW

def main():
    print('关闭展示窗口和 FD。底座平放，两轴真实直立并扶稳。此工具只读并请求 STOP，不启动动作。')
    for p in list_ports.comports():print(p.device,p.description)
    port=serial.Serial();port.port=input('输入 C3 的 COM：').strip().upper()
    port.baudrate=230400;port.timeout=.05;port.write_timeout=.3;port.dtr=True;port.rts=False
    identity=Identity();rows=[];buffer=b'';status=hb=0;stop_sent=False
    try:
        port.open();deadline=time.monotonic()+120
        port.write(b'\nSTATUS\n')
        while time.monotonic()<deadline:
            now=time.monotonic()
            if not identity.verified and now-status>2:port.write(b'\nSTATUS\n');status=now
            if identity.verified and now-hb>.1:port.write(b'HEARTBEAT\n');hb=now
            buffer+=port.read(min(port.in_waiting or 1,8192))
            while b'\n' in buffer:
                raw,buffer=buffer.split(b'\n',1);line=raw.decode('utf-8','replace').strip();identity.feed(line)
                if not identity.verified:continue
                if not stop_sent:port.write(b'STOP\n');stop_sent=True
                row=parse(line,firmware=identity.firmware_name)
                if not row or row['motion_phase']!=0 or row['motion_off']!=1:continue
                if not all(row[f's{i}_state']==1 and row[f's{i}_torque']==0 and row[f's{i}_age_ms']<=80 for i in (1,2)):continue
                rows.append(row)
                if len(rows)>=30:break
            if len(rows)>=30:break
    finally:
        if port.is_open:
            if identity.verified:port.write(b'STOP\n')
            port.close()
    if len(rows)<30:raise RuntimeError('未读到30帧有效卸力反馈，检查供电、ID、A/A 和接线。')
    if any(max(r[f's{i}_position'] for r in rows)-min(r[f's{i}_position'] for r in rows)>8 for i in (1,2)):
        raise RuntimeError('采样时关节移动，保持真实直立姿态后重测。')
    positions={str(i):round(sum(r[f's{i}_position'] for r in rows)/len(rows)) for i in (1,2)}
    result={'firmware':identity.firmware_name,'positions':positions,'samples':len(rows),'automatically_applied':False}
    (ROOT/'local_joint_zero.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('上 ID1 =',positions['1'],'；下 ID2 =',positions['2'])
    print('已保存 local_joint_zero.json，未修改程序零位。参照 docs/06-calibration.md 同步两处并重新编译。')

if __name__=='__main__':
    try:main()
    except Exception as exc:print('ERROR:',exc);sys.exit(1)
