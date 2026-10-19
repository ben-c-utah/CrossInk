#pragma once
#include <BleLabPolicy.h>

namespace BleLabInput {
// -1 is header (expand/collapse), -2 is no activation. Input is already edge-
// classified by MappedInputManager. Focus never invokes an action.
struct Pending {
  int action = -2;
  bool offer(int next) { if (action != -2 || next < -1 || next > 5) return false; action = next; return true; }
  int take() { const int next = action; action = -2; return next; }
};
struct Result { int action; int focus; bool handled; };
constexpr bool valid(int control, bool expanded) { return control >= 0 && control < (expanded ? 7 : 1); }
constexpr Result route(int tap, int down, bool confirm, bool back, bool expanded, int focus) {
  return valid(tap, expanded) ? Result{tap - 1, tap, true} :
         valid(down, expanded) ? Result{-2, down, true} :
         expanded && back ? Result{-1, focus, true} :
         expanded && confirm ? Result{focus - 1, focus, true} : Result{-2, focus, false};
}
constexpr BleLabPolicy::Command command(int action) {
  using C = BleLabPolicy::Command;
  return action == 0 ? C::Toggle : action == 1 ? C::Connect : action == 2 ? C::Wifi :
         action == 3 ? C::Logs : action == 4 ? C::Update : action == 5 ? C::Restart : C::None;
}
} // namespace BleLabInput
