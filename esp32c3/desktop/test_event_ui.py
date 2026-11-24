"""Event window layout and manual command checks, using synthetic telemetry only."""
import tempfile
import time
import tkinter as tk
import unittest
from types import SimpleNamespace
from event_app import EventDashboard
from data import FIELDS, FW, JOINT_ZEROS


class EventTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.ui=EventDashboard(self.root);self.root.update()
        self.tmp=tempfile.TemporaryDirectory();self.ui.record_dir=lambda:self.tmp.name
        self.sent=[]
        self.ui.link=SimpleNamespace(verified=True,identity=SimpleNamespace(firmware_name=FW),
            send=self.sent.append,stop_event=SimpleNamespace(set=lambda:None),join=lambda **k:None)
        r={k:0 for k in FIELDS};r.update(ms=1000,quality=1,zero_ready=1,zero_seq=1,motion_off=1,direction_sign=1)
        for i,z in JOINT_ZEROS.items():r.update({f's{i}_position':z,f's{i}_state':1,f's{i}_voltage':5})
        self.ui.receive(r)
    def tearDown(self):
        self.ui.close();self.tmp.cleanup()
    def test_layout_keeps_all_three_steps_and_stop_visible(self):
        for size in ['1000x760','1120x820']:
            self.root.geometry(size);self.root.update_idletasks();self.ui.draw()
            for label in self.ui.guide_steps:
                self.assertTrue(label.winfo_ismapped())
                self.assertLessEqual(label.winfo_rooty()+label.winfo_height(),label.master.master.winfo_rooty()+label.master.master.winfo_height())
                self.assertLessEqual(label.winfo_reqwidth(),label.master.winfo_width()-50)
            self.assertLessEqual(self.ui.stop_btn.winfo_rooty()+self.ui.stop_btn.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height())
    def test_no_motion_without_confirmation_and_recorder_required(self):
        self.ui.draw();self.ui.getup_btn.invoke();self.assertEqual(self.sent,[])
        self.ui.supported.set(True);self.ui.draw();self.ui.getup_btn.invoke()
        self.assertEqual(self.sent,['GETUP']);self.assertIsNotNone(self.ui.recorder)
        self.assertFalse(self.ui.supported.get())
    def test_escape_and_stop_work_without_confirmation(self):
        self.ui.emergency();self.assertEqual(self.sent,['STOP'])
        self.ui.stop_btn.invoke();self.assertEqual(self.sent,['STOP','STOP'])
    def test_bad_imu_is_not_displayed_as_ready(self):
        self.ui.receive(dict(self.ui.row,quality=3,mode=3,reason=4));self.ui.draw()
        self.assertNotIn('零点就绪',self.ui.state.cget('text'))
        self.assertFalse(self.ui.getup_btn.enabled)
        self.assertTrue(self.ui.imu_reset_btn.enabled)
    def test_reconnect_only_off_and_not_calibration(self):
        self.ui.draw();self.ui.imu_reset_btn.invoke()
        self.assertEqual(self.sent,['IMURESET'])
        self.ui.receive(dict(self.ui.row,motion_phase=2,motion_off=0));self.ui.draw()
        self.assertFalse(self.ui.imu_reset_btn.enabled);self.assertFalse(self.ui.cal_btn.enabled)
    def test_compute_timeout_keeps_specific_reason(self):
        self.ui.receive(dict(self.ui.row,mode=3,reason=8,motion_reason=13));self.ui.draw()
        self.assertIn('周期超时',self.ui.state.cget('text'))
    def test_stale_and_displaced_feedback_cannot_enable_start(self):
        self.ui.supported.set(True);self.ui.last_received=time.monotonic()-1;self.ui.draw()
        self.assertFalse(self.ui.getup_btn.enabled)
        self.ui.receive(dict(self.ui.row,s2_position=3100));self.ui.draw()
        self.assertFalse(self.ui.getup_btn.enabled)
        self.assertIn('摆回',self.ui.state.cget('text'))

if __name__=='__main__':unittest.main()
