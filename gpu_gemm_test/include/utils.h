#ifndef UTILS_H
#define UTILS_H

#include "gemm_types.h"
#include <cuda_runtime.h>

// GPU 内存分配
template<typename T>
T* allocate_device_matrix(int m, int n) {
    T* d_matrix;
    cudaMalloc((void**)&d_matrix, m * n * sizeof(T));
    return d_matrix;
}

// 矩阵初始化
template<typename T>
void initialize_matrix(T* h_matrix, int m, int n, bool random = false);

// 正确性验证
template<typename T>
bool verify_result(const T* result, const T* reference, 
                   int m, int n, T tolerance);

// 性能统计
void compute_statistics(float* times, int num_times, PerfStats& stats);

// 打印矩阵
template<typename T>
void print_matrix(const T* matrix, int m, int n, int max_elements = 16);

// 计算内存大小
size_t calculate_memory_usage(int M, int N, int K, GemmDataType dtype);

// 获取 GPU 信息
void print_gpu_info();

// 错误检查
void check_cuda_error(cudaError_t error, const char* file, int line);

#define CUDA_CHECK(err) check_cuda_error(err, __FILE__, __LINE__)

#endif // UTILS_H
