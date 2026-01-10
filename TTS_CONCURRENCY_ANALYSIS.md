# TTS Concurrency Analysis: 3 Calls Simultaneously

## Your System Specs ✅

- **CPU:** 8 cores, 16 logical processors (threads)
- **RAM:** 16 GB
- **TTS:** Piper TTS (CPU-only mode)
- **Model:** en_US-lessac-medium.onnx (~50MB)

## Performance Analysis

### ✅ **VIABILITY: YES, 3 calls should work well**

### Performance Characteristics

From the local-livekit-plugins documentation and your setup:

**Piper TTS (CPU) Performance:**
- Per character: **~9ms**
- Short response (30 chars): **~270ms**
- Long response (130 chars): **~1200ms**

**With 3 concurrent calls:**
- Each call has its own TTS instance
- Each TTS instance loads the model once (~50MB RAM per instance)
- Total RAM: ~150MB for 3 TTS instances (negligible on 16GB system)
- CPU: TTS uses 1-2 CPU cores per synthesis
- With 16 logical processors, you have plenty of headroom

### Bottlenecks to Watch

1. **TTS Synthesis Latency**
   - ✅ **Short responses (30 chars):** ~270ms per call = **~810ms total** spread across 16 CPUs = **Very manageable**
   - ⚠️ **Long responses (130 chars):** ~1200ms per call = **~3600ms total** = Still fine but noticeable delay
   - **Impact:** Agent responses will have a slight delay, but should be acceptable

2. **CPU Usage**
   - ✅ With 16 logical processors, 3 concurrent TTS syntheses (each using 1-2 cores) = **6 cores max**
   - ✅ **Still have 10+ cores free** for other operations (STT, LLM API calls, etc.)

3. **Memory**
   - ✅ Each TTS instance: ~50MB model + ~50MB runtime = ~100MB
   - ✅ 3 calls: ~300MB total
   - ✅ **Well within your 16GB RAM**

4. **Model Loading**
   - ✅ Model is loaded once per TTS instance
   - ✅ No contention issues (each call has its own instance)

## Real-World Performance Estimate

### Best Case Scenario
- **Short agent responses** (~30 chars each)
- **Staggered timing** (calls start 1-2 seconds apart)
- **Expected latency:** +200-400ms per response (barely noticeable)

### Worst Case Scenario
- **Long agent responses** (~130 chars each)
- **Simultaneous agent speech** (all 3 agents talking at once)
- **Expected latency:** +800-1200ms per response (noticeable but acceptable)

### Typical Scenario
- **Mixed response lengths**
- **Some overlap, some sequential**
- **Expected latency:** +300-600ms average (very acceptable)

## Recommendations

### ✅ **GO AHEAD: 3 calls is viable!**

**Reasons:**
1. ✅ Sufficient CPU resources (16 threads, only need ~6 for TTS)
2. ✅ Sufficient RAM (only ~300MB for 3 TTS instances)
3. ✅ Piper TTS is efficient (CPU-only is actually quite fast)
4. ✅ Async/await architecture handles concurrency well
5. ✅ Each call is independent (no shared state issues)

### Optimization Tips

If you experience issues:

1. **Increase response speed:**
   ```python
   # In config.json
   "tts_speed": 1.2  # Slightly faster (reduces synthesis time)
   ```

2. **Stagger call starts:**
   ```python
   # Already configured in dispatch_calls_parallel.py
   MAX_CONCURRENT_CALLS = 3
   CALL_START_DELAY = 1.0  # 1 second between call starts
   ```

3. **Monitor CPU usage:**
   ```powershell
   # Watch CPU usage while running
   Get-Counter '\Processor(_Total)\% Processor Time'
   ```

4. **If you need more:**
   - 4-5 calls: **Still viable** with your specs
   - 6+ calls: **May experience noticeable delays**
   - **Consider GPU** if you need 10+ concurrent calls (but you wanted CPU-only)

## Testing Strategy

### Test 3 Calls:

1. **Start 3 calls simultaneously:**
   ```python
   # In dispatch_calls_parallel.py
   MAX_CONCURRENT_CALLS = 3
   ```

2. **Monitor:**
   - CPU usage (should stay under 60-70%)
   - Memory usage (should be <1GB for all calls)
   - Response latency (should be <1 second for short responses)
   - Audio quality (should be clear, no dropouts)

3. **Watch for:**
   - ⚠️ Stuttering or choppy audio
   - ⚠️ Long delays between user speech and agent response
   - ⚠️ CPU usage spiking to 100%
   - ⚠️ Memory leaks (RAM growing over time)

## Expected Results

### ✅ **Most Likely Outcome:**
- **3 calls will work smoothly**
- **Slight latency increase** (~300-600ms per response)
- **No audio quality issues**
- **CPU usage: 40-60%**
- **All calls complete successfully**

### ⚠️ **If You Experience Issues:**
- Reduce to 2 concurrent calls
- Or optimize TTS settings (speed, model size)
- Or consider GPU (but defeats CPU-only preference)

## Comparison: CPU vs GPU for 3 Calls

| Metric | CPU (Your Setup) | GPU (Hypothetical) |
|--------|------------------|-------------------|
| **Latency** | ~270-1200ms | ~100-400ms |
| **Concurrent** | ✅ 3-5 calls | ✅ 10+ calls |
| **Quality** | ✅ Same | ✅ Same |
| **Complexity** | ✅ Simple | ⚠️ CUDA setup |
| **Cost** | ✅ Free | ⚠️ GPU required |

**For 3 calls, CPU is perfectly adequate!**

## Conclusion

### ✅ **YES: 3 concurrent calls is very viable with your setup**

**Expected performance:**
- ✅ Smooth operation
- ✅ Acceptable latency (~300-600ms per response)
- ✅ No quality issues
- ✅ CPU headroom for growth

**You can safely test 3 calls and likely scale to 4-5 if needed.**

---

**Next Steps:**
1. Test with 3 calls and monitor performance
2. If successful, consider testing 4-5 calls
3. Only consider GPU if you need 10+ concurrent calls
