#pragma once

// Opt in only for supervised X4 Pro heap experiments; no state in normal builds.
#ifndef CROSSINK_HEAP_DIAGNOSTICS
#define CROSSINK_HEAP_DIAGNOSTICS 0
#endif

#if CROSSINK_HEAP_DIAGNOSTICS
#if !defined(FREEINK_DEVICE_X4PRO) || defined(SIMULATOR)
#error "Heap diagnostics require physical X4 Pro hardware"
#endif
#include <Logging.h>
#include <esp_heap_caps.h>
#include <esp_memory_utils.h>

namespace HeapDiagnostics {
constexpr uint32_t Internal = MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT;
inline void snapshot(const char* stage, const char* owner = "", bool regions = false) {
  multi_heap_info_t info{};
  heap_caps_get_info(&info, Internal);
  LOG_INF("HDBG", "%s owner=%s free=%u largest=%u allocated=%u blocks=%u/%u psram=%u", stage, owner,
          static_cast<unsigned>(info.total_free_bytes), static_cast<unsigned>(info.largest_free_block),
          static_cast<unsigned>(info.total_allocated_bytes), static_cast<unsigned>(info.allocated_blocks),
          static_cast<unsigned>(info.free_blocks), static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));
  if (regions) heap_caps_print_heap_info(Internal);
}
// Only exact, currently owned allocation pointers may be passed here.
inline void allocation(const char* owner, const void* ptr, size_t capacity) {
  if (!ptr) return;
  LOG_INF("HDBG", "allocation %s ptr=%p capacity=%u actual=%u external=%u", owner, ptr,
          static_cast<unsigned>(capacity), static_cast<unsigned>(heap_caps_get_allocated_size(const_cast<void*>(ptr))),
          esp_ptr_external_ram(ptr));
}
inline void blocks(const char* stage) {
  LOG_INF("HDBG", "BEGIN internal block dump %s (addresses/sizes only; no contents)", stage);
  heap_caps_dump(Internal);
  LOG_INF("HDBG", "END internal block dump %s", stage);
}
}  // namespace HeapDiagnostics
#endif
