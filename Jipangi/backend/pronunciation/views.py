from datetime import timedelta
import math
from pathlib import Path

from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.exceptions import APIError

from .models import (
    PracticeSentence,
    PronunciationAnalysis,
    PronunciationCategory,
    PronunciationError,
)
from .serializers import (
    AnalysisAcceptedSerializer,
    AnalysisCreateSerializer,
    AnalysisResultSerializer,
    AnalysisStatusSerializer,
    CustomSentenceCreateSerializer,
    DIFFICULTY_TO_DB,
    RecommendationSerializer,
    RecordSerializer,
    LifestyleTranscriptionResultSerializer,
    LifestyleTranscriptionSerializer,
    SentenceDetailSerializer,
    SentenceListSerializer,
    StatisticsSummarySerializer,
    DIFFICULTY_TO_API,
)
from .services.audio import calculate_request_fingerprint, validate_audio
from .services.sentence_ipa import SentenceIpaError, build_sentence_ipa
from .services.stt import transcribe_korean_audio
from .tasks import process_analysis


PHONOLOGICAL_RULE_CATEGORY_CODES = {
    "liaison",
    "nasalization",
    "liquidization",
    "tensification",
    "aspiration",
    "palatalization",
    "h-deletion",
}


class SentenceListView(ListAPIView):
    permission_classes = (AllowAny,)
    serializer_class = SentenceListSerializer

    def get_queryset(self):
        queryset = _visible_sentences(self.request.user).select_related("category")
        category = self.request.query_params.get("category")
        difficulty = self.request.query_params.get("difficulty")

        if category:
            queryset = queryset.filter(category__code=category)
        if difficulty:
            if difficulty not in DIFFICULTY_TO_DB:
                raise APIError(
                    status_code=400,
                    code="INVALID_REQUEST",
                    message="난이도 값이 올바르지 않습니다.",
                    details={"difficulty": ["easy, normal, hard, special 중 하나여야 합니다."]},
                )
            queryset = queryset.filter(difficulty=DIFFICULTY_TO_DB[difficulty])
        return queryset


class SentenceDetailView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(responses={200: SentenceDetailSerializer})
    def get(self, request, sentence_id):
        sentence = (
            _visible_sentences(request.user)
            .filter(id=sentence_id)
            .select_related("category")
            .first()
        )
        if sentence is None:
            raise APIError(
                status_code=404,
                code="SENTENCE_NOT_FOUND",
                message="연습 문장을 찾을 수 없습니다.",
            )
        return Response(SentenceDetailSerializer(sentence).data)


class CustomSentenceCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=CustomSentenceCreateSerializer,
        responses={201: SentenceDetailSerializer, 200: SentenceDetailSerializer},
    )
    def post(self, request):
        serializer = CustomSentenceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = " ".join(serializer.validated_data["text"].split())
        try:
            ipa_data = build_sentence_ipa(text)
        except SentenceIpaError as exc:
            raise APIError(
                status_code=400,
                code="CUSTOM_SENTENCE_IPA_FAILED",
                message=str(exc),
            ) from exc

        category, _ = PronunciationCategory.objects.get_or_create(
            code="custom-sentences",
            defaults={
                "name": "사용자 지정",
                "description": "사용자가 직접 추가한 연습 문장",
            },
        )
        sentence, created = PracticeSentence.objects.get_or_create(
            created_by=request.user,
            text=text,
            defaults={
                "cached_ipa": ipa_data["cached_ipa"],
                "cached_ipa_variants": ipa_data["cached_ipa_variants"],
                "word_spans": ipa_data["word_spans"],
                "source_metadata": {
                    "source": "user_custom",
                    "created_by_user_id": request.user.id,
                    "normalized_text": ipa_data["normalized_text"],
                    "g2p_pronunciation": ipa_data["g2p_pronunciation"],
                    "converter": "g2pk+kspon-korean-ipa-v1",
                    "ipa_variant_strategy": "standard+rule-lenient-korean-v1",
                    "ipa_variant_count": len(ipa_data["cached_ipa_variants"]),
                },
                "difficulty": DIFFICULTY_TO_DB[serializer.validated_data["difficulty"]],
                "category": category,
                "is_active": True,
            },
        )
        if not created:
            sentence.cached_ipa = ipa_data["cached_ipa"]
            sentence.cached_ipa_variants = ipa_data["cached_ipa_variants"]
            sentence.word_spans = ipa_data["word_spans"]
            sentence.source_metadata = {
                **(sentence.source_metadata or {}),
                "source": "user_custom",
                "created_by_user_id": request.user.id,
                "normalized_text": ipa_data["normalized_text"],
                "g2p_pronunciation": ipa_data["g2p_pronunciation"],
                "converter": "g2pk+kspon-korean-ipa-v1",
                "ipa_variant_strategy": "standard+rule-lenient-korean-v1",
                "ipa_variant_count": len(ipa_data["cached_ipa_variants"]),
            }
            sentence.difficulty = DIFFICULTY_TO_DB[serializer.validated_data["difficulty"]]
            sentence.category = category
            sentence.is_active = True
            sentence.save(
                update_fields=[
                    "cached_ipa",
                    "cached_ipa_variants",
                    "word_spans",
                    "source_metadata",
                    "difficulty",
                    "category",
                    "is_active",
                    "updated_at",
                ]
            )
        return Response(
            SentenceDetailSerializer(sentence).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class CustomSentenceDeleteView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={204: None})
    def delete(self, request, sentence_id):
        sentence = PracticeSentence.objects.filter(
            id=sentence_id,
            created_by=request.user,
            is_active=True,
        ).first()
        if sentence is None:
            raise APIError(
                status_code=404,
                code="CUSTOM_SENTENCE_NOT_FOUND",
                message="삭제할 사용자 지정 문장을 찾을 수 없습니다.",
            )
        sentence.is_active = False
        sentence.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class SentenceRecommendationView(APIView):
    @extend_schema(responses={200: RecommendationSerializer})
    def get(self, request):
        analyses = PronunciationAnalysis.objects.filter(
            user=request.user,
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        )
        recent_analysis_ids = list(analyses.values_list("id", flat=True)[:30])
        category_error = (
            PronunciationError.objects.filter(
                analysis_id__in=recent_analysis_ids,
                analysis__sentence__category__isnull=False,
            )
            .values("analysis__sentence__category_id")
            .annotate(error_count=Count("id"))
            .order_by("-error_count", "analysis__sentence__category_id")
            .first()
        )

        analyzed_sentence_ids = analyses.values_list("sentence_id", flat=True)
        candidates = _visible_sentences(request.user).select_related("category")
        reason = "아직 학습 기록이 없어 쉬운 문장을 추천합니다."

        if category_error:
            category_id = category_error["analysis__sentence__category_id"]
            candidates = candidates.filter(category_id=category_id)
            category = candidates.first().category if candidates.exists() else None
            if category is not None:
                reason = f"최근 {category.name} 오류가 많아 해당 유형의 문장을 추천합니다."
        else:
            candidates = candidates.filter(difficulty=PracticeSentence.Difficulty.BEGINNER)

        sentence = candidates.exclude(id__in=analyzed_sentence_ids).order_by("?").first()
        if sentence is None:
            sentence = (
                _visible_sentences(request.user)
                .filter(difficulty=PracticeSentence.Difficulty.BEGINNER)
                .select_related("category")
                .order_by("?")
                .first()
            )
            reason = "새로운 추천 조건에 맞는 문장이 없어 쉬운 문장을 추천합니다."

        if sentence is None:
            raise APIError(
                status_code=404,
                code="SENTENCE_NOT_FOUND",
                message="추천할 수 있는 연습 문장이 없습니다.",
            )

        response_data = SentenceListSerializer(sentence).data
        response_data["reason"] = reason
        return Response(response_data)


