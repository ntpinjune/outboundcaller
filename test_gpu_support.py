"""
Test GPU/CUDA support for Piper TTS
This script checks if CUDA is available and tests GPU acceleration
"""

import sys
import os
from pathlib import Path

# Fix encoding issues on Windows console
if sys.platform == 'win32':
    try:
        # Set console to UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            # For older Python versions
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        # If encoding setup fails, continue anyway
        pass

def check_nvidia_driver():
    """Check if NVIDIA driver is installed"""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ NVIDIA Driver: Installed")
            # Extract GPU info
            lines = result.stdout.split('\n')
            for line in lines:
                if 'NVIDIA-SMI' in line:
                    print(f"   {line}")
                elif 'Driver Version' in line:
                    print(f"   {line}")
                elif 'GeForce' in line or 'GTX' in line or 'RTX' in line:
                    print(f"   GPU: {line.strip()}")
            return True
        else:
            print("❌ NVIDIA Driver: Not found or not working")
            return False
    except FileNotFoundError:
        print("❌ NVIDIA Driver: nvidia-smi not found in PATH")
        print("   Make sure NVIDIA drivers are installed")
        return False
    except subprocess.TimeoutExpired:
        print("⚠️  NVIDIA Driver: Timeout checking (driver may be slow)")
        return False
    except Exception as e:
        print(f"❌ NVIDIA Driver: Error - {e}")
        return False

def check_cuda_toolkit():
    """Check if CUDA Toolkit is installed"""
    try:
        import subprocess
        result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✅ CUDA Toolkit: Installed")
            lines = result.stdout.split('\n')
            for line in lines:
                if 'release' in line.lower() or 'version' in line.lower():
                    print(f"   {line.strip()}")
            return True
        else:
            print("⚠️  CUDA Toolkit: nvcc not found (may still work with runtime libraries)")
            print("   onnxruntime-gpu includes CUDA runtime, but full toolkit recommended")
            return False
    except FileNotFoundError:
        print("⚠️  CUDA Toolkit: nvcc not found in PATH")
        print("   onnxruntime-gpu includes CUDA runtime libraries")
        print("   Full CUDA Toolkit is optional but recommended")
        return None  # Not required for onnxruntime-gpu
    except subprocess.TimeoutExpired:
        print("⚠️  CUDA Toolkit: Timeout checking")
        return None
    except Exception as e:
        print(f"⚠️  CUDA Toolkit: Error - {e}")
        return None

