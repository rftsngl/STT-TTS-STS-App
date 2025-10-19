"""
STT Provider Selection and Fallback System.
Handles switching between ElevenLabs STT and Faster-Whisper with automatic fallback.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.config import get_settings
from app.voice_utils import get_eleven_provider
from providers.elevenlabs_tts import ElevenLabsError


class STTProviderError(Exception):
    """Exception raised when STT provider fails."""
    pass


class STTProvider:
    """Base class for STT providers."""
    
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: Optional[str] = None,
        timestamps: bool = False,
    ) -> Dict[str, Any]:
        """
        Transcribe audio file.
        
        Args:
            audio_path: Path to audio file (WAV format)
            language: Optional language code
            timestamps: Whether to include timestamps
            
        Returns:
            Dictionary with transcription results
        """
        raise NotImplementedError


class ElevenLabsSTTProvider(STTProvider):
    """ElevenLabs Speech-to-Text provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize ElevenLabs STT provider."""
        self.provider = get_eleven_provider(require=False, api_key=api_key)
        if self.provider is None:
            raise STTProviderError("ElevenLabs API key not configured")
    
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: Optional[str] = None,
        timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe audio using ElevenLabs STT API."""
        try:
            # Read audio file
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            
            # Call ElevenLabs STT API (synchronous version)
            result = self.provider.transcribe_audio_sync(
                audio_data,
                language=language,
                timestamps=timestamps,
            )
            
            # Convert ElevenLabs format to our standard format
            return self._convert_result(result, timestamps)
            
        except ElevenLabsError as exc:
            logger.error("ElevenLabs STT failed: {}", exc)
            raise STTProviderError(f"ElevenLabs STT error: {exc.detail}") from exc
        except Exception as exc:
            logger.error("ElevenLabs STT unexpected error: {}", exc)
            raise STTProviderError(f"ElevenLabs STT failed: {str(exc)}") from exc
    
    def _convert_result(self, result: Dict[str, Any], timestamps: bool) -> Dict[str, Any]:
        """Convert ElevenLabs result format to standard format."""
        text = result.get("text", "")
        
        # Build segments from ElevenLabs response
        segments = []
        if timestamps and "segments" in result:
            for seg in result["segments"]:
                segment = {
                    "text": seg.get("text", ""),
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                }
                if "words" in seg:
                    segment["words"] = seg["words"]
                segments.append(segment)
        elif text:
            # Create a single segment if no timestamp data
            segments = [{"text": text, "start": 0.0, "end": 0.0}]
        
        return {
            "text": text,
            "segments": segments,
            "language": result.get("language", ""),
            "provider": "elevenlabs",
        }


class FasterWhisperSTTProvider(STTProvider):
    """Faster-Whisper local STT provider - DISABLED."""

    def __init__(self):
        """Initialize Faster-Whisper STT provider - DISABLED."""
        raise STTProviderError(
            "Faster-Whisper STT provider is disabled. Please use ElevenLabs STT instead."
        )

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: Optional[str] = None,
        timestamps: bool = False,
    ) -> Dict[str, Any]:
        """Transcribe audio using Faster-Whisper - DISABLED."""
        raise STTProviderError(
            "Faster-Whisper STT provider is disabled. Please use ElevenLabs STT instead."
        )


class STTProviderManager:
    """Manages STT provider selection and fallback."""
    
    def __init__(self):
        """Initialize STT provider manager."""
        self.settings = get_settings()
    
    def get_provider(self, provider_name: Optional[str] = None) -> STTProvider:
        """
        Get STT provider instance.

        Args:
            provider_name: Optional provider name override

        Returns:
            STTProvider instance
        """
        provider_name = provider_name or self.settings.stt_provider

        # Faster-Whisper is disabled, always use ElevenLabs
        if provider_name == "faster-whisper":
            logger.warning("Faster-Whisper is disabled, using ElevenLabs instead")
            provider_name = "elevenlabs"

        if provider_name == "elevenlabs":
            try:
                api_key = self.settings.elevenlabs_stt_api_key or self.settings.xi_api_key
                return ElevenLabsSTTProvider(api_key=api_key)
            except STTProviderError as exc:
                logger.error("ElevenLabs STT provider unavailable: {}", exc)
                raise STTProviderError(
                    "ElevenLabs STT is not available. Please configure your API key."
                ) from exc

        else:
            raise STTProviderError(
                f"Unknown STT provider: {provider_name}. Only ElevenLabs is supported."
            )
    
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: Optional[str] = None,
        timestamps: bool = False,
        provider_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribe audio with automatic fallback.
        
        Args:
            audio_path: Path to audio file
            language: Optional language code
            timestamps: Whether to include timestamps
            provider_name: Optional provider override
            
        Returns:
            Transcription result dictionary
        """
        try:
            provider = self.get_provider(provider_name)
            logger.info("Using STT provider: {}", provider.__class__.__name__)
            return provider.transcribe(audio_path, language=language, timestamps=timestamps)
        except STTProviderError as exc:
            logger.error("STT transcription failed: {}", exc)
            raise


# Global instance
_manager: Optional[STTProviderManager] = None


def get_stt_manager() -> STTProviderManager:
    """Get global STT provider manager instance."""
    global _manager
    if _manager is None:
        _manager = STTProviderManager()
    return _manager

