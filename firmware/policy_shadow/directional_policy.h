#pragma once
#include <math.h>
#include <stdint.h>
#include "policy_networks.h"
// Angles in radians. Policy order = lower ID2, upper ID1.
static const uint8_t POLICY_SERVO_IDS[2]={2,1};
static const float POLICY_LIMIT_RAD[2]={1.658062789f,2.356194490f};
static const float POLICY_DELTA_RAD=0.08f;
static const uint32_t POLICY_PERIOD_US=20000;
enum DirectionMode { DIRECTION_AUTO=0, DIRECTION_FRONT_BACK=1, DIRECTION_DUAL=2 };
struct DirectionalState { int mode; int sign; int stable; uint32_t elapsed; };
static inline float direction_clip(float x) { return fmaxf(-1.f,fminf(1.f,x)); }
static inline void directional_reset(DirectionalState* state) {
    state->mode=DIRECTION_AUTO;state->sign=1;state->stable=0;state->elapsed=0;
}
// State is retained between ticks. Call reset only on enable/reinitialization, not every tick.
// False means invalid input: caller must stop motion through its existing fault handler.
// Default +1 preserves the uploaded simulation convention. The hardware adapter
// may reverse the front/back lower joint in BOTH its observation and action.
static inline bool directional_action(DirectionalState* state,const float obs[4],float action[2],int frontBackJointSign=1) {
    action[0]=0.f;action[1]=0.f;
    for(int i=0;i<4;i++) if(!isfinite(obs[i])) return false;
    if(fabsf(obs[2])>POLICY_LIMIT_RAD[0]+1e-5f || fabsf(obs[3])>POLICY_LIMIT_RAD[1]+1e-5f) return false;
    const float roll=obs[0],pitch=obs[1],lower=obs[2],upper=obs[3];
    if(state->mode==DIRECTION_AUTO) {
        if(fabsf(roll)>.20f && fabsf(pitch)<.07f && fabsf(upper)<.04f) {
            state->mode=DIRECTION_FRONT_BACK;state->sign=roll>0.f?1:-1;state->elapsed=0;
        } else if(fabsf(pitch)>.12f || fabsf(upper)>.04f || fabsf(lower)>.10f) state->mode=DIRECTION_DUAL;
    } else if(state->mode==DIRECTION_FRONT_BACK) {
        if(state->elapsed<UINT32_MAX) state->elapsed++;
        if(fabsf(pitch)>.20f) state->mode=DIRECTION_DUAL;
    }
    bool stable=fabsf(roll)<.08f && fabsf(pitch)<.08f && fabsf(lower)<.08f && fabsf(upper)<.04f;
    state->stable=stable?(state->stable<50?state->stable+1:50):0;
    if(state->stable>=50) {state->mode=DIRECTION_AUTO;state->elapsed=0;}
    float raw[2]={0.f,0.f};
    if(state->mode==DIRECTION_FRONT_BACK) {
        float canonical[4]={state->sign*roll,pitch,frontBackJointSign*state->sign*lower,upper};
        forward_front_back(canonical,raw);
        action[0]=frontBackJointSign*state->sign*direction_clip(raw[0]);
        action[1]=direction_clip(-upper/POLICY_DELTA_RAD);
    } else if(state->mode==DIRECTION_DUAL) {
        forward_side(obs,raw);
        action[0]=direction_clip(raw[0]);action[1]=direction_clip(raw[1]);
    } else {
        action[0]=direction_clip(-lower/POLICY_DELTA_RAD);
        action[1]=direction_clip(-upper/POLICY_DELTA_RAD);
    }
    return isfinite(action[0]) && isfinite(action[1]);
}
static inline bool directional_update_targets(const float action[2],float targets[2]) {
    for(int i=0;i<2;i++) if(!isfinite(action[i]) || !isfinite(targets[i]) || fabsf(targets[i])>POLICY_LIMIT_RAD[i]+1e-5f) return false;
    for(int i=0;i<2;i++) targets[i]=fmaxf(-POLICY_LIMIT_RAD[i],fminf(POLICY_LIMIT_RAD[i],targets[i]+POLICY_DELTA_RAD*direction_clip(action[i])));
    return true;
}