def check_onnxruntime_gpu():
    """Check if onnxruntime-gpu can access CUDA"""
    try:
        import onnxruntime as ort
        
        print("\n📋 ONNX Runtime GPU Check:")
        providers = ort.get_available_providers()
        print(f"   Available providers: {providers}")
        
        has_cuda = "CUDAExecutionProvider" in providers
        has_tensorrt = "TensorrtExecutionProvider" in providers
        
        if has_cuda:
            print("✅ CUDAExecutionProvider: Available")
            
            # Try to create a simple session to verify CUDA works
            try:
                import numpy as np
                # Create a simple test model (identity function)
                test_input = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
                
                # Note: We can't easily test without a real model, but provider presence is good
                print("   CUDA provider is available for use")
                print("   Note: Actual GPU usage depends on model loading")
                return True
            except Exception as e:
                print(f"   ⚠️  Could not verify CUDA functionality: {e}")
                return True  # Provider exists, assume it works
        else:
            print("❌ CUDAExecutionProvider: NOT available")
            print("   This means onnxruntime-gpu was installed but CUDA libraries aren't accessible")
            print("   Possible reasons:")
            print("   1. CUDA runtime libraries not in PATH/LD_LIBRARY_PATH")
            print("   2. cuDNN not properly installed")
            print("   3. GPU driver version incompatible with onnxruntime-gpu's CUDA version")
            return False
            
        if has_tensorrt:
            print("✅ TensorRTExecutionProvider: Available (bonus!)")
        
        return has_cuda
        
    except ImportError:
        print("❌ onnxruntime not installed")
        print("   Install with: pip install onnxruntime-gpu")
        return False
    except Exception as e:
        print(f"❌ Error checking onnxruntime: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_piper_with_gpu():
    """Actually test Piper TTS with GPU"""
    print("\n🎤 Testing Piper TTS with GPU...")
    
    try:
        import sys
        import os
        from pathlib import Path
        
        # CRITICAL: Add CUDA bin directory to PATH before importing anything that uses CUDA
        cuda_bin = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5\bin"
        if os.path.exists(cuda_bin):
            current_path = os.environ.get("PATH", "")
            if cuda_bin not in current_path:
                os.environ["PATH"] = cuda_bin + os.pathsep + current_path
                print(f"   ✅ Added CUDA bin to PATH: {cuda_bin}")
        else:
            print(f"   ⚠️  CUDA bin directory not found: {cuda_bin}")
        
        # Also add the separate cuDNN installation if it exists
        cudnn_separate = r"C:\Program Files\NVIDIA\CUDNN\v9.17\bin\12.9"
        if os.path.exists(cudnn_separate):
            current_path = os.environ.get("PATH", "")
            if cudnn_separate not in current_path:
                os.environ["PATH"] = cudnn_separate + os.pathsep + current_path
                print(f"   ✅ Added separate cuDNN bin to PATH: {cudnn_separate}")
        
        # Add piper paths
        piper_path = Path(__file__).parent / "piper1-gpl"
        if piper_path.exists():
            sys.path.insert(0, str(piper_path))
        
        # Import piper
        try:
            import piper
            from piper import PiperVoice
            print("   ✅ Using installed piper-tts package")
        except ImportError:
            try:
                piper_src_path = piper_path / "src"
                if piper_src_path.exists():
                    if str(piper_src_path) not in sys.path:
                        sys.path.insert(0, str(piper_src_path))
                from piper import PiperVoice
                print("   ✅ Using local piper source")
            except ImportError as e:
                print("❌ Piper TTS package not found")
                print(f"   Import error: {e}")
                return False
        
        # Load voice with GPU
        model_path = Path("piper1-gpl/en_US-lessac-medium.onnx")
        config_path = Path("piper1-gpl/en_US-lessac-medium.onnx.json")
        
        if not model_path.exists():
            print(f"❌ Model file not found: {model_path}")
            return False
        
        print(f"   Loading model: {model_path}")
        print(f"   GPU enabled: True")
        
        # Load voice with timeout protection
        try:
            print("   Attempting to load model with GPU...")
            voice = PiperVoice.load(str(model_path), config_path=str(config_path) if config_path.exists() else None, use_cuda=True)
            
            # Check providers
            try:
                providers = voice.session.get_providers()
                print(f"✅ Voice loaded successfully!")
                print(f"   Execution providers: {providers}")
                if "CUDAExecutionProvider" in providers:
                    print("   ✅ GPU is actually being used!")
                else:
                    print("   ⚠️  GPU was requested but CPU provider is being used")
                    return False
            except AttributeError:
                print("✅ Voice loaded successfully (could not verify provider)")
            
            # Test synthesis
            test_text = "Testing GPU acceleration."
            print(f"   Synthesizing: '{test_text}'")
            audio_chunks = list(voice.synthesize(test_text))
            
            if audio_chunks:
                print(f"✅ Generated {len(audio_chunks)} audio chunk(s)")
                
                try:
                    actual_providers = voice.session.get_providers()
                    if "CUDAExecutionProvider" in actual_providers:
                        print("   ✅ GPU synthesis completed successfully!")
                        return True
                    else:
                        print("   ❌ Using CPU instead of GPU")
                        return False
                except AttributeError:
                    return None
            else:
                print("❌ No audio generated")
                return False
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error loading voice: {error_msg[:200]}...")
            
            if "CUDNN" in error_msg or "cudnn" in error_msg:
                print("   🔍 cuDNN initialization failed!")
                print("   Try: Copy cuDNN DLLs from C:\\Program Files\\NVIDIA\\CUDNN\\v9.17\\bin\\12.9")
                print("   to: C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.5\\bin")
            
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Error testing Piper with GPU: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("GPU/CUDA Support Test for Piper TTS")
    print("=" * 60)
    
    results = {}
    
    # Check NVIDIA driver
    print("\n1. Checking NVIDIA Driver...")
    results['driver'] = check_nvidia_driver()
    
    # Check CUDA Toolkit
    print("\n2. Checking CUDA Toolkit (optional)...")
    results['cuda_toolkit'] = check_cuda_toolkit()
    
    # Check onnxruntime-gpu
    print("\n3. Checking onnxruntime-gpu...")
    results['onnxruntime_gpu'] = check_onnxruntime_gpu()
    
    # Test actual Piper TTS with GPU
    if results.get('onnxruntime_gpu'):
        results['piper_gpu'] = test_piper_with_gpu()
    else:
        print("\n⏭️  Skipping Piper TTS GPU test (onnxruntime-gpu CUDA provider not available)")
        results['piper_gpu'] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    print(f"NVIDIA Driver: {'✅ Working' if results.get('driver') else '❌ Missing'}")
    if results.get('cuda_toolkit') is not None:
        print(f"CUDA Toolkit: {'✅ Installed' if results['cuda_toolkit'] else '⚠️  Optional'}")
    else:
        print("CUDA Toolkit: ⚠️  Optional")
    
    print(f"onnxruntime-gpu CUDA: {'✅ Available' if results.get('onnxruntime_gpu') else '❌ Not Available'}")
    
    if results.get('piper_gpu') is not None:
        print(f"Piper TTS GPU: {'✅ Working' if results['piper_gpu'] else '❌ Failed'}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("Recommendations")
    print("=" * 60)
    
    if not results.get('driver'):
        print("❌ Install NVIDIA GPU drivers first")
        print("   Download from: https://www.nvidia.com/Download/index.aspx")
    
    if not results.get('onnxruntime_gpu'):
        if results.get('driver'):
            print("⚠️  GPU driver is installed but onnxruntime-gpu can't access CUDA")
            print("   Try: pip uninstall onnxruntime-gpu && pip install onnxruntime-gpu")
        else:
            print("⚠️  Install NVIDIA drivers first, then check onnxruntime-gpu")
    
    if results.get('onnxruntime_gpu') and results.get('piper_gpu') is True:
        print("✅ GPU acceleration is working!")
        print("   Enable it in config: piper_use_cuda=true")
        print("   Monitor GPU usage with: nvidia-smi -l 1")
    
    if results.get('onnxruntime_gpu') and results.get('piper_gpu') is False:
        print("❌ onnxruntime-gpu installed but GPU not working")
        print("   cuDNN initialization failed")
        print("   Try copying cuDNN DLLs from:")
        print("   C:\\Program Files\\NVIDIA\\CUDNN\\v9.17\\bin\\12.9")
        print("   to: C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v12.5\\bin")
        print("   Then restart your computer")
        print("   CPU mode will still work: set piper_use_cuda=false")

if __name__ == "__main__":
    main()