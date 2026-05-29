# GPU GEMM 测试工具

一个通用的 GPU GEMM（General Matrix Multiply，广义矩阵乘法）性能测试工具，支持在 Linux 环境下对不同 GPU 的矩阵乘法运算进行全面的性能评估。

## 快速开始

### 环境要求

- Ubuntu 18.04 LTS 或更高版本
- NVIDIA GPU（计算能力 >= 7.0）
- NVIDIA Driver（版本 >= 450）
- CUDA Toolkit（版本 >= 11.0）
- CMake >= 3.20
- C++17 编译器

### 安装和编译

```bash
# 克隆仓库
git clone https://github.com/chenyongminghh/test_program.git
cd test_program/gpu_gemm_test

# 创建构建目录
mkdir -p build
cd build

# 配置和编译
cmake ..
cmake --build . -j$(nproc)
```

### 基础用法

```bash
# 进入构建目录
cd build

# 运行基础 GEMM 测试（FP32，矩阵大小 1024×1024×1024）
./gemmPerf -s 1024

# 运行 BF16 测试
./gemmPerf -s 1024 -g bf16

# 与 cuBLAS 进行性能对比
./gemmPerf -s 1024 -c

# 显示帮助信息
./gemmPerf -h
```

## 文档结构

- `GPU_GEMM_Testing_Tool_Guide.md` - 完整的使用和开发指南
- `GEMM_Principles.md` - GEMM 算法原理详解
- `Testing_Methods.md` - 各种测试方法说明
- `Development_Guide.md` - 完整的开发步骤

## 项目特性

- ✅ 支持多种数据类型（FP32、FP16、BF16、TF32、INT8 等）
- ✅ 灵活的矩阵大小配置
- ✅ 详细的性能指标输出
- ✅ 与 cuBLAS 的性能对比
- ✅ 正确性验证功能
- ✅ 内存分析工具
- ✅ 自动化测试脚本

## 快速命令参考

```bash
# 性能基准测试
./gemmPerf -s 4096 -g fp32 -i 100 -w

# 多数据类型对比
for dtype in fp32 fp16 bf16; do
  ./gemmPerf -s 4096 -g $dtype -i 100
done

# 可扩展性测试
for size in 512 1024 2048 4096 8192; do
  ./gemmPerf -s $size -i 50
done

# 正确性验证
./gemmPerf -m 512 -n 512 -k 512 -C
```

## 更多信息

详细的使用说明、开发步骤和测试方法请参考 `GPU_GEMM_Testing_Tool_Guide.md`。
