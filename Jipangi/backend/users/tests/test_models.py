from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase


class UserModelTests(TestCase):
    def test_username_is_login_identifier_and_normalized(self):
        user = get_user_model().objects.create_user(
            username="TestUser",
            password="safe-password-1234",
        )

        self.assertEqual(user.username, "testuser")
        self.assertEqual(get_user_model().USERNAME_FIELD, "username")
        self.assertTrue(user.check_password("safe-password-1234"))

    def test_username_must_be_unique(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username="same-user",
            password="safe-password-1234",
        )

        with self.assertRaises(ValidationError):
            user_model.objects.create_user(
                username="same-user",
                password="safe-password-1234",
            )
