from rest_framework import serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field

from .models import (
    CorrectionFeedback,
    PracticeSentence,
    PronunciationAnalysis,
    PronunciationCategory,
    PronunciationError,
)
from .services.sentence_ipa import enrich_word_spans


DIFFICULTY_TO_API = {
    PracticeSentence.Difficulty.BEGINNER: "easy",
    PracticeSentence.Difficulty.INTERMEDIATE: "normal",
    PracticeSentence.Difficulty.ADVANCED: "hard",
    PracticeSentence.Difficulty.SPECIAL: "special",
}
DIFFICULTY_TO_DB = {value: key for key, value in DIFFICULTY_TO_API.items()}


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PronunciationCategory
        fields = ("code", "name")


class SentenceListSerializer(serializers.ModelSerializer):
    difficulty = serializers.SerializerMethodField()
    category = CategorySerializer()
    is_custom = serializers.SerializerMethodField()

    class Meta:
        model = PracticeSentence
        fields = ("id", "text", "difficulty", "category", "is_custom")

    @extend_schema_field(OpenApiTypes.STR)
    def get_difficulty(self, obj):
        return DIFFICULTY_TO_API[obj.difficulty]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_custom(self, obj):
        return obj.created_by_id is not None


class SentenceDetailSerializer(SentenceListSerializer):
    target_ipa = serializers.JSONField(source="cached_ipa")
    target_ipa_variants = serializers.JSONField(source="cached_ipa_variants")
    word_spans = serializers.SerializerMethodField()

    class Meta(SentenceListSerializer.Meta):
        fields = SentenceListSerializer.Meta.fields + (
            "target_ipa",
            "target_ipa_variants",
            "word_spans",
        )

    def get_word_spans(self, obj):
        return enrich_word_spans(
            obj.text,
            cached_ipa=obj.cached_ipa,
            word_spans=obj.word_spans,
        )


class AnalysisCreateSerializer(serializers.Serializer):
    sentence_id = serializers.IntegerField(min_value=1)
    audio = serializers.FileField()
    consent_to_store = serializers.BooleanField(default=False)


class CustomSentenceCreateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=255, trim_whitespace=True)
    difficulty = serializers.ChoiceField(
        choices=("easy", "normal", "hard", "special"),
        default="easy",
    )


class LifestyleTranscriptionSerializer(serializers.Serializer):
    audio = serializers.FileField()


class LifestyleTranscriptionResultSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=True)
    language = serializers.CharField()
    language_probability = serializers.FloatField()
    duration = serializers.FloatField()
    segments = serializers.ListField(child=serializers.DictField())
    model = serializers.CharField()


class AnalysisAcceptedSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=("pending",))


class AnalysisStatusSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=("pending", "processing", "completed", "failed")
    )
    failure_reason = serializers.CharField(required=False, allow_blank=True)


class RecommendationSerializer(SentenceListSerializer):
    reason = serializers.CharField()

    class Meta(SentenceListSerializer.Meta):
        fields = SentenceListSerializer.Meta.fields + ("reason",)


class SentenceReferenceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    text = serializers.CharField()
    word_spans = serializers.ListField(child=serializers.DictField(), required=False)


class PronunciationErrorSerializer(serializers.ModelSerializer):
    target_phone = serializers.SerializerMethodField()
    recognized_phone = serializers.SerializerMethodField()
    confidence = serializers.FloatField(allow_null=True)

    class Meta:
        model = PronunciationError
        fields = (
            "sequence",
            "word",
            "word_index",
            "phone_position",
            "target_phone",
            "recognized_phone",
            "operation",
            "confidence",
            "specific_feedback",
        )

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_target_phone(self, obj):
        return obj.target_phone or None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_recognized_phone(self, obj):
        return obj.recognized_phone or None


class CorrectionFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorrectionFeedback
        fields = ("summary", "content", "priority_items")


