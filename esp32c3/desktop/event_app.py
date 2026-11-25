"""Event presentation. Uses the original verified manual controller and recorder."""
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox
import app as original
from data import JOINT_ZEROS, start_positions_ok, FW, DYNAMIC_ZERO_FW

BG='#f4f5f9'; WHITE='#ffffff'; INK='#202b43'; MUTED='#768198'
ACCENT='#6155d9'; GREEN='#188476'; RED='#d44e62'; LINE='#e9ecf4'
FONT='Microsoft YaHei UI'; NUM='Segoe UI Variable Display'


class Pill(tk.Canvas):
    """Keyboard accessible capsule button with the configure interface used by Dashboard."""
    def __init__(self,parent,text,command,width=120,color=LINE,foreground=INK):
        super().__init__(parent,width=width,height=44,bg=parent.cget('bg'),highlightthickness=0,
                         takefocus=True,cursor='hand2')
        self.text=text;self.command=command;self.enabled=True;self.color=color;self.foreground=foreground
        self.hover=False
        self.bind('<Configure>',lambda e:self.paint())
        self.bind('<Enter>',lambda e:self.highlight(True));self.bind('<Leave>',lambda e:self.highlight(False))
        self.bind('<ButtonRelease-1>',self.clicked)
        self.bind('<Return>',lambda e:self.invoke());self.bind('<space>',lambda e:self.invoke())
        self.bind('<FocusIn>',lambda e:self.paint());self.bind('<FocusOut>',lambda e:self.paint())
    def highlight(self,value):self.hover=value;self.paint()
    def clicked(self,event):
        if 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height():self.invoke()
    def invoke(self):
        if self.enabled:self.command()
    def configure(self,cnf=None,**kwargs):
        if isinstance(cnf,dict):kwargs={**cnf,**kwargs}
        if not kwargs:return super().configure(cnf)
        if 'text' in kwargs:self.text=kwargs.pop('text')
        if 'state' in kwargs:self.enabled=kwargs.pop('state')!='disabled'
        if kwargs:super().configure(**kwargs)
        self.paint()
    config=configure
    def paint(self):
        self.delete('all');w=max(10,self.winfo_width());h=max(10,self.winfo_height());r=h/2-2
        color=self.color if self.enabled else '#eef0f5'
        if self.hover and self.enabled:color=ACCENT if self.color==LINE else self.color
        foreground=self.foreground if self.enabled else '#a8afbe'
        if self.hover and self.enabled and self.color==LINE:foreground=WHITE
        outline=ACCENT if self.focus_get()==self else color
        self.create_oval(2,2,2+2*r,h-2,fill=color,outline=color)
        self.create_oval(w-2-2*r,2,w-2,h-2,fill=color,outline=color)
        self.create_rectangle(r+2,2,w-r-2,h-2,fill=color,outline=color)
        if outline!=color:self.create_rectangle(r+2,3,w-r-2,4,fill=outline,outline=outline)
        self.create_text(w/2,h/2,text=self.text,fill=foreground,font=(FONT,10))


class Card(tk.Canvas):
    def __init__(self,parent,padding=20,**kwargs):
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,**kwargs)
        self.padding=padding;self.body=tk.Frame(self,bg=WHITE)
        self.item=self.create_window(padding,padding,window=self.body,anchor='nw')
        self.bind('<Configure>',self.resize)
    def resize(self,event):
        w,h=event.width,event.height;r=min(24,h/2,w/2)
        self.delete('surface')
        self.create_polygon(r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1,
                            smooth=True,splinesteps=24,fill=WHITE,outline=WHITE,tags='surface')
        self.tag_lower('surface');self.itemconfigure(self.item,width=max(1,w-2*self.padding),height=max(1,h-2*self.padding))


