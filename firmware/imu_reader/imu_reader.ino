#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include "src/bosch/bmi270.h"

// IMU diagnostic only. No servo commands.
constexpr int SDA_PIN=4, SCL_PIN=5;
uint8_t imuAddress=0;
bmi2_dev imu={};
bool ready=false;
uint32_t lastSample=0,lastPrint=0,lastError=0;

BMI2_INTF_RETURN_TYPE busRead(uint8_t reg,uint8_t* data,uint32_t len,void* context) {
  uint8_t address=*static_cast<uint8_t*>(context);
  if(len>32) return -1;
  Wire.beginTransmission(address); Wire.write(reg);
  if(Wire.endTransmission(false)!=0) return -1;
  if(Wire.requestFrom(uint16_t(address),size_t(len),true)!=len) {
    while(Wire.available()) Wire.read();
    return -1;
  }
  for(uint32_t i=0;i<len;++i) data[i]=Wire.read();
  return BMI2_OK;
}
BMI2_INTF_RETURN_TYPE busWrite(uint8_t reg,const uint8_t* data,uint32_t len,void* context) {
  if(len>32) return -1;
  Wire.beginTransmission(*static_cast<uint8_t*>(context));
  Wire.write(reg);Wire.write(data,len);
  return Wire.endTransmission()==0?BMI2_OK:-1;
}
void waitUs(uint32_t period,void*) {
  if(period>=1000) delay(period/1000);
  if(period%1000) delayMicroseconds(period%1000);
}
bool check(int8_t code,const char* step) {
  if(code==BMI2_OK) return true;
  Serial.printf("# ERROR %s code=%d\n",step,code);return false;
}
void errorMessage(const char* msg) {
  if(millis()-lastError>=1000) {
    Serial.printf("# ERROR %s\n",msg);lastError=millis();
  }
}
void setup() {
  Serial.begin(115200);delay(1500);
  Serial.println("# ESP32-S3 BMI270 diagnostic v2; SDA=4 SCL=5 UART0=115200");
  Serial.println("# No servo control. Tilt is accelerometer-only, valid near rest.");
  Wire.begin(SDA_PIN,SCL_PIN,100000);Wire.setTimeOut(50);
  int found=0,supported=0;
  for(uint8_t addr=8;addr<120;++addr) {
    Wire.beginTransmission(addr);
    if(Wire.endTransmission()!=0) continue;
    ++found;Serial.printf("# I2C device 0x%02X\n",addr);
    if(addr!=0x68 && addr!=0x69) continue;
    uint8_t id1=0,id2=0;
    if(busRead(0,&id1,1,&addr)!=0 || busRead(0,&id2,1,&addr)!=0) continue;
    Serial.printf("# CHIP_ID[0x00]=0x%02X\n",id1);
    if(id1==BMI270_CHIP_ID && id1==id2) {++supported;imuAddress=addr;}
  }
  if(supported!=1) {
    Serial.printf("# STOP found=%d BMI270=%d; check wiring/model; nothing configured\n",found,supported);
    return;
  }
  imu.intf=BMI2_I2C_INTF;imu.intf_ptr=&imuAddress;
  imu.read=busRead;imu.write=busWrite;imu.delay_us=waitUs;
  imu.read_write_len=32;imu.config_file_ptr=nullptr;
  if(!check(bmi270_init(&imu),"BMI270 init/config upload")) return;
  if(!check(bmi2_set_adv_power_save(BMI2_DISABLE,&imu),"disable APS")) return;
  bmi2_sens_config cfg[2]={};
  cfg[0].type=BMI2_ACCEL;cfg[1].type=BMI2_GYRO;
  if(!check(bmi2_get_sensor_config(cfg,2,&imu),"read config")) return;
  cfg[0].cfg.acc.odr=BMI2_ACC_ODR_100HZ;
  cfg[0].cfg.acc.range=BMI2_ACC_RANGE_2G;
  cfg[0].cfg.acc.bwp=BMI2_ACC_NORMAL_AVG4;
  cfg[0].cfg.acc.filter_perf=BMI2_PERF_OPT_MODE;
  cfg[1].cfg.gyr.odr=BMI2_GYR_ODR_100HZ;
  cfg[1].cfg.gyr.range=BMI2_GYR_RANGE_250;
  cfg[1].cfg.gyr.bwp=BMI2_GYR_NORMAL_MODE;
  cfg[1].cfg.gyr.noise_perf=BMI2_POWER_OPT_MODE;
  cfg[1].cfg.gyr.filter_perf=BMI2_PERF_OPT_MODE;
  if(!check(bmi2_set_sensor_config(cfg,2,&imu),"write config")) return;
  uint8_t sensors[2]={BMI2_ACCEL,BMI2_GYRO};
  if(!check(bmi2_sensor_enable(sensors,2,&imu),"enable sensors")) return;
  if(!check(bmi2_get_sensor_config(cfg,2,&imu),"verify config")) return;
  if(cfg[0].cfg.acc.range!=BMI2_ACC_RANGE_2G || cfg[1].cfg.gyr.range!=BMI2_GYR_RANGE_250 ||
     cfg[0].cfg.acc.odr!=BMI2_ACC_ODR_100HZ || cfg[1].cfg.gyr.odr!=BMI2_GYR_ODR_100HZ) {
    Serial.println("# STOP configuration readback mismatch");return;
  }
  delay(100);ready=true;lastSample=millis();
  Serial.printf("# READY MODEL=BMI270 ID=0x%02X ADDRESS=0x%02X +/-2g +/-250dps sample=100Hz display=10Hz\n",imu.chip_id,imuAddress);
  Serial.println("ms,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps,acc_norm_g,roll_acc_deg,pitch_acc_deg");
}
void loop() {
  if(!ready) {errorMessage("IMU not initialized; check startup log then press RST");delay(20);return;}
  bmi2_sens_data data={};
  if(bmi2_get_sensor_data(&data,&imu)!=BMI2_OK) {
    errorMessage("I2C sample read failed");delay(10);return;
  }
  if(!(data.status&BMI2_DRDY_ACC) || !(data.status&BMI2_DRDY_GYR)) {
    if(millis()-lastSample>1000) errorMessage("No fresh sensor samples");
    delay(2);return;
  }
  lastSample=millis();
  if(millis()-lastPrint<100) return;
  lastPrint=millis();
  float ax=data.acc.x/16384.0f,ay=data.acc.y/16384.0f,az=data.acc.z/16384.0f;
  float gx=data.gyr.x*(250.0f/32768.0f),gy=data.gyr.y*(250.0f/32768.0f),gz=data.gyr.z*(250.0f/32768.0f);
  float norm=sqrtf(ax*ax+ay*ay+az*az);
  float roll=norm>0.05f?atan2f(ay,az)*180.0f/PI:NAN;
  float pitch=norm>0.05f?atan2f(-ax,sqrtf(ay*ay+az*az))*180.0f/PI:NAN;
  Serial.printf("%lu,%.5f,%.5f,%.5f,%.4f,%.4f,%.4f,%.5f,%.2f,%.2f\n",
    (unsigned long)lastSample,ax,ay,az,gx,gy,gz,norm,roll,pitch);
}

