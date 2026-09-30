from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from pronunciation.models import PronunciationAnalysis

from .models import SpeechBaselineAssessment
from .serializers import (
    AuthResponseSerializer,
    BaselineAssessmentInputSerializer,
    BaselineAssessmentResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeResponseSerializer,
    RefreshResponseSerializer,
    RefreshSerializer,
    SignupSerializer,
    UserUpdateSerializer,
    UserSerializer,
    token_pair_for_user,
)
from .throttles import LoginIPRateThrottle, LoginUsernameRateThrottle, SignupRateThrottle


class SignupView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (SignupRateThrottle,)

    @extend_schema(request=SignupSerializer, responses={201: AuthResponseSerializer})
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                **token_pair_for_user(user),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (LoginIPRateThrottle, LoginUsernameRateThrottle)

    @extend_schema(request=LoginSerializer, responses={200: AuthResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(
            {
                **token_pair_for_user(user),
                "user": UserSerializer(user).data,
            }
        )


class RefreshView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(request=RefreshSerializer, responses={200: RefreshResponseSerializer})
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class LogoutView(APIView):
    @extend_schema(request=LogoutSerializer, responses={204: None})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def _response_data(self, user):
        total_completed_analyses = PronunciationAnalysis.objects.filter(
            user=user,
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        ).count()
        assessment = SpeechBaselineAssessment.objects.filter(user=user).first()
        return {
            "id": user.id,
            "username": user.username,
            "age": user.age,
            "phone_number": user.phone_number,
            "joined_at": user.date_joined,
            "total_completed_analyses": total_completed_analyses,
            "baseline_assessment_status": assessment.status if assessment else None,
            "baseline_self_report_score": assessment.self_report_score if assessment else None,
            "baseline_discomfort_level": assessment.discomfort_level if assessment else "",
        }

    @extend_schema(responses={200: MeResponseSerializer})
    def get(self, request):
        return Response(self._response_data(request.user))

    @extend_schema(request=UserUpdateSerializer, responses={200: MeResponseSerializer})
    def patch(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._response_data(request.user))


class BaselineAssessmentView(APIView):
    @extend_schema(responses={200: BaselineAssessmentResponseSerializer})
    def get(self, request):
        assessment = SpeechBaselineAssessment.objects.filter(user=request.user).first()
        if assessment is None:
            return Response(None)
        return Response(BaselineAssessmentResponseSerializer(assessment).data)

    @extend_schema(
        request=BaselineAssessmentInputSerializer,
        responses={200: BaselineAssessmentResponseSerializer},
    )
    def post(self, request):
        serializer = BaselineAssessmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        skipped = serializer.validated_data["skipped"]
        answers = serializer.validated_data["answers"]
        score = None if skipped else sum(answers.values())
        assessment, _ = SpeechBaselineAssessment.objects.update_or_create(
            user=request.user,
            defaults={
                "status": (
                    SpeechBaselineAssessment.Status.SKIPPED
                    if skipped
                    else SpeechBaselineAssessment.Status.COMPLETED
                ),
                "answers": answers,
                "self_report_score": score,
                "discomfort_level": (
                    "" if score is None else SpeechBaselineAssessment.level_for_score(score)
                ),
            },
        )
        return Response(BaselineAssessmentResponseSerializer(assessment).data)
    AuthResponseSerializer,
