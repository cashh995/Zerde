from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        TEACHER = "teacher", "Teacher"
        STUDENT = "student", "Student"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    full_name = models.CharField(max_length=255)

    # Student-specific fields.
    major = models.CharField(max_length=255, blank=True)
    group_name = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "Users"

    def __str__(self) -> str:
        return f"{self.username} ({self.role})"


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        limit_choices_to={"role": User.Role.TEACHER},
    )
    photo = models.URLField(blank=True)
    bio = models.TextField(blank=True)
    education_summary = models.TextField(blank=True)
    experience_summary = models.TextField(blank=True)
    achievements_summary = models.TextField(blank=True)
    linkedin = models.URLField(blank=True)
    github = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "TeacherProfile"

    def __str__(self) -> str:
        return self.user.full_name or self.user.username


class Education(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile, on_delete=models.CASCADE, related_name="educations"
    )
    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "Education"

    def __str__(self) -> str:
        return f"{self.institution} - {self.degree}"


class Experience(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile, on_delete=models.CASCADE, related_name="experiences"
    )
    company = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "Experience"

    def __str__(self) -> str:
        return f"{self.company} - {self.position}"


class Achievement(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile, on_delete=models.CASCADE, related_name="achievements"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    achieved_at = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "Achievements"

    def __str__(self) -> str:
        return self.title


class Skill(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile, on_delete=models.CASCADE, related_name="skills"
    )
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = "Skills"
        unique_together = ("teacher", "name")

    def __str__(self) -> str:
        return self.name


class Course(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile, on_delete=models.CASCADE, related_name="courses"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="courses/", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Courses"

    def __str__(self) -> str:
        return self.title


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    image = models.ImageField(upload_to="lessons/", blank=True, null=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "Lessons"
        ordering = ["course", "order"]
        unique_together = ("course", "order")

    def __str__(self) -> str:
        return f"{self.course.title}: {self.title}"


class Enrollment(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "Enrollments"
        unique_together = ("student", "course")

    def __str__(self) -> str:
        return f"{self.student.username} -> {self.course.title}"


class Test(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="tests")
    title = models.CharField(max_length=255)
    total_marks = models.PositiveIntegerField(default=100)
    passing_marks = models.PositiveIntegerField(default=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Tests"

    def __str__(self) -> str:
        return self.title


class Result(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="results",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    score = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Results"
        unique_together = ("test", "student")

    @property
    def passed(self) -> bool:
        return self.score >= self.test.passing_marks

    def __str__(self) -> str:
        return f"{self.student.username} - {self.test.title}"


class Review(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reviews")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    teacher_reply = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Reviews"
        unique_together = ("course", "student")

    def __str__(self) -> str:
        return f"{self.course.title} ({self.rating}/5)"


class Comment(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="replies", blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Comments"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.user.username}"


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    enrollment = models.OneToOneField(
        Enrollment, on_delete=models.CASCADE, related_name="payment"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    transaction_id = models.CharField(max_length=120, blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Payments"

    def __str__(self) -> str:
        return f"{self.enrollment} - {self.status}"


class Certificate(models.Model):
    enrollment = models.OneToOneField(
        Enrollment, on_delete=models.CASCADE, related_name="certificate"
    )
    certificate_code = models.CharField(max_length=100, unique=True)
    issued_at = models.DateTimeField(default=timezone.now)
    file = models.FileField(upload_to="certificates/", blank=True, null=True)

    class Meta:
        db_table = "Certificates"

    def __str__(self) -> str:
        return self.certificate_code


class Progress(models.Model):
    enrollment = models.ForeignKey(
        Enrollment, on_delete=models.CASCADE, related_name="progress_items"
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress_items")
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    percentage = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        db_table = "Progress"
        unique_together = ("enrollment", "lesson")

    def __str__(self) -> str:
        return f"{self.enrollment} - {self.lesson.title}"


class CourseTest(models.Model):
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name="course_test")
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CourseTests"

    def __str__(self) -> str:
        return f"{self.course.title} - {self.title}"


class CourseTestQuestion(models.Model):
    test = models.ForeignKey(CourseTest, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "CourseTestQuestions"
        ordering = ["order", "id"]
        unique_together = ("test", "order")

    def __str__(self) -> str:
        return f"{self.test.title} #{self.order}"


class CourseTestOption(models.Model):
    question = models.ForeignKey(
        CourseTestQuestion, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "CourseTestOptions"
        ordering = ["order", "id"]
        unique_together = ("question", "order")

    def __str__(self) -> str:
        return f"{self.question_id} - {self.text[:40]}"


class CourseTestAttempt(models.Model):
    test = models.ForeignKey(CourseTest, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_test_attempts",
        limit_choices_to={"role": User.Role.STUDENT},
    )
    score = models.PositiveIntegerField(default=0)
    percentage = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "CourseTestAttempts"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student.username} - {self.test.title} ({self.percentage}%)"


class CourseTestResponse(models.Model):
    attempt = models.ForeignKey(
        CourseTestAttempt, on_delete=models.CASCADE, related_name="responses"
    )
    question = models.ForeignKey(CourseTestQuestion, on_delete=models.CASCADE)
    selected_option = models.ForeignKey(CourseTestOption, on_delete=models.CASCADE)
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = "CourseTestResponses"
        unique_together = ("attempt", "question")

    def __str__(self) -> str:
        return f"{self.attempt_id} - {self.question_id}"


class PlatformSettings(models.Model):
    platform_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "PlatformSettings"
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def __str__(self) -> str:
        return f"Платформа: {self.platform_fee_percent}%"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
