#pragma once
#include "directional_policy.h"
namespace RecoveryOutput {
// Deployment speed gains, not retraining. Always clamp to original trained angles.
inline void apply(const float observation[4],float next[2],int mode,bool forward){
  if(mode==DIRECTION_AUTO)return;
  for(int i=0;i<2;++i){
    if(mode==DIRECTION_FRONT_BACK&&i==1)continue; // preserve exact upper zero hold
    float gain=forward&&i==0?2.f:1.5f;
    next[i]=fmaxf(-POLICY_LIMIT_RAD[i],fminf(POLICY_LIMIT_RAD[i],observation[2+i]+gain*(next[i]-observation[2+i])));
  }
}
}
