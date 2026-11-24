#include "../firmware/policy_shadow/imu_scale.h"
#include "../firmware/policy_shadow/attitude_filter.h"
#include <cassert>

int main() {
  assert(ImuScale::gyro(4096) == 250.f);
  assert(ImuScale::gyro(-16384) == -1000.f);
  assert(ImuScale::accel(16384) == 1.f);
  assert(!ImuScale::saturated(1.f, 300.f));
  assert(!ImuScale::saturated(1.f, -1000.f));
  assert(ImuScale::saturated(1.f, ImuScale::gyro(32767)));
  assert(ImuScale::saturated(1.f, ImuScale::gyro(-32768)));
  assert(ImuScale::saturated(ImuScale::accel(32767), 0.f));
  AttitudeFilter filter;
  float a[3]={0,0,1}, still[3]={0,0,0};
  for (uint32_t t=10000;t<=2000000;t+=10000) filter.update(t,a,still,false);
  assert(filter.initialized);
  // A real 300 dps z-rotation is valid with the new range, and integrates
  // 0.03 degrees per 100 us / 3 degrees per 10 ms, rather than 1/8 speed.
  float w[3]={0,0,300.f*3.14159265358979323846f/180.f};
  assert(filter.update(2010000,a,w,ImuScale::saturated(1.f,300.f)));
  assert(filter.quality==1 && filter.faults==0);
  float yaw=2*std::atan2(filter.q[3],filter.q[0]);
  assert(std::fabs(yaw-3.f*3.14159265358979323846f/180.f)<1e-6f);
  assert(!filter.update(2020000,a,w,ImuScale::saturated(1.f,2000.f)));
  assert(!filter.initialized && filter.quality==3);
}
