#pragma once
#include <cmath>
#include <cstdint>

namespace ImuScale {
// Must match the hardware range configured and read back in imu_setup.h.
constexpr float ACCEL_FULL_SCALE_G = 2.f;
constexpr float GYRO_FULL_SCALE_DPS = 2000.f;
constexpr float SATURATION_FRACTION = .995f;
inline float accel(int16_t raw) { return raw * (ACCEL_FULL_SCALE_G / 32768.f); }
inline float gyro(int16_t raw) { return raw * (GYRO_FULL_SCALE_DPS / 32768.f); }
inline bool saturated(float acceleration, float angularRate) {
  return std::fabs(acceleration) >= ACCEL_FULL_SCALE_G * SATURATION_FRACTION ||
         std::fabs(angularRate) >= GYRO_FULL_SCALE_DPS * SATURATION_FRACTION;
}
}
