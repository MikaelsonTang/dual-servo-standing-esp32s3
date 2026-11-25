"""HD1910 telemetry, recording, and explicitly limited supported motion trials."""
import argparse
from collections import deque
from datetime import datetime
import math
import os
from pathlib import Path
import queue
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import serial.tools.list_ports
from data import row_joint_zeros, DYNAMIC_ZERO_FW, DIRECTION_MODES, DIRECTIONAL_FW, MODES, REASONS, MOTION_REASONS, RECOVERY_STAGES, motion_reason_text, JOINT_ZEROS, FW, target_limits, startup_tolerance, start_positions_ok, Recorder, replay_rows
from transport import Link

ROOT=Path(__file__).resolve().parent
BG='#eef3f5';CARD='#ffffff';INK='#182c39';MUTED='#657c8a';TEAL='#007d79';ORANGE='#d87b35';RED='#bd4146'

class Dashboard:
    def __init__(self,root):
        self.root=root;root.title('HD1910 · 姿态与策略展示');root.geometry('1080x850');root.minsize(1000,780);root.configure(bg=BG)
        root.option_add('*Font',('Microsoft YaHei UI',10))
        self.link=None;self.recorder=None;self.row=None;self.history=deque(maxlen=1000)
        self.last_received=0;self.last_infer=0;self.fullscreen=False;self.replay=[];self.replay_index=0;self.playing=False
        self.replay_start=0;self.replay_offset=0;self.auto_start=False;self.mode='live';self.last_draw=0
        self.last_record=None;self.sample_count=0
        self.display_zeros=JOINT_ZEROS;self.display_limits=target_limits(FW)
        style=ttk.Style(root);style.theme_use('clam')
        style.configure('TButton',font=('Microsoft YaHei UI',10),padding=(12,8),background='#e5ecef',foreground=INK,borderwidth=0)
        style.map('TButton',background=[('active','#d3e2e5'),('disabled','#edf1f2')],foreground=[('disabled','#9aa7ae')])
        style.configure('Accent.TButton',background=TEAL,foreground='white')
        style.map('Accent.TButton',background=[('active','#006963'),('disabled','#a9c3c2')])
        style.configure('Record.TButton',foreground=RED)
        self.top=tk.Frame(root,bg=BG);self.top.pack(fill='x',padx=24,pady=(18,10))
        tk.Label(self.top,text='HD1910',font=('Microsoft YaHei UI',24,'bold'),bg=BG,fg=INK).pack(side='left')
        tk.Label(self.top,text='双舵机自起身 · 姿态与策略',bg=BG,fg=MUTED).pack(side='left',padx=15,pady=(10,0))
        self.source=tk.Label(self.top,text='实机监测',bg='#d8ebe9',fg=TEAL,padx=12,pady=5);self.source.pack(side='right')
        toolbar=tk.Frame(root,bg=CARD,padx=14,pady=10);toolbar.pack(fill='x',padx=24)
        tk.Label(toolbar,text='设备',bg=CARD,fg=MUTED).pack(side='left',padx=(0,8))
        self.port=tk.StringVar();self.ports=ttk.Combobox(toolbar,textvariable=self.port,width=9,state='readonly');self.ports.pack(side='left')
        ttk.Button(toolbar,text='刷新',command=self.refresh).pack(side='left',padx=6)
        self.connect_btn=ttk.Button(toolbar,text='连接设备',command=self.toggle_connection);self.connect_btn.pack(side='left')
        self.connection=tk.Label(toolbar,text='未连接',bg=CARD,fg=MUTED);self.connection.pack(side='left',padx=16)
        ttk.Button(toolbar,text='全屏 F11',command=self.toggle_fullscreen).pack(side='right')
        self.cal_btn=ttk.Button(toolbar,text='校准零点',command=lambda:self.command('CAL'));self.cal_btn.pack(side='right',padx=6)
        status=tk.Frame(root,bg=BG);status.pack(fill='x',padx=26,pady=(12,10))
        self.state=tk.Label(status,text='连接后先进行模型自检；底座保持平放静止，自动归零',font=('Microsoft YaHei UI',11,'bold'),bg=BG,fg=INK);self.state.pack(side='left')
        self.limit_label=tk.Label(status,text='上轴 ID1 ±135° · 下轴 ID2 ±95° / 14 秒',bg=BG,fg=MUTED);self.limit_label.pack(side='right')
        cards=tk.Frame(root,bg=BG);cards.pack(fill='x',padx=24)
        self.values={};self.servo_labels={}
        for i,(key,title,subtitle,color) in enumerate([
            ('roll_rad','底座 Roll','横滚角 · 真实 IMU',TEAL),('pitch_rad','底座 Pitch','俯仰角 · 真实 IMU',TEAL),
            ('lower_target','下关节 ID 2 · 计算目标','实测编码器：等待连接',ORANGE),('upper_target','上关节 ID 1 · 计算目标','实测编码器：等待连接',ORANGE)]):
            cards.columnconfigure(i,weight=1)
            f=tk.Frame(cards,bg=CARD,padx=16,pady=12);f.grid(row=0,column=i,sticky='nsew',padx=(0,10 if i<3 else 0))
            tk.Label(f,text=title,bg=CARD,fg=INK,anchor='w').pack(fill='x')
            value=tk.Label(f,text='—',bg=CARD,fg=color,font=('Segoe UI',28,'bold'),anchor='w');value.pack(fill='x',pady=2)
            label=tk.Label(f,text=subtitle,bg=CARD,fg=MUTED,font=('Microsoft YaHei UI',9),anchor='w',justify='left');label.pack(fill='x');self.values[key]=value
            if key.endswith('target'):self.servo_labels[2 if key=='lower_target' else 1]=label
        middle=tk.Frame(root,bg=BG);middle.pack(fill='both',expand=True,padx=24,pady=12)
        middle.columnconfigure(0,weight=2);middle.columnconfigure(1,weight=3);middle.rowconfigure(0,weight=1)
        self.pose=tk.Canvas(middle,bg=CARD,highlightthickness=0,height=190);self.pose.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        self.chart=tk.Canvas(middle,bg=CARD,highlightthickness=0,height=190);self.chart.grid(row=0,column=1,sticky='nsew')
        self.stats=tk.Label(root,text='等待数据',bg=BG,fg=MUTED,anchor='w');self.stats.pack(fill='x',padx=26,pady=(0,8))
        self.calibration=tk.Label(root,text='启动零点：等待连接',bg=BG,fg=MUTED,anchor='w');self.calibration.pack(fill='x',padx=26,pady=(0,8))
        motionbar=tk.Frame(root,bg=CARD,padx=12,pady=8);motionbar.pack(fill='x',padx=24,pady=(0,8))
        self.supported=tk.BooleanVar(value=False)
        tk.Checkbutton(motionbar,text='已扶稳机器人',variable=self.supported,bg=CARD,fg=INK).pack(side='left')
        self.motion_buttons=[]
        for label,cmd in [('慢速回零','HOLD'),('上轴小幅往返','TEST1'),('下轴小幅往返','TEST2'),('受限策略','POLICY')]:
            b=ttk.Button(motionbar,text=label,command=lambda c=cmd:self.move(c));b.pack(side='left',padx=3);self.motion_buttons.append(b)
        self.stop_btn=tk.Button(motionbar,text='停止 / 卸力 Esc',command=self.emergency,bg=RED,fg='white',font=('Microsoft YaHei UI',11,'bold'),relief='flat',padx=12,pady=6);self.stop_btn.pack(side='right')
        self.motion_label=tk.Label(root,text='输出未启动 · 停止会卸力，请保持扶护',bg=BG,fg=MUTED,anchor='w');self.motion_label.pack(fill='x',padx=26,pady=(0,8))
        recoverybar=tk.Frame(root,bg=CARD,padx=12,pady=8);recoverybar.pack(fill='x',padx=24,pady=(0,8))
        self.getup_btn=ttk.Button(recoverybar,text='扶护起身 · 14 秒',style='Accent.TButton',command=lambda:self.move('GETUP'))
        self.getup_btn.pack(side='left');self.motion_buttons.append(self.getup_btn)
        self.branch=tk.Label(recoverybar,text='先平放完成校准，再整体轻放倒；勾选扶护后启动。停止会卸力。',bg=CARD,fg=MUTED)
        self.branch.pack(side='left',padx=12)
        controls=tk.Frame(root,bg=CARD,padx=12,pady=10);controls.pack(fill='x',padx=24)
        self.start_btn=ttk.Button(controls,text='开始计算',style='Accent.TButton',command=self.start);self.start_btn.pack(side='left')
        self.pause_btn=ttk.Button(controls,text='暂停计算',command=self.pause);self.pause_btn.pack(side='left',padx=6)
        self.zero_btn=ttk.Button(controls,text='重置计算目标',command=lambda:self.command('ZERO'));self.zero_btn.pack(side='left')
        self.record_btn=ttk.Button(controls,text='● 开始录制',style='Record.TButton',command=self.toggle_record);self.record_btn.pack(side='left',padx=(14,6))
        ttk.Button(controls,text='回放记录',command=self.open_replay).pack(side='right')
        ttk.Button(controls,text='打开记录目录',command=lambda:os.startfile(self.record_dir())).pack(side='right',padx=6)
        self.record_label=tk.Label(root,text='未录制 · 录制后自动保存 CSV、原始日志和会话信息',bg=BG,fg=MUTED,anchor='w');self.record_label.pack(fill='x',padx=26,pady=(8,6))
        self.log=tk.Text(root,height=3,bg='#e4ecef',fg=MUTED,relief='flat',font=('Microsoft YaHei UI',9),wrap='word',state='disabled');self.log.pack(fill='x',padx=24,pady=(0,12))
        root.protocol('WM_DELETE_WINDOW',self.close);root.bind('<F11>',lambda e:self.toggle_fullscreen());root.bind('<Escape>',lambda e:self.emergency())
        self.refresh();self.log_message('准备就绪。初始目标是计算参考零位；重置目标不会让舵机回零。')
        self.update_job=root.after(50,self.update)
    def record_dir(self):
        p=ROOT/'recordings';p.mkdir(exist_ok=True);return str(p)
    def refresh(self):
        names=[p.device for p in serial.tools.list_ports.comports() if p.vid]
        self.ports['values']=names
        if self.port.get() not in names:self.port.set(names[0] if names else '')
    def log_message(self,text):
        self.log.configure(state='normal');self.log.insert('end',datetime.now().strftime('%H:%M:%S')+'  '+str(text)+'\n')
        if int(self.log.index('end-1c').split('.')[0])>100:self.log.delete('1.0','30.0')
        self.log.see('end');self.log.configure(state='disabled')
    def toggle_connection(self):
        if self.link:
            self.disconnect();return
        if not self.port.get():self.log_message('没有发现 USB 串口，请连接 ESP32 后刷新。');return
        self.stop_record();self.replay=[];self.playing=False;self.mode='live';self.history.clear();self.row=None;self.last_received=0;self.last_infer=0
        self.source.configure(text='实机监测',bg='#d8ebe9',fg=TEAL)
        self.start_btn.configure(text='开始计算');self.pause_btn.configure(text='暂停计算')
        self.display_zeros=JOINT_ZEROS;self.display_limits=target_limits(FW)
        self.supported.set(False);self.link=Link(self.port.get(),ui_required=True);self.link.start();self.connect_btn.configure(text='断开设备');self.connection.configure(text='正在连接…',fg=MUTED)
    def disconnect(self):
        if self.link:
            self.link.stop_event.set();self.link.join(timeout=1.5);self.link=None
        self.stop_record();self.connection.configure(text='已断开',fg=MUTED);self.connect_btn.configure(text='连接设备')
        self.last_received=0;self.auto_start=False
    def command(self,cmd):
        if self.mode=='live' and self.link and self.link.verified:self.link.send(cmd)
    def move(self,cmd):
        if not self.supported.get() or self.mode!='live':return
        self.supported.set(False)
        if not self.recorder:self.toggle_record()
        if self.recorder:self.command(cmd)
        else:self.log_message('动作未启动：需要先成功创建记录。')
    def emergency(self):
        self.supported.set(False);self.command('STOP');self.playing=False
        self.log_message('已请求停止；等待两颗舵机卸力确认。请继续扶住。')
        self.exit_fullscreen();return 'break'
    def start(self):
        if self.mode=='replay':
            if self.replay_index>=len(self.replay):self.replay_index=0;self.history.clear()
            self.replay_offset=self.replay[self.replay_index]['ms'];self.replay_start=time.monotonic();self.playing=True
        else:self.command('START')
    def pause(self):
        if self.mode=='replay':self.playing=False
        else:self.command('PAUSE')
    def toggle_record(self):
        if self.recorder:self.stop_record();return
        if self.mode!='live' or not self.link or not self.link.verified:return
        try:
            self.recorder=Recorder(self.record_dir(),f'live:{self.port.get()}',firmware=self.link.identity.firmware_name);self.last_record=self.recorder.base
            self.record_btn.configure(text='■ 停止录制');self.log_message('开始录制。CSV 可直接导入 Excel；JSONL 用于回放。')
        except OSError as exc:self.log_message('无法创建记录：'+str(exc))
    def stop_record(self):
        if self.recorder:
            count=self.recorder.count;path=self.recorder.base
            self.recorder.close();self.recorder=None;self.record_btn.configure(text='● 开始录制')
            self.record_label.configure(text=f'已保存 {count} 条数据 · {path.name}.csv',fg=TEAL);self.log_message('记录已保存：'+str(path))
    def open_replay(self,path=None):
        path=path or filedialog.askopenfilename(title='选择录制的原始日志',initialdir=self.record_dir(),filetypes=[('记录文件','*.jsonl')])
        if not path:return
        try:rows=replay_rows(path)
        except Exception as exc:messagebox.showerror('无法回放',str(exc));return
        self.disconnect();self.mode='replay';self.replay=rows;self.replay_index=0;self.history.clear();self.row=None;self.playing=False
        self.display_zeros=rows.joint_zeros;self.display_limits=rows.target_limits_rad
        self.source.configure(text='记录回放 · 非实时',bg='#f5e5d8',fg=ORANGE);self.connection.configure(text='离线回放',fg=ORANGE)
        self.start_btn.configure(text='播放记录');self.pause_btn.configure(text='暂停回放');self.log_message('已加载 '+str(path));self.start()
    def receive(self,row):
        self.display_zeros=row_joint_zeros(row)
        if self.row and row['ms']<self.row['ms']:
            self.history.clear();self.last_infer=0
        self.row=row;self.last_received=time.monotonic();self.history.append(row);self.sample_count+=1
        if row['infer_us']>0:self.last_infer=row['infer_us']
    def update(self):
        try:
            if self.link:
                self.link.touch()
                for _ in range(500):
                    try:kind,value=self.link.events.get_nowait()
                    except queue.Empty:break
                    if kind=='line':
                        line,row=value
                        if self.recorder:
                            try:self.recorder.append(line,row)
                            except OSError as exc:self.command('STOP');self.log_message('录制失败，已请求停止：'+str(exc));self.stop_record()
                        if row is not None:self.receive(row)
                        elif line.startswith('#'):self.log_message(line)
                    elif kind=='verified':
                        self.connection.configure(text='已连接 · 身份已核对',fg=TEAL)
                        self.display_limits=target_limits(self.link.identity.firmware_name)
                        if not self.recorder:self.toggle_record()
                    elif kind=='restart':
                        self.stop_record();self.history.clear();self.row=None;self.last_received=0;self.last_infer=0;self.auto_start=False
                        self.connection.configure(text='正在重新核对…',fg=MUTED);self.log_message(value+'；上一段录制已保存。')
                    elif kind=='error':self.log_message('连接异常：'+value);self.connection.configure(text='连接异常',fg=RED);self.stop_record()
                    elif kind=='closed':self.last_received=0;self.stop_record();self.connect_btn.configure(text='连接设备');self.connection.configure(text='已断开',fg=RED);self.link=None;break
                    elif kind in ('notice','sent'):
                        self.log_message(value if kind=='notice' else '已请求 '+value)
                        if self.recorder:self.recorder.append('# HOST '+str(value))
                if self.auto_start and self.row and self.row['zero_ready'] and self.row['quality'] in (1,2) and self.row['age_us']<=30000:
                    self.command('START');self.auto_start=False
            if self.mode=='replay' and self.playing:
                wanted=self.replay_offset+(time.monotonic()-self.replay_start)*1000
                for _ in range(500):
                    if self.replay_index>=len(self.replay):self.playing=False;break
                    row=self.replay[self.replay_index]
                    if row['ms']>wanted:break
                    self.receive(row);self.replay_index+=1
            if time.monotonic()-self.last_draw>.10:self.draw();self.last_draw=time.monotonic()
        except Exception as exc:
            self.log_message('面板错误：'+str(exc));self.pause()
        self.update_job=self.root.after(30,self.update)
    def draw(self):
        self.limit_label.configure(text=f'上轴 ID1 ±{math.degrees(self.display_limits[1]):.0f}° · 下轴 ID2 ±{math.degrees(self.display_limits[0]):.0f}° / 14 秒')
        live=self.mode=='live';fresh=self.row is not None and (not live or time.monotonic()-self.last_received<.6)
        imu_valid=fresh and self.row['quality'] in (1,2) and self.row['age_us']<=30000
        valid=imu_valid and self.row['zero_ready']==1
        connected=bool(self.link and self.link.verified)
        active_fw=self.link.identity.firmware_name if connected else FW if live else getattr(self.replay,'firmware',None)
        tolerance=startup_tolerance(active_fw)
        ready_motion=bool(live and connected and valid and self.row['motion_phase']==0 and self.row['motion_off']==1 and self.supported.get())
        if ready_motion and active_fw in DYNAMIC_ZERO_FW:
            ready_motion=self.row.get('joint_zero_saved')==1 and self.row.get('joint_zero_state')!=1
        if ready_motion:
            ready_motion=start_positions_ok(self.row,active_fw) and all(self.row[f's{i}_state']==1 and self.row[f's{i}_age_ms']<=80 and self.row[f's{i}_torque']==0 for i in JOINT_ZEROS)
        for b in self.motion_buttons:b.configure(state='normal' if ready_motion else 'disabled')
        if fresh:
            r=self.row;phase=int(r['motion_phase']);why=motion_reason_text(r)
            label={0:'已卸力' if r['motion_off'] else '记录中无卸力确认',1:'正在降低并核对限制',2:'实际运动中，请扶稳',3:'正在停止，等待卸力反馈'}.get(phase,'未知')
            if phase==2 and r['motion_kind']==5:label=RECOVERY_STAGES[int(r['recovery_stage'])]+' · 请扶护'
            actual_fresh=all(r[f's{i}_state']==1 and r[f's{i}_age_ms']<=80 for i in (1,2))
            if not actual_fresh:label='舵机反馈不新鲜，无法确认当前卸力状态'
            if phase==0 and actual_fresh and r['motion_reason'] in (0,1,12,19) and not start_positions_ok(r,active_fw):
                why=f'请摆正并保持：ID1 {self.display_zeros[1]-tolerance}～{self.display_zeros[1]+tolerance}；ID2 {self.display_zeros[2]-tolerance}～{self.display_zeros[2]+tolerance}'
            elif phase==0 and r['motion_reason'] in (0,1,12,19) and live and connected and valid and actual_fresh and not self.supported.get():
                why='位置满足启动范围；扶稳后勾选“已扶稳机器人”'
            target_text=f'当前发送目标 ID1 {int(r["motion_cmd1"])} / ID2 {int(r["motion_cmd2"])}' if phase==2 else f'软件零位 ID1 {self.display_zeros[1]} / ID2 {self.display_zeros[2]}'
            self.motion_label.configure(text=f'{label} · {why}    {target_text}',fg=RED if phase in (1,2,3) or r['motion_reason'] not in (0,1,12,19) else TEAL)
        else:self.motion_label.configure(text='无实时反馈，无法确认卸力 · 请保持扶护',fg=MUTED)
        self.start_btn.configure(state='normal' if (not live or connected and valid) else 'disabled')
        self.pause_btn.configure(state='normal' if (not live or connected) else 'disabled')
        self.zero_btn.configure(state='normal' if live and connected else 'disabled')
        self.record_btn.configure(state='normal' if live and connected else 'disabled')
        self.cal_btn.configure(state='normal' if live and connected and imu_valid else 'disabled')
        for key,label in self.values.items():
            available=valid if key.endswith('rad') else fresh
            label.configure(text=f'{math.degrees(self.row[key]):+.1f}°' if available else '—',fg=(TEAL if key.endswith('rad') else ORANGE) if valid else MUTED)
        for ident,label in self.servo_labels.items():
            s=f's{ident}_';r=self.row
            online=fresh and r[s+'state']==1 and r[s+'age_ms']<=300
            if online:
                torque='关' if r[s+'torque']==0 else '开'
                z=self.display_zeros[ident]
                label.configure(text=f'实测 {int(r[s+"position"])} / 零位 {z} · 差 {int(r[s+"position"])-z:+d}\n{r[s+"voltage"]:.1f} V · {int(r[s+"temperature"])}°C · 扭矩{torque}',fg=TEAL)
            else:
                state={0:'尚无反馈',2:'读取超时',3:'型号不匹配',4:'舵机报错',5:'串口异常'}.get(int(r[s+'state']),'数据过期') if fresh else '未连接'
                label.configure(text=f'实测编码器 —\n{state}',fg=MUTED)
        if live:
            if not fresh:text='等待实时数据' if connected else '未连接设备'
            elif self.row['mode']==3:text=REASONS.get(int(self.row['reason']),'计算已停止')+' · 恢复后可重新开始'
            elif not self.row['zero_ready']:text='正在校准零点 · 请平放静止'
            elif not valid:text=REASONS.get(int(self.row['reason']),'等待有效姿态') if self.row['reason']>=3 else '保持静止，等待 IMU 初始化'
            else:text=MODES[int(self.row['mode'])]
            if fresh and self.row['motion_phase']==2:text=RECOVERY_STAGES[int(self.row['recovery_stage'])]+' · 舵机输出已开启' if self.row['motion_kind']==5 else '正在局部测试 · 舵机输出已开启'
            elif fresh and self.row['motion_reason'] not in (0,1):text=motion_reason_text(self.row)
        else:text=('正在回放' if self.playing else '回放已暂停 / 完成')+f' · {self.replay_index}/{len(self.replay)}'
        branch='先平放完成校准，再整体轻放倒；勾选扶护后启动。停止会卸力。'
        if valid and active_fw in DIRECTIONAL_FW:
            if self.row['motion_phase']==2 and self.row['recovery_stage'] in (2,3,4):
                branch='当前阶段：'+RECOVERY_STAGES[int(self.row['recovery_stage'])]
            elif self.row['mode']==1:
                branch='当前分支：'+DIRECTION_MODES[int(self.row['direction_mode'])]
            else:branch='四方向模型已就绪 · 前后单 ID2 / 左右双舵机'
        self.branch.configure(text=branch)
        self.state.configure(text=text,fg=RED if live and fresh and (self.row['mode']==3 or self.row['motion_reason'] not in (0,1,12,19)) else (TEAL if valid else MUTED))
        if fresh:
            row=self.row
            rate=0 if len(self.history)<2 else 1000*(len(self.history)-1)/max(1,self.history[-1]['ms']-self.history[0]['ms'])
            age=f'{row["age_us"]/1000:.1f} ms' if row['age_us']<1000000000 else '—'
            self.stats.configure(text=f'IMU 采样序号 {int(row["imu_seq"]):,}    数据流 {rate:.1f} Hz    推理 {self.last_infer/1000:.2f} ms    数据年龄 {age}    漏周期 {int(row["missed"])}    丢行 {int(row["dropped"])}')
        else:self.stats.configure(text='等待有效数据 · 断开连接后不显示旧值作为实时值')
        if self.recorder:self.record_label.configure(text=f'● 正在录制 {self.recorder.count:,} 条 · {self.recorder.base.name}.csv',fg=RED)
        if fresh:
            r=self.row
            state=('相对本次零点' if r['zero_ready'] else f'正在平均 {int(r["zero_samples"])} 个静止样本') if r['zero_seq'] or not r['zero_ready'] else '旧版记录 · 未做启动归零'
            raw=f'原始姿态 Roll {math.degrees(r["raw_roll_rad"]):+.2f}° / Pitch {math.degrees(r["raw_pitch_rad"]):+.2f}°' if imu_valid else '等待有效姿态'
            self.calibration.configure(text=f'启动零点：{state}    {raw}')
        else:self.calibration.configure(text='启动零点：等待数据 · 每次启动重新取静止姿态为零')
        self.draw_pose(valid);self.draw_chart()
    def draw_pose(self,valid):
        c=self.pose;c.delete('all');w=max(250,c.winfo_width());h=max(140,c.winfo_height())
        c.create_text(18,20,text='底座姿态',anchor='w',fill=INK,font=('Microsoft YaHei UI',12,'bold'))
        c.create_text(w-16,20,text='示意图',anchor='e',fill=MUTED,font=('Microsoft YaHei UI',9))
        cx=w/2;cy=h*.47;scale=min(w/3.3,h/2.4)
        c.create_oval(cx-scale,cy+scale*.35,cx+scale,cy+scale*.65,fill='#f0f4f5',outline='')
        r=self.row['roll_rad'] if valid else 0;p=self.row['pitch_rad'] if valid else 0
        def project(x,y,z):
            y,z=y*math.cos(r)-z*math.sin(r),y*math.sin(r)+z*math.cos(r)
            x,z=x*math.cos(p)+z*math.sin(p),-x*math.sin(p)+z*math.cos(p)
            return cx+scale*(x*.8-y*.45),cy+scale*(x*.2+y*.35-z*.85)
        corners=[project(x,y,0) for x,y in [(-.7,-.8),(.7,-.8),(.7,.8),(-.7,.8)]]
        c.create_polygon(*sum((list(v) for v in corners),[]),fill='#d1eae7' if valid else '#e1e7e9',outline=TEAL if valid else MUTED,width=2)
        origin=project(0,0,0);up=project(0,0,.8);c.create_line(*origin,*up,fill=TEAL if valid else MUTED,width=5);c.create_oval(up[0]-5,up[1]-5,up[0]+5,up[1]+5,fill=ORANGE,outline='')
        front=project(0,-.9,0);c.create_text(*front,text='双长槽侧',fill=MUTED,font=('Microsoft YaHei UI',9),anchor='n')
        base=h-55
        for i,(key,name) in enumerate([('lower_target','下'),('upper_target','上')]):
            yy=base+22*i;c.create_text(18,yy,text=name,anchor='w',fill=MUTED)
            c.create_line(50,yy,w-24,yy,fill='#e2e9ec',width=5);mid=(50+w-24)/2
            value=max(-1,min(1,self.row[key]/self.display_limits[0 if key.startswith('lower') else 1])) if valid else 0;x=mid+value*(w-74)/2
            c.create_line(mid,yy,x,yy,fill=ORANGE,width=5);c.create_line(mid,yy-7,mid,yy+7,fill=MUTED)
    def draw_chart(self):
        c=self.chart;c.delete('all');w=max(300,c.winfo_width());h=max(140,c.winfo_height())
        c.create_text(18,20,text='姿态变化 · 最近 15 秒',anchor='w',fill=INK,font=('Microsoft YaHei UI',12,'bold'))
        c.create_text(w-100,20,text='● Roll',fill=TEAL);c.create_text(w-40,20,text='● Pitch',fill=ORANGE)
        rows=list(self.history);last=rows[-1]['ms'] if rows else 0;rows=[r for r in rows if r['ms']>=last-15000]
        limit=max(10,min(180,math.ceil(max([abs(math.degrees(r[k])) for r in rows for k in ('roll_rad','pitch_rad')]+[0])/10)*10))
        left,right,top,bottom=48,w-18,48,h-30
        for v in (-limit,0,limit):
            yy=(top+bottom)/2-v*(bottom-top)/(2*limit);c.create_line(left,yy,right,yy,fill='#e5edef');c.create_text(left-7,yy,text=f'{v}°',anchor='e',fill=MUTED,font=('Segoe UI',9))
        for key,color in [('roll_rad',TEAL),('pitch_rad',ORANGE)]:
            points=[]
            for row in rows:
                if not row['zero_ready'] or row['quality'] not in (1,2) or row['age_us']>30000:
                    if len(points)>=4:c.create_line(points,fill=color,width=2)
                    points=[];continue
                xx=left+(row['ms']-(last-15000))/15000*(right-left);yy=(top+bottom)/2-math.degrees(row[key])*(bottom-top)/(2*limit)
                points.extend((xx,yy))
            if len(points)>=4:c.create_line(points,fill=color,width=2)
        c.create_text(left,bottom+16,text='−15 s',anchor='w',fill=MUTED,font=('Segoe UI',9));c.create_text(right,bottom+16,text='现在' if self.mode=='live' else '回放位置',anchor='e',fill=MUTED,font=('Microsoft YaHei UI',9))
    def toggle_fullscreen(self):self.fullscreen=not self.fullscreen;self.root.attributes('-fullscreen',self.fullscreen)
    def exit_fullscreen(self):self.fullscreen=False;self.root.attributes('-fullscreen',False)
    def close(self):
        self.root.after_cancel(self.update_job)
        self.disconnect();self.root.destroy()

def main():
    p=argparse.ArgumentParser();p.add_argument('--connect');p.add_argument('--start',action='store_true');p.add_argument('--replay');args=p.parse_args()
    root=tk.Tk();app=Dashboard(root)
    if args.replay:root.after(200,lambda:app.open_replay(args.replay))
    elif args.connect:
        def connect():app.port.set(args.connect);app.toggle_connection();app.auto_start=args.start
        root.after(200,connect)
    root.mainloop()

if __name__=='__main__':main()
