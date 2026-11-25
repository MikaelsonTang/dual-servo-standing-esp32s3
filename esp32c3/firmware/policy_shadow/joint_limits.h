#pragma once
namespace JointLimits {
// Physical order: upper ID1, lower ID2. Keep measured software zeros.
static int ZERO[2]={337,2872};
static bool calibrated=true; // Firmware sets false until its own NVS record validates.
// Floor(degrees * 4096 / 360), so rounding never exceeds the trained range.
constexpr int COUNTS[2]={1536,1080};
inline bool validZeros(int upper,int lower){
  return upper>=-32767+COUNTS[0]&&upper<=32767-COUNTS[0]&&lower>=-32767+COUNTS[1]&&lower<=32767-COUNTS[1];
}
inline bool applyZeros(int upper,int lower){
  if(!validZeros(upper,lower))return false;ZERO[0]=upper;ZERO[1]=lower;calibrated=true;return true;
}
inline bool allowed(unsigned id,int position){
  return id>=1&&id<=2&&position>=ZERO[id-1]-COUNTS[id-1]&&position<=ZERO[id-1]+COUNTS[id-1];
}
}
