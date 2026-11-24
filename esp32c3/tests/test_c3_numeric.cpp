#include <cmath>
#include <cstdio>
#include <random>
#include "../firmware/policy_shadow/directional_checks.h"
#include "reference_networks.h"
int main(){
  auto result=checkDirectional();
  printf("golden valid=%d error=%.9f mismatches=%u\n",result.valid,result.error,result.mismatches);
  std::mt19937 rng(20261124);std::uniform_real_distribution<float> unit(-1,1);
  float maxError=0;
  for(int n=0;n<20000;++n){
    float in[4]={unit(rng)*3.14159265f,unit(rng)*1.57079633f,unit(rng)*1.65806279f,unit(rng)*2.35619449f};
    float a[2],b[2];
    for(int net=0;net<2;++net){
      if(net){forward_side(in,a);Original::forward_side(in,b);}
      else{forward_front_back(in,a);Original::forward_front_back(in,b);}
      for(int j=0;j<2;++j){if(!std::isfinite(a[j]))return 2;maxError=fmaxf(maxError,fabsf(a[j]-b[j]));}
    }
  }
  printf("random 40000 network evaluations max raw output error=%.9f\n",maxError);
  return result.valid&&maxError<.0003f?0:1;
}
