from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from users.models import SpeechBaselineAssessment


class AuthenticationAPITests(APITestCase):
    def setUp(self):
        cache.clear()

    def signup(self, **overrides):
        payload = {
            "username": "test-user",
            "password": "safe-password-1234",
            "age": 27,
            "phone_number": "010-1234-5678",
            **overrides,
        }
        return self.client.post("/api/v1/auth/signup", payload, format="json")

    def test_signup_returns_tokens_and_stores_optional_profile(self):
        response = self.signup()

        self.assertEqual(response.status_code, 201)
        self.assertIn("access_token", response.data)
        self.assertIn("refresh_token", response.data)
        self.assertEqual(response.data["user"]["username"], "test-user")
        self.assertEqual(response.data["user"]["age"], 27)
        self.assertEqual(response.data["user"]["phone_number"], "01012345678")

    def test_duplicate_username_returns_conflict_code(self):
        self.signup()

        response = self.signup(username="TEST-USER")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "USERNAME_ALREADY_EXISTS")

    def test_login_refresh_logout_and_me(self):
        signup_response = self.signup()
        access_token = signup_response.data["access_token"]
        refresh_token = signup_response.data["refresh_token"]

        login_response = self.client.post(
            "/api/v1/auth/login",
            {"username": "test-user", "password": "safe-password-1234"},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)

        refresh_response = self.client.post(
            "/api/v1/auth/token/refresh",
            {"refresh_token": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertNotEqual(refresh_response.data["refresh_token"], refresh_token)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        me_response = self.client.get("/api/v1/users/me")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["username"], "test-user")
        self.assertIsNone(me_response.data["baseline_assessment_status"])

        logout_response = self.client.post(
            "/api/v1/auth/logout",
            {"refresh_token": refresh_response.data["refresh_token"]},
            format="json",
        )
        self.assertEqual(logout_response.status_code, 204)

        rejected_refresh = self.client.post(
            "/api/v1/auth/token/refresh",
            {"refresh_token": refresh_response.data["refresh_token"]},
            format="json",
        )
        self.assertEqual(rejected_refresh.status_code, 401)
        self.assertEqual(rejected_refresh.data["error"]["code"], "INVALID_TOKEN")

    def test_login_failure_is_generic(self):
        response = self.client.post(
            "/api/v1/auth/login",
            {"username": "missing-user", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "INVALID_CREDENTIALS")

    def test_me_can_update_profile_and_normalizes_phone_number(self):
        signup_response = self.signup()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {signup_response.data['access_token']}"
        )

        response = self.client.patch(
            "/api/v1/users/me",
            {
                "username": "Changed-User",
                "age": 31,
                "phone_number": "010-9999-0000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "changed-user")
        self.assertEqual(response.data["age"], 31)
        self.assertEqual(response.data["phone_number"], "01099990000")

    def test_me_update_rejects_duplicate_username(self):
        self.signup(username="taken-user")
        signup_response = self.signup(username="edit-user")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {signup_response.data['access_token']}"
        )

        response = self.client.patch(
            "/api/v1/users/me",
            {"username": "TAKEN-USER"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "USERNAME_ALREADY_EXISTS")

    def test_new_signup_succeeds_after_another_user_logs_out(self):
        first = self.signup(username="first-user")
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {first.data['access_token']}"
        )
        logout = self.client.post(
            "/api/v1/auth/logout",
            {"refresh_token": first.data["refresh_token"]},
            format="json",
        )
        self.client.credentials()

        second = self.signup(username="second-user", phone_number="")

        self.assertEqual(logout.status_code, 204)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data["user"]["username"], "second-user")

    def test_login_is_rate_limited_by_email_and_ip(self):
        for _ in range(5):
            response = self.client.post(
                "/api/v1/auth/login",
                {"username": "target-user", "password": "wrong-password"},
                format="json",
            )
            self.assertEqual(response.status_code, 401)

        limited = self.client.post(
            "/api/v1/auth/login",
            {"username": "target-user", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.data["error"]["code"], "TOO_MANY_REQUESTS")

    def test_expo_web_origin_is_allowed_by_cors(self):
        response = self.client.get(
            "/api/v1/sentences",
            HTTP_ORIGIN="http://localhost:8081",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Access-Control-Allow-Origin"],
            "http://localhost:8081",
        )

    def test_baseline_assessment_can_be_completed_and_returned_from_me(self):
        signup_response = self.signup()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {signup_response.data['access_token']}"
        )
        answers = {
            "repeat_requests": 2,
            "conversation_avoidance": 1,
            "long_sentence_difficulty": 3,
            "speaking_fatigue": 2,
            "phone_difficulty": 2,
        }

        response = self.client.post(
            "/api/v1/users/me/baseline-assessment",
            {"skipped": False, "answers": answers},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["self_report_score"], 10)
        self.assertEqual(response.data["discomfort_level"], "medium")
        self.assertEqual(SpeechBaselineAssessment.objects.count(), 1)
        me_response = self.client.get("/api/v1/users/me")
        self.assertEqual(me_response.data["baseline_assessment_status"], "completed")
        self.assertEqual(me_response.data["baseline_self_report_score"], 10)

    def test_baseline_assessment_can_be_skipped(self):
        signup_response = self.signup()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {signup_response.data['access_token']}"
        )

        response = self.client.post(
            "/api/v1/users/me/baseline-assessment",
            {"skipped": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "skipped")
        self.assertIsNone(response.data["self_report_score"])

    def test_baseline_assessment_requires_every_answer(self):
        signup_response = self.signup()
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {signup_response.data['access_token']}"
        )

        response = self.client.post(
            "/api/v1/users/me/baseline-assessment",
            {"answers": {"repeat_requests": 1}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
