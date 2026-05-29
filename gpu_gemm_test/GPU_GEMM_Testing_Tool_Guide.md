# 通用 GPU GEMM 测试工具指南

## 目录
1. [概述](#概述)
2. [工具特性](#工具特性)
3. [环境安装](#环境安装)
4. [快速开始](#快速开始)
5. [详细使用说明](#详细使用说明)
6. [GEMM 测试原理](#gemm-测试原理)
7. [测试方法详解](#测试方法详解)
8. [开发步骤](#开发步骤)
9. [常见问题](#常见问题)
10. [参考资源](#参考资源)

---

## 概述

本工具是一个通用的 GPU GEMM（General Matrix Multiply，广义矩阵乘法）性能测试工具，支持在 Linux 环境下对不同 GPU 的矩阵乘法运算进行全面的性能评估。该工具支持多种数据类型、矩阵大小配置和优化算法对比。

### 应用场景
- 评估 GPU 矩阵乘法性能
- 对比不同 GEMM 实现的性能差异
- 验证 CUDA 核函数的正确性
- 分析内存带宽和计算吞吐量
- 性能瓶颈诊断和优化

---

## 工具特性

| 特性 | 说明 |
|------|------|
| **多数据类型支持** | FP32、FP16、BF16、TF32、INT8、INT32 等 |
| **灵活的矩阵大小** | 支持任意大小的矩阵配置（M×N×K） |
| **多种测试模式** | 性能测试、正确性验证、内存分析 |
| **详细性能指标** | TFLOP/s、GB/s、执行时间、内存占用 |
| **对比分析** | 支持与 cuBLAS 进行性能对比 |
| **跨平台支持** | 支持各类 NVIDIA GPU（Hopper、Ampere、Turing 等） |
| **可视化输出** | 生成性能对比图表 |

---

## 环境安装

### 前置要求

```bash
# 系统要求
- Ubuntu 18.04 LTS 或更高版本
- NVIDIA GPU（计算能力 >= 7.0）
- NVIDIA Driver（版本 >= 450）
- CUDA Toolkit（版本 >= 11.0）
```

### 1. 安装 NVIDIA 驱动和 CUDA

```bash
# 检查当前 GPU
lspci | grep -i nvidia

# 安装 NVIDIA 驱动
sudo apt update
sudo apt install nvidia-driver-550  # 根据 GPU 型号选择合适版本

# 安装 CUDA Toolkit（以 CUDA 12.0 为例）
wget https://developer.download.nvidia.com/compute/cuda/12.0.0/local_installers/cuda_12.0.0_525.60.13_linux.run
sudo sh cuda_12.0.0_525.60.13_linux.run

# 配置环境变量
echo 'export PATH=/usr/local/cuda-12.0/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.0/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# 验证安装
nvcc --version
nvidia-smi
```

### 2. 安装依赖工具

```bash
# 基础工具
sudo apt install -y build-essential cmake git wget

# Python 环境（用于数据分析和可视化）
sudo apt install -y python3 python3-pip python3-dev
pip3 install numpy matplotlib pandas scipy

# 可选：性能分析工具
sudo apt install -y nsight-systems  # NVIDIA Nsight Systems
```

### 3. 克隆和设置项目

```bash
# 克隆仓库
git clone https://github.com/chenyongminghh/test_program.git
cd test_program/gpu_gemm_test

# 创建构建目录
mkdir -p build
cd build

# 配置 CMake
cmake ..
cmake --build . -j$(nproc)
```

---

## 快速开始

### 基础用法

```bash
# 进入构建目录
cd build

# 运行基础 GEMM 测试（FP32，矩阵大小 1024×1024×1024）
./gemmPerf -s 1024

# 运行 BF16 测试
./gemmPerf -s 1024 -g bf16

# 运行自定义大小的矩阵测试
./gemmPerf -m 2048 -n 2048 -k 2048 -g fp32

# 与 cuBLAS 进行性能对比
./gemmPerf -s 1024 -c
```

### 输出示例

```
========================================
GPU GEMM 性能测试报告
========================================
GPU: NVIDIA H100 PCIe
CUDA Capability: 9.0

测试配置:
  矩阵大小 (M×N×K): 4096×4096×4096
  数据类型: BF16
  迭代次数: 100

性能结果:
  平均执行时间: 12.34 ms
  峰值性能: 512.45 TFLOP/s
  内存带宽: 892.34 GB/s
  相对于 cuBLAS 的性能: 89.2%

========================================
```

---

## 详细使用说明

### 命令行参数详解

```bash
./gemmPerf [选项]

通用参数:
  -h, --help                显示帮助信息
  -v, --version            显示程序版本
  -V, --verbose            详细输出模式

矩阵大小相关:
  -s, --size <size>        设置矩阵大小（方形矩阵 size×size×size）
  -m, --m-dim <value>      矩阵 M 维度（行数）
  -n, --n-dim <value>      矩阵 N 维度（列数）
  -k, --k-dim <value>      矩阵 K 维度（内积维度）

数据类型相关:
  -g, --gemm-type <type>   指定 GEMM 数据类型
                           可选值: fp32, fp16, bf16, tf32, int8, int32
                           默认: fp32

矩阵存储相关:
  -t, --transpose <type>   矩阵转置类型（0=NN, 1=NT, 2=TN, 3=TT）
                           0: NN (不转置)
                           1: NT (转置 B)
                           2: TN (转置 A)
                           3: TT (都转置)
  -a, --lda <value>        矩阵 A 的行跨度
  -b, --ldb <value>        矩阵 B 的行跨度
  -c, --ldc <value>        矩阵 C 的行跨度

测试控制:
  -i, --iterations <num>   迭代次数（默认: 100）
  -r, --rand-init          随机初始化矩阵数据
  -w, --warmup             执行 Warmup 避免缓存影响

数据验��:
  -C, --compare-cpu        与 CPU 结果进行对比验证
  -c, --compare-cublas     与 cuBLAS 进行性能对比
  -vg, --compare-golden    与黄金数据进行对比
  
内存和调试:
  -z, --calculate-memory   计算矩阵占用内存
  -p, --print-result       打印矩阵结果数据
  -o, --output <path>      输出结果到文件
  -d, --debug              调试模式
```

### 常用命令示例

#### 1. 基础性能测试

```bash
# 测试 FP32 浮点数性能
./gemmPerf -s 4096 -g fp32 -i 100

# 测试 BF16 性能
./gemmPerf -s 4096 -g bf16 -i 100

# 测试 INT8 性能
./gemmPerf -s 4096 -g int8 -i 100
```

#### 2. 自定义矩阵大小

```bash
# 非方形矩阵：M=1024, N=2048, K=512
./gemmPerf -m 1024 -n 2048 -k 512

# 超大矩阵测试
./gemmPerf -m 8192 -n 8192 -k 8192 -i 10
```

#### 3. 内存布局优化测试

```bash
# 测试不同的转置配置
./gemmPerf -s 4096 -t 0    # NN: A 和 B 都不转置
./gemmPerf -s 4096 -t 1    # NT: A 不转置，B 转置
./gemmPerf -s 4096 -t 2    # TN: A 转置，B 不转置
./gemmPerf -s 4096 -t 3    # TT: A 和 B 都转置
```

#### 4. 正确性验证

```bash
# 与 cuBLAS 进行性能和正确性对比
./gemmPerf -s 2048 -g fp32 -C

# 与 CPU 结果进行验证（小矩阵）
./gemmPerf -m 512 -n 512 -k 512 -C
```

#### 5. 完整的性能分析

```bash
# 详细的性能分析（包含 Warmup、多迭代、详细输出）
./gemmPerf -s 4096 -g bf16 -i 100 -w -V -o result.txt

# 详细模式 + CPU 验证 + 内存计算
./gemmPerf -s 2048 -C -z -p -o result.txt
```

---

## GEMM 测试原理

### 1. 矩阵乘法基础

GEMM（General Matrix Multiplication）计算公式：

```
C = α * A * B + β * C
```

其中：
- **A**: M×K 矩阵
- **B**: K×N 矩阵
- **C**: M×N 矩阵（结果）
- **α, β**: 标量系数（通常为 1 和 0）

矩阵乘法的计算复杂度：
- **浮点运算数（FLOP）**: 2 * M * N * K
- **内存访问数（Bytes）**: (M*K + K*N + M*N) * 数据类型大小

### 2. 性能指标

#### 2.1 TFLOP/s（计算吞吐量）

```
TFLOP/s = (2 * M * N * K) / (执行时间 * 1e12)
```

表示 GPU 每秒执行的浮点运算数（万亿次）。

**计算密度分析**:
```
计算密度 = 总 FLOP / 内存访问字节数
         = (2 * M * N * K) / ((M*K + K*N + M*N) * sizeof(数据类型))
```

#### 2.2 GB/s（内存带宽）

```
带宽利用率 = (内存访问字节数) / (执行时间 * 1e9)
```

表示 GPU 内存每秒传输的数据量（十亿字节）。

#### 2.3 计算效率

```
效率 = (实际 TFLOP/s) / (GPU 峰值理论 TFLOP/s) * 100%
```

### 3. GPU 硬件特性

| GPU 架构 | 计算能力 | 峰值 FP32 | 峰值 TF32 | 内存带宽 | 用途 |
|---------|---------|---------|----------|---------|------|
| Hopper (H100) | 9.0 | 67 | 532 | 960 GB/s | AI 训练/推理 |
| Ada (RTX 6000) | 8.9 | 40 | 320 | 960 GB/s | 专业计算 |
| Ampere (A100) | 8.0 | 20 | 312 | 1555 GB/s | AI 计算 |
| Ampere (RTX 3090) | 8.6 | 40 | 319 | 936 GB/s | 消费级计算 |
| Turing (RTX 2080) | 7.5 | 14 | - | 480 GB/s | 消费级入门 |

### 4. 瓶颈分析

#### 4.1 计算瓶颈（Compute Bound）

当 GPU 计算单元满载运行时，无法继续提升计算性能。

**判断条件**：
```
(理论峰值带宽 * 计算密度) <= 理论峰值 FLOP/s
```

**解决方案**：
- 优化算法（如 Tensor Core 利用）
- 增大矩阵大小（提高计算密度）

#### 4.2 内存瓶颈（Memory Bound）

GPU 内存访问速度成为性能瓶颈。

**判断条件**：
```
实际带宽利用率 < 理论峰值带宽 * 50%
```

**解决方案**：
- 增加数据重用率（使用 Shared Memory）
- 优化内存访问模式（合并访问）
- 使用低精度数据类型（减少带宽压力）

---

## 测试方法详解

### 1. 基准测试（Baseline Testing）

用于建立性能基准线。

```bash
# 单精度浮点数基准测试
./gemmPerf -s 4096 -g fp32 -i 100 -w

# 输出分析
# - 平均执行时间
# - 峰值性能（最高 TFLOP/s）
# - 最低性能（最低 TFLOP/s）
# - 标准差
```

**分析要点**：
- 运行结果的稳定性（标准差）
- 是否存在缓存效应（第一次运行比后续慢）
- Warmup 对性能的影响

### 2. 可扩展性测试（Scalability Testing）

测试不同矩阵大小下的性能表现。

```bash
# 脚本：scalability_test.sh
#!/bin/bash

SIZES=(512 1024 2048 4096 8192)
OUTPUT="scalability_results.csv"

echo "MatrixSize,TFLOP/s,BandwidthGB/s,EfficiencyPercent" > $OUTPUT

for size in "${SIZES[@]}"; do
    result=$(./gemmPerf -s $size -i 50)
    # 解析结果并追加到 CSV
    echo "$size,$tflops,$bandwidth,$efficiency" >> $OUTPUT
done

# 生成图表
python3 plot_scalability.py $OUTPUT
```

**关键指标**：
- 性能随矩阵大小的变化趋势
- 最优矩阵大小范围
- 超大矩阵的性能衰减情况

### 3. 数据类型对比测试（Data Type Comparison）

比较不同精度下的性能差异。

```bash
# 运行不同数据类型的测试
for dtype in fp32 fp16 bf16 tf32 int8; do
    echo "Testing $dtype..."
    ./gemmPerf -s 4096 -g $dtype -i 100 -o result_$dtype.txt
done
```

**性能对比分析**：
| 数据类型 | 精度 | 速度倍数 | 内存占用 | 典型应用 |
|---------|------|--------|--------|----------|
| FP32 | 完整 | 1x | 100% | 通用计算 |
| FP16 | 一半 | 2-4x | 50% | AI 训练 |
| BF16 | 一半 | 2-4x | 50% | 大模型训练 |
| TF32 | 特殊 | 2-3x | 75% | Tensor Core |
| INT8 | 量化 | 4-8x | 25% | 推理加速 |

### 4. 正确性验证（Correctness Verification）

确保 GEMM 实现的数学正确性。

```bash
# 4.1 与 cuBLAS 对比（推荐）
./gemmPerf -m 512 -n 512 -k 512 -C

# 4.2 与 CPU 参考实现对比
./gemmPerf -m 256 -n 256 -k 256 -vc

# 4.3 输出详细误差报告
# 使用相对误差（relative error）评估：
# 相对误差 = ||计算结果 - 参考结果|| / ||参考结果||
```

**验证标准**：
```
- FP32: 相对误差 < 1e-5
- FP16: 相对误差 < 1e-3
- BF16: 相对误差 < 1e-2
- INT8: 精确匹配（无浮点误差）
```

### 5. 内存分析（Memory Analysis）

分析内存访问模式和效率。

```bash
# 计算内存占用
./gemmPerf -s 4096 -z

# 输出示例：
# 矩阵 A 内存占用: 64 MB
# 矩阵 B 内存占用: 64 MB
# 矩阵 C 内存占用: 64 MB
# 总内存需求: 192 MB

# 使用 nvidia-smi 监控 GPU 内存
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader -l 1
```

**内存优化指标**：
- **内存带宽利用率** = 实际带宽 / 理论峰值带宽
- **缓存命中率** = L2 缓存命中数 / L2 缓存访问数
- **内存重用比** = 计算次数 / 内存访问次数

### 6. 多GPU 扩展性测试（Multi-GPU Scalability）

测试多 GPU 并行性能。

```bash
# 使用 CUDA_VISIBLE_DEVICES 控制使用的 GPU
export CUDA_VISIBLE_DEVICES=0,1,2,3

# 运行测试（如果程序支持多 GPU）
./gemmPerf -s 4096 -g bf16 -i 100

# 计算扩展效率：
# 扩展效率 = (N GPU 时性能) / (1 GPU 时性能 * N)
```

---

## 开发步骤

### 阶段 1: 项目结构设计

#### 目录结构

```
gpu_gemm_test/
├── CMakeLists.txt              # CMake 构建配置
├── README.md                   # 项目说明
├── GPU_GEMM_Testing_Tool_Guide.md
├── src/
│   ├── main.cu                 # 主程序入口
│   ├── gemm_kernels.cu         # CUDA GEMM 核函数实现
│   ├── utils.cu                # 工具函数（初始化、验证��）
│   ├── performance_counter.cu  # 性能计数和统计
│   └── args_parser.cpp         # 命令行参数解析
├── include/
│   ├── gemm_config.h           # 配置头文件
│   ├── gemm_types.h            # 数据类型定义
│   ├── gemm_kernels.cuh        # 核函数声明
│   └── utils.h                 # 工具函数声明
├── scripts/
│   ├── run_tests.sh            # 测试脚本
│   ├── scalability_test.sh     # 可扩展性测试
│   └── plot_results.py         # 绘制结果图表
└── data/
    └── golden_data/            # 黄金参考数据
```

### 阶段 2-6: 详细实现

详见源代码文件和各专题文档。

---

## 常见问题

### Q1: 编译时出现 "error: no suitable conversion function from "float" to "bfloat16_t""

**原因**: BF16 数据类型转换问题

**解决方案**:
```cuda
// 使用 CUDA 提供的转换函数
__nv_bfloat16 f32_to_bf16(float x) {
    return __float2bfloat16(x);
}

float bf16_to_f32(__nv_bfloat16 x) {
    return __bfloat162float(x);
}
```

### Q2: cuBLAS 对比时出现段错误

**原因**: 数据类型不匹配或内存未初始化

**解决方案**:
```cuda
// 确保使用��确的 cuBLAS 函数
cublasStatus_t status = cublasSgemm(
    handle,
    CUBLAS_OP_N, CUBLAS_OP_N,
    N, M, K,
    &alpha,
    d_B, ldb,          // 注意：cuBLAS 的顺序与标准矩阵乘法不同
    d_A, lda,
    &beta,
    d_C, ldc);
```

### Q3: 性能测试结果波动大

**原因**: GPU 频率波动、系统干扰、缺少 Warmup

**解决方案**:
```bash
# 增加 Warmup 和迭代次数
./gemmPerf -s 4096 -w -i 200

# 固定 GPU 频率（需要 root）
sudo nvidia-smi -lgc 1410  # 固定为最大频率
```

### Q4: 内存不足

**原因**: 矩阵太大或 GPU 显存不足

**解决方案**:
```bash
# 查看 GPU 显存
nvidia-smi

# 减小矩阵大小
./gemmPerf -s 2048  # 而非 8192

# 清理其他 GPU 应用
```

### Q5: 如何用自己的 GPU 优化实现替换 cuBLAS？

**步骤**:
1. 在 `gemm_kernels.cu` 中实现自己的核函数
2. 修改 `launch_gemm_*` 函数调用
3. 重新编译并运行性能测试

---

## 参考资源

### 官方文档
- [NVIDIA CUDA C++ Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- [cuBLAS Documentation](https://docs.nvidia.com/cuda/cublas/)
- [NVIDIA Nsight Systems](https://docs.nvidia.com/nsight-systems/)

### 优化指南
- [Optimizing CUDA for GPU Architecture](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/)
- [GPU Tensor Core Performance](https://www.nvidia.com/en-us/technologies/tensorcore/)

### 参考博客和论文
- [Outperforming cuBLAS on H100](https://cudaforfun.substack.com/p/outperforming-cublas-on-h100-a-worklog)
- [How to Optimize CUDA Matmul Kernel](https://siboehm.com/articles/22/CUDA-MMM)
- [Anatomy of High Performance Matrix Multiplication](https://www.aleksagordic.com/blog/matmul)

### 社区资源
- [NVIDIA CUDA Samples](https://github.com/NVIDIA/cuda-samples)
- [CUTLASS: Fast Linear Algebra in CUDA C++](https://github.com/NVIDIA/cutlass)
- [CuPy: GPU-accelerated NumPy-like Array](https://github.com/cupy/cupy)

---

## 总结

本文档为系统性的 GPU GEMM 性能测试提供了完整的框架。通过本文档，您可以：

1. **快速上手** - 按照安装和快速开始步骤快速部署
2. **深入理解** - 了解 GEMM 算法原理和性能指标
3. **全面测试** - 使用多种测试方法评估性能
4. **自定义开发** - 基于提供的框架开发自己的优化版本
5. **性能优化** - 识别瓶颈并进行针对性优化

通过持续的迭代和优化，您可以实现接近硬件峰值性能的 GEMM 实现。
