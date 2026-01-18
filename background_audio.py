import asyncio
import logging
import av
import numpy as np
import os
from livekit import rtc

logger = logging.getLogger("background-audio")

class BackgroundAudioPlayer:
    def __init__(self, room: rtc.Room, file_path: str, volume: float = 0.1):
        self.room = room
        self.file_path = file_path
        self.volume = max(0.0, min(1.0, volume)) # Clamp 0-1
        self.source = rtc.AudioSource(48000, 1)
        self.track = rtc.LocalAudioTrack.create_audio_track("background_audio", self.source)
        self._task = None
        self._running = False
        
    async def start(self):
        """Start publishing and playing the background audio."""
        if self._running:
            return
            
        if not os.path.exists(self.file_path) and not self.file_path.startswith("http"):
             logger.error(f"Background audio file not found: {self.file_path}")
             return

        self._running = True
        try:
            # Publish the track to the room
            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_UNKNOWN)
            await self.room.local_participant.publish_track(self.track, options)
            logger.info(f"Published background audio from {self.file_path} (volume={self.volume})")
            
            # Start the playback loop
            self._task = asyncio.create_task(self._play_loop())
            
        except Exception as e:
            logger.error(f"Failed to start background audio: {e}")
            self._running = False
            
    async def stop(self):
        """Stop playback."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
    async def _play_loop(self):
        logger.info("Starting background audio loop")
        
        while self._running:
            try:
                # Open with PyAV
                container = av.open(self.file_path)
                stream = container.streams.audio[0]
                
                resampler = av.AudioResampler(
                    format='s16',
                    layout='mono',
                    rate=48000
                )
                
                for frame in container.decode(stream):
                    if not self._running:
                        break
                        
                    # Resample to 48kHz mono s16
                    resampled_frames = resampler.resample(frame)
                    
                    for f in resampled_frames:
                        if not self._running:
                            break

                        # Convert to numpy for volume adjustment
                        arr = f.to_ndarray()
                        
                        # Apply volume
                        if self.volume != 1.0:
                            arr = (arr * self.volume).astype(np.int16)
                            
                        # Convert back to bytes
                        data_bytes = arr.tobytes()
                        
                        # Create LiveKit AudioFrame
                        rtc_frame = rtc.AudioFrame(
                            data=data_bytes,
                            sample_rate=48000,
                            num_channels=1,
                            samples_per_channel=f.samples
                        )
                        
                        # Push to source
                        await self.source.capture_frame(rtc_frame)
                        
                        # Calculate duration to sleep
                        duration = f.samples / 48000.0
                        await asyncio.sleep(duration)
                
                container.close()
                
                if not self._running:
                    break
                    
                # Small pause if file was very short? 
                # No, immediate loop is usually desired for bg noise.
                    
            except Exception as e:
                logger.error(f"Error in audio loop: {e}")
                await asyncio.sleep(5) # Delay before retry
