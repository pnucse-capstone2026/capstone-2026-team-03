import hashlib
import logging
import subprocess
import tempfile
import wave
from pathlib import Path
from uuid import uuid4

import filetype
from django.conf import settings
from mutagen import File as MutagenFile

from config.exceptions import APIError


MAX_AUDIO_SIZE = 20 * 1024 * 1024
MAX_AUDIO_DURATION = 30
logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {"wav", "wave", "m4a", "aac", "mp4", "webm", "ogg", "mp3", "caf", "mov"}
ALLOWED_MIME_TYPES = {
    "audio/aac",
    "audio/caf",
    "audio/m4a",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/wave",
    "audio/wav",
    "audio/webm",
    "audio/x-caf",
    "audio/x-m4a",
    "audio/x-wav",
    "video/mp4",
    "video/webm",
    "video/quicktime",
}
MIME_EXTENSION = {
    "audio/aac": "aac",
    "audio/caf": "caf",
    "audio/m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/ogg": "ogg",
    "audio/wave": "wav",
    "audio/wav": "wav",
    "audio/webm": "webm",
    "audio/x-caf": "caf",
    "audio/x-m4a": "m4a",
    "audio/x-wav": "wav",
    "video/mp4": "m4a",
    "video/webm": "webm",
    "video/quicktime": "mov",
}


def calculate_request_fingerprint(*, user_id, sentence_id, audio_path):
    digest = hashlib.sha256()
    digest.update(str(user_id).encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(sentence_id).encode("utf-8"))
    digest.update(b"\0")
    with Path(audio_path).open("rb") as audio:
        for chunk in iter(lambda: audio.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_audio(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";")[0].lower()
    if uploaded_file.size > MAX_AUDIO_SIZE:
        _audio_error("AUDIO_TOO_LARGE", "음성 파일은 20MB 이하여야 합니다.")

    header = uploaded_file.read(4096)
    uploaded_file.seek(0)
    kind = filetype.guess(header)
    detected_mime = kind.mime if kind is not None else ""
    if not detected_mime and content_type in ALLOWED_MIME_TYPES:
        detected_mime = content_type
    logger.info(
        "Audio upload received: name=%s size=%s extension=%s content_type=%s detected_mime=%s",
        uploaded_file.name,
        uploaded_file.size,
        extension,
        content_type,
        detected_mime or "unknown",
    )
    if detected_mime and detected_mime not in ALLOWED_MIME_TYPES:
        _audio_error("INVALID_AUDIO_FORMAT", "음성 파일의 실제 형식을 확인할 수 없습니다.")
    if extension == "wave":
        extension = "wav"
    if extension not in ALLOWED_EXTENSIONS:
        extension = MIME_EXTENSION.get(detected_mime, "")
    if extension not in ALLOWED_EXTENSIONS:
        _audio_error("INVALID_AUDIO_FORMAT", "지원하지 않는 음성 파일 형식입니다.")

    path = _write_temporary_audio(uploaded_file, extension)
    try:
        duration = _audio_duration(path, extension)
        if duration > MAX_AUDIO_DURATION:
            _audio_error("AUDIO_TOO_LONG", "음성 길이는 30초 이하여야 합니다.")
    except APIError:
        Path(path).unlink(missing_ok=True)
        raise
    except Exception as exc:
        Path(path).unlink(missing_ok=True)
        logger.warning(
            "Audio validation failed after upload: name=%s path=%s error=%s",
            uploaded_file.name,
            path,
            exc,
        )
        raise APIError(
            status_code=400,
            code="INVALID_AUDIO_FORMAT",
            message="음성 파일을 읽을 수 없습니다.",
        ) from exc
    return path


def _write_temporary_audio(uploaded_file, extension):
    directory = Path(settings.MEDIA_ROOT) / "audio_tmp"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.{extension}"
    with path.open("wb") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    uploaded_file.seek(0)
    return str(path)


def _audio_duration(path, extension):
    if extension == "wav":
        try:
            with wave.open(path, "rb") as audio:
                return audio.getnframes() / audio.getframerate()
        except wave.Error:
            pass

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        pass

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        pass

    try:
        return _decoded_wav_duration(path)
    except (OSError, subprocess.CalledProcessError, wave.Error):
        pass

    audio = MutagenFile(path)
    if audio is None or audio.info is None:
        raise ValueError("오디오 메타데이터를 읽을 수 없습니다.")
    return float(audio.info.length)


def _decoded_wav_duration(path):
    with tempfile.NamedTemporaryFile(suffix=".wav") as wav_file:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                path,
                "-ac",
                "1",
                "-ar",
                "16000",
                wav_file.name,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        with wave.open(wav_file.name, "rb") as audio:
            return audio.getnframes() / audio.getframerate()


def _audio_error(code, message):
    raise APIError(status_code=400, code=code, message=message)
