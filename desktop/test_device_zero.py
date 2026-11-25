"""Per-device zero must govern both the startup guard and the visible UI."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data import FIELDS, FW, Identity, Recorder, parse, replay_rows, start_positions_ok
from transport import require_current_firmware
from test_event_ui import EventTests


class DeviceZeroTests(EventTests):
    def test_live_window_rejects_old_firmware(self):
        self.assertIn('ESP32-S3 · V21',self.root.title())
        current=Identity();line=f'# FW={FW} BAUD=230400 SERVO_OUTPUT=LIMITED';current.feed(line)
        require_current_firmware(line,current)
        old=Identity();line='# FW=HD1910_RECOVERY_V20 BAUD=230400 SERVO_OUTPUT=LIMITED';old.feed(line)
        with self.assertRaisesRegex(RuntimeError,'固件版本不匹配'):require_current_firmware(line,old)

    def custom(self, saved=1):
        row = dict(self.ui.row, joint_zero1=4045, joint_zero2=321,
                   joint_zero_saved=saved, s1_position=4045, s2_position=321,
                   motion_cmd1=4045, motion_cmd2=321)
        self.ui.receive(row)
        return row

    def test_saved_zero_accepts_new_positions(self):
        row = self.custom()
        parsed = parse(','.join(str(row[k]) for k in FIELDS), firmware=FW)
        self.assertTrue(start_positions_ok(parsed, FW))
        self.ui.supported.set(True)
        self.ui.draw()
        self.assertTrue(self.ui.getup_btn.enabled)
        self.assertEqual(self.ui.display_zeros, {1: 4045, 2: 321})
        for ident in (1, 2):
            displaced = dict(row, **{f's{ident}_position': row[f's{ident}_position'] + 49})
            self.assertFalse(start_positions_ok(displaced, FW))

    def test_new_board_needs_explicit_capture(self):
        self.custom(saved=0)
        self.ui.supported.set(True)
        self.ui.draw()
        self.assertFalse(self.ui.getup_btn.enabled)
        self.assertTrue(self.ui.joint_zero_btn.enabled)
        with patch('event_app.messagebox.askyesno', return_value=False):
            self.ui.joint_zero_btn.invoke()
        self.assertEqual(self.sent, [])
        with patch('event_app.messagebox.askyesno', return_value=True):
            self.ui.joint_zero_btn.invoke()
        self.assertEqual(self.sent, ['JOINTZERO'])
        self.assertFalse(self.ui.supported.get())

    def test_capture_requires_off_level_stable(self):
        row = self.custom()
        self.ui.receive(dict(row, joint_zero_state=1))
        self.ui.draw()
        self.assertFalse(self.ui.joint_zero_btn.enabled)
        self.ui.receive(dict(row, roll_rad=1.5))
        self.ui.draw()
        self.assertFalse(self.ui.joint_zero_btn.enabled)

    def test_record_replay_uses_frame_zero(self):
        row = self.custom()
        with tempfile.TemporaryDirectory() as directory:
            recorder = Recorder(directory, 'synthetic', firmware=FW)
            recorder.append(','.join(str(row[k]) for k in FIELDS), row)
            path = recorder.base.with_suffix('.jsonl')
            recorder.close()
            rows = replay_rows(path)
            self.assertTrue(start_positions_ok(rows[0], FW))
            self.assertEqual(rows[0]['joint_zero1'], 4045)
            self.assertEqual(rows[0]['joint_zero2'], 321)


if __name__ == '__main__':
    unittest.main()
