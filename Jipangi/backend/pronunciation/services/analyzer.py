import json
import subprocess
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils.module_loading import import_string


class AnalyzerTemporaryError(Exception):
    pass


def run_analyzer(audio_path, target_ipa):
    backend = import_string(settings.PRONUNCIATION_ANALYZER_BACKEND)
    return backend(audio_path=audio_path, target_ipa=target_ipa)


def development_analyzer(*, audio_path, target_ipa):
    return {
        "recognized_ipa": list(target_ipa),
        "analyzer_metadata": {
            "backend": "development-stub",
            "warning": "실제 음성 분석 결과가 아닙니다.",
        },
        "feedback": {
            "summary": "개발용 분석이 완료되었습니다.",
            "content": "현재 개발 환경에서는 목표 IPA를 그대로 반환합니다.",
            "priority_items": [],
            "structured_output": {"development_stub": True},
            "model_name": "",
            "model_version": "",
            "is_validated": False,
        },
    }


def production_analyzer(*, audio_path, target_ipa):
    """Recognize a WAV with the internal Allosaurus checkpoint service."""
    try:
        audio_bytes = _wav_bytes(audio_path)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AnalyzerTemporaryError("음성 파일을 WAV로 변환할 수 없습니다.") from exc

    request = Request(
        f"{settings.ALLOSAURUS_URL.rstrip('/')}/v1/recognize",
        data=audio_bytes,
        headers={"Content-Type": "audio/wav", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.ALLOSAURUS_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AnalyzerTemporaryError("Allosaurus 음성 분석 서비스에 연결할 수 없습니다.") from exc

    recognized_ipa = payload.get("recognized_ipa")
    if not isinstance(recognized_ipa, list) or not all(
        isinstance(phone, str) and phone for phone in recognized_ipa
    ):
        raise AnalyzerTemporaryError("Allosaurus 응답의 IPA 형식이 올바르지 않습니다.")

    return {
        "recognized_ipa": recognized_ipa,
        "analyzer_metadata": {
            "backend": "allosaurus-http",
            "service_url": settings.ALLOSAURUS_URL,
            "target_phone_count": len(target_ipa),
        },
    }


def _wav_bytes(audio_path):
    source = Path(audio_path)
    if source.suffix.lower() == ".wav":
        return source.read_bytes()

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
                str(source),
                "-ac",
                "1",
                "-ar",
                "16000",
                wav_file.name,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return Path(wav_file.name).read_bytes()
