cmake_minimum_required(VERSION 3.20)
project(gpu_gemm_test CUDA CXX)

# 设置 CUDA 架构
set(CMAKE_CUDA_ARCHITECTURES 70 75 80 86 89 90a)

# 设置 C++ 标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)

# 寻找 CUDA
find_package(CUDA REQUIRED)

# 包含目录
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)
include_directories(${CUDA_INCLUDE_DIRS})

# 源文件
set(SOURCES
    src/main.cu
    src/gemm_kernels.cu
    src/utils.cu
    src/performance_counter.cu
    src/args_parser.cpp
)

# 创建可执行文件
add_executable(gemmPerf ${SOURCES})

# 链接库
target_link_libraries(gemmPerf 
    PRIVATE 
    ${CUDA_LIBRARIES}
    ${CUDA_CUBLAS_LIBRARIES}
)

# 编译选项
if(UNIX AND NOT APPLE)
    target_compile_options(gemmPerf PRIVATE
        $<$<COMPILE_LANGUAGE:CUDA>:
            -Xcompiler -Wall
            -Xcompiler -O3
            -lineinfo
        >
        $<$<COMPILE_LANGUAGE:CXX>:
            -Wall
            -O3
        >
    )
endif()

# 输出信息
message(STATUS "CUDA Architectures: ${CMAKE_CUDA_ARCHITECTURES}")
message(STATUS "CUDA Include: ${CUDA_INCLUDE_DIRS}")
message(STATUS "CUDA Libraries: ${CUDA_LIBRARIES}")
