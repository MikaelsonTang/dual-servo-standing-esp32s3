#pragma once
#include "servo_protocol.h"
#include "joint_limits.h"
// One profile for BOTH controller configuration and UART write validation.
namespace ServoWriteLimits {
constexpr uint16_t CURRENT=150,TORQUE=900,SPEED=150;
inline bool allowed(uint8_t id,uint8_t address,uint16_t value,uint8_t bytes,
                    const ServoRead::State* states,uint32_t now){
  if(id!=1&&id!=2)return false;
  const auto& s=states[id-1];
  if(address==40&&bytes==1&&value==0)return true;
  if(address==44&&bytes==2&&value<=CURRENT&&value<=s.factoryCurrent)return true;
  if(address==48&&bytes==2&&value<=TORQUE&&value<=s.factoryTorque)return true;
  if(address==46&&bytes==2&&value==SPEED)return true;
  if((address==9||address==11)&&bytes==2&&value==0&&s.eepromLock==1&&s.torque==0&&s.age(now)<=80)return true;
  int position=value&0x8000?-int(value&0x7fff):int(value);
  return address==42&&bytes==2&&JointLimits::allowed(id,position);
}
}
