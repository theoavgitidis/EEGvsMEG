cmake_minimum_required(VERSION 3.16)
project(unicorn_terminal LANGUAGES CXX)
if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The supplied Unicorn.dll requires 64-bit Windows.")
endif()
add_executable(unicorn_terminal main.cpp)
target_compile_features(unicorn_terminal PRIVATE cxx_std_17)
target_include_directories(unicorn_terminal PRIVATE ../lib)
target_link_libraries(unicorn_terminal PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../lib/Unicorn.lib")
add_custom_command(TARGET unicorn_terminal POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
  "${CMAKE_CURRENT_SOURCE_DIR}/../lib/Unicorn.dll" "$<TARGET_FILE_DIR:unicorn_terminal>")
