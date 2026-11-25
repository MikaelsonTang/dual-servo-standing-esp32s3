#pragma once
#include <cstdint>
#include <cmath>
#include <algorithm>
#include "joint_limits.h"
#include "servo_write_limits.h"

namespace Motion {
constexpr auto& ZERO=JointLimits::ZERO;
constexpr int RANGE=24; // local tests only
constexpr int START_RANGE=48; // allowed initial zero error, about 4.2 degrees
constexpr auto& RECOVERY_RANGE=JointLimits::COUNTS;
// HD-1910-C001 detailed manufacturer specification: rated input 4.0--8.4 V.
// Preserve the 5.5 V upper guard for this fixed-5 V bench supply.
constexpr unsigned MIN_VOLTAGE_DV=40,MAX_VOLTAGE_DV=55;
constexpr float COUNTS_PER_RAD=4096.f/6.283185307179586f;
enum Kind { HOLD=1,UPPER=2,LOWER=3,POLICY=4,RECOVERY=5 };
enum Reason { NONE=0,HOST_STOP=1,HEARTBEAT=2,IMU=3,FEEDBACK=4,ELECTRICAL=5,
  BOUNDS=6,TRACKING=7,LIMITS=8,WRITE=9,DURATION=10,PREFLIGHT=11,COMPLETE=12,
  LOOP=13,ZERO_MISMATCH=14,TILT=15,TORQUE=16,NUMERIC=17,CONFIG=18,HOME_COMPLETE=19,ZERO_UNSET=20 };
enum RecoveryStage { NO_RECOVERY=0,NETWORK=1,VERIFY_UPRIGHT=2,RETURN_ZERO=3,ZERO_HOLD=4 };
constexpr float UPRIGHT_TILT=.20943951f, HOME_ABORT_TILT=.34906585f; // 12 / 20 degrees
constexpr float UPRIGHT_RATE_DPS=35.f;
constexpr int HOME_STEP=9, HOME_LEAD=24, HOME_TOLERANCE=8;
// Both joints can lag during recovery. Pace each against its own fresh feedback
// in every network branch; retain the independent 512-count tracking stop.
constexpr uint16_t RECOVERY_CURRENT=ServoWriteLimits::CURRENT, RECOVERY_TORQUE=ServoWriteLimits::TORQUE, RECOVERY_SPEED=ServoWriteLimits::SPEED;
constexpr int RECOVERY_STEP=52, FRONT_STEP=68, RECOVERY_LEAD=192;
inline uint16_t signedWord(int position){return position<0?uint16_t(-position)|0x8000:uint16_t(position);}
inline float encoderRadians(int i,int encoder){return (ZERO[i]-encoder)/COUNTS_PER_RAD;}
inline int encoded(int i,float angle,int range=RANGE){
  angle=std::max(-range/COUNTS_PER_RAD,std::min(range/COUNTS_PER_RAD,angle));
  return ZERO[i]-int(std::lround(angle*COUNTS_PER_RAD));
}
template<class Bus> struct Controller {
  Bus& bus;
  // 0: OFF confirmed; 1: reducing and verifying RAM limits; 2: active; 3: stopping.
  unsigned phase=3,kind=0,reason=HOST_STOP,stage=0,waypoint=0;
  bool offConfirmed=false,waitingWrite=false,initial[2]={true,true};
  int command[2]={ZERO[0],ZERO[1]},desired[2]={ZERO[0],ZERO[1]};
  int startPosition[2]={};
  // Keep sub-count model increments until a goal write consumes them. Bound
  // this accumulator to one count even when feedback pacing blocks a write.
  float subcount[2]={};bool subcountActive[2]={false,false};
  uint16_t current[2]={},torque[2]={};
  uint32_t started=0,lastPoll=0,writeSerial=0,configAt=0,stableAt=0;
  uint32_t goalAt[2]={},rampAt[2]={},offAt[2]={};
  uint8_t offSent=0,offNext=0;
  unsigned recoveryStage=NO_RECOVERY,faultId=0;
  int faultActual=0,faultTarget=0;
  bool fallenSeen=false,forwardPace=false;
  uint32_t uprightAt=0,homeStableAt=0;
  explicit Controller(Bus& b):bus(b){}
  bool engaged()const{return phase==1||phase==2;}
  bool recovery()const{return kind==RECOVERY;}
  bool activePolicy()const{return phase==2&&(kind==POLICY||(recovery()&&recoveryStage==NETWORK))&&!initial[0]&&!initial[1];}
  bool returningHome()const{return recovery()&&recoveryStage>=RETURN_ZERO;}
  bool pacedJoint(unsigned i)const{return i<2&&recovery()&&recoveryStage==NETWORK;}
  void setForwardPace(bool forward){forwardPace=forward&&activePolicy();}
  unsigned goalStep(unsigned i)const{return returningHome()?HOME_STEP:pacedJoint(i)?(forwardPace&&i==1?FRONT_STEP:RECOVERY_STEP):recovery()?52:1;}
  bool leadAllowed(unsigned i,int next)const{
    if(!pacedJoint(i))return true;
    int actual=bus.states[i].position;
    // If an external displacement made lag large, allow steps that reduce it.
    return std::abs(next-actual)<=RECOVERY_LEAD||std::abs(next-actual)<std::abs(command[i]-actual);
  }
  void stop(unsigned why){
    // Latch the failing readback before torque-off changes the actual pose.
    if(why==TRACKING&&engaged())for(int i=0;i<2;++i){
      if(!initial[i]&&std::abs(bus.states[i].position-command[i])>(recovery()?512:30)){
        faultId=i+1;faultActual=bus.states[i].position;faultTarget=command[i];break;
      }
    }
    if(phase!=3){phase=3;offSent=0;offNext=0;offConfirmed=false;}
    reason=why;kind=0;forwardPace=false;clearSubcount();
  }
  void clearSubcount(){for(int i=0;i<2;++i){subcount[i]=0;subcountActive[i]=false;}}
  unsigned check(uint32_t now,bool starting=false)const{
    for(int i=0;i<2;++i){
      auto& s=bus.states[i];
      if(!s.identified||s.state!=1||s.age(now)>80)return FEEDBACK;
      if(s.voltage<MIN_VOLTAGE_DV||s.voltage>MAX_VOLTAGE_DV||s.temperature>=50||s.status||s.error)return ELECTRICAL;
      if(std::abs(s.position-ZERO[i])>(recovery()?RECOVERY_RANGE[i]+57:80))return BOUNDS;
      if(starting){
        bool multi=s.angleLow==0&&s.angleHigh==0;
        if(now-s.lastIdentity>2500||(!multi&&(s.angleLow>std::min(ZERO[i]-RANGE,s.position)||s.angleHigh<std::max(ZERO[i]+RANGE,s.position)||s.angleLow>=s.angleHigh)))return LIMITS;
        if(s.torque)return TORQUE;
        if(std::abs(s.position-ZERO[i])>START_RANGE)return ZERO_MISMATCH;
        if(!s.currentLimit||!s.torqueLimit)return LIMITS;
        if(recovery()&&(s.eepromLock!=1||!s.factoryCurrent||!s.factoryTorque))return CONFIG;
      }
      if(phase==2){
        if(s.currentLimit!=current[i]||s.torqueLimit!=torque[i])return LIMITS;
        if(recovery()&&(s.angleLow!=0||s.angleHigh!=0||s.eepromLock!=1||s.speedLimit!=RECOVERY_SPEED))return CONFIG;
        if(!initial[i]){
          if(std::abs(s.position-command[i])>(recovery()?512:30))return TRACKING;
          if(int32_t(s.lastData-goalAt[i])>0&&s.torque!=1)return TORQUE;
        }else if(s.torque)return TORQUE;
      }
    }
    return NONE;
  }
  bool start(unsigned requested,uint32_t now,bool imuGood,float tilt,uint32_t heartbeatAge){
    if(phase!=0||!offConfirmed||bus.pending||requested<HOLD||requested>RECOVERY)return false;
    if(!JointLimits::calibrated){reason=ZERO_UNSET;return false;}
    kind=requested;
    unsigned failure=check(now,true);
    if(!imuGood)failure=IMU;
    else if(!std::isfinite(tilt)||(!recovery()&&tilt>.174533f))failure=TILT;
    else if(heartbeatAge>500)failure=HEARTBEAT;
    if(failure){reason=failure;kind=0;return false;}
    for(int i=0;i<2;++i){
      current[i]=std::min(uint16_t(recovery()?RECOVERY_CURRENT:40),recovery()?bus.states[i].factoryCurrent:bus.states[i].currentLimit);
      torque[i]=std::min(uint16_t(recovery()?RECOVERY_TORQUE:150),recovery()?bus.states[i].factoryTorque:bus.states[i].torqueLimit);
      command[i]=bus.states[i].position;desired[i]=ZERO[i];initial[i]=true;
      startPosition[i]=bus.states[i].position;
    }
    phase=1;kind=requested;reason=NONE;stage=waypoint=0;started=now;stableAt=0;offConfirmed=false;
    recoveryStage=recovery()?NETWORK:NO_RECOVERY;fallenSeen=tilt>=.61086524f;
    uprightAt=homeStableAt=0;faultId=0;faultActual=faultTarget=0;
    forwardPace=false;clearSubcount();
    return true;
  }
  bool send(unsigned i,uint8_t address,uint16_t value,uint8_t bytes,uint32_t now){
    bool allowed=address==40&&bytes==1&&value==0;
    if(phase==1){
      auto& s=bus.states[i];
      if(address==44&&bytes==2&&value==current[i]&&value<=(recovery()?s.factoryCurrent:s.currentLimit)&&value<=(recovery()?RECOVERY_CURRENT:40))allowed=true;
      if(address==48&&bytes==2&&value==torque[i]&&value<=(recovery()?s.factoryTorque:s.torqueLimit)&&value<=(recovery()?RECOVERY_TORQUE:150))allowed=true;
      if(recovery()&&address==46&&bytes==2&&value==RECOVERY_SPEED)allowed=true;
      if(recovery()&&(address==9||address==11)&&bytes==2&&value==0&&s.eepromLock==1&&s.torque==0&&s.age(now)<=80)allowed=true;
    }
    // Local motions may capture an off-zero start, then move inward at the
    // existing 1 count / 30 ms rate. Desired local targets remain +/-24.
    int position=value&0x8000?-int(value&0x7fff):int(value);
    int range=recovery()?RECOVERY_RANGE[i]:std::max(RANGE,std::abs(startPosition[i]-ZERO[i]));
    if(phase==2&&address==42&&bytes==2&&position>=ZERO[i]-range&&position<=ZERO[i]+range){
      allowed=initial[i]?std::abs(position-bus.states[i].position)<=2:
        std::abs(position-command[i])<=int(goalStep(i))&&now-rampAt[i]>=(recovery()?20u:30u);
      if(!initial[i])allowed=allowed&&leadAllowed(i,position);
      if(recovery()&&recoveryStage==VERIFY_UPRIGHT&&!initial[i])allowed=false;
      if(returningHome()&&!initial[i])allowed=allowed&&
        std::abs(position-ZERO[i])<std::abs(command[i]-ZERO[i])&&
        std::abs(position-bus.states[i].position)<=HOME_LEAD;
      if(!recovery()){
        if(initial[i])allowed=allowed&&std::abs(position-ZERO[i])<=START_RANGE;
        else if(std::abs(position-ZERO[i])>RANGE)
          allowed=allowed&&std::abs(position-ZERO[i])<std::abs(command[i]-ZERO[i]);
      }
    }
    if(!allowed||!bus.write(i+1,address,value,bytes,now)){stop(WRITE);return false;}
    waitingWrite=true;writeSerial=bus.writeDone;return true;
  }
  void policy(float lower,float upper){
    if(!activePolicy())return;
    if(!std::isfinite(lower)||!std::isfinite(upper)){stop(NUMERIC);return;}
    const float angle[2]={upper,lower};
    for(int i=0;i<2;++i){
      int range=recovery()?RECOVERY_RANGE[i]:RANGE;
      float offset=std::max(-float(range),std::min(float(range),angle[i]*COUNTS_PER_RAD));
      float delta=float(ZERO[i]-command[i])-offset;
      // Larger requests retain the existing slew/lead controls. Only recovery
      // increments below half a count need accumulation; local tests unchanged.
      if(recovery()&&std::abs(delta)<.5f){
        subcountActive[i]=true;
        subcount[i]=std::max(-1.f,std::min(1.f,subcount[i]+delta));
        int wanted=command[i]+int(std::lround(subcount[i]));
        desired[i]=std::max(ZERO[i]-range,std::min(ZERO[i]+range,wanted));
        if(desired[i]!=wanted)subcount[i]=0;
      }else{
        subcount[i]=0;subcountActive[i]=false;
        desired[i]=ZERO[i]-int(std::lround(offset));
      }
    }
  }
  void updateRecovery(uint32_t now,float tilt,float rateDps){
    if(!recovery()||phase!=2||initial[0]||initial[1])return;
    if(tilt>=.61086524f)fallenSeen=true;
    bool upright=std::isfinite(rateDps)&&rateDps<=UPRIGHT_RATE_DPS&&tilt<=UPRIGHT_TILT;
    if(recoveryStage==NETWORK&&fallenSeen&&upright){
      // Freeze the existing sent goals first. No goal jump or encoder recapture.
      recoveryStage=VERIFY_UPRIGHT;uprightAt=now;
      clearSubcount();
      for(int i=0;i<2;++i)desired[i]=command[i];
    }
    if(recoveryStage==VERIFY_UPRIGHT){
      if(!upright){recoveryStage=NETWORK;uprightAt=0;return;}
      bool settled=now-uprightAt>=150;
      for(int i=0;i<2;++i){auto& s=bus.states[i];settled=settled&&
        int32_t(s.lastData-uprightAt)>0&&std::abs(s.position-command[i])<=HOME_LEAD;}
      if(settled){recoveryStage=RETURN_ZERO;for(int i=0;i<2;++i)desired[i]=ZERO[i];}
    }
    if(returningHome()){
      if(tilt>HOME_ABORT_TILT){stop(TILT);return;}
      bool home=upright;
      for(int i=0;i<2;++i)home=home&&command[i]==ZERO[i]&&
        int32_t(bus.states[i].lastData-rampAt[i])>0&&std::abs(bus.states[i].position-ZERO[i])<=HOME_TOLERANCE;
      if(!home){homeStableAt=0;recoveryStage=RETURN_ZERO;}
      else if(!homeStableAt){homeStableAt=now;recoveryStage=ZERO_HOLD;}
      else if(now-homeStableAt>=500)stop(HOME_COMPLETE);
    }
  }
  void tick(uint32_t now,bool imuGood,float tilt,uint32_t heartbeatAge,float rateDps=0){
    if(engaged()){
      if(lastPoll&&now-lastPoll>40)stop(LOOP);
      else if(heartbeatAge>500)stop(HEARTBEAT);
      else if(!imuGood)stop(IMU);
      else if(!std::isfinite(tilt)||(!recovery()&&tilt>.349066f))stop(TILT);
      else if(now-started>(recovery()?14000u:12000u))stop(DURATION);
      else {unsigned error=check(now);if(error)stop(error);}
    }
    lastPoll=now;
    // Run posture recognition even while an earlier write is awaiting its ACK.
    // check() above keeps all existing stops ahead of any recovery handoff.
    if(engaged())updateRecovery(now,tilt,rateDps);
    if(waitingWrite&&bus.writeDone!=writeSerial){
      waitingWrite=false;
      if(!bus.writeOK&&engaged())stop(WRITE);
    }
    if(bus.pending)return;
    if(phase==3){
      // Never infer OFF from a write ACK. Require fresh, later readbacks for BOTH.
      bool confirmed=offSent==3;
      for(int i=0;i<2;++i){auto& s=bus.states[i];confirmed=confirmed&&s.identified&&s.state==1&&s.age(now)<=80&&int32_t(s.lastData-offAt[i])>0&&s.torque==0;}
      if(confirmed){phase=0;offConfirmed=true;waitingWrite=false;return;}
      if(offSent!=3||now-offAt[offNext]>=150){
        unsigned i=offNext;offNext^=1;
        if(send(i,40,0,1,now)){offAt[i]=now;offSent|=1<<i;}
        return;
      }
      bus.query(now,10,true);return;
    }
    if(phase==0){
      // An external controller or brownout must never silently arm this session.
      for(auto& s:bus.states)if(s.state==1&&s.age(now)<=80&&s.torque!=0){stop(TORQUE);return;}
      bus.query(now,20);return;
    }
    // Read priority keeps the two feedback ages bounded, also during writes.
    if(now-bus.lastQuery>=15){
      bool needIdentity=phase==1&&recovery()&&stage==10&&(bus.states[0].lastIdentity<=configAt||bus.states[1].lastIdentity<=configAt);
      bus.query(now,15,true,needIdentity);return;
    }
    if(phase==1){
      unsigned count=recovery()?10:4;
      if(stage<count){
        unsigned i=recovery()?stage/5:stage/2;
        unsigned sub=recovery()?stage%5:stage%2;
        uint8_t addr;uint16_t value;
        if(recovery()){
          const uint8_t addresses[5]={9,11,48,44,46};addr=addresses[sub];
          value=sub<2?0:sub==2?torque[i]:sub==3?current[i]:RECOVERY_SPEED;
        }else{addr=sub?44:48;value=sub?current[i]:torque[i];}
        if(send(i,addr,value,2,now)){++stage;configAt=now;}
        return;
      }
      if(recovery())for(auto& s:bus.states)if(int32_t(s.lastIdentity-configAt)<=0)return;
      for(auto& s:bus.states)if(int32_t(s.lastData-configAt)<=0)return;
      unsigned failure=check(now,true);if(failure){stop(failure);return;}
      for(int i=0;i<2;++i){
        auto& s=bus.states[i];
        if(s.currentLimit!=current[i]||s.torqueLimit!=torque[i]){stop(LIMITS);return;}
        if(recovery()&&(s.angleLow!=0||s.angleHigh!=0||s.speedLimit!=RECOVERY_SPEED||std::abs(s.position-startPosition[i])>4)){stop(CONFIG);return;}
        command[i]=s.position;
      }
      phase=2;return;
    }
    if(kind==UPPER||kind==LOWER){
      constexpr int offsets[5]={0,-10,0,10,0};
      int i=kind==UPPER?0:1;desired[i]=ZERO[i]+offsets[waypoint];
      bool settled=!initial[0]&&!initial[1];
      for(int j=0;j<2;++j)settled=settled&&command[j]==desired[j]&&std::abs(bus.states[j].position-desired[j])<=4;
      if(!settled)stableAt=0;
      else if(!stableAt)stableAt=now;
      else if(now-stableAt>=350){stableAt=0;if(++waypoint==5){stop(COMPLETE);return;}}
    }
    for(int i=0;i<2;++i){
      if(initial[i]){
        // First goal itself activates torque. Capture the latest measured pose.
        int value=bus.states[i].position;
        if(send(i,42,signedWord(value),2,now)){command[i]=value;initial[i]=false;goalAt[i]=rampAt[i]=now;}
        return;
      }
      if(command[i]!=desired[i]&&now-rampAt[i]>=(recovery()?20u:30u)){
        int step=int(goalStep(i)),delta=desired[i]-command[i];
        int value=command[i]+std::max(-step,std::min(step,delta));
        if(!leadAllowed(i,value))continue;
        // During home, wait for fresh feedback to catch up instead of building
        // a large position error. The original deadline and fault stops remain.
        if(returningHome()&&std::abs(value-bus.states[i].position)>HOME_LEAD)continue;
        if(send(i,42,signedWord(value),2,now)){
          if(subcountActive[i])subcount[i]-=float(value-command[i]);
          command[i]=value;rampAt[i]=now;
        }
        return;
      }
    }
  }
};
}
