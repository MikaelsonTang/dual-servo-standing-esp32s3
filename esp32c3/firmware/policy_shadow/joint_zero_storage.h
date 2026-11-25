#pragma once
#include "joint_zero_capture.h"
namespace JointZeroStorage {
template<class Store> bool read(JointZeroRecord& record){
  Store prefs;if(!prefs.begin("hd1910-jz",true))return false;
  bool ok=prefs.getBytesLength("v1")==sizeof(record)&&prefs.getBytes("v1",&record,sizeof(record))==sizeof(record);
  prefs.end();return ok&&record.valid();
}
template<class Store> bool load(){
  JointLimits::calibrated=false;JointZeroRecord record;
  return read<Store>(record)&&JointLimits::applyZeros(record.position[0],record.position[1]);
}
template<class Store> bool persist(int upper,int lower){
  if(!JointLimits::validZeros(upper,lower))return false;
  JointZeroRecord record;record.position[0]=upper;record.position[1]=lower;record.checksum=record.digest();
  Store prefs;if(!prefs.begin("hd1910-jz",false))return false;
  bool ok=prefs.putBytes("v1",&record,sizeof(record))==sizeof(record);prefs.end();
  JointZeroRecord verified;
  if(!ok||!read<Store>(verified)||verified.position[0]!=upper||verified.position[1]!=lower)return false;
  return JointLimits::applyZeros(upper,lower);
}
}
