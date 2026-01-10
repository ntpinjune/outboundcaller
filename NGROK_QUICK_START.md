# ngrok Quick Start Guide

This guide will help you set up ngrok to allow your friend to access the web server from anywhere on the internet.

## Quick Setup (3 Steps)

### Step 1: Install ngrok

Run the setup script:
```powershell
.\setup_ngrok.ps1
```

This will:
- Download ngrok if not installed
- Guide you through getting an auth token (free account required)
- Configure ngrok

**Or install manually:**
1. Go to https://ngrok.com/download
2. Download Windows version
3. Extract `ngrok.exe` to a folder in your PATH (or this directory)

### Step 2: Get Free ngrok Account

1. Sign up at: https://dashboard.ngrok.com/signup (free!)
2. Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken
3. Configure it:
   ```powershell
   ngrok config add-authtoken YOUR_TOKEN_HERE
   ```

### Step 3: Start Everything

**Option A: Use the all-in-one script (recommended):**
```powershell
.\start_remote_server.ps1
```

This starts both the web server and ngrok automatically.

**Option B: Start manually:**

1. **Start web server** (in one terminal):
   ```powershell
   # Optional: Set password for security
   $env:WEB_SERVER_PASSWORD = "your-password-here"
   
   # Start server
   .\venv\Scripts\python.exe web_server.py
   ```

2. **Start ngrok** (in another terminal):
   ```powershell
   ngrok http 5000
   ```

## What You'll See

After starting ngrok, you'll see something like:

```
ngrok                                                                        
                                                                              
Session Status                online                                         
Account                       Your Name (Plan: Free)                          
Version                       3.x.x                                           
Region                        United States (us)                              
Latency                       45ms                                            
Web Interface                 http://127.0.0.1:4040                           
Forwarding                    https://abc123def456.ngrok.io -> http://localhost:5000
                                                                              
Connections                   ttl     opn     rt1     rt5     p50     p90     
                              0       0       0.00    0.00    0.00    0.00    
```

## Share the URL

**The important part is this line:**
```
Forwarding    https://abc123def456.ngrok.io -> http://localhost:5000
```

**Share this URL with your friend:** `https://abc123def456.ngrok.io`

They can access it from anywhere on the internet!

## Security

### Set a Password (Recommended)

Before starting, set a password:

```powershell
$env:WEB_SERVER_PASSWORD = "your-secure-password"
```

Your friend will be prompted for:
- **Username:** (can be anything, not checked)
- **Password:** (the password you set)

### HTTPS Included

ngrok provides HTTPS automatically - the URL will be `https://` not `http://`

## Making Changes

1. Your friend accesses: `https://YOUR_NGROK_URL.ngrok.io`
2. Enters password if you set one
3. Makes changes in the web interface
4. Clicks "Save Configuration"
5. **You restart the agent** to apply changes:
   ```powershell
   # Stop current agent (Ctrl+C)
   # Then restart
   .\venv\Scripts\python.exe agent.py dev
   ```

## Monitoring

### ngrok Web Interface

ngrok provides a web interface to monitor traffic:
- **URL:** `http://127.0.0.1:4040`
- View all HTTP requests in real-time
- Inspect request/response data
- Replay requests for testing

### View Requests

Open in browser: `http://localhost:4040`

You'll see:
- All requests your friend makes
- Request details (headers, body, etc.)
- Response data
- Timeline of requests

## Troubleshooting

### "ngrok: command not found"

**Solution:** 
- If you installed to current directory, use: `.\ngrok.exe http 5000`
- Or add the directory to your PATH

### "Your account is limited"

**Free tier limits:**
- 1 tunnel at a time ✅
- 40 connections per minute ✅
- Random URLs (different each time you start) ✅

**Solution:** 
- Use the same ngrok session (don't restart)
- Or upgrade to paid plan for custom domains

### "Connection refused"

**Check:**
1. Is web server running? Test: `http://localhost:5000`
2. Is ngrok pointing to correct port? Should be `5000`
3. Try restarting both web server and ngrok

### "Tunnel closed" / URL stopped working

**Cause:** ngrok free tier assigns new URLs each time you start

**Solution:** 
- Keep ngrok running in a separate terminal
- Share the new URL when it changes
- Or use paid plan for static domain

### URL changes every time

**Free tier behavior:** URLs are random and change when you restart ngrok

**Workarounds:**
- Keep ngrok running (don't close the terminal)
- Share the new URL when you restart
- Use paid plan for custom domain (e.g., `https://my-agent.ngrok.io`)

## Advanced Usage

### Custom Subdomain (Paid Plan)

If you have a paid ngrok plan:
```powershell
ngrok http 5000 --subdomain=my-custom-name
```

### Password in Script

Create `start_with_password.ps1`:
```powershell
$env:WEB_SERVER_PASSWORD = "your-password-here"
.\venv\Scripts\python.exe web_server.py
```

Then run ngrok separately.

### Multiple Tunnels

If you need multiple tunnels (paid plan):
```powershell
# Terminal 1: Web server
ngrok http 5000 --region=us

# Terminal 2: Another service
ngrok http 8000 --region=us
```

## Summary

1. **Install:** `.\setup_ngrok.ps1`
2. **Get token:** https://dashboard.ngrok.com/get-started/your-authtoken
3. **Start:** `.\start_remote_server.ps1` OR `ngrok http 5000`
4. **Share URL:** `https://YOUR_URL.ngrok.io`
5. **Set password:** `$env:WEB_SERVER_PASSWORD = "password"` (optional but recommended)

That's it! Your friend can now access the web server from anywhere! 🚀

## Tips

- **Keep ngrok terminal open** - closing it closes the tunnel
- **Monitor requests** - use `http://localhost:4040` to see what your friend is doing
- **Set a password** - always use password when exposing to internet
- **Free tier is fine** - random URLs are fine for testing and personal use
- **Upgrade if needed** - paid plans give custom domains and more features
