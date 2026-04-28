from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Achievement,
    Certificate,
    Comment,
    Course,
    CourseTest,
    CourseTestAttempt,
    CourseTestOption,
    CourseTestQuestion,
    CourseTestResponse,
    Education,
    Enrollment,
    Experience,
    Lesson,
    Payment,
    PlatformSettings,
    Progress,
    Result,
    Review,
    Skill,
    TeacherProfile,
    Test,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "full_name", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "full_name")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Additional info",
            {
                "fields": (
                    "role",
                    "full_name",
                    "major",
                    "group_name",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Additional info",
            {
                "classes": ("wide",),
                "fields": (
                    "role",
                    "full_name",
                    "major",
                    "group_name",
                ),
            },
        ),
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "linkedin", "github", "updated_at")
    search_fields = ("user__username", "user__full_name", "linkedin", "github")
    list_select_related = ("user",)


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ("teacher", "institution", "degree", "start_date", "end_date")
    search_fields = ("teacher__user__full_name", "institution", "degree", "field_of_study")
    list_select_related = ("teacher", "teacher__user")


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("teacher", "company", "position", "is_current")
    list_filter = ("is_current",)
    search_fields = ("teacher__user__full_name", "company", "position")
    list_select_related = ("teacher", "teacher__user")


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("teacher", "title", "achieved_at")
    search_fields = ("teacher__user__full_name", "title")
    list_select_related = ("teacher", "teacher__user")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("teacher", "name", "level")
    search_fields = ("teacher__user__full_name", "name", "level")
    list_select_related = ("teacher", "teacher__user")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "price", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title", "teacher__user__full_name")
    list_select_related = ("teacher", "teacher__user")


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order")
    search_fields = ("title", "course__title")
    list_select_related = ("course",)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "enrolled_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("student__username", "student__full_name", "course__title")
    list_select_related = ("student", "course")


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson", "total_marks", "passing_marks", "created_at")
    search_fields = ("title", "lesson__title")
    list_select_related = ("lesson",)


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("student", "test", "score", "submitted_at", "passed_status")
    search_fields = ("student__username", "student__full_name", "test__title")
    list_select_related = ("student", "test")

    @admin.display(boolean=True, description="Passed")
    def passed_status(self, obj):
        return obj.passed


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("course", "student", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("course__title", "student__username", "student__full_name")
    list_select_related = ("course", "student")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("lesson", "user", "parent", "created_at")
    search_fields = ("lesson__title", "user__username", "user__full_name", "content")
    list_select_related = ("lesson", "user", "parent")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "amount", "status", "paid_at", "created_at")
    list_filter = ("status",)
    search_fields = ("enrollment__student__username", "enrollment__course__title", "transaction_id")
    list_select_related = ("enrollment", "enrollment__student", "enrollment__course")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "certificate_code", "issued_at")
    search_fields = ("certificate_code", "enrollment__student__username", "enrollment__course__title")
    list_select_related = ("enrollment", "enrollment__student", "enrollment__course")


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "lesson", "is_completed", "percentage", "completed_at")
    list_filter = ("is_completed",)
    search_fields = ("enrollment__student__username", "enrollment__course__title", "lesson__title")
    list_select_related = ("enrollment", "enrollment__student", "enrollment__course", "lesson")


@admin.register(CourseTest)
class CourseTestAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "created_at")
    search_fields = ("title", "course__title")
    list_select_related = ("course",)


@admin.register(CourseTestQuestion)
class CourseTestQuestionAdmin(admin.ModelAdmin):
    list_display = ("test", "order", "text")
    search_fields = ("test__title", "text")
    list_select_related = ("test", "test__course")


@admin.register(CourseTestOption)
class CourseTestOptionAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "text", "is_correct")
    list_filter = ("is_correct",)
    search_fields = ("question__text", "text")
    list_select_related = ("question", "question__test")


@admin.register(CourseTestAttempt)
class CourseTestAttemptAdmin(admin.ModelAdmin):
    list_display = ("test", "student", "score", "percentage", "created_at")
    search_fields = ("test__title", "student__username", "student__full_name")
    list_select_related = ("test", "test__course", "student")


@admin.register(CourseTestResponse)
class CourseTestResponseAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "selected_option", "is_correct")
    list_filter = ("is_correct",)
    search_fields = (
        "attempt__student__username",
        "question__text",
        "selected_option__text",
    )
    list_select_related = ("attempt", "question", "selected_option")


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ("platform_fee_percent", "updated_at")

    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
