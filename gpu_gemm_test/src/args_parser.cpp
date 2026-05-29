#include "gemm_types.h"
#include <iostream>
#include <cstring>
#include <cstdlib>

class ArgumentParser {
public:
    bool parse(int argc, char** argv, GemmConfig& config) {
        // 默认配置
        config.M = config.N = config.K = 1024;
        config.data_type = GEMM_FP32;
        config.transpose_type = TRANSPOSE_NN;
        config.lda = config.M;
        config.ldb = config.K;
        config.ldc = config.M;
        config.alpha = 1.0f;
        config.beta = 0.0f;
        config.num_iterations = 100;
        config.warmup = false;
        config.verify = false;
        config.compare_cublas = false;
        config.print_result = false;
        config.verbose = false;
        strcpy(config.output_file, "");
        
        for (int i = 1; i < argc; i++) {
            std::string arg = argv[i];
            
            if (arg == "-h" || arg == "--help") {
                print_help();
                return false;
            }
            else if (arg == "-s" || arg == "--size") {
                int size = atoi(argv[++i]);
                config.M = config.N = config.K = size;
                config.lda = config.M;
                config.ldb = config.K;
                config.ldc = config.M;
            }
            else if (arg == "-m" || arg == "--m-dim") {
                config.M = atoi(argv[++i]);
                config.lda = config.M;
            }
            else if (arg == "-n" || arg == "--n-dim") {
                config.N = atoi(argv[++i]);
            }
            else if (arg == "-k" || arg == "--k-dim") {
                config.K = atoi(argv[++i]);
                config.ldb = config.K;
            }
            else if (arg == "-g" || arg == "--gemm-type") {
                config.data_type = parse_data_type(argv[++i]);
            }
            else if (arg == "-t" || arg == "--transpose") {
                config.transpose_type = (TransposeType)atoi(argv[++i]);
            }
            else if (arg == "-a" || arg == "--lda") {
                config.lda = atoi(argv[++i]);
            }
            else if (arg == "-b" || arg == "--ldb") {
                config.ldb = atoi(argv[++i]);
            }
            else if (arg == "-c" || arg == "--ldc") {
                config.ldc = atoi(argv[++i]);
            }
            else if (arg == "-i" || arg == "--iterations") {
                config.num_iterations = atoi(argv[++i]);
            }
            else if (arg == "-w" || arg == "--warmup") {
                config.warmup = true;
            }
            else if (arg == "-C" || arg == "--verify") {
                config.verify = true;
            }
            else if (arg == "-c" || arg == "--compare-cublas") {
                config.compare_cublas = true;
            }
            else if (arg == "-p" || arg == "--print-result") {
                config.print_result = true;
            }
            else if (arg == "-V" || arg == "--verbose") {
                config.verbose = true;
            }
            else if (arg == "-o" || arg == "--output") {
                strcpy(config.output_file, argv[++i]);
            }
        }
        
        config.lda = config.lda == 0 ? config.M : config.lda;
        config.ldb = config.ldb == 0 ? config.K : config.ldb;
        config.ldc = config.ldc == 0 ? config.M : config.ldc;
        
        return true;
    }
    
private:
    GemmDataType parse_data_type(const char* type_str) {
        if (strcmp(type_str, "fp32") == 0) return GEMM_FP32;
        if (strcmp(type_str, "fp16") == 0) return GEMM_FP16;
        if (strcmp(type_str, "bf16") == 0) return GEMM_BF16;
        if (strcmp(type_str, "tf32") == 0) return GEMM_TF32;
        if (strcmp(type_str, "int8") == 0) return GEMM_INT8;
        if (strcmp(type_str, "int32") == 0) return GEMM_INT32;
        return GEMM_FP32;
    }
    
    void print_help() const {
        std::cout << "GPU GEMM Performance Testing Tool\n\n"
                  << "Usage: ./gemmPerf [options]\n\n"
                  << "General Options:\n"
                  << "  -h, --help              Show this help message\n"
                  << "  -v, --version           Show version\n"
                  << "  -V, --verbose           Verbose output\n\n"
                  << "Matrix Size Options:\n"
                  << "  -s, --size <n>          Square matrix size (default: 1024)\n"
                  << "  -m, --m-dim <n>         Matrix M dimension\n"
                  << "  -n, --n-dim <n>         Matrix N dimension\n"
                  << "  -k, --k-dim <n>         Matrix K dimension\n\n"
                  << "Data Type Options:\n"
                  << "  -g, --gemm-type <type>  Data type: fp32|fp16|bf16|tf32|int8|int32\n"
                  << "                          (default: fp32)\n\n"
                  << "Matrix Layout Options:\n"
                  << "  -t, --transpose <type>  Transpose type: 0(NN)|1(NT)|2(TN)|3(TT)\n"
                  << "  -a, --lda <n>           Leading dimension of A\n"
                  << "  -b, --ldb <n>           Leading dimension of B\n"
                  << "  -c, --ldc <n>           Leading dimension of C\n\n"
                  << "Test Control Options:\n"
                  << "  -i, --iterations <n>    Number of iterations (default: 100)\n"
                  << "  -w, --warmup            Run warmup before test\n"
                  << "  -C, --verify            Verify correctness\n"
                  << "  -c, --compare-cublas    Compare with cuBLAS\n"
                  << "  -p, --print-result      Print result matrix\n\n"
                  << "Output Options:\n"
                  << "  -o, --output <file>     Output file path\n\n"
                  << "Examples:\n"
                  << "  ./gemmPerf -s 4096 -g fp32 -i 100\n"
                  << "  ./gemmPerf -m 2048 -n 2048 -k 2048 -w\n"
                  << "  ./gemmPerf -s 2048 -g bf16 -c -V\n";
    }
};
