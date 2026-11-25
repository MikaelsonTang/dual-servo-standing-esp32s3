#pragma once
#include <cmath>
#include <cstdint>
#include "policy_control.h"
namespace Shadow {
constexpr uint32_t PERIOD_US=20000, MAX_AGE_US=30000;
// Policy order: lower ID2 +/-90, upper ID1 +/-130, matching training.
static const auto& LIMIT=POLICY_LIMIT_RAD;
constexpr float DELTA=.08f;
inline float clip(float v,float lo,float hi){return v<lo?lo:(v>hi?hi:v);}
// Same Euler convention and exact-pitch canonical roll as the training code.
// Double intermediates avoid a float-rounding 0/pi flip at exact pitch=90 deg.
inline bool angles(const float* q,float& roll,float& pitch,bool& singular){
  double n=0; for(int i=0;i<4;++i){if(!std::isfinite(q[i]))return false;n+=double(q[i])*q[i];}
  if(std::fabs(n-1.)>.001)return false;
  double w=q[0]/std::sqrt(n),x=q[1]/std::sqrt(n),y=q[2]/std::sqrt(n),z=q[3]/std::sqrt(n);
  double a=2*(w*x+y*z),b=1-2*(x*x+y*y),s=2*(w*y-z*x);
  roll=std::hypot(a,b)<1e-12?0.f:float(std::atan2(a,b));
  pitch=float(std::asin(s<-1?-1:(s>1?1:s)));
  singular=std::hypot(a,b)<.05;
  return std::isfinite(roll)&&std::isfinite(pitch);
}
inline bool integrate(const float* raw,const float* before,float* action,float* after){
  for(int i=0;i<2;++i)if(!std::isfinite(raw[i])||!std::isfinite(before[i])||std::fabs(before[i])>LIMIT[i]+.000001f)return false;
  for(int i=0;i<2;++i){action[i]=clip(raw[i],-1,1);after[i]=clip(before[i]+DELTA*action[i],-LIMIT[i],LIMIT[i]);}
  return true;
}
inline bool fresh(uint32_t now,uint32_t sample){return uint32_t(now-sample)<=MAX_AGE_US;}
}
