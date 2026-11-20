#pragma once
#include "directional_runtime.h"
#include "directional_vectors.h"

struct DirectionCheckResult {bool valid=true;float error=0;unsigned mismatches=0;};
// The same full sequential test is compiled natively and run on the ESP.
// Optional service callback keeps the boot torque-off/readback loop responsive.
inline DirectionCheckResult checkDirectional(void (*service)()=nullptr){
  DirectionCheckResult result;DirectionController controller(1),hardware,reference(1);
  for(int i=0;i<TEST_COUNT;++i){
    if(i%TRACE_LENGTH==0){controller.reset();hardware.reset();reference.reset();}
    float action[2]={},target[2]={};
    bool ok=controller.step(test_observations[i],action,target);
    result.valid=result.valid&&ok;
    if(controller.state.mode!=test_modes[i])++result.mismatches;
    for(int j=0;j<2;++j){
      if(!isfinite(action[j])||!isfinite(target[j]))result.valid=false;
      result.error=fmaxf(result.error,fabsf(action[j]-test_actions[i][j]));
      result.error=fmaxf(result.error,fabsf(target[j]-test_targets[i][j]));
    }
    // Check the hardware frame against the original model frame over the same
    // complete traces, including nonzero prior targets and branch transitions.
    const bool reversed=test_modes[i]==DIRECTION_FRONT_BACK;
    float mapped[4];for(int j=0;j<4;++j)mapped[j]=test_observations[i][j];
    if(reversed)mapped[2]=-mapped[2];
    float ha[2]={},ht[2]={},ra[2]={},rt[2]={};
    result.valid=hardware.step(test_observations[i],ha,ht)&&result.valid;
    result.valid=reference.step(mapped,ra,rt)&&result.valid;
    if(hardware.state.mode!=test_modes[i]||reference.state.mode!=test_modes[i]||
       hardware.state.sign!=reference.state.sign||hardware.state.stable!=reference.state.stable||
       hardware.state.elapsed!=reference.state.elapsed)++result.mismatches;
    if(reversed){ra[0]=-ra[0];rt[0]=-rt[0];}
    for(int j=0;j<2;++j){
      if(!isfinite(ha[j])||!isfinite(ht[j]))result.valid=false;
      result.error=fmaxf(result.error,fabsf(ha[j]-ra[j]));
      result.error=fmaxf(result.error,fabsf(ht[j]-rt[j]));
    }
    if(service&&i%4==0)service();
  }
  float bad[4]={NAN,0,0,0},action[2]={},target[2]={};
  result.valid=result.valid&&!controller.step(bad,action,target);
  result.valid=result.valid&&!hardware.step(bad,action,target);
  result.valid=result.valid&&result.mismatches==0&&result.error<.0003f;
  return result;
}