class AnalysisCreateView(APIView):
    @extend_schema(request=AnalysisCreateSerializer, responses={202: AnalysisAcceptedSerializer})
    def post(self, request):
        if "audio" not in request.FILES:
            raise APIError(
                status_code=400,
                code="AUDIO_FILE_REQUIRED",
                message="음성 파일이 필요합니다.",
            )

        serializer = AnalysisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sentence = _visible_sentences(request.user).filter(
            id=serializer.validated_data["sentence_id"],
        ).first()
        if sentence is None:
            raise APIError(
                status_code=404,
                code="SENTENCE_NOT_FOUND",
                message="연습 문장을 찾을 수 없습니다.",
            )
        if not sentence.cached_ipa:
            raise APIError(
                status_code=409,
                code="SENTENCE_IPA_NOT_READY",
                message="연습 문장의 목표 IPA가 준비되지 않았습니다.",
            )

        audio_path = validate_audio(serializer.validated_data["audio"])
        request_fingerprint = calculate_request_fingerprint(
            user_id=request.user.id,
            sentence_id=sentence.id,
            audio_path=audio_path,
        )
        analysis = PronunciationAnalysis.objects.create(
            user=request.user,
            sentence=sentence,
            target_ipa=sentence.cached_ipa,
            status=PronunciationAnalysis.Status.PENDING,
            consent_to_store=serializer.validated_data["consent_to_store"],
            request_fingerprint=request_fingerprint,
        )
        try:
            process_analysis.delay(str(analysis.id), audio_path)
        except Exception as exc:
            Path(audio_path).unlink(missing_ok=True)
            analysis.delete()
            raise APIError(
                status_code=503,
                code="ANALYSIS_QUEUE_UNAVAILABLE",
                message="분석 작업을 등록할 수 없습니다.",
            ) from exc

        return Response(
            {"analysis_id": str(analysis.id), "status": "pending"},
            status=status.HTTP_202_ACCEPTED,
        )


class AnalysisStatusView(APIView):
    @extend_schema(responses={200: AnalysisStatusSerializer})
    def get(self, request, analysis_id):
        analysis = _user_analysis(request.user, analysis_id)
        return Response(
            {
                "analysis_id": str(analysis.id),
                "status": analysis.status,
                "failure_reason": analysis.failure_reason,
            }
        )


class LifestyleTranscriptionView(APIView):
    @extend_schema(
        request=LifestyleTranscriptionSerializer,
        responses={200: LifestyleTranscriptionResultSerializer},
    )
    def post(self, request):
        if "audio" not in request.FILES:
            raise APIError(
                status_code=400,
                code="AUDIO_FILE_REQUIRED",
                message="음성 파일이 필요합니다.",
            )

        serializer = LifestyleTranscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audio_path = validate_audio(serializer.validated_data["audio"])
        try:
            result = transcribe_korean_audio(audio_path)
        except Exception as exc:
            raise APIError(
                status_code=503,
                code="STT_UNAVAILABLE",
                message="음성 받아쓰기를 처리할 수 없습니다.",
            ) from exc
        finally:
            Path(audio_path).unlink(missing_ok=True)
        return Response(result)


class AnalysisResultView(APIView):
    @extend_schema(responses={200: AnalysisResultSerializer})
    def get(self, request, analysis_id):
        analysis = _user_analysis(request.user, analysis_id)
        if analysis.status in {
            PronunciationAnalysis.Status.PENDING,
            PronunciationAnalysis.Status.PROCESSING,
        }:
            raise APIError(
                status_code=409,
                code="ANALYSIS_IN_PROGRESS",
                message="발음 분석이 진행 중입니다.",
            )
        if analysis.status == PronunciationAnalysis.Status.FAILED:
            raise APIError(
                status_code=409,
                code="ANALYSIS_FAILED",
                message="발음 분석에 실패했습니다.",
            )

        analysis = (
            PronunciationAnalysis.objects.filter(id=analysis.id)
            .select_related("sentence", "feedback")
            .prefetch_related("errors")
            .get()
        )
        return Response(AnalysisResultSerializer(analysis).data)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, analysis_id):
        analysis = _user_analysis(request.user, analysis_id)
        if analysis.status in {
            PronunciationAnalysis.Status.PENDING,
            PronunciationAnalysis.Status.PROCESSING,
        }:
            raise APIError(
                status_code=409,
                code="ANALYSIS_IN_PROGRESS",
                message="진행 중인 분석은 삭제할 수 없습니다.",
            )
        analysis.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _user_analysis(user, analysis_id):
    analysis = PronunciationAnalysis.objects.filter(id=analysis_id, user=user).first()
    if analysis is None:
        raise APIError(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="발음 분석 결과를 찾을 수 없습니다.",
        )
    if (
        not analysis.consent_to_store
        and analysis.expires_at is not None
        and analysis.expires_at <= timezone.now()
    ):
        analysis.delete()
        raise APIError(
            status_code=404,
            code="ANALYSIS_NOT_FOUND",
            message="발음 분석 결과를 찾을 수 없습니다.",
        )
    return analysis


