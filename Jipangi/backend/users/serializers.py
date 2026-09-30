import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from config.exceptions import APIError

from .models import SpeechBaselineAssessment


BASELINE_QUESTION_KEYS = (
    "repeat_requests",
    "conversation_avoidance",
    "long_sentence_difficulty",
    "speaking_fatigue",
    "phone_difficulty",
)


def normalize_phone_number(value):
    phone_number = re.sub(r"[\s-]", "", value or "")
    if phone_number and not re.fullmatch(r"01[016789]\d{7,8}", phone_number):
        raise serializers.ValidationError("휴대전화 번호 형식을 확인해 주세요.")
    return phone_number


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username", "age", "phone_number")


class AuthResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserSerializer()


class RefreshResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class MeResponseSerializer(UserSerializer):
    joined_at = serializers.DateTimeField()
    total_completed_analyses = serializers.IntegerField()
    baseline_assessment_status = serializers.ChoiceField(
        choices=SpeechBaselineAssessment.Status.choices,
        allow_null=True,
    )
    baseline_self_report_score = serializers.IntegerField(allow_null=True)
    baseline_discomfort_level = serializers.ChoiceField(
        choices=SpeechBaselineAssessment.DiscomfortLevel.choices,
        allow_blank=True,
    )

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            "joined_at",
            "total_completed_analyses",
            "baseline_assessment_status",
            "baseline_self_report_score",
            "baseline_discomfort_level",
        )


class SignupSerializer(serializers.Serializer):
    username = serializers.RegexField(
        regex=r"^[a-zA-Z0-9_.-]+$",
        min_length=4,
        max_length=30,
        error_messages={"invalid": "아이디는 영문, 숫자, 밑줄, 마침표, 하이픈만 사용할 수 있습니다."},
    )
    password = serializers.CharField(write_only=True, min_length=8)
    age = serializers.IntegerField(min_value=1, max_value=120, required=False, allow_null=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")

    def validate_username(self, value):
        username = value.strip().lower()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise APIError(
                status_code=409,
                code="USERNAME_ALREADY_EXISTS",
                message="이미 사용 중인 아이디입니다.",
            )
        return username

    def validate_phone_number(self, value):
        return normalize_phone_number(value)

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return get_user_model().objects.create_user(**validated_data)
        except IntegrityError as exc:
            raise APIError(
                status_code=409,
                code="USERNAME_ALREADY_EXISTS",
                message="이미 사용 중인 아이디입니다.",
            ) from exc


class UserUpdateSerializer(serializers.ModelSerializer):
    username = serializers.RegexField(
        regex=r"^[a-zA-Z0-9_.-]+$",
        min_length=4,
        max_length=30,
        required=False,
        error_messages={"invalid": "아이디는 영문, 숫자, 밑줄, 마침표, 하이픈만 사용할 수 있습니다."},
    )
    age = serializers.IntegerField(min_value=1, max_value=120, required=False, allow_null=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "age", "phone_number")

    def validate_username(self, value):
        username = value.strip().lower()
        queryset = get_user_model().objects.filter(username__iexact=username)
        if self.instance is not None:
            queryset = queryset.exclude(id=self.instance.id)
        if queryset.exists():
            raise APIError(
                status_code=409,
                code="USERNAME_ALREADY_EXISTS",
                message="이미 사용 중인 아이디입니다.",
            )
        return username

    def validate_phone_number(self, value):
        return normalize_phone_number(value)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs["username"].strip().lower()
        user = authenticate(
            request=self.context.get("request"),
            username=username,
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise APIError(
                status_code=401,
                code="INVALID_CREDENTIALS",
                message="아이디 또는 비밀번호가 올바르지 않습니다.",
            )
        attrs["user"] = user
        return attrs


class BaselineAssessmentInputSerializer(serializers.Serializer):
    skipped = serializers.BooleanField(default=False)
    answers = serializers.DictField(
        child=serializers.IntegerField(min_value=0, max_value=4),
        required=False,
        default=dict,
    )

    def validate(self, attrs):
        if attrs["skipped"]:
            attrs["answers"] = {}
            return attrs

        answers = attrs["answers"]
        missing = sorted(set(BASELINE_QUESTION_KEYS) - set(answers))
        unknown = sorted(set(answers) - set(BASELINE_QUESTION_KEYS))
        if missing or unknown:
            raise serializers.ValidationError(
                {
                    "answers": {
                        "missing": missing,
                        "unknown": unknown,
                    }
                }
            )
        return attrs


class BaselineAssessmentResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpeechBaselineAssessment
        fields = (
            "status",
            "answers",
            "self_report_score",
            "discomfort_level",
            "assessment_version",
            "created_at",
            "updated_at",
        )


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, attrs):
        serializer = TokenRefreshSerializer(data={"refresh": attrs["refresh_token"]})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as exc:
            raise APIError(
                status_code=401,
                code="INVALID_TOKEN",
                message="Refresh Token이 유효하지 않습니다.",
            ) from exc

        return {
            "access_token": serializer.validated_data["access"],
            "refresh_token": serializer.validated_data["refresh"],
        }


class LogoutSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def save(self, **kwargs):
        try:
            RefreshToken(self.validated_data["refresh_token"]).blacklist()
        except Exception as exc:
            raise APIError(
                status_code=401,
                code="INVALID_TOKEN",
                message="Refresh Token이 유효하지 않습니다.",
            ) from exc


def token_pair_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
    }
