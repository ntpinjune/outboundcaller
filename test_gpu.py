"""
Quick GPU test for Piper TTS - Run this to verify GPU acceleration
Usage: python test_gpu.py
"""

import sys
from pathlib import Path

# Add paths for piper
piper_path = Path(__file__).parent / "piper1-gpl"
if piper_path.exists():
    sys.path.insert(0, str(piper_path))

def test_gpu():
    """Test if GPU acceleration is working for Piper TTS"""
    print("=" * 60)
    print("Quick GPU Test for Piper TTS")
    print("=" * 60)
    
    # Check onnxruntime CUDA provider
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        has_cuda_provider = "CUDAExecutionProvider" in providers
        print(f"\n1. ONNX Runtime CUDA Provider: {'✅ Available' if has_cuda_provider else '❌ Not Available'}")
        if has_cuda_provider:
            print(f"   Providers: {providers}")
        else:
            print("   Install with: pip install onnxruntime-gpu")
            return False
    except ImportError:
        print("\n❌ onnxruntime not installed")
        return False
    
    # Check if CUDA runtime DLLs are available (the actual test)
    print("\n2. Testing Piper TTS with GPU...")
    try:
        from piper import PiperVoice
        
        model_path = Path("piper1-gpl/en_US-lessac-medium.onnx")
        config_path = Path("piper1-gpl/en_US-lessac-medium.onnx.json")
        
        if not model_path.exists():
            print(f"   ❌ Model not found: {model_path}")
            return False
        
        print(f"   Loading model: {model_path}")
        print(f"   GPU enabled: True")
        
        # Try to load with GPU
        voice = PiperVoice.load(
            str(model_path),
            config_path=str(config_path) if config_path.exists() else None,
            use_cuda=True
        )
        
        # Check actual execution provider (this is the real test)
        try:
            actual_providers = voice.session.get_providers()
            print(f"   Execution providers actually used: {actual_providers}")
            
            if "CUDAExecutionProvider" in actual_providers:
                print("   ✅ GPU is ACTUALLY being used!")
                
                # Test synthesis
                test_text = "Testing GPU acceleration with Piper TTS."
                print(f"   Synthesizing: '{test_text}'")
                audio_chunks = list(voice.synthesize(test_text))
                
                if audio_chunks:
                    print(f"   ✅ Generated {len(audio_chunks)} audio chunk(s)")
                    print(f"   ✅ GPU acceleration is WORKING!")
                    print("\n💡 Tip: Monitor GPU usage with: nvidia-smi -l 1")
                    return True
                else:
                    print("   ❌ No audio generated")
                    return False
            else:
                print("   ❌ GPU requested but CPU is being used")
                print("   Reason: CUDA runtime DLLs missing (cublasLt64_12.dll)")
                print("   Solution: Install CUDA Toolkit 12.x from NVIDIA")
                print("   Download: https://developer.nvidia.com/cuda-downloads")
                return False
                
        except AttributeError:
            print("   ⚠️  Could not verify execution provider")
            print("   (Older Piper version - assume GPU works if no errors)")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gpu()
    print("\n" + "=" * 60)
    if success is True:
        print("✅ GPU Test: PASSED - GPU acceleration is working!")
        print("   You can enable GPU in your agent by setting piper_use_cuda=true")
    elif success is False:
        print("❌ GPU Test: FAILED - GPU is not actually being used")
        print("   Install CUDA Toolkit 12.x to enable GPU acceleration")
    else:
        print("⚠️  GPU Test: UNCERTAIN - Could not verify GPU usage")
    print("=" * 60)
