from __future__ import annotations

from pathlib import Path
from .models import Segment, TranscriptSpan


def transcribe(video_path: Path, model_size: str = "small") -> list[TranscriptSpan]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Speech transcription is optional. Install it with: pip install -e '.[speech]'"
        ) from exc

    model = WhisperModel(model_size, device="auto", compute_type="int8")
    spans: list[TranscriptSpan] = []
    result, _ = model.transcribe(str(video_path), vad_filter=True)
    for seg in result:
        text = seg.text.strip()
        if text:
            spans.append(TranscriptSpan(start=float(seg.start), end=float(seg.end), text=text))
    return spans


def attach_transcript(segments: list[Segment], spans: list[TranscriptSpan]) -> list[Segment]:
    for seg in segments:
        texts: list[str] = []
        for span in spans:
            overlap = min(seg.end, span.end) - max(seg.start, span.start)
            if overlap > 0:
                texts.append(span.text)
        seg.speech = " ".join(texts).strip()
    return segments
