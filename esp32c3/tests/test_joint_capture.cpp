#define main controller_regressions
#include "test_motion.cpp"
#undef main
#include "../firmware/policy_shadow/joint_zero_capture.h"
int main(){
  assert(controller_regressions()==0);
  int previous[2]={JointLimits::ZERO[0],JointLimits::ZERO[1]};
  ServoRead::State states[2];for(auto& s:states){s.identified=s.haveData=true;s.state=1;s.voltage=50;}
  states[0].position=4045;states[1].position=321;
  auto run=[&](JointZeroCapture& c){for(uint32_t t=100;t<1400&&c.active();t+=20){for(auto& s:states)s.lastData=t;c.update(t,true,true,states);}};
  JointZeroCapture capture;assert(!capture.request(100,false));assert(capture.request(100,true));run(capture);
  assert(capture.state==2&&capture.result[0]==4045&&capture.result[1]==321);
  assert(JointLimits::ZERO[0]==previous[0]&&JointLimits::ZERO[1]==previous[1]); // collector cannot apply or move anything
  JointZeroRecord record;record.position[0]=4045;record.position[1]=321;record.checksum=record.digest();assert(record.valid());
  ++record.position[0];assert(!record.valid());
  assert(!JointLimits::applyZeros(32760,321));
  assert(JointLimits::applyZeros(4045,321));
  assert(JointLimits::allowed(1,4045+1536)&&JointLimits::allowed(1,4045-1536));
  assert(!JointLimits::allowed(1,4045+1537));
  {Rig r;r.run(Motion::RECOVERY);assert(r.c.command[0]==4045&&r.c.command[1]==321);r.c.policy(.1f,.1f);r.step(200);assert(r.c.command[0]<4045&&r.c.command[1]<321);r.c.stop(Motion::HOST_STOP);r.off();}
  for(unsigned fault=0;fault<5;++fault){
    JointZeroCapture c;assert(c.request(100,true));for(auto& s:states){s.lastData=100;s.torque=0;s.state=1;}
    if(fault==0)c.update(100,false,true,states);
    if(fault==1)c.update(100,true,false,states);
    if(fault==2){states[0].torque=1;c.update(100,true,true,states);}
    if(fault==3){states[0].lastData=0;c.update(200,true,true,states);}
    if(fault==4){c.update(100,true,true,states);states[0].position+=20;for(auto& s:states)s.lastData=120;c.update(120,true,true,states);states[0].position-=20;}
    assert(c.state==3&&JointLimits::ZERO[0]==4045&&JointLimits::ZERO[1]==321);
  }
  JointLimits::calibrated=false;{Rig r;assert(!r.c.start(Motion::RECOVERY,r.now,true,0,0));assert(r.c.reason==Motion::ZERO_UNSET);}
  JointLimits::applyZeros(previous[0],previous[1]);
  puts("PASS: stable capture, bad sample rejection, record corruption, custom zero 4045/321 and bounds/start guard");
}
