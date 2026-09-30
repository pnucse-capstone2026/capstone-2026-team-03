import threading
from pathlib import Path

from django.conf import settings


_MODEL = None
_MODEL_LOCK = threading.Lock()


def transcribe_korean_audio(audio_path):
    model = _get_model()
    segments, info = model.transcribe(
        str(audio_path),
        language="ko",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    segment_rows = [
        {
            "start": round(float(segment.start), 2),
            "end": round(float(segment.end), 2),
            "text": segment.text.strip(),
        }
        for segment in segments
        if segment.text.strip()
    ]
    text = " ".join(row["text"] for row in segment_rows).strip()
    return {
        "text": text,
        "language": info.language,
        "language_probability": round(float(info.language_probability or 0), 4),
        "duration": round(float(info.duration or 0), 2),
        "segments": segment_rows,
        "model": settings.WHISPER_MODEL_SIZE,
    }


def _get_model():
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                from faster_whisper import WhisperModel

                _MODEL = WhisperModel(
                    settings.WHISPER_MODEL_SIZE,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE,
                    download_root=str(Path(settings.BASE_DIR) / "models" / "whisper"),
                )
    return _MODEL
