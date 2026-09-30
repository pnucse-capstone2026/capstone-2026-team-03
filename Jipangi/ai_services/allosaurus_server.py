#!/usr/bin/env python3
"""Internal HTTP service for the selected Korean Allosaurus checkpoint.

This service intentionally binds to 127.0.0.1 by default.  Django sends WAV
bytes to it; it must never be exposed as a public endpoint.
"""

import argparse
import json
import logging
import tempfile
import threading
from argparse import Namespace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from allosaurus.am.utils import torch_load
from allosaurus.app import read_recognizer


LOGGER = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 20 * 1024 * 1024


class RecognitionService:
    def __init__(self, model_dir: Path, checkpoint: Path, device_id: int):
        if not model_dir.is_dir():
            raise ValueError(f"Allosaurus model directory does not exist: {model_dir}")
        if not checkpoint.is_file():
            raise ValueError(f"Allosaurus checkpoint does not exist: {checkpoint}")

        config = Namespace(
            model=model_dir.name,
            device_id=device_id,
            lang="ipa",
            approximate=False,
            prior=None,
        )
        self.recognizer = read_recognizer(config, model_dir.parent)
        # read_recognizer loads model.pt.  Explicitly re-load the chosen best-PER
        # checkpoint so the runtime cannot silently use a different snapshot.
        torch_load(self.recognizer.am, checkpoint, device_id)
        self.model_dir = model_dir
        self.checkpoint = checkpoint
        self.device_id = device_id
        self._lock = threading.Lock()

    def recognize(self, wav_bytes: bytes) -> list[str]:
        if not wav_bytes:
            raise ValueError("empty audio")
        if len(wav_bytes) > MAX_AUDIO_BYTES:
            raise ValueError("audio exceeds 20 MiB")

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(wav_bytes)
            audio_file.flush()
            # The recognizer contains a shared PyTorch model.  Serializing calls
            # avoids concurrent CPU inference contention and keeps results stable.
            with self._lock:
                phones = self.recognizer.recognize(
                    audio_file.name, lang_id="ipa", topk=1, emit=1.0, timestamp=False
                )
        return [phone for phone in str(phones).split() if phone]


def make_handler(service: RecognitionService):
    class Handler(BaseHTTPRequestHandler):
        server_version = "JipangiAllosaurus/1.0"

        def do_GET(self):
            if self.path != "/healthz":
                self._json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
                return
            self._json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "model": service.model_dir.name,
                    "checkpoint": service.checkpoint.name,
                    "device": "cpu" if service.device_id < 0 else f"cuda:{service.device_id}",
                },
            )

        def do_POST(self):
            if self.path != "/v1/recognize":
                self._json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_AUDIO_BYTES:
                    raise ValueError("invalid audio size")
                phones = service.recognize(self.rfile.read(length))
                self._json(HTTPStatus.OK, {"recognized_ipa": phones})
            except ValueError as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"detail": str(exc)})
            except Exception:
                LOGGER.exception("Allosaurus recognition failed")
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"detail": "recognition failed"})

        def log_message(self, format, *args):
            LOGGER.info("%s - %s", self.address_string(), format % args)

        def _json(self, status: HTTPStatus, payload: dict):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    parser.add_argument("--device-id", type=int, default=-1)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "allosaurus/allosaurus/pretrained/kspon_ko_v3_expanded_resume_epoch27_to40",
    )
    parser.add_argument("--checkpoint", type=Path, default=None)
    args = parser.parse_args()

    model_dir = args.model_dir.resolve()
    checkpoint = (args.checkpoint or model_dir / "model_0.08876.pt").resolve()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    service = RecognitionService(model_dir, checkpoint, args.device_id)
    LOGGER.info("Loaded Allosaurus checkpoint: %s", checkpoint)
    ThreadingHTTPServer((args.host, args.port), make_handler(service)).serve_forever()


if __name__ == "__main__":
    main()
