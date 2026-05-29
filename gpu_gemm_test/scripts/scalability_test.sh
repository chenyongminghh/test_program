#!/bin/bash

# Scalability Test Script
# Tests performance across different matrix sizes

BUILD_DIR="./build"
OUTPUT_FILE="scalability_results.csv"

if [ ! -f "${BUILD_DIR}/gemmPerf" ]; then
    echo "Error: gemmPerf not found in ${BUILD_DIR}"
    echo "Please build the project first."
    exit 1
fi

echo "Running scalability tests..."
echo "Results will be saved to ${OUTPUT_FILE}"
echo ""

# Test parameters
SIZES=(512 1024 2048 4096 8192)
ITERATIONS=50
DATA_TYPES="fp32 fp16 bf16"

echo "MatrixSize,DataType,MinTime,MaxTime,MeanTime,StdDev,PeakTFLOPS,AvgTFLOPS,Bandwidth" > $OUTPUT_FILE

for dtype in $DATA_TYPES; do
    echo "Testing data type: $dtype"
    
    for size in "${SIZES[@]}"; do
        echo -n "  Matrix size ${size}x${size}x${size}... "
        
        # Run test and capture output
        output=$(${BUILD_DIR}/gemmPerf -s $size -g $dtype -i $ITERATIONS -V 2>&1)
        
        # Extract relevant metrics (this requires parsing the output)
        # For now, just store basic info
        echo "$size,$dtype,test_output" >> $OUTPUT_FILE
        echo "Done"
    done
done

echo ""
echo "Results saved to $OUTPUT_FILE"
echo "To plot results, run: python3 plot_results.py $OUTPUT_FILE"
