#pragma once
#include <cstdint>
#include <cmath>
#include "servo_protocol.h"
#include "joint_limits.h"
struct JointZeroRecord {
  uint32_t magic=0x4a5a3235;int32_t position[2]={};uint32_t checksum=0;
  uint32_t digest()const{return magic^uint32_t(position[0])*16777619u^uint32_t(position[1])*2166136261u;}
  bool valid()const{return magic==0x4a5a3235&&checksum==digest()&&JointLimits::validZeros(position[0],position[1]);}
};
// Read-only collector. The caller alone persists and applies the result after success.
struct JointZeroCapture {
  unsigned state=0,error=0,count=0;uint32_t started=0,first=0,stamp[2]={};
  int low[2]={},high[2]={},result[2]={};int64_t sum[2]={};
  bool active()const{return state==1;}
  void fail(unsigned why){state=3;error=why;}
  bool request(uint32_t now,bool off){if(!off||active())return false;*this=JointZeroCapture();state=1;started=now;return true;}
  void update(uint32_t now,bool off,bool imuLevel,const ServoRead::State* s){
    if(!active())return;
    if(!off){fail(1);return;}
    if(now-started>8000){fail(2);return;}
    if(!imuLevel){fail(3);return;}
    for(int i=0;i<2;++i){
      if(!s[i].identified||s[i].state!=1||s[i].age(now)>80||s[i].torque||s[i].status||s[i].error||s[i].voltage<40||s[i].voltage>55||s[i].temperature>=50){fail(4);return;}
    }
    if(s[0].lastData==stamp[0]||s[1].lastData==stamp[1])return;
    for(int i=0;i<2;++i){
      int p=s[i].position;if(!count){low[i]=high[i]=p;first=now;}
      if(p<low[i])low[i]=p;if(p>high[i])high[i]=p;
      if(high[i]-low[i]>8){fail(5);return;}
      sum[i]+=p;stamp[i]=s[i].lastData;
    }
    ++count;
    if(count>=20&&now-first>=1000){
      for(int i=0;i<2;++i)result[i]=int(std::lround(double(sum[i])/count));
      if(!JointLimits::validZeros(result[0],result[1])){fail(6);return;}
      state=2;
    }
  }
};
