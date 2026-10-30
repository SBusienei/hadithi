from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    detected_language: str
    language_probability: float
    model: str


class FasterWhisperTranscriber:
    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        self.model_name = os.getenv("WHISPER_MODEL", "base")
        self.model = WhisperModel(
            self.model_name,
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            cpu_threads=int(os.getenv("WHISPER_CPU_THREADS", "4")),
            num_workers=1,
        )

    def transcribe(self, audio_path: Path, language: str) -> TranscriptionResult:
        segments, info = self.model.transcribe(
            str(audio_path),
            language=language,
            beam_size=1,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 350,
                "speech_pad_ms": 250,
            },
            condition_on_previous_text=False,
            initial_prompt=(
                "Luanda Magere, Lwanda Magere, Luo, Kano Plains, Kisumu, Kenya."
                if language == "en"
                else "Luanda Magere, Lwanda Magere, Waluo, Uwanda wa Kano, Kisumu, Kenya."
            ),
            hotwords="Luanda Magere Lwanda Magere Luo Kano Plains Kisumu Kenya",
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return TranscriptionResult(
            text=text,
            detected_language=info.language,
            language_probability=info.language_probability,
            model=self.model_name,
        )


@lru_cache(maxsize=1)
def get_transcriber() -> FasterWhisperTranscriber:
    return FasterWhisperTranscriber()