class EventDashboard(original.Dashboard):
    def __init__(self,root):
        # Keep the proven transport, heartbeat, validation, STOP and recording paths.
        super().__init__(root)
        for child in root.winfo_children():child.pack_forget()
        root.title('HD1910 · C3 完整测试 · V25');root.geometry('1120x880');root.minsize(1000,820);root.configure(bg=BG)
        root.option_add('*Font',(FONT,10))
        header=tk.Frame(root,bg=BG);header.pack(fill='x',padx=32,pady=(24,18))
        brand=tk.Frame(header,bg=BG);brand.pack(side='left')
        tk.Label(brand,text='HD1910',font=(NUM,28,'bold'),bg=BG,fg=INK).pack(side='left')
        tk.Label(brand,text='自起身实验室',font=(FONT,16),bg=BG,fg=INK).pack(side='left',padx=18,pady=(6,0))
        self.source=tk.Label(header,text='双舵机 · 智能控制',font=(FONT,10),bg=BG,fg=ACCENT);self.source.pack(side='right',pady=10)
        bar=Card(root,height=82,padding=18);bar.pack(fill='x',padx=32)
        b=bar.body
        tk.Label(b,text='设备连接',fg=INK,bg=WHITE).pack(side='left',padx=(0,14))
        self.ports=ttk.Combobox(b,textvariable=self.port,width=8,state='readonly',font=(NUM,11));self.ports.pack(side='left',padx=(0,8),ipady=4)
        Pill(b,'刷新',self.refresh,width=70).pack(side='left',padx=4)
        self.connect_btn=Pill(b,'连接设备',self.toggle_connection,width=118,color=ACCENT,foreground=WHITE);self.connect_btn.pack(side='left',padx=4)
        self.connection=tk.Label(b,text='未连接',bg=WHITE,fg=MUTED);self.connection.pack(side='left',padx=16)
        Pill(b,'全屏 F11',self.toggle_fullscreen,width=100).pack(side='right')
        self.imu_reset_btn=Pill(b,'重连 IMU',self.reset_imu,width=98);self.imu_reset_btn.pack(side='right',padx=4)
        self.cal_btn=Pill(b,'校准 IMU',lambda:self.command('CAL'),width=108);self.cal_btn.pack(side='right',padx=8)
        status=tk.Frame(root,bg=BG);status.pack(fill='x',padx=36,pady=(17,12))
        self.state=tk.Label(status,text='先平放机器人，再连接设备',bg=BG,fg=INK,font=(FONT,11));self.state.pack(side='left')
        self.limit_label=tk.Label(status,bg=BG,fg=MUTED,font=(NUM,10));self.limit_label.pack(side='right')
        metrics=tk.Frame(root,bg=BG);metrics.pack(fill='x',padx=32)
        self.values={};self.servo_labels={}
        for i,(key,title,note,color) in enumerate([
            ('roll_rad','前后倾角','底座姿态 · Roll',GREEN),('pitch_rad','左右倾角','底座姿态 · Pitch',GREEN),
            ('lower_target','下关节 · ID 2','等待舵机反馈',ACCENT),('upper_target','上关节 · ID 1','等待舵机反馈',ACCENT)]):
            metrics.columnconfigure(i,weight=1,uniform='metric')
            card=Card(metrics,height=158,padding=18);card.grid(row=0,column=i,sticky='ew',padx=(0,12 if i<3 else 0))
            tk.Label(card.body,text=title,bg=WHITE,fg=INK,anchor='w').pack(fill='x')
            value=tk.Label(card.body,text='—',bg=WHITE,fg=color,font=(NUM,31),anchor='w');value.pack(fill='x',pady=(2,0));self.values[key]=value
            sub=tk.Label(card.body,text=note,bg=WHITE,fg=MUTED,font=(FONT,9),anchor='w',justify='left');sub.pack(fill='x')
            if key.endswith('target'):self.servo_labels[2 if key=='lower_target' else 1]=sub
        center=tk.Frame(root,bg=BG);center.pack(fill='both',expand=True,padx=32,pady=16)
        center.columnconfigure(0,weight=5);center.columnconfigure(1,weight=4);center.rowconfigure(0,weight=1)
        view=Card(center,height=225,padding=12);view.grid(row=0,column=0,sticky='nsew',padx=(0,14))
        self.pose=tk.Canvas(view.body,bg=WHITE,highlightthickness=0);self.pose.pack(fill='both',expand=True)
        guide=Card(center,height=225,padding=22);guide.grid(row=0,column=1,sticky='nsew')
        tk.Label(guide.body,text='三步，完成一次起身',font=(FONT,13),bg=WHITE,fg=INK,anchor='w').pack(fill='x',pady=(0,12))
        self.guide_steps=[]
        for number,title in [('01','平放连接，等待零点就绪'),('02','轻放倒并扶稳，手指避开关节'),('03','勾选扶护确认，点击「启动起身」')]:
            row=tk.Frame(guide.body,bg=WHITE);row.pack(fill='x',pady=7)
            tk.Label(row,text=number,font=(NUM,14),bg=WHITE,fg=ACCENT,width=3,anchor='w').pack(side='left',anchor='n')
            label=tk.Label(row,text=title,bg=WHITE,fg=INK,font=(FONT,10),anchor='w');label.pack(side='left',pady=3)
            self.guide_steps.append(label)
        action=Card(root,height=185,padding=20);action.pack(fill='x',padx=32)
        row=tk.Frame(action.body,bg=WHITE);row.pack(fill='x')
        tk.Checkbutton(row,text='已扶稳机器人',variable=self.supported,bg=WHITE,fg=INK,activebackground=WHITE,
                       selectcolor=WHITE,font=(FONT,11),cursor='hand2').pack(side='left',padx=(0,16))
        self.getup_btn=Pill(row,'启动起身',lambda:self.move('GETUP'),width=170,color=ACCENT,foreground=WHITE);self.getup_btn.pack(side='left')
        self.motion_buttons=[self.getup_btn]
        self.stop_btn=Pill(row,'停止并卸力 · Esc',self.emergency,width=180,color=RED,foreground=WHITE);self.stop_btn.pack(side='right')
        self.motion_label=tk.Label(action.body,text='停止会卸力，请保持扶护',bg=WHITE,fg=MUTED,font=(FONT,9),anchor='w');self.motion_label.pack(fill='x',pady=(14,0))
        zero_row=tk.Frame(action.body,bg=WHITE);zero_row.pack(fill='x',pady=(8,0))
        self.joint_zero_btn=Pill(zero_row,'保存当前直立关节零位',self.capture_joint_zero,width=205)
        self.joint_zero_btn.pack(side='left')
        self.joint_zero_label=tk.Label(zero_row,text='等待设备关节零位',bg=WHITE,fg=MUTED,font=(FONT,9),anchor='w')
        self.joint_zero_label.pack(side='left',padx=12)
        self.footer=tk.Label(root,text='手动启动  /  站稳回零  /  自动保存实验记录',bg=BG,fg=MUTED,font=(FONT,9));self.footer.pack(fill='x',pady=(12,16))
        self.refresh()

    def capture_joint_zero(self):
        if not self.joint_zero_btn.enabled:return
        confirmed=messagebox.askyesno('保存这台设备的关节零位','请确认：底座平放、两轴真实直立、机器人已扶稳且舵机已卸力。\n保存后本设备的启动、角度范围和回零都以此为基准。\n不要在倒下或关节弯折时保存。现在读取并保存？',parent=self.root)
        if confirmed:
            self.supported.set(False);self.command('JOINTZERO')
            self.log_message('开始只读稳定采样，保持真实直立约2秒；保存到本C3，不启动舵机。')

    def reset_imu(self):
        self.supported.set(False);self.command('IMURESET')
        self.log_message('重新初始化 IMU，保留本次水平零点；保持静止，恢复后手动启动。')

    def draw_chart(self):pass

    def draw(self):
        super().draw()
        live=self.link and self.link.verified and self.row and time.monotonic()-self.last_received<.6
        active=live and self.row['motion_phase'] in (1,2,3)
        self.getup_btn.configure(text='正在起身…' if active else '启动起身')
        for key in ('roll_rad','pitch_rad'):
            self.values[key].configure(fg=GREEN if live else MUTED)
        for key in ('lower_target','upper_target'):self.values[key].configure(fg=ACCENT if live else MUTED)
        for ident,label in self.servo_labels.items():
            r=self.row
            if live and r[f's{ident}_state']==1 and r[f's{ident}_age_ms']<=300:
                angle=(self.display_zeros[ident]-r[f's{ident}_position'])*360/4096
                label.configure(text=f'实际 {angle:+.1f}° · 目标见上方\n{r[f"s{ident}_voltage"]:.1f} V · '+('已卸力' if r[f's{ident}_torque']==0 else '扭矩已开启'),fg=MUTED)
        if live and self.row['quality'] in (1,2) and self.row['age_us']<=30000 and self.row['mode']!=3 and not active and self.row['motion_reason'] in (0,1,12,19) and self.row['zero_ready']:
            firmware=self.link.identity.firmware_name
            if start_positions_ok(self.row,firmware):
                self.state.configure(text='零点就绪 · 放倒并扶稳后，即可启动',fg=GREEN)
            else:self.state.configure(text='请先将两轴摆回直立零位附近',fg=MUTED)
        off=bool(live and self.row['motion_phase']==0 and self.row['motion_off']==1)
        self.imu_reset_btn.configure(state='normal' if off else 'disabled')
        self.cal_btn.configure(state='normal' if off and self.row['quality'] in (1,2) and self.row['age_us']<=30000 else 'disabled')
        dynamic=bool(self.link and self.link.identity.firmware_name in DYNAMIC_ZERO_FW)
        zsaved=bool(live and self.row.get('joint_zero_saved')==1)
        collecting=bool(live and self.row.get('joint_zero_state')==1)
        level=bool(live and self.row['quality'] in (1,2) and self.row['age_us']<=30000 and self.row['zero_ready'] and abs(self.row['roll_rad'])<.12 and abs(self.row['pitch_rad'])<.12)
        feedback=bool(live and all(self.row[f's{i}_state']==1 and self.row[f's{i}_age_ms']<=80 and self.row[f's{i}_torque']==0 for i in (1,2)))
        self.joint_zero_btn.configure(state='normal' if dynamic and off and level and feedback and not collecting else 'disabled')
        self.imu_reset_btn.configure(state='normal' if off and not collecting else 'disabled')
        imu_valid=bool(live and self.row['quality'] in (1,2) and self.row['age_us']<=30000)
        self.cal_btn.configure(state='normal' if off and imu_valid and not collecting else 'disabled')
        ztext=f"本设备零位 ID1 {self.display_zeros[1]} / ID2 {self.display_zeros[2]}" if zsaved else '本设备未保存：请将两轴真实直立后保存'
        if collecting:
            ztext='正在采样，请保持底座平放、两轴直立静止…';self.state.configure(text=ztext,fg=ACCENT)
        elif dynamic and live and self.row.get('joint_zero_state')==3:
            errors={1:'已取消或未卸力',2:'采样超时',3:'底座不水平/不静止或IMU未就绪',4:'舵机反馈/供电无效',5:'关节在移动，请保持直立静止',6:'编码器行程越界',7:'存储写入/校验失败'}
            ztext='保存失败：'+errors.get(self.row.get('joint_zero_error'),'未知原因')
        elif dynamic and live and not zsaved:self.state.configure(text='请先保存本设备的直立关节零位',fg=MUTED)
        self.joint_zero_label.configure(text=ztext,fg=GREEN if zsaved else MUTED)
        if dynamic and live and not zsaved:
            for ident,label in self.servo_labels.items():
                label.configure(text=f'编码器 {int(self.row[f"s{ident}_position"])} · 未设关节零位\n{self.row[f"s{ident}_voltage"]:.1f} V · '+('已卸力' if self.row[f's{ident}_torque']==0 else '扭矩已开启'))
            self.values['lower_target'].configure(text='—');self.values['upper_target'].configure(text='—')
            self.motion_label.configure(text='请把两轴摆成真实直立，点击“保存当前直立关节零位”；无需凑旧设备的编码器数值',fg=MUTED)
        self.footer.configure(text=('V25 · 模型推理 '+f'{self.last_infer/1000:.2f} ms'+' · 记录 '+str(self.recorder.count)+' 条' if self.recorder else '手动启动  /  站稳回零  /  自动保存实验记录'))


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--connect');args=parser.parse_args()
    root=tk.Tk();ui=EventDashboard(root)
    if args.connect:
        def connect():ui.port.set(args.connect);ui.toggle_connection()
        root.after(250,connect)
    root.mainloop()

if __name__=='__main__':main()
