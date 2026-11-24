uint8_t imuFailReg=0,imuFailStatus=0; char imuFailOp='N';
// Reused original BMI270 initialization; only console banner removed and I2C timeout bounded to 10 ms.
BMI2_INTF_RETURN_TYPE busRead(uint8_t reg,uint8_t* data,uint32_t len,void* context) {
  uint8_t address=*static_cast<uint8_t*>(context);
  if(len>32){imuFailReg=reg;imuFailStatus=255;imuFailOp='L';return -1;}
  Wire.beginTransmission(address); Wire.write(reg);
  uint8_t status=Wire.endTransmission(false);
  if(status!=0){imuFailReg=reg;imuFailStatus=status;imuFailOp='R';Serial.printf("# I2C_READ_FAIL REG=0x%02X LEN=%lu STATUS=%u\n",reg,(unsigned long)len,status);return -1;}
  if(Wire.requestFrom(uint16_t(address),size_t(len),true)!=len) {
    imuFailReg=reg;imuFailStatus=254;imuFailOp='S';Serial.printf("# I2C_SHORT_READ REG=0x%02X LEN=%lu\n",reg,(unsigned long)len);
    while(Wire.available()) Wire.read();
    return -1;
  }
  for(uint32_t i=0;i<len;++i) data[i]=Wire.read();
  return BMI2_OK;
}

BMI2_INTF_RETURN_TYPE busWrite(uint8_t reg,const uint8_t* data,uint32_t len,void* context) {
  if(len>32){imuFailReg=reg;imuFailStatus=255;imuFailOp='L';return -1;}
  Wire.beginTransmission(*static_cast<uint8_t*>(context));
  Wire.write(reg);Wire.write(data,len);
  uint8_t status=Wire.endTransmission();
  if(status){imuFailReg=reg;imuFailStatus=status;imuFailOp='W';Serial.printf("# I2C_WRITE_FAIL REG=0x%02X LEN=%lu STATUS=%u\n",reg,(unsigned long)len,status);}
  return status==0?BMI2_OK:-1;
}
void waitUs(uint32_t period,void*) {
  // FreeRTOS delay() rounds to ticks; always satisfy Bosch minimum delays.
  uint32_t begin=micros();
  if(period>=2000)delay(period/1000);
  while(uint32_t(micros()-begin)<period)delayMicroseconds(1);
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
void initImu() {
  ready=false;imuFailOp='N';imuFailReg=imuFailStatus=0;
  // Allow startup configuration upload the same timeout as the proven C3 diagnostic.
  // Restore the bounded runtime timeout only after configuration verifies.
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
  bool initialized=false;
  for(unsigned attempt=1;attempt<=3;++attempt){
    if(check(bmi270_init(&imu),"BMI270 init/config upload")){initialized=true;break;}
    Serial.printf("# IMU_INIT_RETRY attempt=%u\n",attempt);delay(100);
  }
  if(!initialized){Serial.println("# IMU_INIT_FAILED");return;}
  if(!check(bmi2_set_adv_power_save(BMI2_DISABLE,&imu),"disable APS")) return;
  bmi2_sens_config cfg[2]={};
  cfg[0].type=BMI2_ACCEL;cfg[1].type=BMI2_GYRO;
  if(!check(bmi2_get_sensor_config(cfg,2,&imu),"read config")) return;
  cfg[0].cfg.acc.odr=BMI2_ACC_ODR_100HZ;
  cfg[0].cfg.acc.range=BMI2_ACC_RANGE_2G;
  cfg[0].cfg.acc.bwp=BMI2_ACC_NORMAL_AVG4;
  cfg[0].cfg.acc.filter_perf=BMI2_PERF_OPT_MODE;
  cfg[1].cfg.gyr.odr=BMI2_GYR_ODR_100HZ;
  cfg[1].cfg.gyr.range=BMI2_GYR_RANGE_2000;
  cfg[1].cfg.gyr.bwp=BMI2_GYR_NORMAL_MODE;
  cfg[1].cfg.gyr.noise_perf=BMI2_POWER_OPT_MODE;
  cfg[1].cfg.gyr.filter_perf=BMI2_PERF_OPT_MODE;
  if(!check(bmi2_set_sensor_config(cfg,2,&imu),"write config")) return;
  uint8_t sensors[2]={BMI2_ACCEL,BMI2_GYRO};
  if(!check(bmi2_sensor_enable(sensors,2,&imu),"enable sensors")) return;
  if(!check(bmi2_get_sensor_config(cfg,2,&imu),"verify config")) return;
  if(cfg[0].cfg.acc.range!=BMI2_ACC_RANGE_2G || cfg[1].cfg.gyr.range!=BMI2_GYR_RANGE_2000 ||
     cfg[0].cfg.acc.odr!=BMI2_ACC_ODR_100HZ || cfg[1].cfg.gyr.odr!=BMI2_GYR_ODR_100HZ) {
    Serial.println("# STOP configuration readback mismatch");return;
  }
  Wire.setTimeOut(10);
  delay(100);ready=true;lastSample=millis();
  Serial.printf("# READY MODEL=BMI270 ID=0x%02X ADDRESS=0x%02X +/-%.0fg +/-%.0fdps sample=100Hz display=50Hz FUSION=BMI270_FUSION_PIN67_V1\n",imu.chip_id,imuAddress,ImuScale::ACCEL_FULL_SCALE_G,ImuScale::GYRO_FULL_SCALE_DPS);
  Serial.printf("# CALIBRATION_SHA256=%s\n",CALIBRATION_SHA256);
}
