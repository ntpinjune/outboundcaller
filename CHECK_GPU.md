# Quick GPU Check Guide for GTX 1080

## Step 1: Verify NVIDIA Driver (Required)

Open PowerShell and run:
```powershell
nvidia-smi
```

**Expected output:** You should see your GTX 1080 listed with driver version and GPU memory info.

**If this fails:**
- Install/update NVIDIA drivers from: https://www.nvidia.com/Download/index.aspx
- Your GTX 1080 supports CUDA Compute Capability 6.1, so it's compatible

## Step 2: Check CUDA Toolkit (Optional but Recommended)

Run:
```powershell
nvcc --version
```

**Expected output:** CUDA version number (e.g., "release 11.8", "release 12.1")

**If this fails:**
- This is OK! `onnxruntime-gpu` includes CUDA runtime libraries
- Full CUDA Toolkit is optional but recommended for best performance
- Download from: https://developer.nvidia.com/cuda-downloads

## Step 3: Check onnxruntime-gpu CUDA Provider

Run this in your venv:
```powershell
.\venv\Scripts\python.exe -c "import onnxruntime as ort; providers = ort.get_available_providers(); print('Providers:', providers); print('CUDA Available:', 'CUDAExecutionProvider' in providers)"
```

**Expected output:**
```
Providers: ['CUDAExecutionProvider', 'CPUExecutionProvider', ...]
CUDA Available: True
```

**If CUDA is NOT available:**
- `onnxruntime-gpu` is installed but CUDA libraries aren't accessible
- Possible causes:
  1. **CUDA runtime not in PATH** - onnxruntime-gpu includes these but they might not be found
  2. **Driver version mismatch** - Your driver might be too old for the CUDA version in onnxruntime-gpu
  3. **cuDNN missing** - onnxruntime-gpu should include this, but verify

## Step 4: Test Piper TTS with GPU

Run the comprehensive test:
```powershell
.\venv\Scripts\python.exe test_gpu_support.py
```

This will:
- Check NVIDIA driver
- Check CUDA Toolkit (optional)
- Check onnxruntime-gpu CUDA provider
- Actually test Piper TTS with GPU enabled

## Step 5: Monitor GPU Usage (Real-time)

While testing, run this in another terminal:
```powershell
nvidia-smi -l 1
```

This updates every second and shows:
- GPU utilization (%)
- Memory usage
- Processes using GPU

**When Piper TTS uses GPU, you should see:**
- `python.exe` or your Python process using GPU
- GPU utilization > 0%
- Memory allocated to your process

## Troubleshooting

### onnxruntime-gpu installed but CUDA provider not available

**Try reinstalling:**
```powershell
.\venv\Scripts\pip.exe uninstall onnxruntime-gpu -y
.\venv\Scripts\pip.exe install onnxruntime-gpu
```

**Check driver version:**
```powershell
nvidia-smi | Select-String "Driver Version"
```

**For onnxruntime-gpu 1.23.2, you need:**
- CUDA 11.8 or 12.x
- Driver version >= 525.60 (for CUDA 12.x) or >= 520.61 (for CUDA 11.8)

**If driver is too old:**
- Update NVIDIA drivers (they're free)
- Download from: https://www.nvidia.com/Download/index.aspx

### cuDNN Issues

onnxruntime-gpu includes cuDNN, but if you're having issues:

1. **Install full CUDA Toolkit** (includes cuDNN):
   - Download from: https://developer.nvidia.com/cuda-downloads
   - Install with default settings
   - This ensures all CUDA libraries are properly installed

2. **Verify cuDNN separately** (optional):
   - Download from: https://developer.nvidia.com/cudnn
   - Extract to CUDA installation directory
   - Usually: `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.x\`

### GTX 1080 Specific Notes

- **Compute Capability:** 6.1 (fully supported)
- **CUDA Support:** Yes, all CUDA versions support Pascal architecture
- **Memory:** 8GB VRAM (plenty for Piper TTS models)
- **Performance:** Should see 2-5x speedup vs CPU for TTS

## Quick Test Command

Run this single command to check everything:
```powershell
Write-Host "1. NVIDIA Driver:"; nvidia-smi --query-gpu=name,driver_version --format=csv,noheader; Write-Host "`n2. CUDA Toolkit:"; nvcc --version 2>&1 | Select-String "release"; Write-Host "`n3. onnxruntime-gpu:"; .\venv\Scripts\python.exe -c "import onnxruntime as ort; providers = ort.get_available_providers(); print('CUDA Available:', 'CUDAExecutionProvider' in providers)"
```

## Once GPU is Working

1. **Enable in config.json:**
```json
{
  "agent": {
    "tts_provider": "piper",
    "piper_use_cuda": true
  }
}
```

2. **Or via web interface:**
   - Go to TTS Settings tab
   - Select "Piper" as provider
   - Check "Enable GPU Acceleration (CUDA)"
   - Save

3. **Verify in logs:**
   When you start the agent, you should see:
   ```
   ✅ CUDA/GPU provider available - using GPU acceleration
   ✅ Piper TTS instance created: ..., GPU, ...
   ```

4. **Monitor during use:**
   ```powershell
   nvidia-smi -l 1
   ```
   You should see GPU utilization when TTS is generating audio.
