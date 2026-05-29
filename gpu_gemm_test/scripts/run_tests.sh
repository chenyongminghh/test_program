#!/bin/bash

# GPU GEMM Test Suite

set -e

echo "=== GPU GEMM Test Suite ==="
echo ""

# Change to build directory
cd build

if [ ! -f "gemmPerf" ]; then
    echo "Error: gemmPerf executable not found. Please build first."
    echo "Run: cmake .. && make"
    exit 1
fi

echo "[1/4] Basic Functionality Test..."
./gemmPerf -s 512 -i 10

echo ""
echo "[2/4] Data Type Compatibility Test..."
for dtype in fp32 fp16 bf16; do
    echo "  Testing $dtype..."
    ./gemmPerf -s 1024 -g $dtype -i 5
done

echo ""
echo "[3/4] Scalability Test..."
for size in 512 1024 2048 4096; do
    echo "  Testing ${size}x${size}x${size}..."
    ./gemmPerf -s $size -i 3
done

echo ""
echo "[4/4] Correctness Verification (small matrix)..."
./gemmPerf -s 256 -C -w

echo ""
echo "=== All tests completed ==="
