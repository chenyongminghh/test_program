#include "gemm_types.h"
#include <cuda_runtime.h>
#include <cstdio>
#include <cmath>

class PerformanceCounter {
public:
    PerformanceCounter() {
        cudaEventCreate(&start);
        cudaEventCreate(&stop);
    }
    
    ~PerformanceCounter() {
        cudaEventDestroy(start);
        cudaEventDestroy(stop);
    }
    
    void begin() {
        cudaEventRecord(start);
    }
    
    float end() {
        cudaEventRecord(stop);
        cudaEventSynchronize(stop);
        
        float elapsed_ms;
        cudaEventElapsedTime(&elapsed_ms, start, stop);
        return elapsed_ms;
    }
    
private:
    cudaEvent_t start, stop;
};

void print_performance_report(const GemmConfig& config, const PerfStats& stats) {
    printf("\n========================================\n");
    printf("Performance Report\n");
    printf("========================================\n\n");
    
    printf("Test Configuration:\n");
    printf("  Matrix Size (M×N×K): %d×%d×%d\n", config.M, config.N, config.K);
    printf("  Data Type: %s\n", get_dtype_name(config.data_type));
    printf("  Iterations: %d\n", config.num_iterations);
    printf("  Alpha: %.2f, Beta: %.2f\n\n", config.alpha, config.beta);
    
    printf("Timing Results (ms):\n");
    printf("  Minimum Time: %.4f\n", stats.min_time_ms);
    printf("  Maximum Time: %.4f\n", stats.max_time_ms);
    printf("  Mean Time: %.4f\n", stats.mean_time_ms);
    printf("  Std Dev: %.4f\n\n", stats.std_dev_ms);
    
    printf("Performance Metrics:\n");
    printf("  Peak TFLOP/s: %.2f\n", stats.peak_tflops);
    printf("  Average TFLOP/s: %.2f\n", stats.avg_tflops);
    printf("  Bandwidth (GB/s): %.2f\n", stats.bandwidth_gbs);
    printf("  Compute Efficiency: %.2f%%\n\n", stats.compute_efficiency);
    
    if (stats.is_correct) {
        printf("Verification: PASSED\n");
        printf("  Absolute Error: %.2e\n", stats.absolute_error);
        printf("  Relative Error: %.2e\n", stats.relative_error);
    } else {
        printf("Verification: FAILED\n");
    }
    
    printf("========================================\n\n");
}
