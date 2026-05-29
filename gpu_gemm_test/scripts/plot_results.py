#!/usr/bin/env python3

import sys
import csv
import matplotlib.pyplot as plt
import numpy as np

def plot_scalability(csv_file):
    """
    Plot scalability test results from CSV file
    """
    
    if not os.path.exists(csv_file):
        print(f"Error: File {csv_file} not found")
        return
    
    # Read CSV
    sizes = []
    tflops = {}
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                size = int(row['MatrixSize'])
                dtype = row['DataType']
                peak_tflops = float(row['PeakTFLOPS'])
                
                if dtype not in tflops:
                    tflops[dtype] = []
                
                if size not in sizes:
                    sizes.append(size)
                
                tflops[dtype].append((size, peak_tflops))
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    # Sort sizes
    sizes.sort()
    
    # Create plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    for dtype, data in tflops.items():
        data.sort(key=lambda x: x[0])
        x = [d[0] for d in data]
        y = [d[1] for d in data]
        ax.plot(x, y, marker='o', label=dtype)
    
    ax.set_xlabel('Matrix Size')
    ax.set_ylabel('TFLOP/s')
    ax.set_title('GPU GEMM Scalability Test')
    ax.legend()
    ax.grid(True)
    
    plt.tight_layout()
    plt.savefig('scalability_results.png')
    print("Plot saved to scalability_results.png")

if __name__ == "__main__":
    import os
    
    if len(sys.argv) < 2:
        print("Usage: python3 plot_results.py <csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    plot_scalability(csv_file)
