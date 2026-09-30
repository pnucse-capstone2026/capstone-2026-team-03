from datetime import timedelta
from pathlib import Path
from time import monotonic

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import (
    CorrectionFeedback,
    PronunciationAnalysis,
    PronunciationError,
)
from .services.alignment import error_rows, pronunciation_score_with_variants
from .services.analyzer import AnalyzerTemporaryError, run_analyzer
from .services.ipa_variants import ipa_sequences_from_variants
from .services.qwen import QwenFeedbackError, generate_feedback


@shared_task(name="pronunciation.healthcheck")
def healthcheck():
    return "ok"


@shared_task(bind=True, max_retries=2, name="pronunciation.process_analysis")
def process_analysis(self, analysis_id, audio_path):
    started_at = monotonic()
    cleanup_audio = True
    try:
        analysis = PronunciationAnalysis.objects.select_related("sentence").get(id=analysis_id)
        analysis.status = PronunciationAnalysis.Status.PROCESSING
        analysis.failure_reason = ""
        analysis.save(update_fields=["status", "failure_reason", "updated_at"])

        result = run_analyzer(audio_path, analysis.target_ipa)
        recognized_ipa = result["recognized_ipa"]
        if not isinstance(recognized_ipa, list):
            raise ValueError("recognized_ipa는 배열이어야 합니다.")

        target_ipa_variants = ipa_sequences_from_variants(
            analysis.target_ipa,
            analysis.sentence.cached_ipa_variants,
        )
        score, alignment, matched_variant = pronunciation_score_with_variants(
            target_ipa_variants,
            recognized_ipa,
        )
        errors = error_rows(alignment, analysis.sentence.word_spans)
        feedback = None
        try:
            feedback = generate_feedback(
                sentence=analysis.sentence.text,
                target_ipa=matched_variant["ipa"],
                recognized_ipa=recognized_ipa,
                score=score,
                errors=errors,
            )
        except QwenFeedbackError as exc:
            # A feedback outage must not discard the completed acoustic analysis.
            result.setdefault("analyzer_metadata", {})["qwen_feedback_error"] = str(exc)
            feedback = _fallback_feedback(
                sentence=analysis.sentence.text,
                score=score,
                errors=errors,
                reason=str(exc),
            )
        completed_at = timezone.now()

        with transaction.atomic():
            analysis.target_ipa = matched_variant["ipa"]
            analysis.recognized_ipa = recognized_ipa
            analysis.alignment = alignment
            analysis.score = score
            analysis.status = PronunciationAnalysis.Status.COMPLETED
            analysis.processing_ms = int((monotonic() - started_at) * 1000)
            analysis.analyzer_metadata = {
                **result.get("analyzer_metadata", {}),
                "matched_ipa_variant": matched_variant,
                "ipa_variant_count": len(target_ipa_variants),
            }
            analysis.expires_at = (
                None if analysis.consent_to_store else completed_at + timedelta(minutes=30)
            )
            analysis.save(
                update_fields=[
                    "target_ipa",
                    "recognized_ipa",
                    "alignment",
                    "score",
                    "status",
                    "processing_ms",
                    "analyzer_metadata",
                    "expires_at",
                    "updated_at",
                ]
            )
            PronunciationError.objects.filter(analysis=analysis).delete()
            PronunciationError.objects.bulk_create(
                [PronunciationError(analysis=analysis, **row) for row in errors]
            )
            _save_feedback(analysis, feedback)
            _save_error_feedback(analysis, feedback)

        _schedule_expiration(analysis)
        return {"analysis_id": str(analysis.id), "status": analysis.status}
    except PronunciationAnalysis.DoesNotExist:
        return {"analysis_id": str(analysis_id), "status": "deleted"}
    except AnalyzerTemporaryError as exc:
        if self.request.retries < self.max_retries:
            cleanup_audio = False
            raise self.retry(exc=exc, countdown=2 ** (self.request.retries + 1))
        _mark_failed(analysis_id, exc, started_at)
        return {"analysis_id": str(analysis_id), "status": "failed"}
    except Exception as exc:
        _mark_failed(analysis_id, exc, started_at)
        return {"analysis_id": str(analysis_id), "status": "failed"}
    finally:
        if cleanup_audio:
            Path(audio_path).unlink(missing_ok=True)


@shared_task(name="pronunciation.delete_expired_analysis")
def delete_expired_analysis(analysis_id):
    deleted, _ = PronunciationAnalysis.objects.filter(
        id=analysis_id,
        consent_to_store=False,
        expires_at__isnull=False,
        expires_at__lte=timezone.now(),
    ).delete()
    return deleted > 0


