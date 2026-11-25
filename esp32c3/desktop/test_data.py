import json
import math
from pathlib import Path
import tempfile
import unittest
from data import FIELDS,V5_FIELDS,V4_FIELDS,LEGACY_FIELDS,FW,MODEL,DIRECTIONAL_MODEL,REVERSED_MODEL,CAL,Identity,Recorder,parse,replay_rows,JOINT_ZEROS,JOINT_RANGE,MODELS,startup_tolerance,start_positions_ok,motion_reason_text,home_settings
from transport import Link

class Tests(unittest.TestCase):
    def row(self):
        row={k:0 for k in FIELDS};row.update(direction_sign=1,mode=1,quality=1,qw=1,az_g=1,acc_norm=1,motion_cmd1=JOINT_ZEROS[1],motion_cmd2=JOINT_ZEROS[2])
        row.update(joint_zero1=337,joint_zero2=2872,joint_zero_saved=1)
        return row,','.join(str(row[k]) for k in FIELDS)
    def test_reject_nonfinite_and_invalid_targets(self):
        row,line=self.row();self.assertEqual(parse(line)['mode'],1)
        with self.assertRaises(ValueError):parse(line.replace('1','nan',1))
        row['lower_target']=2.2
        with self.assertRaises(ValueError):parse(','.join(str(row[k]) for k in FIELDS))
    def test_identity_requires_all_three_matching_fields(self):
        identity=Identity();identity.feed(f'\ufffdROM_GARBAGE# FW={FW} BAUD=230400 SERVO_OUTPUT=LIMITED');identity.feed('# MODEL_SHA256='+MODELS[FW])
        self.assertFalse(identity.verified);identity.feed('# CALIBRATION_SHA256='+CAL);self.assertTrue(identity.verified)
        identity.feed('# MODEL_SHA256=wrong');self.assertFalse(identity.verified)
    def test_new_boot_requires_fresh_identity(self):
        identity=Identity()
        for line in [f'# FW={FW} BAUD=230400 SERVO_OUTPUT=LIMITED','# MODEL_SHA256='+MODELS[FW],'# CALIBRATION_SHA256='+CAL]:identity.feed(line)
        self.assertTrue(identity.verified)
        identity.feed(f'# FW={FW} BAUD=230400 SERVO_OUTPUT=LIMITED');self.assertFalse(identity.verified)
        identity.feed('# MODEL_SHA256='+MODELS[FW]);self.assertFalse(identity.verified)
        identity.feed('# CALIBRATION_SHA256='+CAL);self.assertTrue(identity.verified)
    def test_v8_v9_record_actual_range_and_reject_unknown(self):
        for firmware,gyro in [('HD1910_RECOVERY_V8',250),('HD1910_RECOVERY_V9',2000)]:
            identity=Identity()
            for line in [f'# FW={firmware} BAUD=230400 SERVO_OUTPUT=LIMITED','# MODEL_SHA256='+MODELS[firmware],'# CALIBRATION_SHA256='+CAL]:identity.feed(line)
            self.assertTrue(identity.verified)
            self.assertEqual(identity.firmware_name,firmware)
            with tempfile.TemporaryDirectory() as path:
                record=Recorder(path,'test:synthetic',firmware=identity.firmware_name)
                row,line=self.row();record.append(line,row);record.close()
                meta=json.loads(record.base.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()[0])
                self.assertEqual(meta['firmware'],firmware)
                self.assertEqual(meta['imu_gyro_range_dps'],gyro)
                self.assertAlmostEqual(replay_rows(record.base.with_suffix('.jsonl')).target_limit_rad,2.0943951023931953)
            identity.feed('# FW=UNKNOWN BAUD=230400 SERVO_OUTPUT=LIMITED')
            self.assertFalse(identity.verified)
            self.assertIsNone(identity.firmware_name)
    def test_replay_rejects_clock_reset(self):
        with tempfile.TemporaryDirectory() as path:
            record=Recorder(path,'test:synthetic');row,line=self.row()
            for ms in (1000,20):
                row['ms']=ms;record.append(','.join(str(row[k]) for k in FIELDS),row)
            record.close()
            with self.assertRaisesRegex(ValueError,'\u91cd\u542f'):replay_rows(record.base.with_suffix('.jsonl'))
    def test_legacy_rows_only_accepted_for_replay(self):
        row,line=self.row();old=','.join(str(row[k]) for k in LEGACY_FIELDS)
        self.assertIsNone(parse(old))
        replay=parse(old,allow_legacy=True)
        self.assertEqual(replay['zero_seq'],0)
        self.assertEqual(replay['raw_roll_rad'],row['roll_rad'])
    def test_record_and_replay_preserve_values_and_source(self):
        with tempfile.TemporaryDirectory() as path:
            record=Recorder(path,'test:synthetic');row,line=self.row();record.append('# ACK START');record.append(line,row);record.close()
            self.assertEqual(replay_rows(record.base.with_suffix('.jsonl')),[row])
            self.assertEqual(json.loads(record.base.with_suffix('.json').read_text())['source'],'test:synthetic')
            self.assertEqual(len(record.base.with_suffix('.csv').read_text(encoding='utf-8-sig').splitlines()),2)
    def test_cannot_send_arbitrary_or_servo_commands(self):
        link=Link('NOT_OPENED')
        for cmd in ['RUN','TORQUE_ON','WRITE','START\nRUN']:
            with self.assertRaises(ValueError):link.send(cmd)
        self.assertTrue(link.commands.empty())
    def test_stop_discards_queued_motion(self):
        link=Link('NOT_OPENED');link.send('HOLD');link.send('TEST2');link.send('STOP')
        self.assertTrue(link.commands.empty());self.assertTrue(link.emergency.is_set())
    def test_reject_invalid_physical_output_and_phase(self):
        row,_=self.row();row['motion_cmd1']=JOINT_ZEROS[1]+JOINT_RANGE[1]+1
        with self.assertRaises(ValueError):parse(','.join(str(row[k]) for k in FIELDS))
        row['motion_cmd1']=JOINT_ZEROS[1];row['motion_phase']=4
        with self.assertRaises(ValueError):parse(','.join(str(row[k]) for k in FIELDS))

    def test_recovery_negative_goal_only_in_recovery(self):
        row,_=self.row();row.update(motion_phase=2,motion_kind=5,motion_cmd1=-687)
        self.assertEqual(parse(','.join(str(row[k]) for k in FIELDS))['motion_cmd1'],-687)
        row['motion_kind']=4
        with self.assertRaises(ValueError):parse(','.join(str(row[k]) for k in FIELDS))
        row['motion_phase']=0
        self.assertEqual(parse(','.join(str(row[k]) for k in FIELDS))['motion_cmd1'],-687)

    def test_old_record_retains_its_own_zero(self):
        row,_=self.row();row.update(motion_cmd1=341,motion_cmd2=2899)
        with tempfile.TemporaryDirectory() as path:
            p=Path(path)/'old.jsonl'
            p.write_text(json.dumps({'type':'session','firmware':'HD1910_LIMITED_V4'})+'\n'+json.dumps({'raw':','.join(str(row[k]) for k in FIELDS)})+'\n',encoding='utf-8')
            rows=replay_rows(p)
            self.assertEqual(rows.joint_zeros,{1:341,2:2899})
            self.assertEqual(rows[0]['motion_cmd2'],2899)

    def test_v10_limits_and_record_replay(self):
        row,_=self.row();row.update(motion_phase=2,motion_kind=5,motion_cmd1=-1142,motion_cmd2=3896,
                                  lower_target=math.radians(90),upper_target=math.radians(130))
        line=','.join(str(row[k]) for k in FIELDS)
        self.assertEqual(parse(line)['upper_target'],math.radians(130))
        with tempfile.TemporaryDirectory() as path:
            record=Recorder(path,'test:synthetic');record.append(line,row);record.close()
            rows=replay_rows(record.base.with_suffix('.jsonl'))
            self.assertEqual(rows.target_limits_rad,(math.radians(95),math.radians(135)))
            self.assertEqual(rows.model_sha256,MODELS[FW])
            self.assertEqual(rows[0],row)
        for key,value in [('lower_target',math.radians(96)),('upper_target',math.radians(136)),('motion_cmd1',-1200),('motion_cmd2',3953)]:
            bad=dict(row);bad[key]=value
            with self.assertRaises(ValueError):parse(','.join(str(bad[k]) for k in FIELDS))

    def test_version_model_pair_must_match(self):
        for fw,wrong in [(FW,MODELS['HD1910_RECOVERY_V8']),('HD1910_RECOVERY_V8',MODEL)]:
            identity=Identity()
            for line in [f'# FW={fw} BAUD=230400 SERVO_OUTPUT=LIMITED','# MODEL_SHA256='+wrong,'# CALIBRATION_SHA256='+CAL]:identity.feed(line)
            self.assertFalse(identity.verified)

    def test_widened_start_respects_version_and_both_axes(self):
        for fw,limit in [('HD1910_RECOVERY_V10',24),(FW,48)]:
            self.assertEqual(startup_tolerance(fw),limit)
            row,_=self.row()
            row.update(s1_position=337+limit,s2_position=2872-limit)
            self.assertTrue(start_positions_ok(row,fw))
            row['s1_position']+=1;self.assertFalse(start_positions_ok(row,fw))
            row.update(s1_position=337-limit,s2_position=2872+limit)
            self.assertTrue(start_positions_ok(row,fw))
            row['s2_position']+=1;self.assertFalse(start_positions_ok(row,fw))
        row,_=self.row();row.update(s1_position=363,s2_position=2917)
        self.assertTrue(start_positions_ok(row,FW))
        self.assertFalse(start_positions_ok(row,'HD1910_RECOVERY_V10'))

    def test_local_capture_envelope_matches_firmware_version(self):
        row,_=self.row();row.update(motion_phase=2,motion_kind=1,motion_cmd1=385,motion_cmd2=2824)
        line=','.join(str(row[k]) for k in FIELDS)
        self.assertIsNotNone(parse(line,firmware=FW))
        with self.assertRaises(ValueError):parse(line,firmware='HD1910_RECOVERY_V10')
        row['motion_cmd1']=386
        with self.assertRaises(ValueError):parse(','.join(str(row[k]) for k in FIELDS),firmware=FW)
        self.assertEqual(MODELS['HD1910_RECOVERY_V10'],MODEL)

    def test_v11_live_rows_preserve_motion_and_v12_requires_stage(self):
        row,_=self.row();row.update(motion_phase=2,motion_kind=5,motion_cmd1=-500,motion_cmd2=3100)
        line=','.join(str(row[k]) for k in V4_FIELDS)
        old=parse(line,firmware='HD1910_RECOVERY_V11')
        self.assertEqual(old['motion_cmd1'],-500);self.assertEqual(old['recovery_stage'],0)
        self.assertIsNone(parse(line,firmware=FW))
        self.assertEqual(parse(line,allow_legacy=True)['motion_cmd2'],3100)

    def test_recovery_stages_and_latched_failure_survive_replay(self):
        row,_=self.row();row.update(motion_phase=0,motion_reason=7,motion_fault_id=2,
            motion_fault_actual=3087,motion_fault_target=2567,s2_position=2938,recovery_stage=2)
        line=','.join(str(row[k]) for k in FIELDS)
        text=motion_reason_text(parse(line))
        self.assertIn('下轴 ID2',text);self.assertIn('45.7°',text)
        self.assertIn('3087',text);self.assertNotIn('2938',text)
        with tempfile.TemporaryDirectory() as path:
            r=Recorder(path,'test:synthetic');r.append(line,row);r.close()
            self.assertEqual(replay_rows(r.base.with_suffix('.jsonl')),[row])
        for key,value in [('recovery_stage',5),('motion_fault_id',3),('motion_fault_target',32768)]:
            bad=dict(row);bad[key]=value
            with self.assertRaises(ValueError):parse(','.join(str(bad[k]) for k in FIELDS))

    def test_home_speed_metadata_preserves_firmware_version(self):
        for fw,step in [('HD1910_RECOVERY_V12',6),('HD1910_RECOVERY_V13',9),('HD1910_RECOVERY_V14',9)]:
            row,_=self.row();line=','.join(str(row[k]) for k in FIELDS)
            with tempfile.TemporaryDirectory() as path:
                rec=Recorder(path,'test:synthetic',firmware=fw);rec.append(line,row);rec.close()
                meta=json.loads(rec.base.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()[0])
                self.assertTrue(meta['automatic_return_to_zero'])
                self.assertEqual(meta['auto_home_settings']['step_counts'],step)
                self.assertEqual(meta['auto_home_settings']['lead_counts'],24)
            self.assertIsNone(parse(','.join(str(row[k]) for k in V4_FIELDS),firmware=fw))
        self.assertIsNone(home_settings('HD1910_RECOVERY_V11'))

    def test_v14_requires_both_network_bundle_and_router_state(self):
        identity=Identity()
        for line in [f'# FW={FW} BAUD=230400 SERVO_OUTPUT=LIMITED','# MODEL_SHA256='+MODEL,'# CALIBRATION_SHA256='+CAL]:identity.feed(line)
        self.assertFalse(identity.verified)
        identity.feed('# MODEL_SHA256='+MODELS[FW]);self.assertTrue(identity.verified)
        row,_=self.row();row.update(recovery_stage=3,motion_fault_id=2,motion_fault_actual=3100,motion_fault_target=2600)
        old=','.join(str(row[k]) for k in V5_FIELDS)
        self.assertIsNone(parse(old,firmware=FW))
        for fw in ('HD1910_RECOVERY_V12','HD1910_RECOVERY_V13'):
            parsed=parse(old,firmware=fw)
            self.assertEqual(parsed['recovery_stage'],3)
            self.assertEqual(parsed['motion_fault_actual'],3100)
            self.assertEqual(parsed['direction_sign'],1)
        self.assertEqual(parse(old,allow_legacy=True)['motion_fault_id'],2)

    def test_directional_state_validation_and_metadata(self):
        row,_=self.row();row.update(direction_mode=1,direction_sign=-1,direction_stable=42,direction_elapsed=700)
        line=','.join(str(row[k]) for k in FIELDS)
        self.assertEqual(parse(line),row)
        with tempfile.TemporaryDirectory() as path:
            rec=Recorder(path,'test:synthetic');rec.append(line,row);rec.close()
            self.assertEqual(replay_rows(rec.base.with_suffix('.jsonl')),[row])
            meta=json.loads(rec.base.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()[0])
            self.assertEqual(meta['direction_models']['side'],'c958db0d1c87dbe3d8e400a1519076494eb930f008d93d7223b22ec358b055ba')
            self.assertEqual(meta['direction_models']['bundle'],MODELS[FW])
        for key,value in [('direction_mode',3),('direction_sign',0),('direction_stable',51),('direction_elapsed',-1),('direction_elapsed',1.5)]:
            bad=dict(row);bad[key]=value
            with self.assertRaises(ValueError):parse(','.join(str(bad[k]) for k in FIELDS))

    def test_v15_reversal_identity_and_history(self):
        for fw,model,sign in [('HD1910_RECOVERY_V14',DIRECTIONAL_MODEL,1),('HD1910_RECOVERY_V15',REVERSED_MODEL,-1)]:
            identity=Identity()
            for s in [f'# FW={fw} BAUD=230400 SERVO_OUTPUT=LIMITED','# MODEL_SHA256='+model,'# CALIBRATION_SHA256='+CAL]:identity.feed(s)
            self.assertTrue(identity.verified)
            identity.feed('# MODEL_SHA256='+(REVERSED_MODEL if sign==1 else DIRECTIONAL_MODEL))
            self.assertFalse(identity.verified)
            with tempfile.TemporaryDirectory() as path:
                rec=Recorder(path,'test:synthetic',firmware=fw);rec.close()
                meta=json.loads(rec.base.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()[0])
                self.assertEqual(meta['front_back_ID2_joint_sign'],sign)
                self.assertEqual(meta['direction_models']['bundle'],model)

    def test_v16_pacing_metadata_and_fault_language(self):
        for fw,step,lead in [('HD1910_RECOVERY_V15',52,None),('HD1910_RECOVERY_V16',26,192)]:
            with tempfile.TemporaryDirectory() as path:
                rec=Recorder(path,'test:synthetic',firmware=fw);rec.close()
                meta=json.loads(rec.base.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()[0])
                self.assertEqual(meta['front_back_ID2_joint_sign'],-1)
                self.assertEqual(meta['recovery_pacing']['front_back_id2_step_counts'],step)
                self.assertEqual(meta['recovery_pacing']['front_back_id2_lead_counts'],lead)
                self.assertEqual(meta['recovery_pacing']['tracking_stop_counts'],512)
        row,_=self.row();row.update(motion_reason=7,motion_fault_id=2,motion_fault_actual=2509,motion_fault_target=1962)
        text=motion_reason_text(row)
        self.assertIn('未跟上目标',text);self.assertIn('48.1°',text)

    def test_v17_both_joint_pacing_and_history(self):
        for fw,step,lead in [('HD1910_RECOVERY_V16',52,None),('HD1910_RECOVERY_V17',26,192)]:
            identity=Identity()
            for s in [f'# FW={fw} BAUD=230400 SERVO_OUTPUT=LIMITED','# MODEL_SHA256='+REVERSED_MODEL,'# CALIBRATION_SHA256='+CAL]:identity.feed(s)
            self.assertTrue(identity.verified)
            with tempfile.TemporaryDirectory() as path:
                rec=Recorder(path,'test:synthetic',firmware=fw);rec.close()
                meta=json.loads(rec.base.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()[0])
                self.assertEqual(meta['recovery_pacing']['dual_step_counts'],step)
                self.assertEqual(meta['recovery_pacing'].get('dual_lead_counts'),lead)
                self.assertEqual(meta['auto_home_settings']['step_counts'],9)
                self.assertEqual(meta['front_back_ID2_joint_sign'],-1)
                if fw=='HD1910_RECOVERY_V17':
                    self.assertEqual(meta['recovery_pacing']['paced_ids'],[1,2])
        row,_=self.row();row.update(motion_reason=7,motion_fault_id=1,motion_fault_actual=21,motion_fault_target=-493)
        text=motion_reason_text(row)
        self.assertIn('上轴 ID1',text);self.assertIn('45.2°',text)

    def test_v18_fractional_increment_metadata_and_identity(self):
        for fw,enabled in [('HD1910_RECOVERY_V17',False),('HD1910_RECOVERY_V18',True)]:
            identity=Identity()
            for line in [f'# FW={fw} BAUD=230400 SERVO_OUTPUT=LIMITED','# MODEL_SHA256='+REVERSED_MODEL,'# CALIBRATION_SHA256='+CAL]:identity.feed(line)
            self.assertTrue(identity.verified)
            with tempfile.TemporaryDirectory() as path:
                r=Recorder(path,'test:synthetic',firmware=fw);r.close()
                meta=json.loads(r.base.with_suffix('.jsonl').read_text(encoding='utf-8').splitlines()[0])
                sub=meta['recovery_pacing']['subcount_accumulator']
                self.assertEqual(sub is not None,enabled)
                if enabled:
                    self.assertEqual(sub['cap_counts'],1)
                    self.assertEqual(sub['below_counts'],0.5)
                self.assertEqual(meta['recovery_pacing']['dual_step_counts'],26)
                self.assertEqual(meta['recovery_pacing']['dual_lead_counts'],192)

if __name__=='__main__':unittest.main()
