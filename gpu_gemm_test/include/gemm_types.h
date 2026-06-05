#ifndef GEMM_TYPES_H
#define GEMM_TYPES_H

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <cstdint>

// 数据类型枚举
enum GemmDataType {
    GEMM_FP32 = 0,
    GEMM_FP16 = 1,
    GEMM_BF16 = 2,
    GEMM_TF32 = 3,
    GEMM_INT8 = 4,
    GEMM_INT32 = 5
};

// 矩阵转置类型
enum TransposeType {
    TRANSPOSE_NN = 0,  // 都不转置
    TRANSPOSE_NT = 1,  // B 转置
    TRANSPOSE_TN = 2,  // A 转置
    TRANSPOSE_TT = 3   // 都转置
};

// GEMM 配置结构
struct GemmConfig {
    int M, N, K;                    // 矩阵维度
    GemmDataType data_type;         // 数据类型
    TransposeType transpose_type;   // 转置类型
    int lda, ldb, ldc;              // 矩阵步长
    float alpha, beta;              // 标量系数
    int num_iterations;             // 迭代次数
    bool warmup;                    // 是否进行 Warmup
    bool verify;                    // 是否进行正确性验证
    bool compare_cublas;            // 是否与 cuBLAS 对比
    bool print_result;              // 是否打印结果
    bool verbose;                   // 详细输出
    char output_file[256];          // 输出文件路径
};

// 性能统计结构
struct PerfStats {
    float min_time_ms;
    float max_time_ms;
    float mean_time_ms;
    float std_dev_ms;
    float peak_tflops;
    float avg_tflops;
    float bandwidth_gbs;
    float compute_efficiency;
    double absolute_error;
    double relative_error;
    bool is_correct;
};

// 获取数据类型名称
inline const char* get_dtype_name(GemmDataType dtype) {
    switch (dtype) {
        case GEMM_FP32: return "FP32";
        case GEMM_FP16: return "FP16";
        case GEMM_BF16: return "BF16";
        case GEMM_TF32: return "TF32";
        case GEMM_INT8: return "INT8";
        case GEMM_INT32: return "INT32";
        default: return "UNKNOWN";
    }
}

// 获取数据类型大小
inline size_t get_dtype_size(GemmDataType dtype) {
    switch (dtype) {
        case GEMM_FP32: return sizeof(float);
        case GEMM_FP16: return sizeof(__half);
        case GEMM_BF16: return sizeof(__nv_bfloat16);
        case GEMM_TF32: return sizeof(float);
        case GEMM_INT8: return sizeof(int8_t);
        case GEMM_INT32: return sizeof(int32_t);
        default: return sizeof(float);
    }
}

#endif // GEMM_TYPES_H
