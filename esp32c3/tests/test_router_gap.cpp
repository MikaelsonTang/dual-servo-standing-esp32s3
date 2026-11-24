#include <cassert>
#include <cmath>
#include <cstdio>
#include <initializer_list>
#include "../firmware/policy_shadow/directional_runtime.h"
int main(){
  for(float roll:{-1.72f,1.72f})for(float pitch:{-.121f,-.12f,-.0873f,-.07f,0.f,.07f,.0873f,.12f,.121f}){
    DirectionController controller;
    float obs[4]={roll,pitch,0,0},action[2],target[2];
    assert(controller.step(obs,action,target));
    assert(controller.state.mode==(fabsf(pitch)<=.12f?DIRECTION_FRONT_BACK:DIRECTION_DUAL));
    assert(fabsf(action[0])+fabsf(action[1])>.0001f);
    for(int n=0;n<100;++n){obs[2]=target[0];obs[3]=target[1];assert(controller.step(obs,action,target));assert(controller.state.mode!=DIRECTION_AUTO);}
  }
  puts("PASS: front/back +/-98deg with +/-4..7deg cross-lean enters a network, no AUTO dead zone");
}
