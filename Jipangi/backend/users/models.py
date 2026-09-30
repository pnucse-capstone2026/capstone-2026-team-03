from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    username = models.CharField("아이디", max_length=30, unique=True)
    email = models.EmailField("이메일", blank=True, default="")
    age = models.PositiveSmallIntegerField(
        "연령",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
    )
    phone_number = models.CharField("전화번호", max_length=20, blank=True, default="")

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "user_account"
        ordering = ["id"]
        verbose_name = "사용자"
        verbose_name_plural = "사용자"

    def clean(self):
        super().clean()
        self.username = self.username.strip().lower()
        if self.email:
            self.email = self.__class__.objects.normalize_email(self.email).lower()

    def __str__(self):
        return self.username


class SpeechBaselineAssessment(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "완료"
        SKIPPED = "skipped", "건너뜀"

    class DiscomfortLevel(models.TextChoices):
        LOW = "low", "낮음"
        MEDIUM = "medium", "보통"
        HIGH = "high", "높음"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="speech_baseline_assessment",
        verbose_name="사용자",
    )
    status = models.CharField(max_length=20, choices=Status.choices, verbose_name="상태")
    answers = models.JSONField(default=dict, blank=True, verbose_name="자가 보고 응답")
    self_report_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        verbose_name="자가 보고 불편 점수",
    )
    discomfort_level = models.CharField(
        max_length=10,
        choices=DiscomfortLevel.choices,
        blank=True,
        default="",
        verbose_name="자가 보고 불편 수준",
    )
    assessment_version = models.CharField(max_length=30, default="self-report-v1")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "speech_baseline_assessment"
        ordering = ["-updated_at"]
        verbose_name = "초기 발음 상태 평가"
        verbose_name_plural = "초기 발음 상태 평가"

    @classmethod
    def level_for_score(cls, score):
        if score <= 4:
            return cls.DiscomfortLevel.LOW
        if score <= 11:
            return cls.DiscomfortLevel.MEDIUM
        return cls.DiscomfortLevel.HIGH

    def __str__(self):
        return f"{self.user.username} - {self.get_status_display()}"
