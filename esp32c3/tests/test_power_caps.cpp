#define main original_motion_main
#include "test_motion.cpp"
#undef main
int main(){
  assert(original_motion_main()==0);
  for(bool lowFactory:{false,true}){
    Rig r;
    for(auto& s:r.bus.physical){s.factoryCurrent=lowFactory?70:500;s.factoryTorque=lowFactory?400:1000;}
    r.step(50);r.run(Motion::RECOVERY);
    for(int i=0;i<2;++i){
      assert(r.c.current[i]==(lowFactory?70:150));assert(r.c.torque[i]==(lowFactory?400:900));
      assert(r.bus.states[i].speedLimit==150);
    }
    for(auto w:r.bus.writes){
      if(w.addr==44)assert(w.value<=(lowFactory?70:150));
      if(w.addr==48)assert(w.value<=(lowFactory?400:900));
      assert(w.addr!=55); // EEPROM remains locked.
    }
    r.c.policy(1.5f,-2.f);r.step(1000);
    assert(r.c.phase==2);r.c.stop(Motion::HOST_STOP);r.off();
  }
  puts("PASS: V26 higher output, low factory caps honored, STOP verified");
}
