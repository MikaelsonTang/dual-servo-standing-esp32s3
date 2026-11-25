#include <cassert>
#include <cstdio>
#include "../firmware/policy_shadow/servo_write_limits.h"
int main(){
  ServoRead::State states[2];
  for(auto& s:states){s.factoryCurrent=500;s.factoryTorque=1000;s.eepromLock=1;s.haveData=true;s.lastData=1000;}
  for(unsigned id=1;id<=2;++id){
    assert(ServoWriteLimits::allowed(id,44,150,2,states,1000));
    assert(ServoWriteLimits::allowed(id,48,900,2,states,1000));
    assert(ServoWriteLimits::allowed(id,46,150,2,states,1000));
    assert(!ServoWriteLimits::allowed(id,44,151,2,states,1000));
    assert(!ServoWriteLimits::allowed(id,48,901,2,states,1000));
    assert(!ServoWriteLimits::allowed(id,46,151,2,states,1000));
    states[id-1].factoryCurrent=70;states[id-1].factoryTorque=400;
    assert(!ServoWriteLimits::allowed(id,44,150,2,states,1000));
    assert(!ServoWriteLimits::allowed(id,48,900,2,states,1000));
    assert(ServoWriteLimits::allowed(id,44,70,2,states,1000));
    assert(ServoWriteLimits::allowed(id,48,400,2,states,1000));
    assert(!ServoWriteLimits::allowed(id,55,0,1,states,1000));
    assert(ServoWriteLimits::allowed(id,40,0,1,states,1000));
  }
  assert(!ServoWriteLimits::allowed(3,40,0,1,states,1000));
  puts("PASS: actual UART write guard accepts V26 profile and enforces factory caps");
}
