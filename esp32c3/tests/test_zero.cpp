#include "../firmware/policy_shadow/startup_zero.h"
#include "../firmware/policy_shadow/shadow_core.h"
#include <cassert>
#include <limits>
int main(){
  StartupZero z;float q[4]={std::cos(.04f),std::sin(.04f),0,0},a[3]={0,0,1},w[3]={},out[4];
  assert(!z.relative(q,out));
  for(unsigned i=0;i<=199;++i)assert(!z.update(10000*i,q,a,w,1));
  assert(z.update(2000000,q,a,w,1)&&z.ready&&z.sequence==1);
  assert(z.relative(q,out)&&std::fabs(out[0]-1)<1e-6&&std::fabs(out[1])<1e-6);
  // q_current = reference * pitch(+0.3). Remove a different-axis offset.
  float d=.15f,cur[4]={q[0]*std::cos(d),q[1]*std::cos(d),q[0]*std::sin(d),q[1]*std::sin(d)};
  float roll,pitch;bool singular;
  assert(z.relative(cur,out)&&Shadow::angles(out,roll,pitch,singular));
  assert(std::fabs(roll)<1e-6&&std::fabs(pitch-.3f)<1e-6);
  assert(!z.update(2010000,cur,a,w,1)&&z.ready); // latched reference never follows motion
  z.request();assert(!z.ready);
  for(unsigned i=0;i<90;++i)z.update(i*10000,q,a,w,1);
  w[0]=2;assert(!z.update(900000,q,a,w,1)&&z.samples==0);w[0]=0;
  for(unsigned i=0;i<=200;++i){float sign=i%2?-1.f:1.f,flip[4];for(int j=0;j<4;++j)flip[j]=q[j]*sign;z.update(1000000+i*10000,flip,a,w,1);}
  assert(z.ready&&z.sequence==2&&z.relative(q,out)&&std::fabs(out[0]-1)<1e-6);
  z.request();z.update(4000000,q,a,w,1);z.update(4010000,cur,a,w,1);assert(z.samples==0);
  z.update(4020000,q,a,w,1);z.update(4070000,q,a,w,1);assert(z.samples==0);
  a[0]=std::numeric_limits<float>::quiet_NaN();assert(!z.update(4080000,q,a,w,1));
}
