"""
Test script for Piper TTS - verifies audio generation and optionally GPU usage
"""
import sys
from pathlib import Path

# Add paths
piper_path = Path(__file__).parent / "piper1-gpl"
if piper_path.exists():
    sys.path.insert(0, str(piper_path))

try:
    import piper
    from piper import PiperVoice
    print("✅ Piper package imported successfully")
except ImportError as e:
    print(f"❌ Failed to import piper: {e}")
    print("   Install with: pip install piper-tts")
    sys.exit(1)

def test_piper_tts(use_cuda=False, test_text="Hello, this is a test of Piper TTS."):
    """Test Piper TTS audio generation"""
    
    # Model path
    model_path = Path("piper1-gpl/en_US-lessac-medium.onnx")
    config_path = Path("piper1-gpl/en_US-lessac-medium.onnx.json")
    
    if not model_path.exists():
        print(f"❌ Model file not found: {model_path}")
        print("   Make sure the model file exists in piper1-gpl/")
        return False
    
    try:
        print(f"📦 Loading Piper voice model...")
        print(f"   Model: {model_path}")
        print(f"   GPU: {'Enabled' if use_cuda else 'Disabled (CPU)'}")
        
        # Load voice
        voice = PiperVoice.load(
            model_path=model_path,
            config_path=config_path if config_path.exists() else None,
            use_cuda=use_cuda
        )
        
        print(f"✅ Voice loaded successfully")
        print(f"   Sample rate: {voice.config.sample_rate} Hz")
        print(f"   Execution provider: {voice.session.get_providers()}")
        
        # Test synthesis
        print(f"\n🎤 Synthesizing text: '{test_text}'")
        
        audio_chunks = list(voice.synthesize(test_text))
        
        if not audio_chunks:
            print("❌ No audio chunks generated!")
            return False
        
        print(f"✅ Generated {len(audio_chunks)} audio chunk(s)")
        
        # Calculate total audio duration
        total_samples = sum(len(chunk.audio_float_array) for chunk in audio_chunks)
        duration_seconds = total_samples / voice.config.sample_rate
        
        print(f"   Total samples: {total_samples}")
        print(f"   Duration: {duration_seconds:.2f} seconds")
        # Get channels from AudioChunk (PiperConfig doesn't have num_channels)
        num_channels = audio_chunks[0].sample_channels if audio_chunks else 1
        print(f"   Audio format: {voice.config.sample_rate} Hz, {num_channels} channel(s)")
        
        # Save to WAV file for testing
        output_file = Path("test_piper_output.wav")
        
        try:
            import wave
            import numpy as np
            
            # Get channels from AudioChunk (PiperConfig doesn't have num_channels)
            num_channels = audio_chunks[0].sample_channels if audio_chunks else 1
            
            with wave.open(str(output_file), "wb") as wav_file:
                wav_file.setframerate(voice.config.sample_rate)
                wav_file.setnchannels(num_channels)
                wav_file.setsampwidth(2)  # 16-bit
                
                for chunk in audio_chunks:
                    # Use the built-in audio_int16_bytes property
                    audio_bytes = chunk.audio_int16_bytes
                    wav_file.writeframes(audio_bytes)
            
            print(f"\n💾 Audio saved to: {output_file}")
            print(f"   You can play this file to verify the audio quality")
            print(f"   File size: {output_file.stat().st_size / 1024:.2f} KB")
            
            return True
            
        except ImportError:
            print("⚠️  Could not save WAV file (wave module not available)")
            return True  # Still success - audio was generated
            
    except Exception as e:
        print(f"❌ Error during synthesis: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_gpu_availability():
    """Check if GPU/CUDA is available"""
    try:
        import onnxruntime as ort
        
        # Check available providers
        providers = ort.get_available_providers()
        print(f"📋 Available ONNX Runtime providers: {providers}")
        
        has_cuda = "CUDAExecutionProvider" in providers
        if has_cuda:
            print("✅ CUDA/GPU support is available!")
            try:
                # Try to get CUDA device info
                import subprocess
                result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print("\n🎮 NVIDIA GPU Info:")
                    lines = result.stdout.split('\n')[:5]
                    for line in lines:
                        print(f"   {line}")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                print("⚠️  Could not check GPU details (nvidia-smi not available)")
        else:
            print("⚠️  CUDA/GPU support is NOT available")
            print("   To enable GPU:")
            print("   1. Install onnxruntime-gpu: pip install onnxruntime-gpu")
            print("   2. Install CUDA and cuDNN libraries")
            print("   3. Restart the agent")
        
        return has_cuda
        
    except ImportError:
        print("⚠️  Could not check GPU availability (onnxruntime not available)")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Piper TTS Test Script")
    print("=" * 60)
    
    # Check GPU availability
    print("\n1. Checking GPU availability...")
    has_cuda = check_gpu_availability()
    
    # Test with CPU first
    print("\n2. Testing Piper TTS with CPU...")
    cpu_success = test_piper_tts(use_cuda=False)
    
    # Test with GPU if available
    if has_cuda:
        print("\n3. Testing Piper TTS with GPU...")
        print("   Note: Monitor GPU usage with 'nvidia-smi -l 1' in another terminal")
        gpu_success = test_piper_tts(use_cuda=True, test_text="Testing GPU acceleration with Piper TTS.")
        
        # Show execution provider info if available
        if gpu_success:
            try:
                from pathlib import Path
                from piper import PiperVoice
                model_path = Path("piper1-gpl/en_US-lessac-medium.onnx")
                config_path = Path("piper1-gpl/en_US-lessac-medium.onnx.json")
                voice = PiperVoice.load(str(model_path), config_path=str(config_path) if config_path.exists() else None, use_cuda=True)
                providers = voice.session.get_providers()
                print(f"   Execution providers actually used: {providers}")
                if "CUDAExecutionProvider" in providers:
                    print("   ✅ GPU is actually being used!")
                else:
                    print("   ⚠️  CUDA provider requested but CPU was used instead")
            except Exception as e:
                print(f"   ⚠️  Could not verify execution provider: {e}")
    else:
        gpu_success = None
        print("\n3. Skipping GPU test (CUDA not available)")
        print("   To enable GPU:")
        print("   1. Make sure NVIDIA drivers are installed (run: nvidia-smi)")
        print("   2. Install/update CUDA Toolkit if needed")
        print("   3. Reinstall onnxruntime-gpu if CUDA provider still not available")
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"✅ CPU Test: {'PASSED' if cpu_success else 'FAILED'}")
    if gpu_success is not None:
        print(f"{'✅' if gpu_success else '❌'} GPU Test: {'PASSED' if gpu_success else 'FAILED'}")
    
    if cpu_success:
        print("\n✅ Piper TTS is working correctly!")
        print("   You can now use it in your agent by setting TTS_PROVIDER=piper")
    else:
        print("\n❌ Piper TTS test failed. Check the errors above.")