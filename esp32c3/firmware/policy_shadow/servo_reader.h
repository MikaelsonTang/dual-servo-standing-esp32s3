#pragma once
#include "driver/uart.h"
#include "servo_protocol.h"
#include "joint_limits.h"
#include "servo_write_limits.h"

// One in-flight transaction; Motion::Controller is the sole write caller.
struct ServoReader {
  ServoRead::State states[2];
  bool installed=false,pending=false,identity=false,writing=false,writeOK=false;
  uint8_t selected=0,next=0,rx[128]={};size_t count=0;
  uint32_t sent=0,lastQuery=0,writeDone=0;
  static constexpr uart_port_t BUS=UART_NUM_1;
  void begin(){
    uart_config_t cfg={};cfg.baud_rate=1000000;cfg.data_bits=UART_DATA_8_BITS;
    cfg.parity=UART_PARITY_DISABLE;cfg.stop_bits=UART_STOP_BITS_1;
    cfg.flow_ctrl=UART_HW_FLOWCTRL_DISABLE;cfg.source_clk=UART_SCLK_APB;
    if(uart_param_config(BUS,&cfg)!=ESP_OK||uart_driver_install(BUS,1024,256,0,nullptr,0)!=ESP_OK){states[0].state=states[1].state=5;return;}
    if(uart_set_pin(BUS,4,5,UART_PIN_NO_CHANGE,UART_PIN_NO_CHANGE)!=ESP_OK){uart_driver_delete(BUS);states[0].state=states[1].state=5;return;}
    installed=true;
  }
  void finish(bool ok){pending=false;if(writing){writeOK=ok;++writeDone;}}
  bool send(const uint8_t* tx,size_t n,uint32_t now){
    if(!installed||pending)return false;
    count=0;uart_flush_input(BUS);sent=now;
    if(uart_write_bytes(BUS,tx,n)!=int(n))return false;
    pending=true;return true;
  }
  bool write(uint8_t id,uint8_t address,uint16_t value,uint8_t bytes,uint32_t now){
    // Only locked (non-persistent) angle-mode changes; never unlock EEPROM.
    if(!ServoWriteLimits::allowed(id,address,value,bytes,states,now)){
      Serial.printf("# WRITE_REJECT ID=%u REG=%u VALUE=%u BYTES=%u\n",id,address,value,bytes);return false;
    }
    uint8_t tx[9]={255,255,id,uint8_t(bytes+3),3,address,uint8_t(value),uint8_t(value>>8),0};
    size_t n=bytes+7;uint8_t sum=0;for(size_t i=2;i<n-1;++i)sum+=tx[i];tx[n-1]=uint8_t(~sum);
    selected=id-1;writing=true;identity=false;return send(tx,n,now);
  }
  void query(uint32_t now,uint32_t interval=20,bool liveOnly=false,bool identityOnly=false){
    if(!installed||pending||now-lastQuery<interval)return;
    selected=next;next^=1;lastQuery=now;
    auto& s=states[selected];identity=identityOnly||!s.identified||(!liveOnly&&now-s.lastIdentity>=2000);
    uint8_t tx[8];ServoRead::request(selected+1,identity,tx);writing=false;
    if(!send(tx,8,now))s.state=5;
  }
  void poll(){
    if(!installed||!pending)return;
    uint32_t now=millis();auto& s=states[selected];
    int n=uart_read_bytes(BUS,rx+count,sizeof(rx)-count,0);
    if(n<0){s.state=5;finish(false);return;}count+=size_t(n);
    for(size_t p=0;p+6<=count;++p){
      if(rx[p]!=255||rx[p+1]!=255||rx[p+2]!=selected+1)continue;
      uint8_t length=rx[p+3];
      if(length!=(writing?2:(identity?42:33))&&!(length==2&&rx[p+4]!=0))continue;
      size_t total=size_t(length)+4;if(p+total>count||!ServoRead::checksum(rx+p,total))continue;
      if(rx[p+4]){s.state=4;s.error=rx[p+4];finish(false);return;}
      if(!writing){
        if(identity){
          const uint8_t* e=rx+p+5;s.identified=ServoRead::identityMatches(selected+1,e);s.lastIdentity=now;
          s.angleLow=uint16_t(e[9])|(uint16_t(e[10])<<8);s.angleHigh=uint16_t(e[11])|(uint16_t(e[12])<<8);
          s.factoryCurrent=uint16_t(e[28])|(uint16_t(e[29])<<8);s.factoryTorque=uint16_t(e[16])|(uint16_t(e[17])<<8);s.mode=e[33];
          Serial.printf("# SERVO_CONFIG ID=%u MODE=%u ANGLE=%u,%u FACTORY_CURRENT=%u FACTORY_TORQUE=%u VOLTAGE_DV=%u,%u OFFSET_BYTES=%u,%u\n",selected+1,s.mode,s.angleLow,s.angleHigh,s.factoryCurrent,s.factoryTorque,e[15],e[14],e[31],e[32]);
          if(!s.identified)s.state=3;
        }else if(s.identified)s.decode(rx+p+5,now);
      }
      finish(true);return;
    }
    if(now-sent>=25||count==sizeof(rx)){s.state=2;finish(false);}
  }
};
