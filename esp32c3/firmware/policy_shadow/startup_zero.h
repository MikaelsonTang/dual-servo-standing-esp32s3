#pragma once
#include <cmath>
#include <cstdint>

// Per-boot attitude reference. Average only a continuous stationary window.
// The stored installation transform and gyro bias remain separate.
struct StartupZero {
  bool ready=false,haveTime=false;
  uint32_t previousUs=0,elapsedUs=0,sequence=0;
  unsigned samples=0;
  float reference[4]={1,0,0,0},anchor[4]={1,0,0,0},sum[4]={};
  void clearWindow(){haveTime=false;elapsedUs=0;samples=0;for(float& v:sum)v=0;}
  void request(){ready=false;clearWindow();}
  static bool unit(const float* q){
    double n=0;for(int i=0;i<4;++i){if(!std::isfinite(q[i]))return false;n+=double(q[i])*q[i];}
    return std::fabs(n-1)<.001;
  }
  bool update(uint32_t now,const float* q,const float* a,const float* gyroDps,unsigned quality){
    if(ready)return false;
    double an=0,wn=0;
    for(int i=0;i<3;++i){
      if(!std::isfinite(a[i])||!std::isfinite(gyroDps[i])){clearWindow();return false;}
      an+=double(a[i])*a[i];wn+=double(gyroDps[i])*gyroDps[i];
    }
    if(quality!=1||!unit(q)||an<.95*.95||an>1.05*1.05||wn>1.){clearWindow();return false;}
    uint32_t dt=now-previousUs;
    if(haveTime&&(dt<2000||dt>30000)){clearWindow();return false;}
    if(samples==0)for(int i=0;i<4;++i)anchor[i]=q[i];
    double dot=0;for(int i=0;i<4;++i)dot+=double(anchor[i])*q[i];
    if(std::fabs(dot)<.9999619){clearWindow();return false;} // moved >1 degree
    if(haveTime)elapsedUs+=dt;
    haveTime=true;previousUs=now;++samples;
    for(int i=0;i<4;++i)sum[i]+=dot<0?-q[i]:q[i];
    if(elapsedUs<2000000||samples<180)return false;
    double n=0;for(float v:sum)n+=double(v)*v;n=std::sqrt(n);
    if(n<1){clearWindow();return false;}
    for(int i=0;i<4;++i)reference[i]=float(sum[i]/n);
    ready=true;++sequence;return true;
  }
  bool relative(const float* q,float* out)const{
    if(!ready||!unit(q))return false;
    // q_relative = conjugate(q_reference) * q_current.
    float w=reference[0],x=-reference[1],y=-reference[2],z=-reference[3];
    out[0]=w*q[0]-x*q[1]-y*q[2]-z*q[3];
    out[1]=w*q[1]+x*q[0]+y*q[3]-z*q[2];
    out[2]=w*q[2]-x*q[3]+y*q[0]+z*q[1];
    out[3]=w*q[3]+x*q[2]-y*q[1]+z*q[0];
    return unit(out);
  }
};
