"""
Chatterbox TTS integration for LiveKit Agents

A custom TTS provider that uses a local Chatterbox TTS server instead of ElevenLabs.
"""

import asyncio
import logging
from typing import Optional
from livekit import rtc
from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions
from livekit.agents._exceptions import APIError
from livekit.agents import utils
import httpx

logger = logging.getLogger("chatterbox-tts")


class ChatterboxTTS(tts.TTS):
    """Custom TTS provider for Chatterbox TTS Server"""

    def __init__(
        self,
        api_url: str = "http://localhost:8004",
        voice: str = "Emily.wav",
        model: str = "chatterbox-turbo",
        speed: float = 1.0,
        **kwargs,
    ):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False, aligned_transcript=False),
            sample_rate=24000,
            num_channels=1,
            **kwargs,
        )
        self.api_url = api_url.rstrip("/")
        self.voice = voice
        self._model = model  # Store in private attribute
        self.speed = speed
        self._client = httpx.AsyncClient(timeout=60.0)

    @property
    def model(self) -> str:
        """Get the model name for this TTS instance."""
        return self._model

    @property
    def provider(self) -> str:
        """Get the provider name for this TTS instance."""
        return "chatterbox"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS, **kwargs
    ) -> tts.ChunkedStream:
        """Synthesize speech from text using Chatterbox TTS API"""
        
        logger.info(f"Synthesizing text with Chatterbox TTS: {text[:50]}...")
        
        # Use instance speed if speed parameter not provided
        tts_speed = kwargs.get('speed', self.speed)
        
        # Build payload - Chatterbox TTS might expect different field names
        # Try OpenAI-compatible format first
        payload = {
            "model": self._model,
            "input": text,  # OpenAI uses "input"
            "voice": self.voice,
            "response_format": "wav",  # LiveKit works best with WAV
            "speed": tts_speed,
        }
        
        # Note: Some TTS servers use "text" instead of "input"
        # If this fails, we may need to adjust the payload format

        # Create a chunked stream
        url = f"{self.api_url}/v1/audio/speech"
        stream = ChatterboxChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            api_url=url,
            payload=payload,
        )
        return stream

    async def aclose(self):
        """Cleanup"""
        await self._client.aclose()


class ChatterboxChunkedStream(tts.ChunkedStream):
    """Chunked stream for Chatterbox TTS audio"""

    def __init__(
        self,
        *,
        tts: "ChatterboxTTS",
        input_text: str,
        conn_options: APIConnectOptions,
        api_url: str,
        payload: dict,
    ):
        super().__init__(
            tts=tts,
            input_text=input_text,
            conn_options=conn_options,
        )
        self._api_url = api_url
        self._payload = payload
        self._client = httpx.AsyncClient(timeout=60.0)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        """Run the synthesis and emit audio frames"""
        request_id = utils.shortuuid()
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=24000,  # Chatterbox default
            num_channels=1,
            stream=False,
            mime_type="audio/wav",
        )

        try:
            # Log the request for debugging
            logger.debug(f"Chatterbox TTS request: URL={self._api_url}, Payload={self._payload}")
            
            # Make request to Chatterbox TTS Server
            response = await self._client.post(
                self._api_url,
                json=self._payload,
                timeout=30.0,  # Add explicit timeout
            )
            
            # Log response status
            logger.debug(f"Chatterbox TTS response: status={response.status_code}")
            
            response.raise_for_status()

            # Get audio data
            audio_data = response.content
            
            if not audio_data or len(audio_data) == 0:
                logger.error("Chatterbox TTS returned empty audio data")
                from livekit.agents._exceptions import APIError
                raise APIError("TTS generation failed: Empty audio response from server")
            
            logger.debug(f"Chatterbox TTS received {len(audio_data)} bytes of audio data")

            # Push the audio data directly (AudioEmitter will handle decoding)
            output_emitter.push(audio_data)

        except httpx.TimeoutException as e:
            logger.error(f"Chatterbox TTS request timeout: {e}")
            from livekit.agents._exceptions import APIError
            raise APIError(f"TTS generation failed: Request timeout - {str(e)}")
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.text
                # Try to parse JSON error response
                if e.response.headers.get("content-type", "").startswith("application/json"):
                    error_json = e.response.json()
                    error_detail = error_json.get("detail", error_json.get("error", error_detail))
            except Exception:
                pass
            
            logger.error(
                f"Chatterbox TTS API error: {e.response.status_code} - {error_detail}. "
                f"Request URL: {self._api_url}, Payload: {self._payload}"
            )
            from livekit.agents._exceptions import APIError
            raise APIError(f"TTS generation failed: {error_detail} (status {e.response.status_code})")
        except httpx.RequestError as e:
            logger.error(f"Chatterbox TTS connection error: {e}")
            from livekit.agents._exceptions import APIError
            raise APIError(f"TTS generation failed: Connection error - {str(e)}")
        except Exception as e:
            logger.error(f"Error calling Chatterbox TTS: {e}", exc_info=True)
            from livekit.agents._exceptions import APIError
            raise APIError(f"TTS generation failed: {str(e)}") from e

    async def aclose(self) -> None:
        """Cleanup"""
        await self._client.aclose()
        await super().aclose()
