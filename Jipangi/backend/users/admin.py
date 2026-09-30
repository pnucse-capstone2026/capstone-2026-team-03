from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import SpeechBaselineAssessment, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("id",)
    list_display = ("username", "age", "phone_number", "is_staff", "is_active", "date_joined")
    search_fields = ("username", "phone_number")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "사용자 정보",
            {"fields": ("age", "phone_number", "email", "first_name", "last_name")},
        ),
        (
            "권한",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("접속 기록", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "age",
                    "phone_number",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )


@admin.register(SpeechBaselineAssessment)
class SpeechBaselineAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "self_report_score",
        "discomfort_level",
        "updated_at",
    )
    list_filter = ("status", "discomfort_level", "assessment_version")
    search_fields = ("user__username", "user__phone_number")
    readonly_fields = ("created_at", "updated_at")
