"""Validated telemetry and lossless session recording for the demonstration panel."""
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path

FW = 'HD1910_C3_TEST_V25'
SUPPORTED_FW = {'HD1910_RECOVERY_V8':250, 'HD1910_RECOVERY_V9':2000, 'HD1910_RECOVERY_V10':2000, 'HD1910_RECOVERY_V11':2000, 'HD1910_RECOVERY_V12':2000, 'HD1910_RECOVERY_V13':2000}
NEW_MODEL_FW = {'HD1910_RECOVERY_V10','HD1910_RECOVERY_V11','HD1910_RECOVERY_V12','HD1910_RECOVERY_V13'}
HOME_FW = {'HD1910_RECOVERY_V12','HD1910_RECOVERY_V13'}
DIRECTIONAL_FW = {'HD1910_RECOVERY_V14','HD1910_RECOVERY_V15','HD1910_RECOVERY_V16','HD1910_RECOVERY_V17','HD1910_RECOVERY_V18','HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25'}
REVERSED_FW = {'HD1910_RECOVERY_V15','HD1910_RECOVERY_V16','HD1910_RECOVERY_V17','HD1910_RECOVERY_V18','HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25'}
SUPPORTED_FW.update({name:2000 for name in DIRECTIONAL_FW})
NEW_MODEL_FW.update(DIRECTIONAL_FW)
HOME_FW.update(DIRECTIONAL_FW)
JOINT_ZEROS = {1:337,2:2872}
JOINT_RANGE = {1:1536,2:1080}
LOCAL_RANGE = 24
OLD_MODEL = '7ad4c3a2f801061d00734f082b50372c19c611973cd9448a577b74d9049bfe63'
MODEL = 'f241a32ac9819a4d5557911d84a3aca591cac3b7b22296c9611e10a11355fb57'
MODELS={name:(MODEL if name in NEW_MODEL_FW else OLD_MODEL) for name in SUPPORTED_FW}
DIRECTIONAL_MODEL = '2a1ca9fb594891bd83c2db0cd212f746363e85bae131c0bced4e9bc9ba7888e7'
FRONT_BACK_MODEL = '4aa79d29219442475321ea70efccd8b40d5a935f74f2099a3b0168c85f653c94'
REVERSED_MODEL = 'b285841d9e81dcf724abc6637d9527cb11605fc309d972d1e84f397ac263630c'
MODELS.update({'HD1910_RECOVERY_V14':DIRECTIONAL_MODEL,**{fw:REVERSED_MODEL for fw in REVERSED_FW}})
MODELS['HD1910_RECOVERY_V19']='86647683a0628acff8f2fe8699cb7e644ba2aed419d94edb244a00a23022503e'

MODELS['HD1910_RECOVERY_V20']=MODELS['HD1910_C3_TEST_V21']=MODELS['HD1910_RECOVERY_V19']

MODELS['HD1910_C3_TEST_V22']='0487b14b45465970e21f6f0ca1f74981679cad538eb43bf27f909a5e02466969'

MODELS['HD1910_C3_TEST_V23']='853d25cacdaf2e8fe011563d9350fbc3ba93be257f02749f3fe880fd665cdaeb'

MODELS['HD1910_C3_TEST_V24']='941a19dc513c485d91ecf97d6e4a2e75412a43dab0471ea062c2a27daa52e95a'

MODELS['HD1910_C3_TEST_V25']='f731c6ae5f5a458c0a1cff4f99b54111c2db78e5fa4b5572f398dfa834b48509'
DYNAMIC_ZERO_FW={'HD1910_C3_TEST_V25'}

def row_joint_zeros(row):
    return {i:int(row.get(f'joint_zero{i}',JOINT_ZEROS[i])) for i in (1,2)}

def target_limits(firmware):
    degrees=(95,135) if firmware in ('HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25') else (90,130) if firmware in NEW_MODEL_FW else (120,120) if firmware in SUPPORTED_FW else (90,90)
    return tuple(math.radians(v) for v in degrees)
