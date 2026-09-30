from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from pronunciation.models import (
    PracticeSentence,
    PronunciationAnalysis,
    PronunciationCategory,
    PronunciationError,
)


class RecordAndStatisticsAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="user@example.com",
            username="사용자",
            password="safe-password-1234",
        )
        category = PronunciationCategory.objects.create(code="liaison", name="연음화")
        sentence = PracticeSentence.objects.create(
            text="안녕하세요.",
            cached_ipa=["a", "n"],
            difficulty=PracticeSentence.Difficulty.BEGINNER,
            category=category,
        )
        cls.stored = PronunciationAnalysis.objects.create(
            user=cls.user,
            sentence=sentence,
            target_ipa=["a", "n"],
            recognized_ipa=["a"],
            score=Decimal("50.0"),
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        )
        PronunciationError.objects.create(
            analysis=cls.stored,
            sequence=0,
            phone_position=1,
            target_phone="n",
            operation=PronunciationError.Operation.DELETION,
        )
        PronunciationAnalysis.objects.create(
            user=cls.user,
            sentence=sentence,
            target_ipa=["a", "n"],
            recognized_ipa=["a", "n"],
            score=Decimal("100.0"),
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=False,
        )
        higher_user = get_user_model().objects.create_user(
            email="higher@example.com",
            username="높은사용자",
            password="safe-password-1234",
        )
        lower_user = get_user_model().objects.create_user(
            email="lower@example.com",
            username="낮은사용자",
            password="safe-password-1234",
        )
        PronunciationAnalysis.objects.create(
            user=higher_user,
            sentence=sentence,
            target_ipa=["a", "n"],
            recognized_ipa=["a", "n"],
            score=Decimal("90.0"),
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        )
        PronunciationAnalysis.objects.create(
            user=lower_user,
            sentence=sentence,
            target_ipa=["a", "n"],
            recognized_ipa=["a"],
            score=Decimal("20.0"),
            status=PronunciationAnalysis.Status.COMPLETED,
            consent_to_store=True,
        )

    def setUp(self):
        access = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_records_only_include_stored_completed_analysis(self):
        response = self.client.get("/api/v1/records")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["sentence_id"], self.stored.sentence_id)
        self.assertEqual(response.data["results"][0]["score"], 50.0)
        self.assertEqual(response.data["results"][0]["error_count"], 1)

    def test_statistics_exclude_analysis_without_consent(self):
        response = self.client.get("/api/v1/statistics/summary")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_analyses"], 1)
        self.assertEqual(response.data["average_score"], 50.0)
        self.assertEqual(response.data["best_score"], 50.0)
        self.assertEqual(response.data["error_summary"][0]["category"]["code"], "liaison")
        self.assertEqual(response.data["error_summary"][0]["count"], 1)
        self.assertEqual(response.data["rule_error_summary"][0]["category"]["code"], "liaison")
        self.assertEqual(response.data["rule_error_summary"][0]["category"]["name"], "연음화")
        self.assertEqual(response.data["rule_error_summary"][0]["count"], 1)
        self.assertEqual(response.data["peer_rank"]["total_users"], 3)
        self.assertEqual(response.data["peer_rank"]["rank"], 2)
        self.assertEqual(response.data["peer_rank"]["top_percent"], 67)
        self.assertEqual(response.data["peer_rank"]["better_than_percent"], 33.3)
        self.assertEqual(response.data["weekly_trend"]["current_count"], 1)
        self.assertEqual(response.data["weekly_trend"]["previous_count"], 0)
        self.assertEqual(response.data["weekly_trend"]["current_average"], 50.0)
        self.assertEqual(response.data["weekly_trend"]["status"], "new_week")
