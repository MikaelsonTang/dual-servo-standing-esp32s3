#include "../firmware/policy_shadow/servo_protocol.h"
#include <cassert>
#include <initializer_list>
int main(){
  uint8_t tx[8]={};for(int id=1;id<=2;++id)for(bool identity:{false,true}){
    assert(ServoRead::request(id,identity,tx));assert(tx[4]==2&&ServoRead::checksum(tx,8));
    assert(tx[5]==(identity?0:40)&&tx[6]==(identity?40:31));
  }
  assert(!ServoRead::request(254,false,tx));tx[7]^=1;assert(!ServoRead::checksum(tx,8));
  uint8_t e[40]={3,46,0,10,31,1};e[30]=1;e[33]=4;
  assert(ServoRead::identityMatches(1,e));e[2]=1;assert(!ServoRead::identityMatches(1,e));
  ServoRead::State s;uint8_t data[31]={};data[16]=0x55;data[17]=1;data[22]=50;data[23]=29;
  s.decode(data,1000);assert(s.position==341&&s.voltage==50&&s.temperature==29&&s.liveState(1100)==1&&s.liveState(1400)==2);
  data[17]=0x81;s.decode(data,2000);assert(s.position==-341);
}
