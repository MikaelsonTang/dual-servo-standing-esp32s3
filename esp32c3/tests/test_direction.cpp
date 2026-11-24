#include <cassert>
#include <cstdio>
#include <limits>
#include <initializer_list>
#include "../firmware/policy_shadow/directional_checks.h"
int main(){
  auto test=checkDirectional();assert(test.valid);
  printf("DIRECTIONAL_PASS CASES=%d MODE_MISMATCHES=%u ERROR=%.9f\n",TEST_COUNT,test.mismatches,test.error);
  // A pure fore/aft fall now commands the opposite physical ID2 motion.
  for(float roll:{-1.4f,1.4f}){
    DirectionController hardware,original(1);float x[4]={roll,0,0,0};
    float ha[2],ht[2],oa[2],ot[2];
    assert(hardware.step(x,ha,ht)&&original.step(x,oa,ot));
    assert(fabsf(ha[0])>.01f&&ha[0]==-oa[0]&&ht[0]==-ot[0]);
    assert(ht[1]==0&&ot[1]==0);
    // On fallback, the dual model consumes the real hardware target directly;
    // it must not inherit an extra sign flip from the fore/aft branch.
    float lateral[4]={roll,.3f,ht[0],0};float a[2],t[2],raw[2];
    assert(hardware.step(lateral,a,t));forward_side(lateral,raw);
    assert(hardware.state.mode==DIRECTION_DUAL);
    assert(a[0]==direction_clip(raw[0])&&a[1]==direction_clip(raw[1]));
  }
  DirectionController c;float action[2],target[2];
  float forward[4]={1.4f,0,0,0};assert(c.step(forward,action,target));
  assert(c.state.mode==DIRECTION_FRONT_BACK&&c.state.sign==1&&action[1]==0&&target[1]==0);
  // Retain the chosen sign across zero; never reconstruct a fresh state per tick.
  forward[0]=-.1f;forward[2]=.2f;assert(c.step(forward,action,target));
  assert(c.state.mode==DIRECTION_FRONT_BACK&&c.state.sign==1&&c.state.elapsed==1);
  forward[1]=.21f;assert(c.step(forward,action,target));assert(c.state.mode==DIRECTION_DUAL);
  forward[1]=0;assert(c.step(forward,action,target));assert(c.state.mode==DIRECTION_DUAL);
  c.reset();forward[0]=-1.4f;forward[2]=0;assert(c.step(forward,action,target));
  assert(c.state.mode==DIRECTION_FRONT_BACK&&c.state.sign==-1&&target[1]==0);
  // A distinct trial starts without the previous direction latch.
  c.reset();float side[4]={0,1.4f,0,0};assert(c.step(side,action,target));assert(c.state.mode==DIRECTION_DUAL);
  float zero[4]={};for(int i=0;i<49;++i)assert(c.step(zero,action,target));
  assert(c.state.mode==DIRECTION_DUAL);assert(c.step(zero,action,target));
  assert(c.state.mode==DIRECTION_AUTO&&action[0]==0&&action[1]==0);
  for(int i=0;i<4;++i){float invalid[4]={};invalid[i]=NAN;assert(!c.step(invalid,action,target));}
  float large[4]={0,0,1.70f,0};assert(!c.step(large,action,target));
  large[2]=0;large[3]=2.40f;assert(!c.step(large,action,target));
  puts("PASS: router persistence, reflection, fallback, re-enable, stable reset and invalid observations");
}
