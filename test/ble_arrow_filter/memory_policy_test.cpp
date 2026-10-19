#include "BleMemoryPolicy.h"

using namespace BleMemoryPolicy;

constexpr Snapshot Hardware{132792, 81908, 8272852, 0, true};
static_assert(!evaluate(Hardware, Start).any());
static_assert(!evaluate({Start.freeInternal, Start.largestInternal, 1, 0, true}, Start).any());
static_assert(evaluate({Start.freeInternal - 1, Start.largestInternal, 1, 0, true}, Start).freeInternal);
static_assert(evaluate({Start.freeInternal, Start.largestInternal - 1, 1, 0, true}, Start).largestInternal);
static_assert(evaluate({132792, 81908, 8272852, 1, true}, Start).wifi);
static_assert(evaluate({132792, 81908, 8272852, 0, false}, Start).psram);
static_assert(evaluate({132792, 81908, 0, 0, true}, Start).psram);

constexpr auto AllFail = evaluate({0, 0, 0, 1, false}, Start);
static_assert(AllFail.wifi && AllFail.freeInternal && AllFail.largestInternal && AllFail.psram);
static_assert(PostStart.freeInternal == 65536 && PostStart.largestInternal == 32768);
static_assert(Running.freeInternal == 49152 && Running.largestInternal == 24576);
static_assert(!evaluate({65536, 32768, 1, 0, true}, PostStart).any());
static_assert(evaluate({65535, 32768, 1, 0, true}, PostStart).any());
static_assert(evaluate({65536, 32767, 1, 0, true}, PostStart).any());
static_assert(!evaluate({49152, 24576, 1, 0, true}, Running).any());
static_assert(evaluate({49151, 24576, 1, 0, true}, Running).any());
static_assert(evaluate({49152, 24575, 1, 0, true}, Running).any());