def joint_ranges(firmware):return JOINT_RANGE if firmware in ('HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25') else {1:1479,2:1024} if firmware in NEW_MODEL_FW else {1:1365,2:1365}
def startup_tolerance(firmware=FW):return 48 if firmware=='HD1910_RECOVERY_V11' or firmware in HOME_FW else 24

def home_settings(firmware=FW):
    if firmware not in HOME_FW:return None
    return {'upright_deg':12,'rate_dps':35,'verify_ms':150,
            'step_counts':6 if firmware=='HD1910_RECOVERY_V12' else 9,'period_ms':20,
            'lead_counts':24,'tolerance_counts':8,'hold_ms':500,'total_deadline_ms':14000,
            'finish':'torque_off_confirmed'}
def recovery_pacing(firmware=FW):
    if firmware in ('HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25'):
        result=recovery_pacing('HD1910_C3_TEST_V22')
        result.update(front_back_id2_step_counts=52,dual_step_counts=52,front_accelerated_id2_step_counts=68,speed_register=100,current_limit_register=90,torque_limit_register=600,factory_caps_enforced=True)
        return result
    if firmware in ('HD1910_RECOVERY_V17','HD1910_RECOVERY_V18','HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25'):
        return {'front_back_id2_step_counts':26,'period_ms':20,'front_back_id2_lead_counts':192,
                'dual_step_counts':26,'dual_lead_counts':192,'paced_ids':[1,2],
                'scope':'each_joint_all_network_branches','tracking_stop_counts':512,
                'subcount_accumulator':({'below_counts':0.5,'cap_counts':1,'consume':'successful_goal_write','reset':'stop_start_or_home'} if firmware in ('HD1910_RECOVERY_V18','HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25') else None)}
    return {'front_back_id2_step_counts':26 if firmware=='HD1910_RECOVERY_V16' else 52,
            'period_ms':20,'front_back_id2_lead_counts':192 if firmware=='HD1910_RECOVERY_V16' else None,
            'dual_step_counts':52,'tracking_stop_counts':512}

def start_positions_ok(row,firmware=FW):
    return all(abs(row[f's{i}_position']-z)<=startup_tolerance(firmware) for i,z in row_joint_zeros(row).items())

CAL = '67082628752294a7a020e0629b10fec3a27c37073f868a123dfd0c4f0e524276'
LEGACY_FIELDS = 'ms,tick,imu_seq,policy_seq,mode,reason,quality,age_us,period_us,late_us,loop_max_us,imu_us,infer_us,roll_rad,pitch_rad,lower_before,upper_before,action_lower,action_upper,lower_target,upper_target,acc_norm,acc_weight,faults,saturations,missed,dropped,singular,qw,qx,qy,qz,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps'.split(',')
V2_FIELDS = LEGACY_FIELDS + 'raw_roll_rad,raw_pitch_rad,ref_qw,ref_qx,ref_qy,ref_qz,zero_ready,zero_seq,zero_samples'.split(',')
SERVO_FIELDS = [f's{i}_{k}' for i in (1,2) for k in ('state','position','voltage','temperature','torque','status','age_ms','error')]
V3_FIELDS = V2_FIELDS + SERVO_FIELDS
MOTION_FIELDS = 'motion_phase,motion_kind,motion_reason,motion_off,motion_cmd1,motion_cmd2,s1_current_limit,s1_torque_limit,s2_current_limit,s2_torque_limit'.split(',')
V4_FIELDS = V3_FIELDS + MOTION_FIELDS
HOME_FIELDS = 'recovery_stage,motion_fault_id,motion_fault_actual,motion_fault_target'.split(',')
V5_FIELDS = V4_FIELDS + HOME_FIELDS
DIRECTION_FIELDS = 'direction_mode,direction_sign,direction_stable,direction_elapsed'.split(',')
V6_FIELDS = V5_FIELDS + DIRECTION_FIELDS
JOINT_ZERO_FIELDS = "joint_zero1,joint_zero2,joint_zero_saved,joint_zero_state,joint_zero_error".split(",")
FIELDS = V6_FIELDS + JOINT_ZERO_FIELDS
DIRECTION_MODES = {0:'等待倾倒方向',1:'前后：ID2 动作，ID1 保持零位',2:'左右/斜倒：双舵机策略'}
RECOVERY_STAGES = {0:'起身',1:'策略起身',2:'已接近水平，确认站稳',3:'站稳后慢速回零',4:'已到零位，核对后卸力'}
MOTION_REASONS = {0:'正常',1:'已停止',2:'心跳超时',3:'IMU 无效',4:'舵机反馈超时',5:'供电/温度/舵机状态异常',6:'实测位置越界',7:'跟踪误差过大',8:'限流/限矩或角度限制不符',9:'写入或应答失败',10:'12 秒到时',11:'启动检查失败',12:'小角度往返完成',13:'程序周期超时',14:'偏离保存零位，请手动摆正',15:'底座倾斜超过试验范围',16:'扭矩状态不符',17:'数值无效'}
MOTION_REASONS[20]='未保存本设备关节零位，请先直立并保存'
MOTION_REASONS.update({10:'本次动作到时，已请求卸力',18:'多圈位置配置或 EEPROM 写锁不符',19:'站立后回零完成'})
MODES = {0:'计算已暂停', 1:'正在计算 · 无动作输出', 2:'等待 IMU 静止初始化', 3:'计算已停止 · 检查状态'}
REASONS = {0:'数据有效',1:'已暂停',2:'初始化中',3:'姿态数据过期',4:'IMU 通信异常',5:'姿态无效或量程饱和',6:'计算结果异常',7:'电脑连接超时',8:'控制周期超时',9:'正在校准零点 · 请平放静止'}

