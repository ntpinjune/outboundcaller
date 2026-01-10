# How to Let Your Friend Access the Web Server

## Current Status ✅

- ✅ Web server is running on port 5000
- ✅ Password is set
- ✅ ngrok is installed and configured
- ⏳ Just need to start ngrok tunnel

## 3 Simple Steps

### Step 1: Start ngrok Tunnel

**Open a NEW terminal window** (keep the web server terminal open), then run:

```powershell
cd C:\Users\Nolan\Desktop\outboundcaller-1
.\ngrok.exe http 5000
```

### Step 2: Copy the ngrok URL

You'll see output like this:

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

**Copy this URL:** `https://abc123def456.ngrok.io`

(Your URL will be different - it's random each time)

### Step 3: Share with Your Friend

**Send them:**
1. **The ngrok URL:** `https://abc123def456.ngrok.io`
2. **The password you set** (they'll need it when accessing)

**They can then:**
- Open the URL in their browser
- Enter the password when prompted
- Make changes to the configuration
- Click "Save Configuration"
- You'll need to restart the agent for changes to take effect

## Important Notes

⚠️ **Keep both terminals open:**
- Terminal 1: Web server (already running)
- Terminal 2: ngrok (you need to start this)

⚠️ **The ngrok URL changes each time:**
- If you close and restart ngrok, you'll get a new URL
- You'll need to share the new URL with your friend

⚠️ **To apply changes:**
- Your friend can make changes via the web interface
- **You need to manually restart the agent** for changes to take effect:
  ```powershell
  # Stop agent (Ctrl+C)
  # Then restart:
  .\venv\Scripts\python.exe agent.py dev
  ```

## Testing It Yourself First

Before sharing with your friend, test it yourself:

1. **Open ngrok web interface:** `http://localhost:4040`
   - You'll see all incoming requests
   - Good for monitoring what your friend does

2. **Test the ngrok URL:**
   - Open the ngrok URL in your browser
   - Should show the same interface as `http://localhost:5000`
   - Enter password when prompted

## Quick Reference

**Start ngrok:**
```powershell
.\ngrok.exe http 5000
```

**View requests:**
```
http://localhost:4040
```

**Stop everything:**
- Press `Ctrl+C` in both terminals
- Or just close the terminals

## Troubleshooting

**"Port 5000 already in use":**
- The web server is already running (that's fine!)
- Just start ngrok: `.\ngrok.exe http 5000`

**"Tunnel not found":**
- Make sure web server is running
- Check: `http://localhost:5000/api/health`
- Should return `{"status": "healthy"}`

**Friend can't connect:**
- Check ngrok is running
- Verify web server is running
- Make sure password is correct
- Check firewall isn't blocking

**URL stopped working:**
- You probably restarted ngrok (new URL each time)
- Get the new URL and share it again
- Or keep ngrok running (don't close the terminal)

## Summary

1. ✅ Web server is running (you're good!)
2. Start ngrok: `.\ngrok.exe http 5000`
3. Copy the ngrok URL from the output
4. Share URL + password with your friend
5. Keep both terminals open while your friend uses it

That's it! 🚀
