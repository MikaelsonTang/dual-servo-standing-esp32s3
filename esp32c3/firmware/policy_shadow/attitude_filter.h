#pragma once
#include <cmath>
#include <cstdint>

// Quaternion maps calibrated base vectors into a gravity-aligned world frame.
// Mahony-style proportional gravity correction, fixed measured gyro bias
// supplied by the caller, no integral/adaptive bias and no heading reference.
// Shared verbatim between ESP32 firmware and native offline tests.
struct AttitudeFilter {
  float q[4]={1,0,0,0};
  float weight=0, accNorm=0, dt=0;
  unsigned quality=0; // 0 acquiring, 1 corrected, 2 gyro-only, 3 invalid sample/gap
  unsigned faults=0;
  bool initialized=false, haveTime=false;
  uint32_t previousUs=0;
  float stableSeconds=0, accSum[3]={0,0,0}, reference[3]={0,0,1};
  unsigned stableSamples=0;
  static constexpr float KP=2.0f;

  static float norm3(const float* v) { return std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]); }
  static bool finite3(const float* v) { return std::isfinite(v[0])&&std::isfinite(v[1])&&std::isfinite(v[2]); }
  static float clamp(float x,float lo,float hi) { return x<lo?lo:(x>hi?hi:x); }
  void invalidate() {
    initialized=false; quality=3; weight=0; stableSeconds=0; stableSamples=0;
    for(float& v:accSum)v=0;
    ++faults;
  }
  void resetAcquisition() {
    stableSeconds=0; stableSamples=0;
    for(float& v:accSum)v=0;
  }
  void gravity(float* v) const {
    v[0]=2*(q[1]*q[3]-q[0]*q[2]);
    v[1]=2*(q[0]*q[1]+q[2]*q[3]);
    v[2]=1-2*(q[1]*q[1]+q[2]*q[2]);
  }
  void integrate(const float* omega,float seconds) {
    float n=norm3(omega), half=.5f*n*seconds;
    float scale=n>1e-8f?std::sin(half)/n:.5f*seconds;
    float b[4]={std::cos(half),omega[0]*scale,omega[1]*scale,omega[2]*scale};
    float a[4]={q[0],q[1],q[2],q[3]};
    q[0]=a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3];
    q[1]=a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2];
    q[2]=a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1];
    q[3]=a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0];
    float nQ=std::sqrt(q[0]*q[0]+q[1]*q[1]+q[2]*q[2]+q[3]*q[3]);
    if(!std::isfinite(nQ)||nQ<.1f){invalidate();return;}
    for(float& v:q)v/=nQ;
  }
  void initializeFromGravity(const float* a) {
    float roll=std::atan2(a[1],a[2]);
    float pitch=std::atan2(-a[0],std::sqrt(a[1]*a[1]+a[2]*a[2]));
    float cr=std::cos(roll/2),sr=std::sin(roll/2),cp=std::cos(pitch/2),sp=std::sin(pitch/2);
    q[0]=cr*cp;q[1]=sr*cp;q[2]=cr*sp;q[3]=-sr*sp; // initial yaw=0, not measured
    initialized=true; quality=1; weight=1;
  }
  bool update(uint32_t nowUs,const float* a,const float* w,bool saturated=false) {
    uint32_t elapsed=nowUs-previousUs;
    previousUs=nowUs;
    dt=haveTime?elapsed*1e-6f:0;
    bool first=!haveTime;haveTime=true;
    if(!finite3(a)||!finite3(w)||saturated){invalidate();return false;}
    accNorm=norm3(a);
    if(first){quality=0;return false;}
    if(dt<.002f||dt>.030f){invalidate();return false;}
    if(!initialized) {
      quality=0;
      if(accNorm<.90f||accNorm>1.10f||norm3(w)>.017453293f){resetAcquisition();return false;}
      float u[3]={a[0]/accNorm,a[1]/accNorm,a[2]/accNorm};
      if(stableSamples==0)for(int i=0;i<3;++i)reference[i]=u[i];
      float cosine=u[0]*reference[0]+u[1]*reference[1]+u[2]*reference[2];
      if(cosine<.99939f){resetAcquisition();return false;} // >2 degrees during acquisition
      stableSeconds+=dt;++stableSamples;
      for(int i=0;i<3;++i)accSum[i]+=a[i];
      if(stableSeconds>=1.5f&&stableSamples>=100)initializeFromGravity(accSum);
      return initialized;
    }
    integrate(w,dt);
    if(!initialized)return false;
    float deviation=std::fabs(accNorm-1.0f);
    weight=clamp((.15f-deviation)/.10f,0,1); // full <=0.05g, zero >=0.15g deviation
    if(accNorm<.1f)weight=0;
    if(weight>0) {
      float predicted[3];gravity(predicted);
      float u[3]={a[0]/accNorm,a[1]/accNorm,a[2]/accNorm};
      float correction[3]={
        KP*weight*(u[1]*predicted[2]-u[2]*predicted[1]),
        KP*weight*(u[2]*predicted[0]-u[0]*predicted[2]),
        KP*weight*(u[0]*predicted[1]-u[1]*predicted[0])};
      integrate(correction,dt);
    }
    if(initialized)quality=weight>0?1:2;
    return initialized;
  }
};
