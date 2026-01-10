# Piper TTS Integration

This agent now supports using Piper TTS as a local TTS provider alongside ElevenLabs and Chatterbox.

## Setup

### 1. Install Piper TTS

Piper TTS is already included in the `piper1-gpl` folder. If you need to install it separately:

```bash
pip install piper-tts
```

Or if using the local folder, the code will automatically add it to the Python path.

### 2. Download a Voice Model

Voice models are available from [Piper Voices](https://github.com/rhasspy/piper/releases).

A sample model (`en_US-lessac-medium.onnx`) is already included in `piper1-gpl/`.

To download additional voices:
```bash
python -m piper.download_voices en_US-lessac-medium
```

Or manually download from: https://github.com/rhasspy/piper/releases

### 3. Configure Piper TTS

You can configure Piper TTS in three ways:

#### Option A: Web Interface (Recommended)

1. Open the web configuration interface: `http://127.0.0.1:5000`
2. Go to the "Agent Settings" tab
3. Select "Piper (Local)" from the "TTS Provider" dropdown
4. Configure:
   - **Piper Model Path**: `piper1-gpl/en_US-lessac-medium.onnx` (or your model path)
   - **Piper Config Path**: `piper1-gpl/en_US-lessac-medium.onnx.json` (optional, auto-detected if not provided)
   - **Piper Length Scale**: 1.0 (controls speech speed - lower = faster, higher = slower)
   - **Piper Noise Scale**: 0.667 (voice variation)
   - **Piper Noise W Scale**: 0.8 (speaking variation)
   - **Piper Volume**: 1.0 (volume multiplier)
   - **TTS Speed**: 0.5-2.0 (affects length_scale)
5. Click "Save Configuration"

#### Option B: Environment Variables

Add to your `.env.local`:
```bash
TTS_PROVIDER=piper
PIPER_MODEL_PATH=piper1-gpl/en_US-lessac-medium.onnx
PIPER_CONFIG_PATH=piper1-gpl/en_US-lessac-medium.onnx.json
PIPER_LENGTH_SCALE=1.0
PIPER_NOISE_SCALE=0.667
PIPER_NOISE_W_SCALE=0.8
PIPER_VOLUME=1.0
TTS_SPEED=1.0
```

#### Option C: config.json

Edit `config.json`:
```json
{
  "agent": {
    "tts_provider": "piper",
    "piper_model_path": "piper1-gpl/en_US-lessac-medium.onnx",
    "piper_config_path": "piper1-gpl/en_US-lessac-medium.onnx.json",
    "piper_length_scale": 1.0,
    "piper_noise_scale": 0.667,
    "piper_noise_w_scale": 0.8,
    "piper_volume": 1.0,
    "tts_speed": 1.0
  }
}
```

## Configuration Options

- **piper_model_path**: Path to the .onnx model file (required)
- **piper_config_path**: Path to the .json config file (optional, defaults to model_path + ".json")
- **piper_length_scale**: Speech speed control (default: 1.0)
  - Lower values (0.5-0.9) = faster speech
  - Higher values (1.1-2.0) = slower speech
  - Note: TTS_SPEED is also mapped to length_scale (inverse relationship)
- **piper_noise_scale**: Voice variation (default: 0.667)
  - Lower = more consistent
  - Higher = more varied
- **piper_noise_w_scale**: Speaking variation (default: 0.8)
  - Controls variation in speaking style
- **piper_volume**: Volume multiplier (default: 1.0)
  - Range: 0.0-1.0

## How It Works

1. The agent checks the `TTS_PROVIDER` setting
2. If set to `"piper"`, it uses the `PiperTTS` class from `piper1-gpl/livekit_piper_tts.py`
3. `PiperTTS` loads the voice model from the specified path
4. Audio is generated locally using the Piper TTS engine
5. Audio is converted to PCM format and streamed to the call

## Advantages of Piper TTS

- **100% Local**: No API calls, no internet required
- **Free**: No subscription or usage limits
- **Fast**: Low latency for voice generation
- **Offline**: Works completely offline
- **Privacy**: All processing happens locally

## Available Voice Models

Piper supports many languages and voice models. Browse available voices at:
https://github.com/rhasspy/piper/releases

Popular English voices:
- `en_US-lessac-medium` (included)
- `en_US-lessac-low`
- `en_US-lessac-high`

## Troubleshooting

### "Piper TTS not available"
- Make sure `piper1-gpl/livekit_piper_tts.py` exists
- Ensure `piper-tts` package is accessible (either installed or in `piper1-gpl/src/piper/`)
- Check that the `piper1-gpl` folder exists

### "Model not found"
- Verify the model path in config.json is correct
- Check that the .onnx file exists at the specified path
- Download a voice model if needed

### Import errors
- Install piper-tts: `pip install piper-tts`
- Or ensure `piper1-gpl/src/piper/` contains the piper package
- Check Python path includes the piper1-gpl folder

### Audio quality issues
- Adjust `piper_noise_scale` and `piper_noise_w_scale` for better quality
- Try different voice models
- Adjust `piper_length_scale` if speech sounds too fast/slow

## Switching Between TTS Providers

You can easily switch between ElevenLabs, Chatterbox, and Piper TTS via:
- Web interface: Change "TTS Provider" dropdown
- Config file: Change `tts_provider` value
- Environment variable: Set `TTS_PROVIDER=piper`

The agent will automatically use the selected provider.
