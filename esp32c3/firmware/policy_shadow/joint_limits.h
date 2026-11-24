#pragma once
namespace JointLimits {
// Physical order: upper ID1, lower ID2. Keep measured software zeros.
constexpr int ZERO[2]={337,2872};
// Floor(degrees * 4096 / 360), so rounding never exceeds the trained range.
constexpr int COUNTS[2]={1536,1080};
inline bool allowed(unsigned id,int position){
  return id>=1&&id<=2&&position>=ZERO[id-1]-COUNTS[id-1]&&position<=ZERO[id-1]+COUNTS[id-1];
}
}
