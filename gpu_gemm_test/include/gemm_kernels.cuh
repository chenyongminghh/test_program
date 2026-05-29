#ifndef GEMM_KERNELS_CUH
#define GEMM_KERNELS_CUH

#include "gemm_types.h"
#include <cuda_runtime.h>

// 朴素 GEMM 核函数
__global__ void gemm_naive(
    int M, int N, int K,
    const float* A, int lda,
    const float* B, int ldb,
    float* C, int ldc,
    float alpha, float beta);

// 使用共享内存的优化 GEMM
__global__ void gemm_shared_memory(
    int M, int N, int K,
    const float* A, int lda,
    const float* B, int ldb,
    float* C, int ldc,
    float alpha, float beta);

// 核函数包装类
class GemmKernel {
public:
    virtual void launch(const GemmConfig& config,
                       const float* d_A,
                       const float* d_B,
                       float* d_C) = 0;
    virtual ~GemmKernel() {}
};

class GemmNaiveKernel : public GemmKernel {
public:
    void launch(const GemmConfig& config,
               const float* d_A,
               const float* d_B,
               float* d_C) override;
};

class GemmSharedMemoryKernel : public GemmKernel {
public:
    void launch(const GemmConfig& config,
               const float* d_A,
               const float* d_B,
               float* d_C) override;
};

#endif // GEMM_KERNELS_CUH
