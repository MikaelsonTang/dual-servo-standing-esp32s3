import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from test_event_ui import EventTests
from data import FW,FIELDS,Identity,parse,start_positions_ok,Recorder,replay_rows
from transport import require_current_firmware

class DeviceZeroTests(EventTests):
    def test_live_window_rejects_old_firmware(self):
        current=Identity();line=f'# FW={FW} BAUD=230400 SERVO_OUTPUT=LIMITED';current.feed(line)
        require_current_firmware(line,current)
        old=Identity();line='# FW=HD1910_C3_TEST_V25 BAUD=230400 SERVO_OUTPUT=LIMITED';old.feed(line)
        with self.assertRaisesRegex(RuntimeError,'固件版本不匹配'):require_current_firmware(line,old)

    def test_v26_has_no_recovery_total_deadline_in_ui_or_metadata(self):
        from data import home_settings,recovery_pacing
        self.ui.draw();self.assertIn('无总时限',self.ui.limit_label.cget('text'))
        self.assertNotIn('14 秒',self.ui.limit_label.cget('text'))
        self.assertIsNone(home_settings(FW)['total_deadline_ms'])
        profile=recovery_pacing(FW)
        self.assertEqual((profile['current_limit_register'],profile['torque_limit_register'],profile['speed_register']),(150,900,150))
    def custom(self,saved=1):
        r=dict(self.ui.row,joint_zero1=4045,joint_zero2=321,joint_zero_saved=saved,
               s1_position=4045,s2_position=321,motion_cmd1=4045,motion_cmd2=321)
        self.ui.receive(r);return r
    def test_custom_zero_frame_accepted_and_start_enabled(self):
        r=self.custom();parsed=parse(','.join(str(r[k]) for k in FIELDS),firmware=FW)
        self.assertTrue(start_positions_ok(parsed,FW));self.ui.supported.set(True);self.ui.draw()
        self.assertTrue(self.ui.getup_btn.enabled);self.assertEqual(self.ui.display_zeros,{1:4045,2:321})
        self.assertNotIn('289',self.ui.motion_label.cget('text'))
    def test_new_device_must_explicitly_save_zero(self):
        self.custom(saved=0);self.ui.supported.set(True);self.ui.draw()
        self.assertFalse(self.ui.getup_btn.enabled);self.assertTrue(self.ui.joint_zero_btn.enabled)
        self.assertIn('未设',self.ui.servo_labels[1].cget('text'))
    def test_capture_confirmation_and_no_automatic_motion(self):
        self.custom(saved=0);self.ui.draw()
        with patch('event_app.messagebox.askyesno',return_value=False):self.ui.joint_zero_btn.invoke()
        self.assertEqual(self.sent,[])
        with patch('event_app.messagebox.askyesno',return_value=True):self.ui.joint_zero_btn.invoke()
        self.assertEqual(self.sent,['JOINTZERO']);self.assertFalse(self.ui.supported.get())
    def test_collecting_or_fallen_cannot_save_or_start(self):
        r=self.custom();self.ui.receive(dict(r,joint_zero_state=1));self.ui.supported.set(True);self.ui.draw()
        self.assertFalse(self.ui.getup_btn.enabled);self.assertFalse(self.ui.joint_zero_btn.enabled)
        self.ui.receive(dict(r,roll_rad=1.5));self.ui.draw();self.assertFalse(self.ui.joint_zero_btn.enabled)
    def test_record_replay_uses_device_zero_each_frame(self):
        r=self.custom()
        with tempfile.TemporaryDirectory() as directory:
            rec=Recorder(directory,'synthetic',firmware=FW)
            raw=','.join(str(r[k]) for k in FIELDS);rec.append(raw,r);path=rec.base.with_suffix('.jsonl');rec.close()
            replay=replay_rows(path)
            self.assertEqual(replay[0]['joint_zero1'],4045);self.assertEqual(replay[0]['joint_zero2'],321)
            self.assertTrue(start_positions_ok(replay[0],FW))
