# Install piper-tts in the venv
Write-Host "Installing piper-tts in venv..." -ForegroundColor Cyan
.\venv\Scripts\pip.exe install piper-tts

Write-Host "`nVerifying installation..." -ForegroundColor Cyan
.\venv\Scripts\python.exe -c "import piper; from piper import PiperVoice; print('✅ piper-tts is installed in venv')"

Write-Host "`nDone! You can now run: .\venv\Scripts\python.exe test_gpu_support.py" -ForegroundColor Green