def _visible_sentences(user):
    queryset = PracticeSentence.objects.filter(is_active=True)
    if user.is_authenticated:
        return queryset.filter(Q(created_by__isnull=True) | Q(created_by=user))
    return queryset.filter(created_by__isnull=True)


class RecordListView(ListAPIView):
    serializer_class = RecordSerializer

    def get_queryset(self):
        queryset = (
            PronunciationAnalysis.objects.filter(
                user=self.request.user,
                status=PronunciationAnalysis.Status.COMPLETED,
                consent_to_store=True,
            )
            .select_related("sentence", "sentence__category")
            .annotate(error_count=Count("errors"))
            .order_by("-created_at")
        )
        category = self.request.query_params.get("category")
        difficulty = self.request.query_params.get("difficulty")
        if category:
            queryset = queryset.filter(sentence__category__code=category)
        if difficulty:
            if difficulty not in DIFFICULTY_TO_DB:
                raise APIError(
                    status_code=400,
                    code="INVALID_REQUEST",
                    message="난이도 값이 올바르지 않습니다.",
                    details={"difficulty": ["easy, normal, hard, special 중 하나여야 합니다."]},
                )
            queryset = queryset.filter(sentence__difficulty=DIFFICULTY_TO_DB[difficulty])
        return queryset