class AnalysisResultSerializer(serializers.ModelSerializer):
    analysis_id = serializers.UUIDField(source="id")
    sentence = serializers.SerializerMethodField()
    score = serializers.FloatField()
    errors = PronunciationErrorSerializer(many=True)
    feedback = serializers.SerializerMethodField()
    matched_ipa_variant = serializers.SerializerMethodField()

    class Meta:
        model = PronunciationAnalysis
        fields = (
            "analysis_id",
            "sentence",
            "target_ipa",
            "recognized_ipa",
            "score",
            "errors",
            "feedback",
            "matched_ipa_variant",
            "created_at",
        )

    @extend_schema_field(SentenceReferenceSerializer)
    def get_sentence(self, obj):
        return {
            "id": obj.sentence_id,
            "text": obj.sentence.text,
            "word_spans": enrich_word_spans(
                obj.sentence.text,
                cached_ipa=obj.sentence.cached_ipa,
                word_spans=obj.sentence.word_spans,
            ),
        }

    @extend_schema_field(CorrectionFeedbackSerializer(allow_null=True))
    def get_feedback(self, obj):
        try:
            feedback = obj.feedback
        except CorrectionFeedback.DoesNotExist:
            return None
        return CorrectionFeedbackSerializer(feedback).data

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_matched_ipa_variant(self, obj):
        return (obj.analyzer_metadata or {}).get("matched_ipa_variant")


class RecordSerializer(serializers.ModelSerializer):
    analysis_id = serializers.UUIDField(source="id")
    sentence_id = serializers.IntegerField(read_only=True)
    sentence = serializers.CharField(source="sentence.text")
    score = serializers.FloatField()
    difficulty = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    error_count = serializers.IntegerField()

    class Meta:
        model = PronunciationAnalysis
        fields = (
            "analysis_id",
            "sentence_id",
            "sentence",
            "score",
            "difficulty",
            "category",
            "error_count",
            "created_at",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_difficulty(self, obj):
        return DIFFICULTY_TO_API[obj.sentence.difficulty]

    @extend_schema_field(CategorySerializer(allow_null=True))
    def get_category(self, obj):
        if obj.sentence.category is None:
            return None
        return CategorySerializer(obj.sentence.category).data


class RecentScoreSerializer(serializers.Serializer):
    analysis_id = serializers.UUIDField()
    score = serializers.FloatField()
    created_at = serializers.DateTimeField()


class ErrorSummarySerializer(serializers.Serializer):
    category = CategorySerializer()
    count = serializers.IntegerField()


class DifficultyStatsSerializer(serializers.Serializer):
    difficulty = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    average_score = serializers.FloatField()
    min_score = serializers.FloatField()
    q1_score = serializers.FloatField()
    median_score = serializers.FloatField()
    q3_score = serializers.FloatField()
    max_score = serializers.FloatField()


class PeerRankSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    rank = serializers.IntegerField()
    top_percent = serializers.IntegerField()
    better_than_percent = serializers.FloatField()
    average_score = serializers.FloatField()


class WeeklyTrendSerializer(serializers.Serializer):
    current_average = serializers.FloatField(allow_null=True)
    previous_average = serializers.FloatField(allow_null=True)
    delta = serializers.FloatField(allow_null=True)
    current_count = serializers.IntegerField()
    previous_count = serializers.IntegerField()
    status = serializers.CharField()


class StatisticsSummarySerializer(serializers.Serializer):
    total_analyses = serializers.IntegerField()
    total_practices = serializers.IntegerField()
    streak_days = serializers.IntegerField()
    average_score = serializers.FloatField()
    best_score = serializers.FloatField()
    recent_scores = RecentScoreSerializer(many=True)
    difficulty_stats = DifficultyStatsSerializer(many=True)
    error_summary = ErrorSummarySerializer(many=True)
    rule_error_summary = ErrorSummarySerializer(many=True)
    peer_rank = PeerRankSerializer(allow_null=True)
    weekly_trend = WeeklyTrendSerializer()
