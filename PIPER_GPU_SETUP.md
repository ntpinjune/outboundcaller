# Piper TTS GPU Setup Guide

## Overview

Piper TTS can use GPU acceleration via CUDA for faster audio generation. This guide explains how to enable GPU support.

## Prerequisites

To use GPU acceleration, you need:

1. **NVIDIA GPU** with CUDA support
2. **CUDA Toolkit** (version 11.8 or later recommended)
3. **cuDNN** library
4. **onnxruntime-gpu** Python package

## Step 1: Check GPU Availability

First, verify you have an NVIDIA GPU:

```powershell
nvidia-smi
```

If this command works, you have an NVIDIA GPU and driver installed.

## Step 2: Install onnxruntime-gpu

Uninstall the CPU version and install the GPU version:

```powershell
.\venv\Scripts\pip.exe uninstall onnxruntime -y
.\venv\Scripts\pip.exe install onnxruntime-gpu
```

**Important:** `onnxruntime-gpu` requires CUDA and cuDNN to be installed on your system. If they're not installed, the GPU provider won't be available.

## Step 3: Verify GPU Provider

Test if GPU support is available:

```powershell
.\venv\Scripts\python.exe -c "import onnxruntime as ort; print('Providers:', ort.get_available_providers()); print('Has CUDA:', 'CUDAExecutionProvider' in ort.get_available_providers())"
```

You should see `CUDAExecutionProvider` in the list if GPU support is available.

## Step 4: Enable GPU in Configuration

### Option A: Web Interface

1. Open the web configuration interface (usually at `http://localhost:5000`)
2. Navigate to the **TTS Settings** tab
3. Select **Piper** as the TTS provider
4. Check the **"Enable GPU Acceleration (CUDA)"** checkbox
5. Save the configuration

### Option B: config.json

Edit `config.json` and set:

```json
{
  "agent": {
    "tts_provider": "piper",
    "piper_use_cuda": true,
    ...
  }
}
```

### Option C: Environment Variable

Set the environment variable:

```powershell
$env:PIPER_USE_CUDA = "true"
```

## Step 5: Verify GPU Usage

When you start the agent, check the logs. You should see:

```
✅ CUDA/GPU provider available - using GPU acceleration
✅ Piper TTS instance created: piper1-gpl/en_US-lessac-medium.onnx, GPU, ...
```

If GPU is not available but requested, you'll see:

```
⚠️  GPU requested but CUDA provider not available. Falling back to CPU.
```

The agent will automatically fall back to CPU if GPU is not available.

## Troubleshooting

### GPU Not Available

If `CUDAExecutionProvider` is not in the available providers list:

1. **Check CUDA Installation:**
   ```powershell
   nvcc --version
   ```
   If this fails, install CUDA Toolkit from NVIDIA's website.

2. **Check cuDNN Installation:**
   cuDNN should be installed in your CUDA directory. Verify it's properly installed.

3. **Reinstall onnxruntime-gpu:**
   ```powershell
   .\venv\Scripts\pip.exe uninstall onnxruntime-gpu -y
   .\venv\Scripts\pip.exe install onnxruntime-gpu
   ```

4. **Check ONNX Runtime Compatibility:**
   Make sure your CUDA version is compatible with the installed `onnxruntime-gpu` version.

### Performance Tips

- **GPU is beneficial for:** Long sentences, batch processing, multiple concurrent requests
- **CPU may be sufficient for:** Short phrases, single requests, systems without dedicated GPU
- **Memory:** GPU models require GPU memory. Monitor with `nvidia-smi`

## Testing GPU Performance

You can test GPU performance with the test script:

```powershell
.\venv\Scripts\python.exe test_piper_tts.py
```

The script will automatically detect and use GPU if available.

## Notes

- GPU acceleration requires more setup but can significantly speed up audio generation
- The agent automatically falls back to CPU if GPU is not available
- CPU mode works fine for most use cases - GPU is optional for better performance
- Make sure your system has enough GPU memory for the model size
