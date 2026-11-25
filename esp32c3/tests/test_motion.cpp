#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include "../firmware/policy_shadow/servo_protocol.h"
#include "../firmware/policy_shadow/limited_motion.h"
struct Write {int id,addr,value;uint32_t time;int observed;};
struct FakeBus {
  ServoRead::State states[2],physical[2];
  bool pending=false,writeOK=true,failWrite=false,freeze=false,ignoreConfig=false,stall=false;
  uint32_t writeDone=0,lastQuery=0;
  int speedPerMs=0,goals[2]={Motion::ZERO[0],Motion::ZERO[1]};
  bool stallAxis[2]={false,false};
  int next=0;std::vector<Write> writes;
  FakeBus(){for(int i=0;i<2;++i){auto& s=physical[i];s.identified=s.haveData=true;s.state=1;s.voltage=50;s.temperature=30;s.position=Motion::ZERO[i];s.currentLimit=s.factoryCurrent=300;s.torqueLimit=s.factoryTorque=1000;s.angleLow=0;s.angleHigh=4095;s.eepromLock=1;s.mode=4;states[i]=s;}}
  bool write(uint8_t id,uint8_t addr,uint16_t value,uint8_t,uint32_t now){
    if(!ServoWriteLimits::allowed(id,addr,value,addr==40?1:2,states,now))return false;
    assert(!pending);writes.push_back({id,addr,value,now,states[id-1].position});auto& p=physical[id-1];
    if(addr==40)p.torque=value;
    else if(addr==44)p.currentLimit=value;
    else if(addr==48)p.torqueLimit=value;
    else if(addr==42){goals[id-1]=value&0x8000?-int(value&0x7fff):int(value);if(!stall&&!stallAxis[id-1]&&!speedPerMs)p.position=goals[id-1];p.torque=1;}
    else if(addr==46)p.speedLimit=value;
    else if(addr==9||addr==11){assert(p.eepromLock==1&&p.torque==0);if(!ignoreConfig){if(addr==9)p.angleLow=value;else p.angleHigh=value;}}
    else assert(false);
    pending=true;return true;
  }
  void query(uint32_t now,uint32_t interval,bool=false,bool=false){
    if(pending||now-lastQuery<interval)return;lastQuery=now;
    if(!freeze){states[next]=physical[next];states[next].lastData=states[next].lastIdentity=now;}
    next^=1;
  }
  void finish(){
    if(speedPerMs&&!stall)for(int i=0;i<2;++i)if(physical[i].torque&&!stallAxis[i]){
      int delta=goals[i]-physical[i].position;
      physical[i].position+=std::max(-speedPerMs,std::min(speedPerMs,delta));
    }
    if(pending){pending=false;writeOK=!failWrite;++writeDone;}
  }
};
struct Rig {
  FakeBus bus;Motion::Controller<FakeBus> c{bus};uint32_t now=1000;
  Rig(){step(150);assert(c.phase==0&&c.offConfirmed);}
  void step(int ms,uint32_t hb=0,bool imu=true,float tilt=0,float rate=0){for(int k=0;k<ms;++k){++now;bus.finish();c.tick(now,imu,tilt,hb,rate);}}
  void run(unsigned kind=Motion::HOLD){assert(c.start(kind,now,true,0,0));step(200);assert(c.phase==2);}
  void off(){step(150);assert(c.phase==0&&c.offConfirmed);for(auto& s:bus.states)assert(s.torque==0);}
};
int main(){
#ifdef _MSC_VER
  _set_error_mode(_OUT_TO_STDERR);
  _set_abort_behavior(0,_WRITE_ABORT_MSG|_CALL_REPORTFAULT);
#endif
  {Rig r;r.bus.states[1].position=Motion::ZERO[1]-49;assert(!r.c.start(Motion::HOLD,r.now,true,0,0));assert(r.c.reason==Motion::ZERO_MISMATCH);}
  {Rig r;r.bus.states[0].angleLow=Motion::ZERO[0]-Motion::RANGE+1;assert(!r.c.start(Motion::HOLD,r.now,true,0,0));assert(r.c.reason==Motion::LIMITS);}
  {Rig r;r.bus.states[0].position+=12;r.bus.physical[0].position+=12;r.run();
    int first=-1;for(auto w:r.bus.writes)if(w.addr==42&&w.id==1){first=w.value;break;}assert(first==Motion::ZERO[0]+12);
    r.c.stop(Motion::HOST_STOP);auto n=r.bus.writes.size();r.off();for(size_t i=n;i<r.bus.writes.size();++i)assert(r.bus.writes[i].addr==40);}
  {Rig r;r.run(Motion::POLICY);r.c.policy(100,-100);r.step(5000);
    int last[2]={Motion::ZERO[0],Motion::ZERO[1]};uint32_t times[2]={};
    for(auto w:r.bus.writes)if(w.addr==42){int i=w.id-1;assert(std::abs(w.value-Motion::ZERO[i])<=Motion::RANGE);assert(std::abs(w.value-last[i])<=1);if(times[i])assert(w.time-times[i]>=30);last[i]=w.value;times[i]=w.time;}
    assert(r.c.command[0]==Motion::ZERO[0]+Motion::RANGE&&r.c.command[1]==Motion::ZERO[1]-Motion::RANGE);r.step(1,501);assert(!r.c.engaged()&&r.c.reason==Motion::HEARTBEAT);r.off();}
  {Rig r;r.run();r.bus.freeze=true;r.step(100);assert(r.c.phase==3&&!r.c.offConfirmed);r.step(300);assert(!r.c.offConfirmed);r.bus.freeze=false;r.off();}
  {Rig r;r.run();r.bus.physical[1].position+=90;r.step(50);assert(!r.c.engaged()&&r.c.reason==Motion::BOUNDS);r.off();}
  {Rig r;r.run();r.bus.physical[1].position+=32;r.step(50);assert(!r.c.engaged()&&r.c.reason==Motion::TRACKING);r.off();}
  {Rig r;r.run();r.bus.physical[0].voltage=39;r.step(50);assert(!r.c.engaged()&&r.c.reason==Motion::ELECTRICAL);r.off();}
  {Rig r;for(auto& s:r.bus.physical)s.voltage=40;r.step(50);r.run();r.step(100);assert(r.c.phase==2);r.c.stop(Motion::HOST_STOP);r.off();}
  {Rig r;r.run();r.bus.physical[1].voltage=56;r.step(50);assert(!r.c.engaged()&&r.c.reason==Motion::ELECTRICAL);r.off();}
  {Rig r;r.run();r.bus.physical[0].torqueLimit=1000;r.step(50);assert(!r.c.engaged()&&r.c.reason==Motion::LIMITS);r.off();}
  {Rig r;r.bus.failWrite=true;assert(r.c.start(Motion::HOLD,r.now,true,0,0));r.step(100);assert(!r.c.engaged());for(auto w:r.bus.writes)assert(w.addr!=42);r.bus.failWrite=false;r.off();}
  {Rig r;r.run();r.step(1,0,false);assert(r.c.reason==Motion::IMU);r.off();}
  {Rig r;r.run();r.step(1,0,true,.4f);assert(r.c.reason==Motion::TILT);r.off();}
  {Rig r;r.run();r.now+=50;r.step(1);assert(r.c.reason==Motion::LOOP);r.off();}
  {Rig r;r.run();r.step(12001);assert(!r.c.engaged()&&r.c.reason==Motion::DURATION);r.off();}
  {Rig r;r.run(Motion::UPPER);r.step(6000);assert(!r.c.engaged()&&r.c.reason==Motion::COMPLETE);r.off();}
  {Rig r;r.run(Motion::POLICY);r.c.policy(NAN,0);assert(r.c.reason==Motion::NUMERIC);r.off();}
  {Rig r;r.run(Motion::RECOVERY);r.c.policy(-1.5707963f,1.5707963f);r.step(2000);
    assert(r.c.phase==2&&r.c.command[0]==Motion::ZERO[0]-1024&&r.c.command[1]==Motion::ZERO[1]+1024);
    int last[2]={Motion::ZERO[0],Motion::ZERO[1]};bool negative=false;
    for(auto w:r.bus.writes)if(w.addr==42){int v=w.value&0x8000?-(w.value&0x7fff):w.value;negative|=v<0;assert(std::abs(v-last[w.id-1])<=78);last[w.id-1]=v;}
    assert(negative);r.c.stop(Motion::HOST_STOP);auto count=r.bus.writes.size();r.off();for(size_t i=count;i<r.bus.writes.size();++i)assert(r.bus.writes[i].addr==40);}
  {Rig r;r.bus.states[0].eepromLock=0;assert(!r.c.start(Motion::RECOVERY,r.now,true,1.57f,0));assert(r.c.reason==Motion::CONFIG);}
  {Rig r;r.bus.ignoreConfig=true;assert(r.c.start(Motion::RECOVERY,r.now,true,1.57f,0));r.step(700);assert(!r.c.engaged()&&r.c.reason==Motion::CONFIG);for(auto w:r.bus.writes)assert(w.addr!=42);r.off();}
  {Rig r;assert(r.c.start(Motion::RECOVERY,r.now,true,1.57f,0));r.step(500,0,true,1.57f);assert(r.c.phase==2);r.step(120000,0,true,1.57f);assert(r.c.phase==2);r.c.stop(Motion::HOST_STOP);r.off();}
  {Rig r;r.run(Motion::RECOVERY);r.bus.physical[0].position=Motion::ZERO[0]+Motion::RECOVERY_RANGE[0]+58;r.step(50);assert(r.c.reason==Motion::BOUNDS);r.off();}
  {Rig r;r.run(Motion::RECOVERY);r.c.policy(-10.f,10.f);r.step(2000);assert(r.c.command[0]==-1199&&r.c.command[1]==3952);assert(r.c.phase==2);r.c.stop(Motion::HOST_STOP);r.off();}
  {Rig r;r.run(Motion::RECOVERY);r.c.policy(10.f,-10.f);r.step(2000);
    assert(r.c.command[0]==1873&&r.c.command[1]==1792);r.c.stop(Motion::HOST_STOP);r.off();}
  {Rig r;r.run(Motion::RECOVERY);r.bus.physical[1].position=Motion::ZERO[1]+1138;r.step(50);assert(r.c.reason==Motion::BOUNDS);r.off();}
  for(unsigned id=1;id<=2;++id){int z=Motion::ZERO[id-1],r=Motion::RECOVERY_RANGE[id-1];
    assert(JointLimits::allowed(id,z-r)&&JointLimits::allowed(id,z+r));
    assert(!JointLimits::allowed(id,z-r-1)&&!JointLimits::allowed(id,z+r+1));}
  assert(!JointLimits::allowed(0,337)&&!JointLimits::allowed(3,2872));
  for(unsigned kind=Motion::HOLD;kind<=Motion::RECOVERY;++kind)for(int sign:{-1,1}){
    Rig r;int initial[2]={Motion::ZERO[0]+sign*48,Motion::ZERO[1]-sign*48};
    for(int i=0;i<2;++i)r.bus.physical[i].position=initial[i];
    r.step(50);r.run(kind);r.step(5000);
    int last[2]={initial[0],initial[1]};uint32_t at[2]={};bool seen[2]={};
    for(auto w:r.bus.writes)if(w.addr==42){int i=w.id-1,v=w.value&0x8000?-int(w.value&0x7fff):w.value;
      if(!seen[i]){assert(v==initial[i]);seen[i]=true;}
      else if(kind!=Motion::RECOVERY){
        assert(std::abs(v-last[i])<=1&&w.time-at[i]>=30);
        if(std::abs(v-Motion::ZERO[i])>Motion::RANGE)assert(std::abs(v-Motion::ZERO[i])<std::abs(last[i]-Motion::ZERO[i]));
      }
      assert(std::abs(v-Motion::ZERO[i])<=48);last[i]=v;at[i]=w.time;
    }
    assert(seen[0]&&seen[1]&&last[0]==Motion::ZERO[0]&&last[1]==Motion::ZERO[1]);
    r.c.stop(Motion::HOST_STOP);auto n=r.bus.writes.size();r.off();
    for(size_t i=n;i<r.bus.writes.size();++i)assert(r.bus.writes[i].addr==40);
  }
  for(unsigned kind=Motion::HOLD;kind<=Motion::RECOVERY;++kind)for(int sign:{-1,1})for(int i=0;i<2;++i){
    Rig r;r.bus.physical[i].position=Motion::ZERO[i]+sign*49;r.step(50);
    assert(!r.c.start(kind,r.now,true,0,0)&&r.c.reason==Motion::ZERO_MISMATCH);
    for(auto w:r.bus.writes)assert(w.addr!=42);
  }
  {Rig r;r.bus.physical[0].position=Motion::ZERO[0]+48;r.step(50);r.run();
    r.c.command[0]=Motion::ZERO[0]+30;r.c.rampAt[0]=r.now-30;r.bus.pending=false;
    assert(!r.c.send(0,42,Motion::signedWord(Motion::ZERO[0]+31),2,r.now));assert(r.c.reason==Motion::WRITE);r.off();}
  {Rig r;r.bus.physical[0].position=Motion::ZERO[0]-48;r.step(50);r.bus.states[0].angleLow=Motion::ZERO[0]-40;
    assert(!r.c.start(Motion::HOLD,r.now,true,0,0)&&r.c.reason==Motion::LIMITS);}
  // No handoff just because GETUP was started on a level base.
  {Rig r;r.run(Motion::RECOVERY);r.step(1000);assert(r.c.activePolicy()&&r.c.recoveryStage==Motion::NETWORK);}
  // Full range, both signs: freeze goals, verify real feedback, slow inward home,
  // hold briefly and confirm OFF. Capturing current feedback cannot jump a goal.
  for(int sign:{-1,1}){
    Rig r;assert(r.c.start(Motion::RECOVERY,r.now,true,1.6f,0));r.step(250,0,true,1.6f);
    r.c.policy(sign*1.5707963f,-sign*2.2689280f);r.step(1800,0,true,1.6f);
    int last[2]={r.c.command[0],r.c.command[1]};r.step(1,0,true,.1f,10);
    assert(r.c.recoveryStage==Motion::VERIFY_UPRIGHT&&!r.c.activePolicy());
    auto n=r.bus.writes.size();r.c.policy(0,0);r.step(120,0,true,.1f,10);
    for(size_t j=n;j<r.bus.writes.size();++j)assert(r.bus.writes[j].addr!=42);
    r.step(9000,0,true,.1f,10);
    assert(r.c.reason==Motion::HOME_COMPLETE&&r.c.offConfirmed);
    uint32_t at[2]={};
    for(size_t j=n;j<r.bus.writes.size();++j){auto w=r.bus.writes[j];if(w.addr!=42)continue;
      int i=w.id-1,v=w.value&0x8000?-int(w.value&0x7fff):int(w.value);
      assert(std::abs(v-last[i])<=Motion::HOME_STEP);
      assert(std::abs(v-Motion::ZERO[i])<std::abs(last[i]-Motion::ZERO[i]));
      if(at[i])assert(w.time-at[i]>=20);at[i]=w.time;last[i]=v;
    }
    for(int i=0;i<2;++i)assert(last[i]==Motion::ZERO[i]&&r.bus.states[i].torque==0);
  }
  // A fast crossing or brief near-upright sample cannot authorize home.
  {Rig r;assert(r.c.start(Motion::RECOVERY,r.now,true,1.6f,0));r.step(250,0,true,1.6f);
    r.step(250,0,true,.1f,100);assert(r.c.recoveryStage==Motion::NETWORK);
    r.step(100,0,true,.1f,0);assert(r.c.recoveryStage==Motion::VERIFY_UPRIGHT);
    r.step(1,0,true,.5f,0);assert(r.c.recoveryStage==Motion::NETWORK&&r.c.activePolicy());}
  // Landing with a pre-existing lag: freeze prevents further target windup;
  // home waits for BOTH actual positions to catch up, not elapsed time alone.
  {Rig r;assert(r.c.start(Motion::RECOVERY,r.now,true,1.6f,0));r.step(250,0,true,1.6f);
    r.c.policy(-1.f,-1.f);r.step(500,0,true,1.6f);
    r.bus.stall=true;r.bus.physical[1].position=r.c.command[1]-300;
    r.step(400,0,true,.1f,0);assert(r.c.recoveryStage==Motion::VERIFY_UPRIGHT);
    int frozen=r.c.command[1];r.c.policy(1,1);r.step(300,0,true,.1f,0);assert(r.c.command[1]==frozen);
    r.bus.physical[1].position=frozen;r.step(60,0,true,.1f,0);
    assert(r.c.recoveryStage==Motion::RETURN_ZERO);
    int actual=r.bus.physical[1].position;r.step(500,0,true,.1f,0);
    assert(std::abs(r.c.command[1]-actual)<=Motion::HOME_LEAD&&r.c.engaged());
    r.c.stop(Motion::HOST_STOP);r.off();}
  // Every stop remains effective while returning. No home goals after a stop.
  for(int fault=0;fault<7;++fault){
    Rig r;assert(r.c.start(Motion::RECOVERY,r.now,true,1.6f,0));r.step(250,0,true,1.6f);
    r.c.policy(-1.f,-1.f);r.step(500,0,true,1.6f);r.step(220,0,true,.1f,0);
    assert(r.c.recoveryStage==Motion::RETURN_ZERO&&!r.c.activePolicy());
    if(fault==0)r.c.stop(Motion::HOST_STOP);
    if(fault==1)r.step(1,501);
    if(fault==2)r.step(1,0,false);
    if(fault==3)r.step(1,0,true,.4f);
    if(fault==4){r.bus.physical[1].voltage=39;r.step(50);}
    if(fault==5){r.bus.freeze=true;r.step(100);r.bus.freeze=false;}
    if(fault==6){r.c.stop(Motion::HOST_STOP);r.step(1);}
    const unsigned expected[]={Motion::HOST_STOP,Motion::HEARTBEAT,Motion::IMU,Motion::TILT,Motion::ELECTRICAL,Motion::FEEDBACK,Motion::HOST_STOP};
    assert(!r.c.engaged()&&r.c.reason==expected[fault]);auto n=r.bus.writes.size();r.off();
    for(size_t j=n;j<r.bus.writes.size();++j)assert(r.bus.writes[j].addr==40);
  }
  // Tracking abort is not waived just because the base reaches upright.
  {Rig r;assert(r.c.start(Motion::RECOVERY,r.now,true,1.6f,0));r.step(250,0,true,1.6f);
    r.bus.physical[1].position=r.c.command[1]+520;r.bus.stall=true;
    r.step(50,0,true,.1f,0);assert(r.c.reason==Motion::TRACKING&&r.c.faultId==2);
    assert(r.c.faultActual-r.c.faultTarget==520);r.off();assert(r.c.faultActual-r.c.faultTarget==520);}
  unsigned pacedCases=0;
  // A plant slower than the command rate must reach both limits, including
  // signed positions below zero, without winding up a large tracking error.
  for(int axis=0;axis<2;++axis)for(int sign:{-1,1}){
    Rig r;r.bus.speedPerMs=1;r.run(Motion::RECOVERY);auto n=r.bus.writes.size();
    int prior=r.c.command[axis];uint32_t at=0;
    r.c.policy(axis==1?sign*1.6580628f:0,axis==0?sign*2.3561945f:0);r.step(3500);
    assert(r.c.phase==2&&r.c.command[axis]==Motion::ZERO[axis]-sign*Motion::RECOVERY_RANGE[axis]);
    assert(r.bus.states[axis].position==r.c.command[axis]);
    for(size_t j=n;j<r.bus.writes.size();++j){auto w=r.bus.writes[j];if(w.id!=axis+1||w.addr!=42)continue;
      int value=w.value&0x8000?-int(w.value&0x7fff):int(w.value);
      assert(std::abs(value-prior)<=78&&std::abs(value-w.observed)<=192);
      if(at)assert(w.time-at>=20);at=w.time;prior=value;
    }
    assert(at);r.c.stop(Motion::HOST_STOP);r.off();++pacedCases;
  }
  // A single stalled axis waits; the other continues. Releasing the stalled
  // joint resumes progress from the held command, never from a recaptured goal.
  for(int axis=0;axis<2;++axis)for(int sign:{-1,1}){
    Rig r;r.bus.speedPerMs=1;r.run(Motion::RECOVERY);r.bus.stallAxis[axis]=true;
    r.c.policy(sign*1.5f,-sign*2.2f);r.step(2200);
    int held=r.c.command[axis];assert(std::abs(held-r.bus.states[axis].position)<=192&&r.c.phase==2);
    assert(r.c.command[1-axis]==r.c.desired[1-axis]);
    auto n=r.bus.writes.size();r.step(300);assert(r.c.command[axis]==held);
    for(size_t j=n;j<r.bus.writes.size();++j)assert(r.bus.writes[j].addr!=42);
    r.bus.stallAxis[axis]=false;r.step(3500);
    assert(r.c.command[axis]==r.c.desired[axis]&&r.c.phase==2);
    r.c.stop(Motion::HOST_STOP);r.off();++pacedCases;
  }
  // Reversing a stalled request reduces lag with a small step on either axis.
  for(int axis=0;axis<2;++axis){
    Rig r;r.run(Motion::RECOVERY);r.bus.stall=true;
    r.c.policy(axis==1?1.5f:0,axis==0?1.5f:0);r.step(500);
    int held=r.c.command[axis];r.c.policy(axis==1?-1.5f:0,axis==0?-1.5f:0);r.step(10);
    assert(r.c.command[axis]>held&&r.c.command[axis]-held<=78&&r.c.phase==2);++pacedCases;
  }
  // An external displacement can exceed the lead bound. Corrective steps may
  // reduce that lag, while target progression cannot increase it further.
  for(int axis=0;axis<2;++axis){
    Rig r;r.run(Motion::RECOVERY);r.bus.stall=true;
    r.bus.physical[axis].position=r.c.command[axis]+250;r.step(40);
    int held=r.c.command[axis];r.c.policy(axis==1?-1.5f:0,axis==0?-1.5f:0);r.step(10);
    assert(r.c.command[axis]>held&&r.c.command[axis]-held<=78&&r.c.phase==2);++pacedCases;
  }
  // A caller cannot bypass either joint's lead bound through the write API.
  for(int axis=0;axis<2;++axis){
    Rig r;r.run(Motion::RECOVERY);r.bus.stall=true;
    r.c.policy(axis==1?1.5f:0,axis==0?1.5f:0);r.step(500);
    r.bus.pending=false;r.c.rampAt[axis]=r.now-20;
    assert(!r.c.send(axis,42,Motion::signedWord(r.c.command[axis]-52),2,r.now));
    assert(r.c.reason==Motion::WRITE);r.off();++pacedCases;
  }
  // Switching from lower-only targets to dual targets cannot reset the goals
  // or bypass the 52-count slew and feedback lead bounds on either joint.
  {Rig r;r.run(Motion::RECOVERY);r.c.policy(1.f,0);r.step(200);
    int before[2]={r.c.command[0],r.c.command[1]};bool saw[2]={};
    r.c.policy(1.5f,2.f);auto n=r.bus.writes.size();r.step(200);
    for(size_t j=n;j<r.bus.writes.size();++j){auto w=r.bus.writes[j];if(w.addr!=42)continue;
      int i=w.id-1,value=w.value&0x8000?-int(w.value&0x7fff):int(w.value);
      assert(std::abs(before[i]-value)<=78&&std::abs(value-w.observed)<=192);saw[i]=true;before[i]=value;
    }
    assert(saw[0]&&saw[1]&&r.c.phase==2);++pacedCases;
  }
  // Every stop is still checked while either joint is waiting for feedback.
  for(int axis=0;axis<2;++axis)for(int fault=0;fault<8;++fault){
    Rig r;r.run(Motion::RECOVERY);r.bus.stall=true;
    r.c.policy(axis==1?1.5f:0,axis==0?1.5f:0);r.step(500);assert(r.c.phase==2);
    if(fault==0)r.c.stop(Motion::HOST_STOP);
    if(fault==1)r.step(1,501);
    if(fault==2){r.bus.freeze=true;r.step(100);r.bus.freeze=false;}
    if(fault==3){r.c.stop(Motion::HOST_STOP);r.step(1);}
    if(fault==4){r.bus.physical[axis].voltage=39;r.step(50);}
    if(fault==5){r.bus.physical[axis].position=r.c.command[axis]+520;r.step(50);}
    if(fault==6)r.step(1,0,false);
    if(fault==7){r.now+=50;r.step(1);}
    const unsigned expected[]={Motion::HOST_STOP,Motion::HEARTBEAT,Motion::FEEDBACK,Motion::HOST_STOP,Motion::ELECTRICAL,Motion::TRACKING,Motion::IMU,Motion::LOOP};
    assert(!r.c.engaged()&&r.c.reason==expected[fault]);auto n=r.bus.writes.size();r.off();
    for(size_t j=n;j<r.bus.writes.size();++j)assert(r.bus.writes[j].addr==40);
    ++pacedCases;
  }
  unsigned fractionalCases=0;
  auto increment=[](Rig& r,float upperCounts,float lowerCounts){
    r.c.policy((Motion::ZERO[1]-r.c.command[1]-lowerCounts)/Motion::COUNTS_PER_RAD,
               (Motion::ZERO[0]-r.c.command[0]-upperCounts)/Motion::COUNTS_PER_RAD);
  };
  // Tiny trained actions must accumulate into real writes in either direction,
  // rather than being discarded when observations return to the sent integer.
  for(int axis=0;axis<2;++axis)for(int sign:{-1,1})for(float delta:{.05f,.293f,.49f}){
    Rig r;r.run(Motion::RECOVERY);int before=r.c.command[axis];
    for(int k=0;k<200;++k){increment(r,axis==0?sign*delta:0,axis==1?sign*delta:0);r.step(20);}
    assert(r.c.engaged()&&std::abs(r.c.command[axis]-before-sign*delta*200)<1.1f);
    assert(std::abs(r.c.subcount[axis])<.51f);
    r.c.stop(Motion::HOST_STOP);assert(r.c.subcount[axis]==0&&!r.c.subcountActive[axis]);r.off();++fractionalCases;
  }
  // A blocked joint can retain at most ONE count, not many seconds of model
  // action. Clearing the blockage must not release a large pending target.
  for(int axis=0;axis<2;++axis)for(int sign:{-1,1}){
    Rig r;r.run(Motion::RECOVERY);r.bus.stall=true;
    r.c.command[axis]=Motion::ZERO[axis]+sign*192;r.c.desired[axis]=r.c.command[axis];
    int held=r.c.command[axis];
    for(int k=0;k<100;++k){increment(r,axis==0?sign*.3f:0,axis==1?sign*.3f:0);r.step(20);}
    assert(r.c.command[axis]==held&&std::abs(r.c.subcount[axis])<=1.f&&r.c.engaged());
    r.bus.physical[axis].position=held;r.step(40);
    assert(std::abs(r.c.command[axis]-held)==1&&std::abs(r.c.subcount[axis])<.01f);
    r.c.stop(Motion::HOST_STOP);r.off();++fractionalCases;
  }
  // Stored fractions cannot carry through an absolute larger goal or home.
  {Rig r;r.run(Motion::RECOVERY);increment(r,.3f,-.3f);assert(r.c.subcount[0]>.29f);
    r.c.policy(.5f,-.5f);assert(r.c.subcount[0]==0&&r.c.subcount[1]==0);++fractionalCases;}
  {Rig r;assert(r.c.start(Motion::RECOVERY,r.now,true,1.6f,0));r.step(250,0,true,1.6f);
    increment(r,.3f,-.3f);r.step(1,0,true,0,0);
    assert(r.c.recoveryStage==Motion::VERIFY_UPRIGHT&&r.c.subcount[0]==0&&r.c.subcount[1]==0);++fractionalCases;}
  // Reversing a small action cancels its fractional remainder, with no stale
  // step in the old direction. Tiny motion also crosses encoder zero correctly.
  {Rig r;r.run(Motion::RECOVERY);increment(r,.3f,0);r.step(20);increment(r,-.3f,0);r.step(20);
    assert(r.c.command[0]==Motion::ZERO[0]&&std::abs(r.c.subcount[0])<.01f);++fractionalCases;}
  {Rig r;r.run(Motion::RECOVERY);r.c.command[0]=r.c.desired[0]=1;r.bus.physical[0].position=r.bus.states[0].position=1;
    auto n=r.bus.writes.size();for(int k=0;k<30;++k){increment(r,-.2f,0);r.step(20);}
    assert(r.c.command[0]<0&&r.c.engaged());bool negative=false;
    for(size_t j=n;j<r.bus.writes.size();++j){auto w=r.bus.writes[j];if(w.id==1&&w.addr==42&&(w.value&0x8000))negative=true;}
    assert(negative);++fractionalCases;}
  // Accumulation at either trained limit must not move a goal out of range.
  for(int axis=0;axis<2;++axis)for(int sign:{-1,1}){
    Rig r;r.run(Motion::RECOVERY);int edge=Motion::ZERO[axis]+sign*Motion::RECOVERY_RANGE[axis];
    r.c.command[axis]=r.c.desired[axis]=edge;r.bus.physical[axis].position=r.bus.states[axis].position=edge;
    for(int k=0;k<20;++k){increment(r,axis==0?sign*.3f:0,axis==1?sign*.3f:0);r.step(20);}
    assert(r.c.command[axis]==edge&&r.c.engaged());++fractionalCases;
  }
  printf("PASS: 58 baseline/start + 13 auto-home + %u feedback-pacing + %u sub-count scenarios; no hardware activity\n",pacedCases,fractionalCases);
  return 0;
}
