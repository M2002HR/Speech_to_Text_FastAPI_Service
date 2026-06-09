from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .dg_provider import get_dg_config, transcribe_dg_with_rotation
from .services import APITranscriber


def install_dg_runtime() -> None:
    if getattr(APITranscriber, "_dg_provider_installed", False):
        return
    original = APITranscriber.transcribe

    async def transcribe_with_dg(self: APITranscriber, provider_name: str, audio_path: Path, options: Dict[str, Any]) -> Dict[str, Any]:
        if provider_name == "deepgram":
            return await transcribe_dg_with_rotation(self, get_dg_config(self.settings), audio_path, options)
        return await original(self, provider_name, audio_path, options)

    APITranscriber.transcribe = transcribe_with_dg
    APITranscriber._dg_provider_installed = True