def _save_feedback(analysis, feedback):
    if not feedback:
        return
    CorrectionFeedback.objects.update_or_create(
        analysis=analysis,
        defaults={
            "summary": feedback.get("summary", "발음 분석이 완료되었습니다."),
            "content": feedback.get("content", ""),
            "priority_items": feedback.get("priority_items", []),
            "structured_output": feedback.get("structured_output", {}),
            "model_name": feedback.get("model_name", ""),
            "model_version": feedback.get("model_version", ""),
            "is_validated": feedback.get("is_validated", False),
        },
    )


def _fallback_feedback(*, sentence, score, errors, reason):
    priority_items = []
    for error in errors[:3]:
        target_phone = error.get("target_phone") or "목표 음소"
        recognized_phone = error.get("recognized_phone") or "누락"
        priority_items.append(f"{target_phone} → {recognized_phone}")
    if not priority_items:
        priority_items = ["현재 발음 흐름 유지"]

    if score >= 85:
        summary = "전반적으로 좋은 발음입니다."
        content = (
            f"'{sentence}' 문장은 안정적으로 발음되었습니다. "
            "현재 속도를 유지하면서 모음과 받침을 조금 더 또렷하게 마무리해 보세요."
        )
    elif score >= 60:
        summary = "일부 음소를 다시 점검해 보세요."
        content = (
            f"'{sentence}'에서 몇몇 음소 차이가 감지되었습니다. "
            "문장을 바로 빠르게 반복하기보다, 표시된 IPA 차이를 한 음소씩 천천히 맞춘 뒤 다시 녹음해 보세요."
        )
    else:
        summary = "천천히 끊어서 다시 연습해 보세요."
        content = (
            f"'{sentence}'의 목표 IPA와 인식된 발음 차이가 큽니다. "
            "먼저 단어 단위로 끊어 읽고, 받침과 첫소리를 분명히 낸 뒤 문장 전체를 연결해 보세요."
        )

    error_feedback = []
    for error in errors[:10]:
        target_phone = error.get("target_phone") or "목표 음소"
        recognized_phone = error.get("recognized_phone") or "누락"
        error_feedback.append(
            {
                "sequence": error["sequence"],
                "summary": f"{target_phone} 발음을 확인하세요.",
                "content": (
                    f"정답은 {target_phone}인데 {recognized_phone}처럼 인식되었습니다. "
                    "입 모양과 혀 위치를 천천히 맞춘 뒤 짧게 반복해 보세요."
                ),
                "practice_tip": f"{target_phone} 소리를 3번 천천히 낸 뒤 문장 안에서 다시 말해 보세요.",
            }
        )

    return {
        "summary": summary,
        "content": content,
        "priority_items": priority_items,
        "structured_output": {
            "error_feedback": error_feedback,
            "fallback_reason": reason,
        },
        "model_name": "django-fallback-feedback",
        "model_version": "local-rule-v1",
        "is_validated": False,
    }


def _save_error_feedback(analysis, feedback):
    if not feedback:
        return
    items = feedback.get("structured_output", {}).get("error_feedback", [])
    by_sequence = {item.get("sequence"): item for item in items if isinstance(item, dict)}
    for error in PronunciationError.objects.filter(analysis=analysis):
        item = by_sequence.get(error.sequence)
        if item is None:
            continue
        error.specific_feedback = {
            key: item[key] for key in ("summary", "content", "practice_tip") if key in item
        }
        error.save(update_fields=["specific_feedback"])


def _mark_failed(analysis_id, exc, started_at):
    try:
        analysis = PronunciationAnalysis.objects.get(id=analysis_id)
    except PronunciationAnalysis.DoesNotExist:
        return

    failed_at = timezone.now()
    analysis.status = PronunciationAnalysis.Status.FAILED
    analysis.failure_reason = f"{type(exc).__name__}: {exc}"[:2000]
    analysis.processing_ms = int((monotonic() - started_at) * 1000)
    analysis.expires_at = None if analysis.consent_to_store else failed_at + timedelta(minutes=30)
    analysis.save(
        update_fields=[
            "status",
            "failure_reason",
            "processing_ms",
            "expires_at",
            "updated_at",
        ]
    )
    _schedule_expiration(analysis)


def _schedule_expiration(analysis):
    if analysis.expires_at is not None:
        delete_expired_analysis.apply_async(args=[str(analysis.id)], eta=analysis.expires_at)
