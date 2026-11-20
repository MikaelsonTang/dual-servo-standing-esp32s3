#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include "src/bosch/bmi270.h"
#include "attitude_filter.h"
#include "imu_scale.h"
#include "calibration_generated.h"
#include "directional_runtime.h"
#include "directional_checks.h"
#include "shadow_core.h"
#include "startup_zero.h"
#include "servo_reader.h"
#include "limited_motion.h"

// Explicit, bounded motion commands only. START remains computation-only.
constexpr char FW[]="HD1910_RECOVERY_V20";
// Bundle identity binds both exported networks, the router and its contract.
constexpr char MODEL_SHA[]="86647683a0628acff8f2fe8699cb7e644ba2aed419d94edb244a00a23022503e";
constexpr int SDA_PIN=6,SCL_PIN=7;
AttitudeFilter filter;
StartupZero zero;
ServoReader servos;
Motion::Controller<ServoReader> motion(servos);
DirectionController direction;
unsigned requestedMotion=0;
uint32_t motionRequestAt=0;
bmi2_dev imu={};
uint8_t imuAddress=0;
bool ready=false,enabled=false,numericOk=false,haveSample=false;
uint32_t lastSample=0,lastError=0,lastSampleUs=0,sampleSequence=0,saturations=0;
uint32_t nextTick=0,lastTick=0,tick=0,policySequence=0,lastHeartbeat=0;
uint32_t skipped=0,missed=0,inferUs=0,imuUs=0,loopMaxUs=0,periodUs=0,lateUs=0;
float a[3]={},wDps[3]={},target[2]={},before[2]={},action[2]={};
// reason: 0 OK,1 paused,2 acquiring,3 stale,4 IMU error,5 filter invalid,
// 6 numeric,7 host timeout,8 control deadline,9 zero calibration.
unsigned reason=1;
#include "imu_setup.h"

