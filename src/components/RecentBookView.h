#pragma once

#include <cstddef>
#include <type_traits>
#include <vector>

struct RecentBook;

// Non-owning, allocation-free view. The Home/store owner outlives its readers.
// Mutable views are used only by Home's existing selection/mutation code.
template <typename T>
class BasicRecentBookView {
 public:
  BasicRecentBookView() = default;
  BasicRecentBookView(T* data, size_t size) : data_(data), size_(size) {}
  template <typename U, typename = std::enable_if_t<std::is_convertible<U*, T*>::value>>
  BasicRecentBookView(BasicRecentBookView<U> other) : data_(other.data()), size_(other.size()) {}
  template <typename U, typename = std::enable_if_t<std::is_convertible<const U*, T*>::value>>
  BasicRecentBookView(const std::vector<U>& books) : data_(books.data()), size_(books.size()) {}
  T* data() const { return data_; }
  size_t size() const { return size_; }
  bool empty() const { return size_ == 0; }
  T* begin() const { return data_; }
  T* end() const { return size_ ? data_ + size_ : data_; }
  T& operator[](size_t index) const { return data_[index]; }
  T& front() const { return data_[0]; }

 private:
  T* data_ = nullptr;
  size_t size_ = 0;
};

using RecentBookView = BasicRecentBookView<const RecentBook>;
using MutableRecentBookView = BasicRecentBookView<RecentBook>;
