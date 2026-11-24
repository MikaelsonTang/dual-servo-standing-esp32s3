#pragma once
#include "directional_policy.h"
// Compatibility entry for local integration checks; the new router shares
// exactly the exported per-axis target integration and limits.
static inline bool policy_update_targets(const float action[2],float target_rad[2]) {
    return directional_update_targets(action,target_rad);
}