class StatisticsSummaryView(APIView):
    @staticmethod
    def _percentile(values, ratio):
        if not values:
            return 0.0
        if len(values) == 1:
            return round(values[0], 1)
        index = (len(values) - 1) * ratio
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        weight = index - lower
        return round(values[lower] * (1 - weight) + values[upper] * weight, 1)

    @staticmethod
    def _streak_days(analyses):
        dates = sorted(
            {
                timezone.localtime(row.created_at).date()
                for row in analyses.only("created_at")
            },
            reverse=True,
        )
        if not dates:
            return 0
        streak = 1
        current = dates[0]
        for practice_date in dates[1:]:
            if practice_date == current - timedelta(days=1):
                streak += 1
                current = practice_date
            elif practice_date == current:
                continue
            else:
                break
        return streak

    @staticmethod
    def _peer_rank(average_score):
        if average_score is None:
            return None
        user_rows = list(
            PronunciationAnalysis.objects.filter(
                status=PronunciationAnalysis.Status.COMPLETED,
                consent_to_store=True,
                score__isnull=False,
                user__isnull=False,
            )
            .values("user_id")
            .annotate(average_score=Avg("score"))
        )
        total_users = len(user_rows)
        if total_users < 2:
            return None
        user_average = float(average_score)
        higher_count = sum(
            1 for row in user_rows if float(row["average_score"]) > user_average
        )
        lower_count = sum(
            1 for row in user_rows if float(row["average_score"]) < user_average
        )
        rank = higher_count + 1
        return {
            "total_users": total_users,
            "rank": rank,
            "top_percent": max(1, math.ceil((rank / total_users) * 100)),
            "better_than_percent": round((lower_count / total_users) * 100, 1),
            "average_score": round(user_average, 1),
        }

    @staticmethod
    def _weekly_trend(analyses):
        now = timezone.now()
        current_start = now - timedelta(days=7)
        previous_start = now - timedelta(days=14)
        current = analyses.filter(score__isnull=False, created_at__gte=current_start).aggregate(
            average=Avg("score"),
            count=Count("id"),
        )
        previous = analyses.filter(
            score__isnull=False,
            created_at__gte=previous_start,
            created_at__lt=current_start,
        ).aggregate(
            average=Avg("score"),
            count=Count("id"),
        )
        current_average = current["average"]
        previous_average = previous["average"]
        delta = None
        status_label = "empty"
        if current_average is not None and previous_average is not None:
            delta = round(float(current_average) - float(previous_average), 1)
            if delta >= 8:
                status_label = "big_improvement"
            elif delta >= 2:
                status_label = "improved"
            elif delta > -2:
                status_label = "maintained"
            else:
                status_label = "needs_practice"
        elif current_average is not None:
            status_label = "new_week"

        return {
            "current_average": round(float(current_average), 1) if current_average is not None else None,
            "previous_average": round(float(previous_average), 1) if previous_average is not None else None,
            "delta": delta,
            "current_count": current["count"],
            "previous_count": previous["count"],
            "status": status_label,
        }

    @extend_schema(responses={200: StatisticsSummarySerializer})
    def get(self, request):
        analyses = PronunciationAnalysis.objects.filter(
            user=request.user,
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        )
        score_summary = analyses.aggregate(
            average_score=Avg("score"),
            best_score=Max("score"),
        )
        recent_scores = [
            {
                "analysis_id": str(row["id"]),
                "score": float(row["score"]),
                "created_at": row["created_at"],
            }
            for row in analyses.filter(score__isnull=False)
            .values("id", "score", "created_at")
            .order_by("-created_at")[:7]
        ]
        difficulty_rows = (
            analyses.filter(score__isnull=False)
            .values("sentence__difficulty")
            .annotate(
                count=Count("id"),
                average_score=Avg("score"),
                min_score=Min("score"),
                max_score=Max("score"),
            )
            .order_by("sentence__difficulty")
        )
        difficulty_scores = {}
        for row in analyses.filter(score__isnull=False).values("sentence__difficulty", "score"):
            difficulty_scores.setdefault(row["sentence__difficulty"], []).append(float(row["score"]))
        difficulty_stats = []
        for row in difficulty_rows:
            difficulty = row["sentence__difficulty"]
            scores = sorted(difficulty_scores.get(difficulty, []))
            difficulty_stats.append(
                {
                    "difficulty": DIFFICULTY_TO_API[difficulty],
                    "label": PracticeSentence.Difficulty(difficulty).label,
                    "count": row["count"],
                    "average_score": round(float(row["average_score"]), 1),
                    "min_score": float(row["min_score"]),
                    "q1_score": self._percentile(scores, 0.25),
                    "median_score": self._percentile(scores, 0.5),
                    "q3_score": self._percentile(scores, 0.75),
                    "max_score": float(row["max_score"]),
                }
            )
        error_queryset = PronunciationError.objects.filter(
            analysis__in=analyses,
            analysis__sentence__category__isnull=False,
        )
        error_summary = [
            {
                "category": {
                    "code": row["analysis__sentence__category__code"],
                    "name": row["analysis__sentence__category__name"],
                },
                "count": row["count"],
            }
            for row in error_queryset
            .values(
                "analysis__sentence__category__code",
                "analysis__sentence__category__name",
            )
            .annotate(count=Count("id"))
            .order_by("-count", "analysis__sentence__category__code")
        ]
        rule_error_summary = [
            row
            for row in error_summary
            if row["category"]["code"] in PHONOLOGICAL_RULE_CATEGORY_CODES
        ]

        average_score = score_summary["average_score"]
        best_score = score_summary["best_score"]
        return Response(
            {
                "total_analyses": analyses.count(),
                "total_practices": analyses.count(),
                "streak_days": self._streak_days(analyses),
                "average_score": round(float(average_score), 1) if average_score else 0.0,
                "best_score": float(best_score) if best_score is not None else 0.0,
                "recent_scores": recent_scores,
                "difficulty_stats": difficulty_stats,
                "error_summary": error_summary,
                "rule_error_summary": rule_error_summary,
                "peer_rank": self._peer_rank(average_score),
                "weekly_trend": self._weekly_trend(analyses),
            }
        )
