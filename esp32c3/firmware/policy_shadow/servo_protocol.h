#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace ServoRead {
inline bool request(uint8_t id,bool identity,uint8_t* out){
  if(id!=1&&id!=2)return false;
  uint8_t frame[8]={255,255,id,4,2,uint8_t(identity?0:40),uint8_t(identity?40:31),0};
  uint8_t sum=0;for(int i=2;i<7;++i)sum+=frame[i];frame[7]=uint8_t(~sum);
  std::memcpy(out,frame,8);return true; // READ only; no goal or torque writes
}
inline bool checksum(const uint8_t* p,size_t n){
  if(n<6||p[0]!=255||p[1]!=255||n!=size_t(p[3])+4)return false;
  uint8_t sum=0;for(size_t i=2;i<n;++i)sum+=p[i];return sum==255;
}
inline bool identityMatches(uint8_t id,const uint8_t* e){
  // Same HD1910 fw3.46 layout verified in the earlier local motion tests.
  return e[0]==3&&e[1]==46&&e[2]==0&&e[3]==10&&e[4]==31&&e[5]==id&&
    e[7]!=1&&e[7]!=2&&e[30]==1&&(e[33]==4||e[33]==0);
}
struct State {
  bool identified=false,haveData=false;
  uint8_t state=0,voltage=0,temperature=0,torque=0,status=0,error=0,eepromLock=0,mode=0;
  int position=0;
  uint16_t currentLimit=0,torqueLimit=0,angleLow=0,angleHigh=0,speedLimit=0,factoryCurrent=0,factoryTorque=0;
  uint32_t lastData=0,lastIdentity=0;
  uint32_t age(uint32_t now)const{return haveData?now-lastData:UINT32_MAX;}
  unsigned liveState(uint32_t now)const{return state==1&&age(now)>300?2:state;}
  void decode(const uint8_t* ram,uint32_t now){
    uint16_t v=uint16_t(ram[16])|(uint16_t(ram[17])<<8);
    position=v&0x8000?-int(v&0x7fff):int(v);
    torque=ram[0];voltage=ram[22];temperature=ram[23];status=ram[25];
    currentLimit=uint16_t(ram[4])|(uint16_t(ram[5])<<8);
    torqueLimit=uint16_t(ram[8])|(uint16_t(ram[9])<<8);
    speedLimit=uint16_t(ram[6])|(uint16_t(ram[7])<<8);eepromLock=ram[15];
    lastData=now;haveData=true;state=1;error=0;
  }
};
}
