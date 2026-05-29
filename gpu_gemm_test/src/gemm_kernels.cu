#include "gemm_kernels.cuh"
#include <cuda_runtime.h>

// 核函数 1: 朴素 GEMM（行主序访问）
__global__ void gemm_naive(
    int M, int N, int K,
    const float* A, int lda,
    const float* B, int ldb,
    float* C, int ldc,
    float alpha, float beta) {
    
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    
    if (row < M && col < N) {
        float sum = 0.0f;
        for (int k = 0; k < K; k++) {
            sum += A[row * lda + k] * B[k * ldb + col];
        }
        C[row * ldc + col] = alpha * sum + beta * C[row * ldc + col];
    }
}

// 核函数 2: 使用共享内存的分块 GEMM
__global__ void gemm_shared_memory(
    int M, int N, int K,
    const float* A, int lda,
    const float* B, int ldb,
    float* C, int ldc,
    float alpha, float beta) {
    
    #define TILE_SIZE 32
    __shared__ float As[TILE_SIZE][TILE_SIZE];
    __shared__ float Bs[TILE_SIZE][TILE_SIZE];
    
    int bx = blockIdx.x, by = blockIdx.y;
    int tx = threadIdx.x, ty = threadIdx.y;
    
    int row = by * TILE_SIZE + ty;
    int col = bx * TILE_SIZE + tx;
    
    float sum = 0.0f;
    
    // 迭代每个分块
    for (int kb = 0; kb < (K + TILE_SIZE - 1) / TILE_SIZE; kb++) {
        // 加载数据到共享内存
        int k_idx = kb * TILE_SIZE + tx;
        if (row < M && k_idx < K)
            As[ty][tx] = A[row * lda + k_idx];
        else
            As[ty][tx] = 0.0f;
            
        k_idx = kb * TILE_SIZE + ty;
        if (k_idx < K && col < N)
            Bs[ty][tx] = B[k_idx * ldb + col];
        else
            Bs[ty][tx] = 0.0f;
        
        __syncthreads();
        
        // 计算局部乘积
        for (int k = 0; k < TILE_SIZE; k++) {
            sum += As[ty][k] * Bs[k][tx];
        }
        __syncthreads();
    }
    
    // 写回结果
    if (row < M && col < N) {
        C[row * ldc + col] = alpha * sum + beta * C[row * ldc + col];
    }
    #undef TILE_SIZE
}

// 朴素 GEMM 包装函数
void GemmNaiveKernel::launch(const GemmConfig& config,
                             const float* d_A,
                             const float* d_B,
                             float* d_C) {
    dim3 blockDim(16, 16);  // 256 线程/块
    dim3 gridDim((config.N + blockDim.x - 1) / blockDim.x,
                 (config.M + blockDim.y - 1) / blockDim.y);
    
    gemm_naive<<<gridDim, blockDim>>>(
        config.M, config.N, config.K,
        d_A, config.lda, d_B, config.ldb,
        d_C, config.ldc, config.alpha, config.beta);
}

// 共享内存 GEMM ��装函数
void GemmSharedMemoryKernel::launch(const GemmConfig& config,
                                    const float* d_A,
                                    const float* d_B,
                                    float* d_C) {
    dim3 blockDim(32, 32);
    dim3 gridDim((config.N + 31) / 32,
                 (config.M + 31) / 32);
    
    gemm_shared_memory<<<gridDim, blockDim>>>(
        config.M, config.N, config.K,
        d_A, config.lda, d_B, config.ldb,
        d_C, config.ldc, config.alpha, config.beta);
}
