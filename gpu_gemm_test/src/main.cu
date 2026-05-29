#include <iostream>
#include <cstdio>
#include <cuda_runtime.h>
#include <cublas_v2.h>
#include "gemm_types.h"
#include "gemm_kernels.cuh"
#include "utils.h"
#include "args_parser.cpp"

int main(int argc, char** argv) {
    GemmConfig config;
    ArgumentParser parser;
    
    if (!parser.parse(argc, argv, config)) {
        return 1;
    }
    
    // Print GPU information
    print_gpu_info();
    
    // GPU check and setup
    int device_count;
    cudaGetDeviceCount(&device_count);
    if (device_count == 0) {
        std::cerr << "No CUDA GPU found!" << std::endl;
        return 1;
    }
    
    cudaSetDevice(0);
    cudaDeviceProp props;
    cudaGetDeviceProperties(&props, 0);
    
    printf("========================================\n");
    printf("GPU GEMM Performance Test\n");
    printf("========================================\n");
    printf("GPU: %s\n", props.name);
    printf("CUDA Capability: %d.%d\n", props.major, props.minor);
    printf("========================================\n\n");
    
    // Allocate memory
    size_t size_A = config.M * config.K * sizeof(float);
    size_t size_B = config.K * config.N * sizeof(float);
    size_t size_C = config.M * config.N * sizeof(float);
    
    if (config.verbose) {
        printf("Memory Allocation:\n");
        printf("  Matrix A: %.2f MB\n", size_A / 1024.0 / 1024.0);
        printf("  Matrix B: %.2f MB\n", size_B / 1024.0 / 1024.0);
        printf("  Matrix C: %.2f MB\n", size_C / 1024.0 / 1024.0);
        printf("  Total: %.2f MB\n\n", (size_A + size_B + size_C) / 1024.0 / 1024.0);
    }
    
    float *d_A, *d_B, *d_C;
    CUDA_CHECK(cudaMalloc(&d_A, size_A));
    CUDA_CHECK(cudaMalloc(&d_B, size_B));
    CUDA_CHECK(cudaMalloc(&d_C, size_C));
    
    // Initialize data
    float *h_A = new float[config.M * config.K];
    float *h_B = new float[config.K * config.N];
    float *h_C = new float[config.M * config.N];
    
    initialize_matrix<float>(h_A, config.M, config.K, true);
    initialize_matrix<float>(h_B, config.K, config.N, true);
    initialize_matrix<float>(h_C, config.M, config.N, false);
    
    CUDA_CHECK(cudaMemcpy(d_A, h_A, size_A, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_B, h_B, size_B, cudaMemcpyHostToDevice));
    CUDA_CHECK(cudaMemcpy(d_C, h_C, size_C, cudaMemcpyHostToDevice));
    
    // Warmup
    if (config.warmup) {
        GemmNaiveKernel kernel;
        for (int i = 0; i < 3; i++) {
            kernel.launch(config, d_A, d_B, d_C);
        }
        CUDA_CHECK(cudaDeviceSynchronize());
    }
    
    // Performance test
    printf("Test Configuration:\n");
    printf("  Matrix Size (M×N×K): %d×%d×%d\n", config.M, config.N, config.K);
    printf("  Data Type: %s\n", get_dtype_name(config.data_type));
    printf("  Iterations: %d\n", config.num_iterations);
    printf("  Warmup: %s\n\n", config.warmup ? "Yes" : "No");
    
    cudaEvent_t start, stop;
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));
    
    float *times = new float[config.num_iterations];
    GemmNaiveKernel kernel;
    
    for (int i = 0; i < config.num_iterations; i++) {
        CUDA_CHECK(cudaEventRecord(start));
        kernel.launch(config, d_A, d_B, d_C);
        CUDA_CHECK(cudaEventRecord(stop));
        CUDA_CHECK(cudaEventSynchronize(stop));
        
        float elapsed_ms;
        CUDA_CHECK(cudaEventElapsedTime(&elapsed_ms, start, stop));
        times[i] = elapsed_ms;
    }
    
    // Calculate statistics
    PerfStats stats;
    compute_statistics(times, config.num_iterations, stats);
    
    // Calculate performance metrics
    double flops = 2.0 * config.M * config.N * config.K;
    stats.peak_tflops = flops / (stats.min_time_ms * 1e9);
    stats.avg_tflops = flops / (stats.mean_time_ms * 1e9);
    
    size_t memory_bytes = (config.M * config.K + config.K * config.N + 
                           config.M * config.N) * sizeof(float);
    stats.bandwidth_gbs = memory_bytes / (stats.mean_time_ms * 1e6);
    
    // Theoretical peak for FP32 on typical GPUs (depends on GPU)
    float theoretical_peak = 100.0f;  // This should be adjusted based on GPU
    stats.compute_efficiency = (stats.avg_tflops / theoretical_peak) * 100.0f;
    
    // Print report
    printf("Performance Results:\n");
    printf("  Minimum Time: %.4f ms\n", stats.min_time_ms);
    printf("  Maximum Time: %.4f ms\n", stats.max_time_ms);
    printf("  Mean Time: %.4f ms\n", stats.mean_time_ms);
    printf("  Std Dev: %.4f ms\n\n", stats.std_dev_ms);
    
    printf("Performance Metrics:\n");
    printf("  Peak TFLOP/s: %.2f\n", stats.peak_tflops);
    printf("  Average TFLOP/s: %.2f\n", stats.avg_tflops);
    printf("  Memory Bandwidth: %.2f GB/s\n", stats.bandwidth_gbs);
    printf("========================================\n\n");
    
    // Cleanup
    CUDA_CHECK(cudaFree(d_A));
    CUDA_CHECK(cudaFree(d_B));
    CUDA_CHECK(cudaFree(d_C));
    delete[] h_A;
    delete[] h_B;
    delete[] h_C;
    delete[] times;
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    
    return 0;
}
