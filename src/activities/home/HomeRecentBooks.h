#pragma once

#include <Memory.h>

#include <new>
#include "components/RecentBookView.h"
#include <vector>

#include "RecentBooksStore.h"

// Home owns the active member and its mode flag. Keeping the flag in Home's
// existing padding preserves the controller's original allocation footprint.
// This is fixed-capacity record storage, not an allocator for string contents.
union HomeRecentBooks {
  struct External {
    RecentBook* data;
    size_t size;
    size_t capacity;
  };
  std::vector<RecentBook> internal;
  External external;

  HomeRecentBooks() : internal() {}
  ~HomeRecentBooks() {}  // Home calls destroy(mode) before this union dies.
  HomeRecentBooks(const HomeRecentBooks&) = delete;
  HomeRecentBooks& operator=(const HomeRecentBooks&) = delete;

  static HeapByteBuffer allocateExternal(size_t capacity) {
#if defined(ARDUINO_ARCH_ESP32) && !defined(SIMULATOR) && CROSSINK_BLE_LAB && FREEINK_FB_PSRAM
    if (capacity == 0 || capacity > SIZE_MAX / sizeof(RecentBook)) return {};
    return HeapByteBuffer(static_cast<uint8_t*>(heap_caps_aligned_alloc(
        alignof(RecentBook), capacity * sizeof(RecentBook), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)));
#else
    (void)capacity;
    return {};
#endif
  }

  // Called once, on the empty replacement Home, before it is published.
  void adoptExternal(HeapByteBuffer storage, size_t capacity) {
    internal.~vector();
    ::new (&external) External{reinterpret_cast<RecentBook*>(storage.release()), 0, capacity};
  }

  MutableRecentBookView view(bool isExternal) {
    return isExternal ? MutableRecentBookView(external.data, external.size)
                      : MutableRecentBookView(internal.data(), internal.size());
  }
  RecentBookView view(bool isExternal) const {
    return isExternal ? RecentBookView(external.data, external.size)
                      : RecentBookView(internal);
  }
  size_t capacity(bool isExternal) const { return isExternal ? external.capacity : internal.capacity(); }

  void clear(bool isExternal) {
    if (isExternal) {
      while (external.size) external.data[--external.size].~RecentBook();
    } else {
      internal.clear();
    }
  }
  bool reserve(size_t count, bool isExternal) {
    if (isExternal) return count <= external.capacity;
    internal.reserve(count);
    return true;
  }
  bool pushCopy(const RecentBook& book, bool isExternal) {
    if (isExternal) {
      if (external.size == external.capacity) return false;
      // Commit the element count only after normal C++ construction completes.
      ::new (external.data + external.size) RecentBook(book);
      ++external.size;
    } else {
      internal.push_back(book);
    }
    return true;
  }
  void destroy(bool isExternal) {
    if (isExternal) {
      clear(true);
      HeapByteBufferDeleter{}(reinterpret_cast<uint8_t*>(external.data));
      external.~External();
    } else {
      internal.~vector();
    }
  }
};

static_assert(sizeof(HomeRecentBooks) == sizeof(std::vector<RecentBook>), "Preserve the ordinary vector footprint");