void stopShadow(unsigned why){enabled=false;reason=why;action[0]=action[1]=0;if(motion.engaged())motion.stop(why==1?Motion::HOST_STOP:Motion::IMU);}
bool motionImu(float& tilt){
  float relative[4],r=0,p=0;bool singular=false;
  bool ok=numericOk&&ready&&zero.ready&&haveSample&&filter.initialized&&
    (filter.quality==1||filter.quality==2)&&Shadow::fresh(micros(),lastSampleUs)&&
    zero.relative(filter.q,relative)&&Shadow::angles(relative,r,p,singular);
  // Angle of the base up vector to vertical, including inverted postures.
  tilt=acosf(Shadow::clip(cosf(r)*cosf(p),-1.f,1.f));return ok;
}
void banner(){
  Serial.println();
  Serial.printf("# FW=%s BAUD=230400 SERVO_OUTPUT=LIMITED\n",FW);
  Serial.printf("# MODEL_SHA256=%s\n",MODEL_SHA);
  Serial.println("# MODEL_FRONT_BACK_SHA256=63b35958ed7652a6f9fc75a3c03a02a08d051322b9752ee5b7850105e6ed22b3");
  Serial.println("# MODEL_SIDE_SHA256=c958db0d1c87dbe3d8e400a1519076494eb930f008d93d7223b22ec358b055ba");
  Serial.println("# FRONT_BACK_ID2_SIGN=-1 OBS_AND_ACTION; DUAL_AND_HOME_UNCHANGED");
  Serial.println("# RECOVERY_PACING IDS=1,2 STEP=26/20ms LEAD=192counts EACH_JOINT ALL_BRANCHES TRACKING_STOP=512counts");
  Serial.println("# FRONT_PACING ID2_STEP=34/20ms FRONT_SIGN=1 ACTIVE_ROLL_GT=30deg PITCH_LT=0.20rad LEAD=192counts SPEED_REGISTER=50");
  Serial.println("# SUBCOUNT ACCUMULATE_BELOW=0.5count CAP=1count CONSUME_ON_GOAL_WRITE RESET_ON_STOP_OR_HOME");
  Serial.printf("# CALIBRATION_SHA256=%s\n",CALIBRATION_SHA256);
  Serial.printf("# IMU_RANGE ACCEL_G=%.0f GYRO_DPS=%.0f SATURATION_FRACTION=%.3f\n",ImuScale::ACCEL_FULL_SCALE_G,ImuScale::GYRO_FULL_SCALE_DPS,ImuScale::SATURATION_FRACTION);
  Serial.println("# LIMITS START_ZERO=48counts LOCAL=24counts GETUP_COUNTS_ID1=1536 ID2=1080 TARGET_TRAINED_ID1=135deg ID2=95deg STEP=26/20ms GETUP_TIME=14s VOLTAGE=4.0..5.5V HEARTBEAT=500ms; START=observer_only");
  Serial.println("# AUTO_HOME FALL_SEEN=35deg UPRIGHT=12deg RATE=35dps DWELL=150ms HOME_STEP=9/20ms HOME_LEAD=24counts HOME_TOL=8counts HOLD=500ms TOTAL_TIME=14s THEN_OFF");
}
void commands(){
  static char line[48];static unsigned count=0;static bool overflow=false;
  unsigned budget=64;
  while(Serial.available()&&budget--){
    char c=Serial.read();if(c=='\r')continue;
    if(c!='\n'){if(count<sizeof(line)-1)line[count++]=c;else overflow=true;continue;}
    line[count]=0;
    if(!overflow){
      if(!strcmp(line,"HEARTBEAT"))lastHeartbeat=millis();
      else if(!strcmp(line,"STATUS"))banner();
      else if(!strcmp(line,"STOP")||!strcmp(line,"PAUSE")){requestedMotion=0;stopShadow(1);motion.stop(Motion::HOST_STOP);Serial.println("# ACK STOP requested; wait for motion_off=1");}
      else if(!strcmp(line,"HOLD")||!strcmp(line,"TEST1")||!strcmp(line,"TEST2")||!strcmp(line,"POLICY")||!strcmp(line,"GETUP")){
        if(motion.phase==0&&motion.offConfirmed){
          stopShadow(1);requestedMotion=!strcmp(line,"HOLD")?Motion::HOLD:!strcmp(line,"TEST1")?Motion::UPPER:!strcmp(line,"TEST2")?Motion::LOWER:!strcmp(line,"GETUP")?Motion::RECOVERY:Motion::POLICY;
          motionRequestAt=millis();Serial.println("# MOTION_REQUEST pending_preflight");
        }else Serial.println("# REJECT MOTION not_off");
      }
      else if(!strcmp(line,"ZERO")){requestedMotion=0;stopShadow(1);target[0]=target[1]=0;Serial.println("# ACK ZERO virtual_targets_only");}
      else if(!strcmp(line,"CAL")){requestedMotion=0;stopShadow(9);zero.request();Serial.println("# ACK CAL keep_base_level_and_still");}
      else if(!strcmp(line,"START")){
        if(motion.phase==0&&!requestedMotion&&numericOk&&ready&&zero.ready&&haveSample&&filter.initialized&&(filter.quality==1||filter.quality==2)&&Shadow::fresh(micros(),lastSampleUs)){
          direction.reset();enabled=true;reason=0;lastHeartbeat=millis();Serial.println("# ACK START");
        }else Serial.println("# REJECT START IMU_NOT_READY");
      }else Serial.println("# REJECT UNKNOWN_COMMAND");
    }else {requestedMotion=0;motion.stop(Motion::HOST_STOP);stopShadow(1);Serial.println("# REJECT COMMAND_TOO_LONG");}
    count=0;overflow=false;
  }
}
void sampleImu(){
  if(!ready)return;
  uint32_t begin=micros();bmi2_sens_data data={};
  int8_t code=bmi2_get_sensor_data(&data,&imu);imuUs=micros()-begin;
  if(code!=BMI2_OK){
    if(!zero.ready)zero.clearWindow();
    if(filter.quality!=3)filter.invalidate();
    stopShadow(4);errorMessage("I2C sample read failed");return;
  }
  if(!(data.status&BMI2_DRDY_ACC)||!(data.status&BMI2_DRDY_GYR))return;
  lastSample=millis();lastSampleUs=micros();haveSample=true;++sampleSequence;
  float rawA[3]={ImuScale::accel(data.acc.x),ImuScale::accel(data.acc.y),ImuScale::accel(data.acc.z)};
  float rawW[3]={ImuScale::gyro(data.gyr.x),ImuScale::gyro(data.gyr.y),ImuScale::gyro(data.gyr.z)};
  bool saturated=false;for(int i=0;i<3;++i)if(ImuScale::saturated(rawA[i],rawW[i]))saturated=true;
  if(saturated)++saturations;
  float w[3]={};
  for(int i=0;i<3;++i){a[i]=wDps[i]=0;for(int j=0;j<3;++j){a[i]+=MOUNT_R[i][j]*rawA[j];wDps[i]+=MOUNT_R[i][j]*(rawW[j]-GYRO_BIAS_DPS[j]);}w[i]=wDps[i]*PI/180.f;}
  filter.update(lastSampleUs,a,w,saturated);
  if(zero.update(lastSampleUs,filter.q,a,wDps,filter.quality)){
    Serial.printf("# ZERO_READY sequence=%lu samples=%u\n",(unsigned long)zero.sequence,zero.samples);
    stopShadow(1);
  }
  if(enabled&&(!filter.initialized||filter.quality==3))stopShadow(5);
}
void controlTick(uint32_t now){
  ++tick;periodUs=lastTick?now-lastTick:Shadow::PERIOD_US;lastTick=now;
  uint32_t age=haveSample?now-lastSampleUs:UINT32_MAX;
  if(enabled&&millis()-lastHeartbeat>1500)stopShadow(7);
  if(enabled&&age>Shadow::MAX_AGE_US)stopShadow(3);
  if(haveSample&&age>Shadow::MAX_AGE_US&&filter.initialized)filter.invalidate();
  if(enabled&&(!filter.initialized||!(filter.quality==1||filter.quality==2)))stopShadow(5);
  if(enabled&&(periodUs>30000||lateUs>10000))stopShadow(8);
  float roll=0,pitch=0;bool singular=false;
  float rawRoll=0,rawPitch=0,relative[4]={1,0,0,0};bool rawSingular=false;
  Shadow::angles(filter.q,rawRoll,rawPitch,rawSingular);
  bool attitudeOk=zero.relative(filter.q,relative)&&Shadow::angles(relative,roll,pitch,singular);
  if(enabled&&!attitudeOk)stopShadow(6);
  if(motion.activePolicy()){
    // Policy observes the LAST ACTUALLY SENT targets, avoiding virtual windup.
    target[0]=Motion::encoderRadians(1,motion.command[1]);target[1]=Motion::encoderRadians(0,motion.command[0]);
    enabled=true;reason=0;
  }
  else if(motion.engaged()&&motion.recovery()&&motion.recoveryStage!=Motion::NETWORK){
    enabled=false;reason=1; // Posture verification / home does not run the network.
    target[0]=Motion::encoderRadians(1,motion.command[1]);target[1]=Motion::encoderRadians(0,motion.command[0]);
  }
  before[0]=target[0];before[1]=target[1];action[0]=action[1]=0;inferUs=0;
  if(enabled){
    float observation[4]={roll,pitch,target[0],target[1]},next[2]={};
    uint32_t begin=micros();bool valid=direction.step(observation,action,next);inferUs=micros()-begin;
    if(inferUs>=Shadow::PERIOD_US)stopShadow(8);
    else if(!valid)stopShadow(6);
    else{target[0]=next[0];target[1]=next[1];motion.setForwardPace(direction.state.mode==DIRECTION_FRONT_BACK&&direction.state.sign==1&&roll>.523598776f&&fabsf(pitch)<.20f);motion.policy(target[0],target[1]);++policySequence;}
  }
  unsigned mode=enabled?1:((reason>=3&&reason!=9)?3:(!ready||!filter.initialized||!zero.ready?2:0));
  auto& s1=servos.states[0];auto& s2=servos.states[1];uint32_t stamp=millis();
  char out[1400];
  int n=snprintf(out,sizeof(out),"%lu,%lu,%lu,%lu,%u,%u,%u,%lu,%lu,%lu,%lu,%lu,%lu,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%.5f,%.3f,%u,%lu,%lu,%lu,%u,%.7f,%.7f,%.7f,%.7f,%.5f,%.5f,%.5f,%.4f,%.4f,%.4f,%.7f,%.7f,%.7f,%.7f,%.7f,%.7f,%u,%lu,%u,%u,%d,%.1f,%u,%u,%u,%lu,%u,%u,%d,%.1f,%u,%u,%u,%lu,%u\n",
    (unsigned long)millis(),(unsigned long)tick,(unsigned long)sampleSequence,(unsigned long)policySequence,mode,reason,filter.quality,
    (unsigned long)age,(unsigned long)periodUs,(unsigned long)lateUs,(unsigned long)loopMaxUs,(unsigned long)imuUs,(unsigned long)inferUs,
    roll,pitch,before[0],before[1],action[0],action[1],target[0],target[1],filter.accNorm,filter.weight,filter.faults,
    (unsigned long)saturations,(unsigned long)missed,(unsigned long)skipped,unsigned(singular),filter.q[0],filter.q[1],filter.q[2],filter.q[3],
    a[0],a[1],a[2],wDps[0],wDps[1],wDps[2],rawRoll,rawPitch,
    zero.reference[0],zero.reference[1],zero.reference[2],zero.reference[3],unsigned(zero.ready),(unsigned long)zero.sequence,zero.samples,
    s1.liveState(stamp),s1.position,s1.voltage*.1,s1.temperature,s1.torque,s1.status,(unsigned long)s1.age(stamp),s1.error,
    s2.liveState(stamp),s2.position,s2.voltage*.1,s2.temperature,s2.torque,s2.status,(unsigned long)s2.age(stamp),s2.error);
  if(n>0&&n<int(sizeof(out))){
    n-=1; // append motion state to the same atomic telemetry row
    n+=snprintf(out+n,sizeof(out)-n,",%u,%u,%u,%u,%d,%d,%u,%u,%u,%u,%u,%u,%d,%d,%d,%d,%d,%lu\n",motion.phase,motion.kind,motion.reason,unsigned(motion.offConfirmed),motion.command[0],motion.command[1],s1.currentLimit,s1.torqueLimit,s2.currentLimit,s2.torqueLimit,motion.recoveryStage,motion.faultId,motion.faultActual,motion.faultTarget,direction.state.mode,direction.state.sign,direction.state.stable,(unsigned long)direction.state.elapsed);
  }
  if(n>0&&n<int(sizeof(out))&&Serial.availableForWrite()>=n)Serial.write((const uint8_t*)out,n);else ++skipped;
  loopMaxUs=0;
}
void serviceSelftest(){
  // Selftest can take seconds. Service only the default torque-off state here;
  // no host motion command is processed until setup and IMU acquisition finish.
  servos.poll();motion.tick(millis(),false,0,0);delay(1);
}
void setup(){
  Serial.setTxBufferSize(8192);Serial.begin(230400);delay(1500);banner();
  servos.begin();Serial.println("# SERVO_LIMITED boot_stop TX17 RX18 BAUD1000000 IDS1,2; RAM limits remain reduced after stop");
  serviceSelftest();uint32_t checkStart=millis();
  DirectionCheckResult checked=checkDirectional(serviceSelftest);numericOk=checked.valid;
  Serial.printf("# DIRECTIONAL_%s CASES=%d ADAPTER_CASES=4200 MODE_MISMATCHES=%u ERROR=%.8f SELFTEST_MS=%lu\n",numericOk?"PASS":"FAIL",TEST_COUNT,checked.mismatches,checked.error,(unsigned long)(millis()-checkStart));
  Serial.printf("# NUMERIC_%s ERROR=%.8f\n",numericOk?"PASS":"FAIL",checked.error);
  float cr[2]={1,-1}, cb[2]={Shadow::LIMIT[0],-Shadow::LIMIT[1]}, ca[2]={}, ct[2]={};
  bool controlOk=Shadow::integrate(cr,cb,ca,ct)&&ct[0]==cb[0]&&ct[1]==cb[1];
  cr[1]=NAN;controlOk=controlOk&&!Shadow::integrate(cr,cb,ca,ct);
  numericOk=numericOk&&controlOk;
  Serial.printf("# CONTROL_%s ID2=95 ID1=135\n",controlOk?"PASS":"FAIL");
  initImu();
  Serial.println("ms,tick,imu_seq,policy_seq,mode,reason,quality,age_us,period_us,late_us,loop_max_us,imu_us,infer_us,roll_rad,pitch_rad,lower_before,upper_before,action_lower,action_upper,lower_target,upper_target,acc_norm,acc_weight,faults,saturations,missed,dropped,singular,qw,qx,qy,qz,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,raw_roll_rad,raw_pitch_rad,ref_qw,ref_qx,ref_qy,ref_qz,zero_ready,zero_seq,zero_samples,s1_state,s1_position,s1_voltage,s1_temperature,s1_torque,s1_status,s1_age_ms,s1_error,s2_state,s2_position,s2_voltage,s2_temperature,s2_torque,s2_status,s2_age_ms,s2_error,motion_phase,motion_kind,motion_reason,motion_off,motion_cmd1,motion_cmd2,s1_current_limit,s1_torque_limit,s2_current_limit,s2_torque_limit,recovery_stage,motion_fault_id,motion_fault_actual,motion_fault_target,direction_mode,direction_sign,direction_stable,direction_elapsed");
  nextTick=micros()+Shadow::PERIOD_US;reason=ready?9:4;if(!numericOk)reason=6;
}
void loop(){
  uint32_t begin=micros();commands();sampleImu();servos.poll();
  float tilt=0;bool imuGood=motionImu(tilt);unsigned oldPhase=motion.phase,oldStage=motion.recoveryStage;
  float rate=AttitudeFilter::norm3(wDps);
  motion.tick(millis(),imuGood,tilt,millis()-lastHeartbeat,rate);
  if(oldStage!=motion.recoveryStage)Serial.printf("# RECOVERY_STAGE=%u\n",motion.recoveryStage);
  if(oldPhase!=motion.phase){
    Serial.printf("# MOTION phase=%u reason=%u off=%u\n",motion.phase,motion.reason,unsigned(motion.offConfirmed));
    if(!motion.engaged()&&oldPhase==2){enabled=false;reason=1;}
  }
  if(requestedMotion&&!servos.pending){
    bool ok=millis()-motionRequestAt<=250&&motion.start(requestedMotion,millis(),imuGood,tilt,millis()-lastHeartbeat);
    if(ok)direction.reset();
    Serial.printf("# %s MOTION kind=%u reason=%u\n",ok?"ACK":"REJECT",requestedMotion,motion.reason);
    requestedMotion=0;
  }
  uint32_t now=micros();
  loopMaxUs=max(loopMaxUs,uint32_t(now-begin));
  if(int32_t(now-nextTick)>=0){lateUs=now-nextTick;uint32_t gaps=lateUs/Shadow::PERIOD_US;missed+=gaps;nextTick+=(gaps+1)*Shadow::PERIOD_US;controlTick(now);}
  loopMaxUs=max(loopMaxUs,uint32_t(micros()-begin));delay(1);
}