def motion_reason_text(row):
    why=MOTION_REASONS.get(int(row['motion_reason']),'未知状态')
    ident=int(row.get('motion_fault_id',0))
    if row['motion_reason']==7 and ident in (1,2):
        actual=int(row['motion_fault_actual']);target=int(row['motion_fault_target'])
        return f'{"上轴" if ident==1 else "下轴"} ID{ident} 未跟上目标，已停止：目标 {target} / 实测 {actual}，差 {abs(actual-target)*360/4096:.1f}°'
    return why

def parse(line,allow_legacy=False,firmware=FW):
    if not line or line.startswith('#') or line.startswith('ms,'):
        return None
    parts=line.split(',')
    old_dynamic=len(parts)==len(V6_FIELDS) and (allow_legacy or firmware not in DYNAMIC_ZERO_FW)
    old_motion=len(parts)==len(V4_FIELDS) and (allow_legacy or firmware not in HOME_FW)
    old_home=len(parts)==len(V5_FIELDS) and (allow_legacy or firmware in HOME_FW-DIRECTIONAL_FW)
    if len(parts)!=len(FIELDS) and not old_dynamic and not old_motion and not old_home and not (allow_legacy and len(parts) in (len(LEGACY_FIELDS),len(V2_FIELDS),len(V3_FIELDS))):
        return None
    values=[float(x) for x in parts]
    if not all(math.isfinite(x) for x in values):
        raise ValueError('数据含有非有限值')
    row=dict(zip(FIELDS,values))
    if len(parts)==len(LEGACY_FIELDS):
        row.update(raw_roll_rad=row['roll_rad'],raw_pitch_rad=row['pitch_rad'],ref_qw=1,ref_qx=0,ref_qy=0,ref_qz=0,zero_ready=1,zero_seq=0,zero_samples=0)
    if len(parts)<len(V3_FIELDS):row.update({key:0 for key in SERVO_FIELDS})
    if len(parts)<len(V4_FIELDS):
        row.update({key:0 for key in MOTION_FIELDS});row.update(motion_cmd1=JOINT_ZEROS[1],motion_cmd2=JOINT_ZEROS[2])
    if len(parts)<len(V5_FIELDS):row.update({key:0 for key in HOME_FIELDS})
    if len(parts)<len(V6_FIELDS):row.update(direction_mode=0,direction_sign=1,direction_stable=0,direction_elapsed=0)
    if len(parts)<len(FIELDS):row.update(joint_zero1=JOINT_ZEROS[1],joint_zero2=JOINT_ZEROS[2],joint_zero_saved=1,joint_zero_state=0,joint_zero_error=0)
    if row['joint_zero_saved'] not in (0,1) or row['joint_zero_state'] not in (0,1,2,3) or row['joint_zero_error'] not in range(8):raise ValueError('关节零位状态无效')
    for i,z in row_joint_zeros(row).items():
        if row[f'joint_zero{i}']!=z or abs(z)>32767-joint_ranges(firmware)[i]:raise ValueError('关节零位超出有符号行程')
    if row['direction_mode'] not in DIRECTION_MODES or row['direction_sign'] not in (-1,1):raise ValueError('方向分支状态无效')
    for key,limit in [('direction_stable',50),('direction_elapsed',4294967295)]:
        if row[key]!=int(row[key]) or not 0<=row[key]<=limit:raise ValueError('方向状态计数无效')
    if row['recovery_stage'] not in RECOVERY_STAGES or row['motion_fault_id'] not in (0,1,2):raise ValueError('回零或故障轴状态无效')
    if max(abs(row['motion_fault_actual']),abs(row['motion_fault_target']))>32767:raise ValueError('故障位置无效')
    if row['motion_phase'] not in (0,1,2,3) or row['motion_off'] not in (0,1):raise ValueError('动作状态无效')
    for i,z in row_joint_zeros(row).items():
        if not allow_legacy and abs(row[f'motion_cmd{i}']-z)>joint_ranges(firmware)[i]:raise ValueError('实际发送目标超出受限范围')
        if abs(row[f'motion_cmd{i}'])>32767:raise ValueError('目标编码器值无效')
        if not allow_legacy and row['motion_phase']==2 and row['motion_kind']!=5 and abs(row[f'motion_cmd{i}']-z)>startup_tolerance(firmware):raise ValueError('局部测试目标超出范围')
    for i in (1,2):
        if row[f's{i}_state'] not in range(6):raise ValueError('舵机状态不正确')
    if row['zero_ready'] not in (0,1):raise ValueError('零点状态不正确')
    if row['mode'] not in MODES or row['quality'] not in (0,1,2,3):
        raise ValueError('状态字段不正确')
    for key in ('lower_before','upper_before','lower_target','upper_target'):
        if abs(row[key])>target_limits(firmware)[0 if key.startswith('lower') else 1]+1e-5:
            raise ValueError('计算目标超出模型范围')
    if max(abs(row['action_lower']),abs(row['action_upper']))>1.00001:
        raise ValueError('动作输出超出模型范围')
    return row

