# Remote Access Setup for Web Server

This guide explains how to allow your friend to access the web server and make edits to your agent configuration.

## Quick Start

### 1. Set a Password (Recommended)

For security, set a password before exposing the server:

```powershell
# In PowerShell, set environment variable
$env:WEB_SERVER_PASSWORD = "your-secure-password-here"

# Then start the server
.\venv\Scripts\python.exe web_server.py
```

Or create a `.env.local` file:
```
WEB_SERVER_PASSWORD=your-secure-password-here
```

### 2. Start the Server

The server now listens on `0.0.0.0` by default, which means it's accessible from your local network:

```powershell
.\venv\Scripts\python.exe web_server.py
```

You'll see:
```
🚀 Starting web server on http://0.0.0.0:5000
📝 Access the configuration interface at http://0.0.0.0:5000
```

## Access Methods

### Option 1: Local Network (Same WiFi/LAN)

If your friend is on the same network:

1. **Find your computer's IP address:**
   ```powershell
   ipconfig
   ```
   Look for "IPv4 Address" (e.g., `192.168.1.100`)

2. **Your friend accesses:**
   ```
   http://YOUR_IP_ADDRESS:5000
   ```
   Example: `http://192.168.1.100:5000`

3. **If password is set**, your friend will be prompted for:
   - Username: (can be anything, not checked)
   - Password: (the password you set)

### Option 2: Internet Access via ngrok (Recommended for External Access)

For access from anywhere on the internet:

1. **Install ngrok:**
   - Download from https://ngrok.com/download
   - Or use: `choco install ngrok` (if you have Chocolatey)

2. **Start ngrok tunnel:**
   ```powershell
   ngrok http 5000
   ```

3. **You'll get a public URL like:**
   ```
   https://abc123.ngrok.io
   ```

4. **Share this URL with your friend** - they can access it from anywhere!

5. **For password protection**, set the password as described above.

### Option 3: Port Forwarding (Advanced)

If you have router access:

1. Forward external port (e.g., 8080) to your computer's port 5000
2. Access via: `http://YOUR_PUBLIC_IP:8080`

**Note:** This exposes your server to the internet - **always use a password!**

## Security Features

### Password Protection

The web server supports Basic Authentication:

- Set `WEB_SERVER_PASSWORD` environment variable
- If set, all `/api/*` routes require authentication
- Frontend will prompt for username/password

**Important:** Use a strong password when exposing to the internet!

### CORS Protection

CORS is enabled to allow cross-origin requests, but you should:
- Only share the URL with trusted people
- Use HTTPS when possible (via ngrok or reverse proxy)
- Set a strong password

## Making Changes

### How Your Friend Can Edit Configuration

1. **Access the web interface** (via one of the methods above)
2. **Make changes** in the web form
3. **Click "Save Configuration"**
4. **Agent reload:**
   - The web server will signal that a reload is needed
   - You'll need to **manually restart the agent** for changes to take effect
   - The agent reads config on startup, so restart is required

### Restarting the Agent

After your friend makes changes, restart your agent:

```powershell
# Stop the current agent (Ctrl+C)
# Then restart it
.\venv\Scripts\python.exe agent.py dev
```

Or if running as a service, restart the service.

## Testing Remote Access

### From Your Computer

Test locally first:
```
http://localhost:5000
```

### From Friend's Computer

1. **Same network:** `http://YOUR_IP:5000`
2. **Via ngrok:** `https://YOUR_NGROK_URL.ngrok.io`

### Check Server Logs

The server will log all requests:
```
INFO web-server: GET /api/config
INFO web-server: POST /api/config
```

## Troubleshooting

### "Connection Refused"

- **Check firewall:** Windows Firewall may be blocking port 5000
  ```powershell
  # Allow port 5000 through firewall
  New-NetFirewallRule -DisplayName "Web Server" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
  ```

- **Check server is running:** Make sure `web_server.py` is running
- **Check IP address:** Verify you're using the correct IP

### "Authentication Required"

- This is normal if you set `WEB_SERVER_PASSWORD`
- Your friend needs to enter the password when prompted
- Username can be anything (not checked)

### Changes Not Taking Effect

- **Agent must be restarted** after config changes
- The web server only updates `config.json`
- The agent reads config on startup, so restart is required

## Example Setup Script

Create `start_web_server.ps1`:

```powershell
# Set password
$env:WEB_SERVER_PASSWORD = "your-password-here"

# Get your IP address
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}).IPAddress
Write-Host "Server will be accessible at: http://$ip:5000" -ForegroundColor Green

# Start server
.\venv\Scripts\python.exe web_server.py
```

## Security Best Practices

1. **Always use a password** when exposing to network/internet
2. **Use HTTPS** when possible (ngrok provides this automatically)
3. **Limit access** - only share URL with trusted people
4. **Monitor logs** - check for suspicious activity
5. **Keep it updated** - keep dependencies updated
6. **Don't expose sensitive data** - the web interface shows config, including API keys

## Summary

1. Set `WEB_SERVER_PASSWORD` (recommended)
2. Start server: `.\venv\Scripts\python.exe web_server.py`
3. Share URL:
   - **Local network:** `http://YOUR_IP:5000`
   - **Internet:** Use ngrok: `ngrok http 5000`
4. Friend makes changes via web interface
5. **You restart the agent** to apply changes

The web server is now accessible remotely! 🚀
