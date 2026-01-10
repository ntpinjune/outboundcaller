# Chatterbox TTS Integration

This agent now supports using a local Chatterbox TTS server instead of ElevenLabs for text-to-speech.

## Setup

### 1. Install Dependencies

Make sure `httpx` is installed (it should already be in requirements.txt):
```bash
pip install httpx
```

### 2. Start Your Chatterbox TTS Server

Make sure your Chatterbox TTS server is running on `http://localhost:8004` (or your configured URL).

### 3. Configure TTS Provider

You can switch between ElevenLabs and Chatterbox TTS in two ways:

#### Option A: Web Interface (Recommended)

1. Open the web configuration interface: `http://127.0.0.1:5000`
2. Go to the "Agent Settings" tab
3. Select "Chatterbox (Local)" from the "TTS Provider" dropdown
4. Configure:
   - **Chatterbox API URL**: `http://localhost:8004` (or your server URL)
   - **Chatterbox Voice File**: `Emily.wav` (or your voice file name)
   - **TTS Speed**: 0.5-2.0 (Chatterbox supports wider range than ElevenLabs)
5. Click "Save Configuration"

#### Option B: Environment Variables

Add to your `.env.local`:
```bash
TTS_PROVIDER=chatterbox
CHATTERBOX_API_URL=http://localhost:8004
CHATTERBOX_VOICE=Emily.wav
CHATTERBOX_MODEL=chatterbox-turbo
TTS_SPEED=1.0
```

#### Option C: config.json

Edit `config.json`:
```json
{
  "agent": {
    "tts_provider": "chatterbox",
    "chatterbox_api_url": "http://localhost:8004",
    "chatterbox_voice": "Emily.wav",
    "chatterbox_model": "chatterbox-turbo",
    "tts_speed": 1.0
  }
}
```

## Configuration Options

- **tts_provider**: `"elevenlabs"` or `"chatterbox"`
- **chatterbox_api_url**: URL of your Chatterbox TTS server (default: `http://localhost:8004`)
- **chatterbox_voice**: Voice file name (e.g., `Emily.wav`)
- **chatterbox_model**: Model name (default: `chatterbox-turbo`)
- **tts_speed**: 
  - ElevenLabs: 0.7-1.2
  - Chatterbox: 0.5-2.0 (wider range)

## How It Works

1. The agent checks the `TTS_PROVIDER` setting
2. If set to `"chatterbox"`, it uses `ChatterboxTTS` class
3. `ChatterboxTTS` makes HTTP requests to your local Chatterbox TTS server
4. Audio is returned in WAV format and streamed to the call

## Testing

1. Make sure your Chatterbox TTS server is running
2. Set `TTS_PROVIDER=chatterbox` in the web interface or config
3. Restart your agent: `python agent.py dev`
4. Make a test call from the web interface

## Troubleshooting

### "Chatterbox TTS not available"
- Make sure `livekit_chatterbox_tts.py` exists in the project root
- Ensure `httpx` is installed: `pip install httpx`
- Verify your Chatterbox TTS server is running and accessible

### "Connection refused" or API errors
- Check that your Chatterbox TTS server is running
- Verify the API URL is correct (default: `http://localhost:8004`)
- Test the server directly: `curl http://localhost:8004/v1/audio/speech`

### Audio quality issues
- Check that your voice file exists in the Chatterbox server's voices folder
- Verify the sample rate matches (Chatterbox default: 24000 Hz)
- Adjust TTS speed if audio sounds too fast/slow

## Switching Back to ElevenLabs

Simply change `TTS_PROVIDER` back to `"elevenlabs"` in the web interface or config file.
