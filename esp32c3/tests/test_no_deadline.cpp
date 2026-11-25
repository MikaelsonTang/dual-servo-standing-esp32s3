#define main baseline_main
#include "test_motion.cpp"
#undef main
#include "../firmware/policy_shadow/recovery_output.h"
int main(){
  assert(baseline_main()==0);
  {Rig r;r.run(Motion::RECOVERY);r.step(180000,0,true,1.6f);assert(r.c.phase==2&&r.c.reason!=Motion::DURATION);
   r.c.stop(Motion::HOST_STOP);r.off();}
  {Rig r;r.run(Motion::RECOVERY);r.step(180000,0,true,1.6f);r.c.policy(-.3f,.3f);r.step(500,0,true,1.6f);
   r.step(5000,0,true,.05f,0);assert(!r.c.engaged()&&r.c.reason==Motion::HOME_COMPLETE);r.off();}
  float obs[4]={1.4f,0,0,0},normal[2]={.08f,0},front[2]={.08f,0};
  RecoveryOutput::apply(obs,normal,DIRECTION_FRONT_BACK,false);assert(fabsf(normal[0]-.12f)<1e-6f&&normal[1]==0);
  RecoveryOutput::apply(obs,front,DIRECTION_FRONT_BACK,true);assert(fabsf(front[0]-.16f)<1e-6f&&front[1]==0);
  for(int sign:{-1,1}){float edge[4]={0,1.4f,sign*POLICY_LIMIT_RAD[0],sign*POLICY_LIMIT_RAD[1]},next[2]={edge[2]+sign*.08f,edge[3]+sign*.08f};
    RecoveryOutput::apply(edge,next,DIRECTION_DUAL,false);assert(next[0]==edge[2]&&next[1]==edge[3]);}
  puts("PASS: recovery remains active past 180s, STOP and successful home still finish, gains and trained limits correct");
}
