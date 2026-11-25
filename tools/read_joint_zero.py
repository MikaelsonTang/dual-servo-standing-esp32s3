"""Read S3 firmware identity and joint positions, with explicit STOP. No powered motions."""
import json
from pathlib import Path
import sys
import time
import serial
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from data import Identity,parse

def main():
    portname=input('ESP32 COM port (example COM3): ').strip()
    print('Close the demo window and FD. Put base flat, both joints upright and supported.')
    print('This tool only reads status and sends STOP. It does not change saved zeros.')
    identity=Identity();rows=[];stop_sent=False
    port=serial.Serial(port=None,baudrate=230400,timeout=.1,write_timeout=.3)
    port.port=portname;port.dtr=False;port.rts=False
    try:
        port.open();port.write(b'STATUS\n');deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            line=port.readline().decode('utf-8',errors='replace').strip();identity.feed(line)
            if not identity.verified:continue
            if not stop_sent:port.write(b'STOP\n');stop_sent=True
            row=parse(line,firmware=identity.firmware_name)
            if not row or row['motion_phase']!=0 or row['motion_off']!=1:continue
            if not all(row[f's{i}_state']==1 and row[f's{i}_torque']==0 and row[f's{i}_age_ms']<=80 for i in (1,2)):continue
            rows.append(row)
            if len(rows)>=30:break
    finally:port.close()
    if len(rows)<30:raise RuntimeError('Could not read 30 fresh torque-off samples; check power, ID, jumpers and wiring.')
    positions={str(i):round(sum(r[f's{i}_position'] for r in rows)/len(rows)) for i in (1,2)}
    if any(max(r[f's{i}_position'] for r in rows)-min(r[f's{i}_position'] for r in rows)>8 for i in (1,2)):
        raise RuntimeError('Joints moved during measurement; hold the upright pose and retry.')
    out=Path(__file__).resolve().parents[1]/'local_joint_zero.json'
    out.write_text(json.dumps({'firmware':identity.firmware_name,'positions':positions,'samples':30,'note':'Upright pose must be confirmed by a person; values are not automatically applied.'},indent=2)+'\n',encoding='utf-8')
    print('Upper ID1:',positions['1'],'Lower ID2:',positions['2'])
    print('Saved local_joint_zero.json for read-only comparison; the ESP32 zero is unchanged.')

if __name__=='__main__':
    try:main()
    except Exception as exc:print('ERROR:',exc);sys.exit(1)
