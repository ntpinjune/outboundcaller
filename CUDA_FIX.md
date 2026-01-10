# CUDA Runtime DLL Missing - Fix Guide

## Problem

You're seeing this error:
```
Error loading "onnxruntime_providers_cuda.dll" which depends on "cublasLt64_12.dll" which is missing.
Failed to create CUDAExecutionProvider. Require cuDNN 9.* and CUDA 12.*
```

## Why This Happens

`onnxruntime-gpu 1.23.2` requires **CUDA 12.x runtime libraries**, but they're not installed on your system. The `onnxruntime-gpu` package includes the ONNX Runtime CUDA provider, but it depends on system CUDA libraries that must be installed separately.

## Solution: Install CUDA 12.x Runtime

### Option 1: Install CUDA Toolkit 12.x (Recommended for development)

1. **Download CUDA Toolkit 12.x:**
   - Go to: https://developer.nvidia.com/cuda-downloads
   - Select: Windows → x86_64 → 10/11 → exe (local)
   - Choose CUDA 12.4 or 12.5 (matches your driver version 12.5)

2. **Install:**
   - Run the installer
   - Choose "Express Installation" (includes everything needed)
   - This installs CUDA runtime, cuBLAS, cuDNN, and other required libraries

3. **Add to PATH** (usually automatic, but verify):
   ```
   C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.x\bin
   ```

4. **Restart your terminal** and test again:
   ```powershell
   .\venv\Scripts\python.exe test_gpu_support.py
   ```

### Option 2: Install CUDA Redistributables Only (Lighter)

If you don't need the full toolkit:

1. **Download CUDA Redistributables:**
   - Go to: https://developer.nvidia.com/cuda-12-4-0-download-archive
   - Download "CUDA Runtime" or "CUDA Redistributables"

2. **Install and restart terminal**

### Option 3: Use Older onnxruntime-gpu Version (Workaround)

If you can't install CUDA 12.x, use an older version that uses CUDA 11.x:

```powershell
.\venv\Scripts\pip.exe uninstall onnxruntime-gpu -y
.\venv\Scripts\pip.exe install "onnxruntime-gpu==1.19.2"  # Uses CUDA 11.8
```

**Note:** This may have compatibility issues with newer features.

## Verify Fix

After installing CUDA, verify:

```powershell
# Check if CUDA DLLs are accessible
.\venv\Scripts\python.exe -c "import onnxruntime as ort; session = ort.InferenceSession('test.onnx', providers=['CUDAExecutionProvider']); print('✅ CUDA works!')"
```

Or run the full test:
```powershell
.\venv\Scripts\python.exe test_gpu_support.py
```

You should see:
- ✅ Voice loaded successfully with GPU support
- Execution providers: **['CUDAExecutionProvider']** (not CPUExecutionProvider)
- ✅ GPU is actually being used!

## Current Status

From your test output:
- ✅ NVIDIA Driver: Working (GTX 1080, Driver 556.12, CUDA Version 12.5)
- ✅ onnxruntime-gpu: Installed (version 1.23.2)
- ✅ CUDAExecutionProvider: Declared as available
- ❌ **CUDA Runtime DLLs: Missing** (cublasLt64_12.dll not found)
- ⚠️  **Actual GPU usage: Falling back to CPU** (because DLLs are missing)

## Quick Fix Summary

**Easiest solution:** Install CUDA Toolkit 12.4 or 12.5 from NVIDIA's website. It's a large download (~3GB) but includes everything needed.

**After installation:** Restart terminal and GPU should work automatically.
