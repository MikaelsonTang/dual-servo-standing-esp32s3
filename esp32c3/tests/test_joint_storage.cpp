#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
#include "../firmware/policy_shadow/joint_zero_storage.h"
struct MemoryStore {
  static std::vector<unsigned char> bytes;static bool writeFail,readFail;
  bool begin(const char*,bool){return true;}
  size_t getBytesLength(const char*){return bytes.size();}
  size_t getBytes(const char*,void* out,size_t n){if(readFail||bytes.size()!=n)return 0;memcpy(out,bytes.data(),n);return n;}
  size_t putBytes(const char*,const void* in,size_t n){if(writeFail)return 0;bytes.assign((const unsigned char*)in,(const unsigned char*)in+n);return n;}
  void end(){}
};
std::vector<unsigned char> MemoryStore::bytes;bool MemoryStore::writeFail=false,MemoryStore::readFail=false;
int main(){
  assert(!JointZeroStorage::load<MemoryStore>()&&!JointLimits::calibrated);
  assert(JointZeroStorage::persist<MemoryStore>(4045,321));
  JointLimits::ZERO[0]=0;JointLimits::ZERO[1]=0;JointLimits::calibrated=false; // reboot RAM
  assert(JointZeroStorage::load<MemoryStore>()&&JointLimits::calibrated);
  assert(JointLimits::ZERO[0]==4045&&JointLimits::ZERO[1]==321);
  MemoryStore::writeFail=true;
  assert(!JointZeroStorage::persist<MemoryStore>(350,2800));assert(JointLimits::ZERO[0]==4045);
  MemoryStore::writeFail=false;MemoryStore::readFail=true;
  assert(!JointZeroStorage::persist<MemoryStore>(350,2800));assert(JointLimits::ZERO[0]==4045);
  MemoryStore::readFail=false;
  MemoryStore::bytes[8]^=1;
  assert(!JointZeroStorage::load<MemoryStore>()&&!JointLimits::calibrated);
  MemoryStore::bytes.clear(); // another uncalibrated board
  assert(!JointZeroStorage::load<MemoryStore>()&&!JointLimits::calibrated);
  assert(JointZeroStorage::persist<MemoryStore>(1100,2200));
  assert(JointLimits::ZERO[0]==1100&&JointLimits::ZERO[1]==2200);
  puts("PASS: production storage template, reboot reload, corrupt/missing record, failed write/readback, separate device");
}
