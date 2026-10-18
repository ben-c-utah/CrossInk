# Compile-time assertions run with either the native suite or the target compiler.
add_library(ble_arrow_filter_test OBJECT compile_test.cpp)
target_include_directories(ble_arrow_filter_test PRIVATE ${REPO_ROOT}/lib/hal)