class Identity:
    def __init__(self):
        self.firmware=self.model=self.calibration=False
        self.firmware_name=None
    def feed(self,line):
        # ESP ROM prints at 115200 before the application switches to 230400;
        # its undecodable last line can be joined to the first valid banner.
        if '# FW=' in line:line=line[line.index('# FW='):]
        if line.startswith('# FW='):
            self.model=self.calibration=False
            self.firmware_name=next((name for name in SUPPORTED_FW if line==f'# FW={name} BAUD=230400 SERVO_OUTPUT=LIMITED'),None)
            self.firmware=self.firmware_name is not None
        if line.startswith('# MODEL_SHA256='):self.model=self.firmware and line.split('=',1)[1]==MODELS[self.firmware_name]
        if line.startswith('# CALIBRATION_SHA256='):self.calibration=line.split('=',1)[1]==CAL
    @property
    def verified(self):return self.firmware and self.model and self.calibration

class Recorder:
    def __init__(self,directory,source,firmware=FW):
        if firmware not in SUPPORTED_FW:raise ValueError('未识别的固件，不能创建实机记录')
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        self.started=datetime.now(timezone.utc).isoformat()
        self.base=directory/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.raw=self.base.with_suffix('.jsonl').open('x',encoding='utf-8',buffering=1)
        self.csv_file=self.base.with_suffix('.csv').open('x',encoding='utf-8-sig',newline='')
        self.writer=csv.DictWriter(self.csv_file,fieldnames=['host_utc',*FIELDS]);self.writer.writeheader()
        self.count=0;self.source=source;self.closed=False;self.motion_seen=False
        self.raw.write(json.dumps({'type':'session','source':source,'started_utc':self.started,'firmware':firmware,'imu_gyro_range_dps':SUPPORTED_FW[firmware],'imu_accel_range_g':2,'model_sha256':MODELS[firmware],'direction_models':({'front_back':('63b35958ed7652a6f9fc75a3c03a02a08d051322b9752ee5b7850105e6ed22b3' if firmware in ('HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25') else FRONT_BACK_MODEL),'side':('c958db0d1c87dbe3d8e400a1519076494eb930f008d93d7223b22ec358b055ba' if firmware in ('HD1910_RECOVERY_V19','HD1910_RECOVERY_V20','HD1910_C3_TEST_V21','HD1910_C3_TEST_V22','HD1910_C3_TEST_V23','HD1910_C3_TEST_V24','HD1910_C3_TEST_V25') else MODEL),'bundle':MODELS[firmware]} if firmware in DIRECTIONAL_FW else None),'calibration_sha256':CAL,'front_back_ID2_joint_sign':(-1 if firmware in REVERSED_FW else 1),'recovery_pacing':recovery_pacing(firmware),'angle_reference':'per-boot stationary average; raw fusion quaternion and reference quaternion recorded separately','servo_output_capability':'explicit_assisted_recovery','joint_zeros':None if firmware in DYNAMIC_ZERO_FW else JOINT_ZEROS,'joint_zero_mode':'per-frame, device NVS' if firmware in DYNAMIC_ZERO_FW else 'legacy fixed','joint_range_counts':joint_ranges(firmware),'target_limits_rad':target_limits(firmware),'local_range_counts':LOCAL_RANGE,'startup_tolerance_counts':startup_tolerance(firmware),'local_capture_range_counts':startup_tolerance(firmware),'voltage_limits_v':[4.0,5.5],'automatic_return_to_zero':firmware in HOME_FW,'auto_home_settings':home_settings(firmware),'full_motion_validation':'not_completed; remaining individual physical tests skipped at user request'},ensure_ascii=False)+'\n')
    def append(self,line,row=None):
        stamp=datetime.now(timezone.utc).isoformat()
        item={'host_utc':stamp,'raw':line}
        if row is not None:
            self.motion_seen=self.motion_seen or row['motion_phase']==2
            item['sample']=row;self.writer.writerow({'host_utc':stamp,**row});self.count+=1
            if self.count%50==0:self.csv_file.flush()
        self.raw.write(json.dumps(item,ensure_ascii=False)+'\n')
    def close(self):
        if self.closed:return
        self.closed=True;self.raw.close();self.csv_file.close()
        self.base.with_suffix('.json').write_text(json.dumps({'source':self.source,'started_utc':self.started,'ended_utc':datetime.now(timezone.utc).isoformat(),'samples':self.count,'csv':self.base.with_suffix('.csv').name,'raw':self.base.with_suffix('.jsonl').name,'servo_output_observed':self.motion_seen},ensure_ascii=False,indent=2),encoding='utf-8')

class ReplayRows(list):
    firmware=None
    joint_zeros=JOINT_ZEROS
    target_limit_rad=math.pi/2
    target_limits_rad=(math.pi/2,math.pi/2)
    model_sha256=OLD_MODEL

def replay_rows(path):
    rows=ReplayRows();firmware=None
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        item=json.loads(line)
        if item.get('type')=='session':
            firmware=item.get('firmware');rows.firmware=firmware
            rows.model_sha256=item.get('model_sha256',MODELS.get(firmware,OLD_MODEL))
            rows.target_limits_rad=target_limits(firmware)
            fallback={1:341,2:2899} if item.get('firmware')=='HD1910_LIMITED_V4' else JOINT_ZEROS
            rows.joint_zeros={int(k):int(v) for k,v in (item.get('joint_zeros') or fallback).items()}
            rows.target_limit_rad=max(rows.target_limits_rad)
        raw=item.get('raw','')
        row=parse(raw,allow_legacy=True,firmware=firmware)
        if row is not None:
            if rows and row['ms']<rows[-1]['ms']:
                raise ValueError('记录跨越设备重启，请选择重启后单独录制的文件')
            rows.append(row)
    if not rows:raise ValueError('这个文件没有可回放的记录')
    return rows
