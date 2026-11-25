#pragma once
#include "directional_policy.h"

// One instance per controller; reset only at an explicit enable/new trial.
struct DirectionController {
  DirectionalState state;
  // Only FRONT_BACK uses the reversed ID2 convention. All telemetry, actual
  // sent targets, home and DUAL stay in the existing hardware coordinates.
  static constexpr int FRONT_BACK_JOINT_SIGN=-1;
  const int frontBackJointSign;
  explicit DirectionController(int sign=FRONT_BACK_JOINT_SIGN):frontBackJointSign(sign){reset();}
  void reset(){directional_reset(&state);}
  bool step(const float observation[4],float action[2],float targets[2]){
    if(!directional_action(&state,observation,action,frontBackJointSign))return false;
    targets[0]=observation[2];targets[1]=observation[3];
    return directional_update_targets(action,targets);
  }
};
