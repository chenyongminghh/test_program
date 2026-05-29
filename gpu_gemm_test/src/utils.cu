#include "utils.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cuda_runtime.h>

// 矩阵初始化
template<typename T>
void initialize_matrix(T* h_matrix, int m, int n, bool random) {
    if (random) {
        for (int i = 0; i < m * n; i++) {
            h_matrix[i] = (T)(rand() % 10);
        }
    } else {
        memset(h_matrix, 0, m * n * sizeof(T));
    }
}

// 显式实例化
template void initialize_matrix<float>(float* h_matrix, int m, int n, bool random);
template void initialize_matrix<int>(int* h_matrix, int m, int n, bool random);

// 正确性验证
template<typename T>
bool verify_result(const T* result, const T* reference, 
                   int m, int n, T tolerance) {
    for (int i = 0; i < m * n; i++) {
        if (abs(result[i] - reference[i]) > tolerance) {
            return false;
        }
    }
    return true;
}

// 显式实例化
template bool verify_result<float>(const float* result, const float* reference, 
                                   int m, int n, float tolerance);

// 性能统计
void compute_statistics(float* times, int num_times, PerfStats& stats) {
    stats.min_time_ms = times[0];
    stats.max_time_ms = times[0];
    float sum = 0.0f;
    
    for (int i = 0; i < num_times; i++) {
        if (times[i] < stats.min_time_ms) 
            stats.min_time_ms = times[i];
        if (times[i] > stats.max_time_ms) 
            stats.max_time_ms = times[i];
        sum += times[i];
    }
    
    stats.mean_time_ms = sum / num_times;
    
    // 计算标准差
    float var_sum = 0.0f;
    for (int i = 0; i < num_times; i++) {
        float diff = times[i] - stats.mean_time_ms;
        var_sum += diff * diff;
    }
    stats.std_dev_ms = sqrt(var_sum / num_times);
}

// 打印矩阵
template<typename T>
void print_matrix(const T* matrix, int m, int n, int max_elements) {
    int print_m = m < max_elements ? m : max_elements;
    int print_n = n < max_elements ? n : max_elements;
    
    printf("Matrix (%d x %d):\n", m, n);
    for (int i = 0; i < print_m; i++) {
        for (int j = 0; j < print_n; j++) {
            printf("%8.4f ", (float)matrix[i * n + j]);
        }
        if (print_n < n) printf("...");
        printf("\n");
    }
    if (print_m < m) printf("...\n");
}

// 显式实例化
template void print_matrix<float>(const float* matrix, int m, int n, int max_elements);

// 计算内存大小
size_t calculate_memory_usage(int M, int N, int K, GemmDataType dtype) {
    size_t dtype_size = get_dtype_size(dtype);
    size_t size_A = M * K * dtype_size;
    size_t size_B = K * N * dtype_size;
    size_t size_C = M * N * dtype_size;
    return size_A + size_B + size_C;
}

// 获取 GPU 信息
void print_gpu_info() {
    int device_count;
    cudaGetDeviceCount(&device_count);
    
    if (device_count == 0) {
        printf("No CUDA GPU found!\n");
        return;
    }
    
    printf("========================================\n");
    printf("GPU Information\n");
    printf("========================================\n");
    
    for (int i = 0; i < device_count; i++) {
        cudaSetDevice(i);
        cudaDeviceProp props;
        cudaGetDeviceProperties(&props, i);
        
        printf("Device %d: %s\n", i, props.name);
        printf("  Compute Capability: %d.%d\n", props.major, props.minor);
        printf("  Global Memory: %zu MB\n", props.totalGlobalMem / (1024 * 1024));
        printf("  Shared Memory per Block: %zu KB\n", props.sharedMemPerBlock / 1024);
        printf("  Max Threads per Block: %d\n", props.maxThreadsPerBlock);
        printf("  Max Grid Dimensions: %d x %d x %d\n",
               props.maxGridSize[0], props.maxGridSize[1], props.maxGridSize[2]);
    }
    printf("========================================\n\n");
}

// 错误检查
void check_cuda_error(cudaError_t error, const char* file, int line) {
    if (error != cudaSuccess) {
        printf("CUDA error at %s:%d: %s\n", file, line, cudaGetErrorString(error));
        exit(1);
    }
}
