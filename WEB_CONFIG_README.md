# Web Configuration Interface

A web-based configuration interface for the Outbound Caller Agent that allows you to configure settings without modifying code.

## Features

- **Agent Settings**: Configure LLM provider, TTS voice, speed, and STT provider
- **Call Behavior**: Adjust timing, delays, and response timeouts
- **System Prompt Editor**: Edit the agent's conversation script directly in the web UI
- **Integration Settings**: Configure LiveKit, Google Sheets, AWS S3, and other integrations
- **Call Dispatch**: Configure call dispatch settings and retry logic

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install Flask and Flask-CORS for the web server.

### 2. Start the Web Server

```bash
python web_server.py
```

The server will start on `http://127.0.0.1:5000` by default.

### 3. Access the Web Interface

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### 4. Configure Your Agent

- Navigate through the tabs to configure different settings
- Make changes and click "Save Configuration"
- Changes are saved to `config.json`
- The agent will automatically use these settings on the next call

## Configuration Files

- **`config.json`**: Stores your configuration (created automatically on first save)
- **`config.json.example`**: Example configuration template
- **`.env.local`**: Environment variables (API keys, secrets) - still required for sensitive data

## How It Works

1. **Config Manager** (`config_manager.py`): Loads configuration from `config.json` with environment variable fallback
2. **Web Server** (`web_server.py`): Provides REST API and serves the web interface
3. **Agent Integration**: `agent.py` uses the config manager to load settings dynamically

## Configuration Priority

Settings are loaded in this order (highest priority first):
1. Environment variables (`.env.local`)
2. `config.json` (from web interface)
3. Default values

**Note**: Sensitive data (API keys, secrets) should always be stored in `.env.local` for security. The web interface will not save these values.

## System Prompt

The system prompt can be edited in the "System Prompt" tab. When you save a custom prompt:
- It's stored in `config.json`
- The agent uses it on the next call
- If no custom prompt is set, the agent uses the default prompt from `agent.py`

## API Endpoints

The web server provides these REST API endpoints:

- `GET /api/config` - Get current configuration
- `POST /api/config` - Update configuration
- `GET /api/prompt` - Get system prompt
- `POST /api/prompt` - Update system prompt
- `POST /api/test/connection` - Test LiveKit connection
- `GET /api/health` - Health check

## Security Notes

- API keys and secrets are NOT saved in `config.json` for security
- Always use `.env.local` for sensitive credentials
- The web server runs on localhost by default (not exposed to the internet)
- For production, add authentication to the web server

## Troubleshooting

### Web server won't start
- Check if port 5000 is already in use
- Install Flask: `pip install flask flask-cors`

### Changes not taking effect
- Restart the agent after saving configuration
- Check that `config.json` was created and has your changes
- Verify environment variables aren't overriding your settings

### System prompt not loading
- Make sure you saved the prompt in the web interface
- Check `config.json` has a `system_prompt` field
- If empty, the agent uses the default prompt from `agent.py`

## Next Steps

- Add authentication to the web interface
- Implement call dispatch from the web UI
- Add call history and analytics dashboard
- Export/import configuration presets
