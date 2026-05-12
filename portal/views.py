from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db import IntegrityError
from django.db.models import Avg, Count, Max, Sum
from django.db.models.functions import TruncMonth
from django.db.models import Q
from django.http import FileResponse, JsonResponse
from django.http import Http404
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import io
import random
from pathlib import Path

from .forms import (
    LoginForm,
    PaymentForm,
    TeacherCourseEditForm,
    StudentRegistrationForm,
    TeacherCourseCreateForm,
    TeacherLessonCreateForm,
    TeacherProfileEditForm,
    TeacherRegistrationForm,
    create_teacher_profile,
)
from .models import (
    Certificate,
    Comment,
    Course,
    CourseTestAttempt,
    CourseTestOption,
    CourseTestQuestion,
    CourseTestResponse,
    Enrollment,
    Lesson,
    Payment,
    PlatformSettings,
    Progress,
    CourseTest,
    Review,
    TeacherProfile,
    User,
)


def _teacher_rating(profile: TeacherProfile) -> float:
    return float(
        profile.courses.aggregate(avg_rating=Avg("reviews__rating"))["avg_rating"] or 0
    )


def _generate_username(email: str) -> str:
    base_username = email.split("@")[0].lower().replace(" ", "")
    username = base_username
    counter = 1

    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    return username


def _course_test_band_message(percentage: int) -> str:
    if percentage >= 80:
        return "Керемет! Үздік нәтиже!"
    if percentage >= 60:
        return "Жақсы! Кейбірін қайталаңыз"
    if percentage >= 40:
        return "Қанағаттанарлық"
    return "Курсты қайтадан өтіңіз"


def _student_course_completion(enrollment: Enrollment, course: Course) -> tuple[int, int]:
    total_lessons = course.lessons.count()
    completed_lessons = Progress.objects.filter(
        enrollment=enrollment, lesson__course=course, is_completed=True
    ).count()
    return completed_lessons, total_lessons


def _generate_certificate_code() -> str:
    current_year = timezone.now().year
    for _ in range(20):
        suffix = f"{random.randint(0, 9999):04d}"
        candidate = f"#KZ{current_year}-{suffix}"
        if not Certificate.objects.filter(certificate_code=candidate).exists():
            return candidate
    return f"#KZ{current_year}-{timezone.now().strftime('%H%M')}"


def _build_certificate_pdf(
    student_name: str,
    course_title: str,
    teacher_name: str,
    percentage: int,
    certificate_code: str,
) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    font_name = "Helvetica"
    try:
        windows_font_path = Path("C:/Windows/Fonts/arial.ttf")
        if windows_font_path.exists():
            pdfmetrics.registerFont(TTFont("ArialUnicode", str(windows_font_path)))
            font_name = "ArialUnicode"
    except Exception:
        font_name = "Helvetica"

    border_color = colors.HexColor("#6C63FF")
    pdf.setStrokeColor(border_color)
    pdf.setLineWidth(4)
    pdf.rect(28, 28, page_width - 56, page_height - 56)

    pdf.setStrokeColor(colors.HexColor("#bcb7ff"))
    pdf.setLineWidth(1.2)
    pdf.rect(42, 42, page_width - 84, page_height - 84)

    logo_x, logo_y, logo_w, logo_h = page_width - 170, page_height - 110, 110, 50
    pdf.setFillColor(colors.HexColor("#f1efff"))
    pdf.roundRect(logo_x, logo_y, logo_w, logo_h, 10, fill=1, stroke=0)
    logo_path = settings.BASE_DIR / "portal" / "static" / "portal" / "images" / "logo.png"
    if logo_path.exists():
        pdf.drawImage(
            str(logo_path),
            logo_x + 8,
            logo_y + 6,
            width=logo_w - 16,
            height=logo_h - 12,
            preserveAspectRatio=True,
            mask="auto",
            anchor="c",
        )

    pdf.setFillColor(border_color)
    pdf.setFont(font_name, 36)
    pdf.drawCentredString(page_width / 2, page_height - 160, "СЕРТИФИКАТ")

    pdf.setFillColor(colors.HexColor("#25314f"))
    pdf.setFont(font_name, 16)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 205,
        "Zerde платформасының оқу сертификаты",
    )

    pdf.setFont(font_name, 14)
    pdf.drawCentredString(page_width / 2, page_height - 270, "Осы сертификат табысталады:")

    pdf.setFont(font_name, 24)
    pdf.setFillColor(border_color)
    pdf.drawCentredString(page_width / 2, page_height - 310, student_name)

    pdf.setFillColor(colors.HexColor("#25314f"))
    pdf.setFont(font_name, 14)
    pdf.drawCentredString(page_width / 2, page_height - 355, f"Курс: {course_title}")
    pdf.drawCentredString(page_width / 2, page_height - 385, f"Оқытушы: {teacher_name}")
    pdf.drawCentredString(page_width / 2, page_height - 415, f"Тест нәтижесі: {percentage}%")

    issued_label = timezone.localdate().strftime("%d.%m.%Y")
    pdf.setFillColor(colors.HexColor("#4b5573"))
    pdf.setFont(font_name, 12)
    pdf.drawString(70, 110, f"Күні: {issued_label}")
    pdf.drawRightString(page_width - 70, 110, f"ID: {certificate_code}")

    pdf.setStrokeColor(colors.HexColor("#8c84ff"))
    pdf.setLineWidth(1)
    pdf.line(70, 145, 260, 145)
    pdf.line(page_width - 260, 145, page_width - 70, 145)
    pdf.setFont(font_name, 11)
    pdf.drawString(70, 132, "Zerde")
    pdf.drawRightString(page_width - 70, 132, "Оқу бөлімі")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def home(request):
    q = (request.GET.get("q") or "").strip()
    searched_courses = []
    if q:
        searched_courses = (
            Course.objects.select_related("teacher__user")
            .filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(teacher__user__full_name__icontains=q)
            )
            .order_by("-created_at")[:12]
        )

    latest_courses = Course.objects.select_related("teacher__user").order_by("-created_at")[:6]
    return render(
        request,
        "portal/home.html",
        {
            "search_query": q,
            "searched_courses": searched_courses,
            "latest_courses": latest_courses,
        },
    )


def student_register(request):
    if request.user.is_authenticated:
        return redirect("portal:home")

    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = _generate_username(form.cleaned_data["email"])
            user.email = form.cleaned_data["email"]
            user.role = User.Role.STUDENT
            user.set_password(form.cleaned_data["password"])
            user.save()
            login(request, user)
            messages.success(request, "Студент аккаунты сәтті ашылды.")
            return redirect("portal:home")
    else:
        form = StudentRegistrationForm()

    return render(
        request,
        "portal/auth/register_student.html",
        {"form": form, "page_title": "Студент тіркелуі"},
    )


def teacher_register(request):
    if request.user.is_authenticated:
        return redirect("portal:home")

    if request.method == "POST":
        form = TeacherRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = _generate_username(form.cleaned_data["email"])
            user.email = form.cleaned_data["email"]
            user.role = User.Role.TEACHER
            user.set_password(form.cleaned_data["password"])
            user.save()
            create_teacher_profile(user)
            login(request, user)
            messages.success(request, "Оқытушы аккаунты сәтті ашылды.")
            return redirect("portal:home")
    else:
        form = TeacherRegistrationForm()

    return render(
        request,
        "portal/auth/register_teacher.html",
        {"form": form, "page_title": "Оқытушы тіркелуі"},
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect("portal:role_redirect")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            login(request, form.cleaned_data["user"])
            messages.success(request, "Жүйеге сәтті кірдіңіз.")
            return redirect("portal:role_redirect")
    else:
        form = LoginForm()

    return render(
        request,
        "portal/auth/login.html",
        {"form": form, "page_title": "Жүйеге кіру"},
    )


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Жүйеден сәтті шықтыңыз.")
    return redirect("portal:login")


@login_required
def role_redirect(request):
    user = request.user
    if getattr(user, "role", None) == User.Role.ADMIN or user.is_superuser:
        return redirect("portal:admin_dashboard")
    if getattr(user, "role", None) == User.Role.TEACHER:
        return redirect("portal:teacher_dashboard")
    return redirect("portal:student_dashboard")


@login_required
def teacher_dashboard(request):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")

    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
    courses = Course.objects.filter(teacher=teacher_profile).order_by("-created_at") if teacher_profile else []

    total_students = (
        Enrollment.objects.filter(course__teacher=teacher_profile)
        .values("student_id")
        .distinct()
        .count()
        if teacher_profile
        else 0
    )

    revenue_qs = Payment.objects.filter(
        status=Payment.Status.PAID,
        enrollment__course__teacher=teacher_profile,
    )
    total_revenue = revenue_qs.aggregate(total=Sum("amount"))["total"] or 0

    start_month = (timezone.now().date().replace(day=1) - timezone.timedelta(days=30 * 5))
    monthly_revenue = (
        revenue_qs.filter(paid_at__date__gte=start_month)
        .annotate(month=TruncMonth("paid_at"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    chart_labels = [
        (row["month"].strftime("%Y-%m") if row["month"] else "") for row in monthly_revenue
    ]
    chart_values = [float(row["total"] or 0) for row in monthly_revenue]
    course_test_ids = list(
        CourseTest.objects.filter(course__in=courses).values_list("course_id", flat=True)
    )

    return render(
        request,
        "portal/dashboards/teacher_dashboard.html",
        {
            "teacher_profile": teacher_profile,
            "courses": courses,
            "total_students": total_students,
            "total_revenue": total_revenue,
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "course_test_ids": course_test_ids,
            "page_title": "Оқытушы панелі",
        },
    )


@login_required
def student_dashboard(request):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")

    enrollments = (
        Enrollment.objects.filter(student=request.user, is_active=True)
        .select_related("course")
        .order_by("-enrolled_at")
    )

    progress_by_enrollment = {
        row["enrollment_id"]: int(row["avg_pct"] or 0)
        for row in Progress.objects.filter(enrollment__in=enrollments)
        .values("enrollment_id")
        .annotate(avg_pct=Avg("percentage"))
    }
    enrollment_cards = [
        {"enrollment": enr, "progress": progress_by_enrollment.get(enr.id, 0)}
        for enr in enrollments
    ]

    certificates = Certificate.objects.filter(enrollment__in=enrollments).select_related(
        "enrollment__course"
    )

    payments = (
        Payment.objects.filter(enrollment__in=enrollments)
        .select_related("enrollment__course")
        .order_by("-created_at")[:20]
    )

    return render(
        request,
        "portal/dashboards/student_dashboard.html",
        {
            "enrollments": enrollments,
            "enrollment_cards": enrollment_cards,
            "progress_by_enrollment": progress_by_enrollment,
            "certificates": certificates,
            "payments": payments,
            "page_title": "Студент панелі",
        },
    )


@login_required
def admin_dashboard(request):
    if not (request.user.role == User.Role.ADMIN or request.user.is_superuser):
        return redirect("portal:role_redirect")

    student_count = User.objects.filter(role=User.Role.STUDENT).count()
    teacher_count = User.objects.filter(role=User.Role.TEACHER).count()
    course_count = Course.objects.count()
    revenue_total = (
        Payment.objects.filter(status=Payment.Status.PAID).aggregate(total=Sum("amount"))["total"]
        or 0
    )

    students = User.objects.filter(role=User.Role.STUDENT).order_by("-date_joined")
    teachers = User.objects.filter(role=User.Role.TEACHER).order_by("-date_joined")
    courses = Course.objects.select_related("teacher__user").order_by("-created_at")
    all_payments = (
        Payment.objects.select_related("enrollment__course", "enrollment__student")
        .order_by("-created_at")
    )

    platform_settings = PlatformSettings.load()

    start_month = (timezone.now().date().replace(day=1) - timezone.timedelta(days=30 * 5))
    monthly_revenue = (
        Payment.objects.filter(status=Payment.Status.PAID, paid_at__date__gte=start_month)
        .annotate(month=TruncMonth("paid_at"))
        .values("month")
        .annotate(total=Sum("amount"), cnt=Count("id"))
        .order_by("month")
    )
    chart_labels = [
        (row["month"].strftime("%Y-%m") if row["month"] else "") for row in monthly_revenue
    ]
    chart_values = [float(row["total"] or 0) for row in monthly_revenue]

    return render(
        request,
        "portal/dashboards/admin_dashboard.html",
        {
            "student_count": student_count,
            "teacher_count": teacher_count,
            "course_count": course_count,
            "revenue_total": revenue_total,
            "students": students,
            "teachers": teachers,
            "courses": courses,
            "all_payments": all_payments,
            "platform_settings": platform_settings,
            "chart_labels": chart_labels,
            "chart_values": chart_values,
            "page_title": "Админ панелі",
        },
    )


@login_required
@require_POST
def admin_toggle_user(request, user_id):
    if not (request.user.role == User.Role.ADMIN or request.user.is_superuser):
        return JsonResponse({"error": "Рұқсат жоқ"}, status=403)

    target = get_object_or_404(User, id=user_id)
    if target.id == request.user.id:
        return JsonResponse({"error": "Өзіңізді блоктай алмайсыз"}, status=400)

    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    return JsonResponse({
        "success": True,
        "is_active": target.is_active,
        "message": f"{'Белсендірілді' if target.is_active else 'Блокталды'}: {target.full_name or target.username}",
    })


@login_required
@require_POST
def admin_delete_course(request, course_id):
    if not (request.user.role == User.Role.ADMIN or request.user.is_superuser):
        return JsonResponse({"error": "Рұқсат жоқ"}, status=403)

    course = get_object_or_404(Course, id=course_id)
    title = course.title
    course.delete()
    return JsonResponse({"success": True, "message": f"Курс жойылды: {title}"})


@login_required
@require_POST
def admin_update_platform_settings(request):
    if not (request.user.role == User.Role.ADMIN or request.user.is_superuser):
        return JsonResponse({"error": "Рұқсат жоқ"}, status=403)

    try:
        fee = float(request.POST.get("platform_fee_percent", 20))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Қате мән"}, status=400)

    if fee < 0 or fee > 100:
        return JsonResponse({"error": "0-100 арасында болуы керек"}, status=400)

    ps = PlatformSettings.load()
    ps.platform_fee_percent = fee
    ps.save(update_fields=["platform_fee_percent", "updated_at"])
    return JsonResponse({
        "success": True,
        "platform_fee": float(ps.platform_fee_percent),
        "teacher_fee": float(100 - ps.platform_fee_percent),
        "message": f"Платформа пайызы жаңартылды: {ps.platform_fee_percent}%",
    })


@login_required
def teacher_course_add(request):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")

    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
    if teacher_profile is None:
        messages.error(request, "Алдымен оқытушы профиліңізді толтырыңыз.")
        return redirect("portal:teacher_dashboard")

    if request.method == "POST":
        form = TeacherCourseCreateForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = teacher_profile

            category_label = dict(TeacherCourseCreateForm.CATEGORY_CHOICES).get(
                form.cleaned_data["category"], "Басқа"
            )
            image_file = form.cleaned_data.get("course_image")
            extra_lines = [f"Категория: {category_label}"]
            if image_file:
                extra_lines.append(f"Курс суреті: {image_file.name}")

            base_description = (course.description or "").strip()
            if extra_lines:
                extra_block = "\n".join(extra_lines)
                course.description = (
                    f"{base_description}\n\n{extra_block}" if base_description else extra_block
                )

            course.save()
            messages.success(request, "Жаңа курс сәтті қосылды.")
            return redirect("portal:teacher_dashboard")
    else:
        form = TeacherCourseCreateForm()

    return render(
        request,
        "portal/teacher_course_add.html",
        {"form": form, "page_title": "Жаңа курс қосу"},
    )


@login_required
def teacher_course_edit(request, course_id):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")

    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
    if teacher_profile is None:
        messages.error(request, "Алдымен оқытушы профиліңізді толтырыңыз.")
        return redirect("portal:teacher_dashboard")

    course = Course.objects.filter(id=course_id).first()
    if course is None or course.teacher_id != teacher_profile.id:
        messages.error(request, "Бұл курсты өңдеуге рұқсатыңыз жоқ.")
        return redirect("portal:teacher_dashboard")

    if request.method == "POST":
        form = TeacherCourseEditForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            course = form.save(commit=False)

            category_label = dict(TeacherCourseEditForm.CATEGORY_CHOICES).get(
                form.cleaned_data["category"], "Басқа"
            )
            image_file = form.cleaned_data.get("course_image")

            base_description_lines = []
            for line in (course.description or "").splitlines():
                if line.startswith("Категория:"):
                    continue
                if line.startswith("Курс суреті:"):
                    continue
                base_description_lines.append(line)

            base_description = "\n".join(base_description_lines).strip()
            extra_lines = [f"Категория: {category_label}"]
            if image_file:
                course.image = image_file
                extra_lines.append(f"Курс суреті: {image_file.name}")
            elif course.image:
                extra_lines.append(f"Курс суреті: {course.image.name.split('/')[-1]}")

            extra_block = "\n".join(extra_lines)
            course.description = (
                f"{base_description}\n\n{extra_block}" if base_description else extra_block
            )

            course.save()
            messages.success(request, "Курс мәліметтері сәтті жаңартылды.")
            return redirect("portal:teacher_dashboard")
    else:
        form = TeacherCourseEditForm(instance=course)

    return render(
        request,
        "portal/teacher_course_edit.html",
        {"form": form, "course": course, "page_title": "Курсты өңдеу"},
    )


@login_required
def teacher_course_test_add(request, course_id):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")

    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
    if teacher_profile is None:
        messages.error(request, "Алдымен оқытушы профиліңізді толтырыңыз.")
        return redirect("portal:teacher_dashboard")

    course = Course.objects.filter(id=course_id, teacher=teacher_profile).first()
    if course is None:
        messages.error(request, "Бұл курсқа тест қосуға рұқсатыңыз жоқ.")
        return redirect("portal:teacher_dashboard")

    if request.method == "POST":
        test_title = (request.POST.get("test_title") or "").strip() or f"{course.title} тесті"
        total_questions = int(request.POST.get("total_questions") or 0)

        question_payload = []
        for index in range(1, total_questions + 1):
            question_text = (request.POST.get(f"question_text_{index}") or "").strip()
            options = [
                (request.POST.get(f"question_{index}_option_{option_idx}") or "").strip()
                for option_idx in range(1, 5)
            ]
            correct_option = request.POST.get(f"question_{index}_correct") or ""
            if not question_text:
                continue
            if not all(options):
                messages.error(
                    request,
                    f"{index}-сұрақта барлық 4 вариантты толтырыңыз.",
                )
                return redirect("portal:teacher_course_test_add", course_id=course.id)
            if correct_option not in {"1", "2", "3", "4"}:
                messages.error(
                    request,
                    f"{index}-сұраққа дұрыс жауапты белгілеңіз.",
                )
                return redirect("portal:teacher_course_test_add", course_id=course.id)
            question_payload.append(
                {
                    "text": question_text,
                    "options": options,
                    "correct_index": int(correct_option),
                }
            )

        if not question_payload:
            messages.error(request, "Кемінде бір сұрақ қосыңыз.")
            return redirect("portal:teacher_course_test_add", course_id=course.id)

        with transaction.atomic():
            test, _ = CourseTest.objects.get_or_create(
                course=course,
                defaults={"title": test_title},
            )
            test.title = test_title
            test.save(update_fields=["title"])

            test.questions.all().delete()
            for q_idx, payload in enumerate(question_payload, start=1):
                question = CourseTestQuestion.objects.create(
                    test=test,
                    text=payload["text"],
                    order=q_idx,
                )
                for option_idx, option_text in enumerate(payload["options"], start=1):
                    CourseTestOption.objects.create(
                        question=question,
                        text=option_text,
                        order=option_idx,
                        is_correct=(option_idx == payload["correct_index"]),
                    )

        messages.success(request, "Тест сәтті сақталды.")
        return redirect("portal:teacher_dashboard")

    existing_test = CourseTest.objects.filter(course=course).first()
    existing_questions = []
    if existing_test:
        existing_questions = list(existing_test.questions.prefetch_related("options").order_by("order", "id"))
    return render(
        request,
        "portal/teacher_course_test_add.html",
        {
            "course": course,
            "existing_test": existing_test,
            "existing_questions": existing_questions,
            "page_title": "Курс тестін қосу",
        },
    )


@login_required
def teacher_profile(request):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")
    profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    skills = profile.skills.order_by("name")
    courses_count = profile.courses.count()
    return render(
        request,
        "portal/teacher_profile.html",
        {
            "teacher_profile": profile,
            "skills": skills,
            "courses_count": courses_count,
            "page_title": "Оқытушы профилі",
        },
    )


@login_required
def teacher_profile_edit(request):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")
    profile, _ = TeacherProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = TeacherProfileEditForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль сәтті жаңартылды.")
            return redirect("portal:teacher_profile")
    else:
        form = TeacherProfileEditForm(instance=profile)
    return render(
        request,
        "portal/teacher_profile_edit.html",
        {"form": form, "page_title": "Профильді өзгерту"},
    )


@login_required
def teacher_course_lessons(request, course_id):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")

    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
    if teacher_profile is None:
        messages.error(request, "Алдымен оқытушы профиліңізді толтырыңыз.")
        return redirect("portal:teacher_dashboard")

    course = Course.objects.filter(id=course_id, teacher=teacher_profile).first()
    if course is None:
        messages.error(request, "Бұл курсты өңдеуге рұқсатыңыз жоқ.")
        return redirect("portal:teacher_dashboard")

    lessons = course.lessons.order_by("order")

    if request.method == "POST":
        form = TeacherCourseEditForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            course = form.save(commit=False)

            category_label = dict(TeacherCourseEditForm.CATEGORY_CHOICES).get(
                form.cleaned_data["category"], "Басқа"
            )
            image_file = form.cleaned_data.get("course_image")

            base_description_lines = []
            for line in (course.description or "").splitlines():
                if line.startswith("Категория:"):
                    continue
                if line.startswith("Курс суреті:"):
                    continue
                base_description_lines.append(line)

            base_description = "\n".join(base_description_lines).strip()
            extra_lines = [f"Категория: {category_label}"]
            if image_file:
                course.image = image_file
                extra_lines.append(f"Курс суреті: {image_file.name}")
            elif course.image:
                extra_lines.append(f"Курс суреті: {course.image.name.split('/')[-1]}")

            extra_block = "\n".join(extra_lines)
            course.description = (
                f"{base_description}\n\n{extra_block}" if base_description else extra_block
            )

            course.save()
            messages.success(request, "Курс мәліметтері сәтті жаңартылды.")
            return redirect("portal:teacher_course_lessons", course_id=course.id)
    else:
        form = TeacherCourseEditForm(instance=course)

    return render(
        request,
        "portal/teacher_course_lessons.html",
        {
            "form": form,
            "course": course,
            "lessons": lessons,
            "page_title": f"{course.title} — Сабақтар",
        },
    )


@login_required
def teacher_course_lesson_add(request, course_id):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")

    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
    if teacher_profile is None:
        messages.error(request, "Алдымен оқытушы профилін жасаңыз.")
        return redirect("portal:teacher_profile_edit")

    course = Course.objects.filter(id=course_id, teacher=teacher_profile).first()
    if course is None:
        messages.error(request, "Бұл курсқа сабақ қосуға рұқсатыңыз жоқ.")
        return redirect("portal:teacher_dashboard")

    if request.method == "POST":
        form = TeacherLessonCreateForm(
            request.POST, request.FILES, teacher_profile=teacher_profile
        )
        form.fields.pop("course", None)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            last_order = (
                Lesson.objects.filter(course=course).aggregate(max_o=Max("order"))["max_o"] or 0
            )
            lesson.order = max(lesson.order, (last_order + 1))
            lesson.save()
            messages.success(request, "Жаңа сабақ сәтті қосылды.")
            return redirect("portal:teacher_course_lessons", course_id=course.id)
    else:
        form = TeacherLessonCreateForm(teacher_profile=teacher_profile)
        form.fields.pop("course", None)

    return render(
        request,
        "portal/teacher_course_lesson_add.html",
        {
            "form": form,
            "course": course,
            "page_title": f"{course.title} — Сабақ қосу",
        },
    )


@login_required
def teacher_lesson_add(request):
    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")
    teacher_profile = TeacherProfile.objects.filter(user=request.user).first()
    if teacher_profile is None:
        messages.error(request, "Алдымен оқытушы профилін жасаңыз.")
        return redirect("portal:teacher_profile_edit")

    if request.method == "POST":
        form = TeacherLessonCreateForm(
            request.POST, request.FILES, teacher_profile=teacher_profile
        )
        if form.is_valid():
            lesson = form.save(commit=False)
            last_order = (
                Lesson.objects.filter(course=lesson.course).aggregate(max_o=Max("order"))["max_o"] or 0
            )
            lesson.order = max(lesson.order, (last_order + 1))
            lesson.save()
            messages.success(request, "Жаңа сабақ сәтті қосылды.")
            return redirect("portal:teacher_dashboard")
    else:
        form = TeacherLessonCreateForm(teacher_profile=teacher_profile)

    return render(
        request,
        "portal/teacher_lesson_add.html",
        {"form": form, "page_title": "Сабақ қосу"},
    )


@login_required
def student_courses(request):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")

    q = (request.GET.get("q") or "").strip()
    courses = Course.objects.select_related("teacher__user").order_by("-created_at")
    if q:
        courses = courses.filter(Q(title__icontains=q) | Q(description__icontains=q))

    return render(
        request,
        "portal/student_courses.html",
        {"courses": courses[:30], "search_query": q, "page_title": "Курстар"},
    )


@login_required
def student_course_detail(request, course_id):
    course = Course.objects.select_related("teacher__user").filter(id=course_id).first()
    if course is None:
        raise Http404("Курс табылмады")

    is_course_teacher = (
        request.user.role == User.Role.TEACHER
        and hasattr(request.user, "teacher_profile")
        and course.teacher_id == request.user.teacher_profile.id
    )
    if request.user.role != User.Role.STUDENT and not is_course_teacher:
        return redirect("portal:role_redirect")

    lessons = course.lessons.order_by("order")
    enrollment = None
    completed_lessons = 0
    total_lessons = lessons.count()
    can_take_test = False
    if request.user.role == User.Role.STUDENT:
        enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
        if enrollment:
            completed_lessons, total_lessons = _student_course_completion(enrollment, course)
            can_take_test = total_lessons > 0 and completed_lessons == total_lessons
    course_reviews = course.reviews.select_related("student").order_by("-created_at")
    reviews_summary = course_reviews.aggregate(avg_rating=Avg("rating"), total=Count("id"))
    avg_rating = float(reviews_summary.get("avg_rating") or 0)
    reviews_total = int(reviews_summary.get("total") or 0)

    return render(
        request,
        "portal/student_course_detail.html",
        {
            "course": course,
            "lessons": lessons,
            "enrollment": enrollment,
            "completed_lessons": completed_lessons,
            "total_lessons": total_lessons,
            "can_take_test": can_take_test,
            "course_reviews": course_reviews,
            "avg_rating": avg_rating,
            "reviews_total": reviews_total,
            "page_title": course.title,
        },
    )


@login_required
def student_lesson_detail(request, course_id, lesson_id):
    course = Course.objects.select_related("teacher__user").filter(id=course_id).first()
    if course is None:
        raise Http404("Курс табылмады")

    is_course_teacher = (
        request.user.role == User.Role.TEACHER
        and hasattr(request.user, "teacher_profile")
        and course.teacher_id == request.user.teacher_profile.id
    )
    if request.user.role != User.Role.STUDENT and not is_course_teacher:
        return redirect("portal:role_redirect")

    lesson = course.lessons.filter(id=lesson_id).first()
    if lesson is None:
        raise Http404("Сабақ табылмады")

    enrollment = None
    progress_item = None
    if request.user.role == User.Role.STUDENT:
        enrollment = Enrollment.objects.filter(
            student=request.user, course=course, is_active=True
        ).first()
        if enrollment is None:
            messages.warning(request, "Алдымен курсқа жазылыңыз.")
            return redirect("portal:student_course_detail", course_id=course.id)
        progress_item = Progress.objects.filter(enrollment=enrollment, lesson=lesson).first()
    lessons = course.lessons.order_by("order")
    completed_lessons, total_lessons = _student_course_completion(enrollment, course)
    can_take_test = total_lessons > 0 and completed_lessons == total_lessons

    comments = (
        lesson.comments.filter(parent__isnull=True)
        .select_related("user")
        .prefetch_related("replies__user")
        .order_by("-created_at")
    )

    return render(
        request,
        "portal/student_lesson_detail.html",
        {
            "course": course,
            "lesson": lesson,
            "lessons": lessons,
            "enrollment": enrollment,
            "progress_item": progress_item,
            "can_take_test": can_take_test,
            "comments": comments,
            "page_title": lesson.title,
        },
    )


@login_required
def student_course_test(request, course_id):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")

    course = get_object_or_404(Course, id=course_id)
    enrollment = Enrollment.objects.filter(
        student=request.user, course=course, is_active=True
    ).first()
    if enrollment is None:
        messages.warning(request, "Алдымен курсқа жазылыңыз.")
        return redirect("portal:student_course_detail", course_id=course.id)

    completed_lessons, total_lessons = _student_course_completion(enrollment, course)
    if total_lessons == 0 or completed_lessons != total_lessons:
        messages.warning(
            request,
            "Тестке өту үшін курс сабақтарын толық аяқтауыңыз керек.",
        )
        return redirect("portal:student_course_detail", course_id=course.id)

    test = CourseTest.objects.filter(course=course).first()
    if test is None:
        messages.info(
            request,
            "Бұл курсқа тест дайын емес. Оқытушыдан кейінірек тексеріп көріңіз.",
        )
        return redirect("portal:student_course_detail", course_id=course.id)

    questions = list(test.questions.prefetch_related("options").order_by("order", "id"))
    if not questions:
        messages.info(request, "Тест сұрақтары әлі қосылмаған.")
        return redirect("portal:student_course_detail", course_id=course.id)

    session_key = f"course_test_answers_{test.id}"
    answers = request.session.get(session_key, {})
    current_index = int(request.GET.get("q", 1) or 1)
    current_index = max(1, min(current_index, len(questions)))

    if request.method == "POST":
        question_id = str(request.POST.get("question_id") or "")
        selected_option_id = request.POST.get("selected_option") or ""
        action = request.POST.get("action", "next")

        if question_id and selected_option_id:
            answers[question_id] = selected_option_id
        elif question_id and action != "back":
            answers.pop(question_id, None)

        request.session[session_key] = answers
        request.session.modified = True

        if action == "finish":
            total_questions = len(questions)
            correct_count = 0

            with transaction.atomic():
                attempt = CourseTestAttempt.objects.create(
                    test=test,
                    student=request.user,
                )
                for question in questions:
                    selected_id = answers.get(str(question.id))
                    if not selected_id:
                        continue
                    selected_option = question.options.filter(id=selected_id).first()
                    if selected_option is None:
                        continue
                    is_correct = selected_option.is_correct
                    if is_correct:
                        correct_count += 1
                    CourseTestResponse.objects.create(
                        attempt=attempt,
                        question=question,
                        selected_option=selected_option,
                        is_correct=is_correct,
                    )

                percentage = round((correct_count / total_questions) * 100) if total_questions else 0
                attempt.score = correct_count
                attempt.percentage = percentage
                attempt.save(update_fields=["score", "percentage"])

            if session_key in request.session:
                del request.session[session_key]

            return redirect("portal:student_course_test_result", attempt_id=attempt.id)

        step = -1 if action == "back" else 1
        next_index = max(1, min(current_index + step, len(questions)))
        return redirect(
            f"{reverse('portal:student_course_test', kwargs={'course_id': course.id})}?q={next_index}"
        )

    current_question = questions[current_index - 1]
    selected_option = answers.get(str(current_question.id))
    answered_count = sum(
        1 for question in questions if answers.get(str(question.id))
    )

    return render(
        request,
        "portal/student_course_test.html",
        {
            "course": course,
            "test": test,
            "question": current_question,
            "question_index": current_index,
            "total_questions": len(questions),
            "selected_option": str(selected_option) if selected_option else "",
            "answered_count": answered_count,
            "page_title": f"{course.title} тесті",
        },
    )


@login_required
def student_course_test_result(request, attempt_id):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")

    attempt = get_object_or_404(
        CourseTestAttempt.objects.select_related("test__course"),
        id=attempt_id,
        student=request.user,
    )
    course = attempt.test.course
    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    existing_review = Review.objects.filter(course=course, student=request.user).first()
    existing_certificate = (
        Certificate.objects.filter(enrollment=enrollment).first() if enrollment else None
    )

    if request.method == "POST":
        if existing_review:
            messages.info(request, "Сіз бұл курсқа пікір қалдырып қойдыңыз.")
            return redirect("portal:student_course_test_result", attempt_id=attempt.id)

        rating_value = (request.POST.get("rating") or "").strip()
        comment = (request.POST.get("comment") or "").strip()
        try:
            rating = int(rating_value)
        except (TypeError, ValueError):
            rating = 0

        if rating < 1 or rating > 5:
            messages.error(request, "1-ден 5-ке дейін жұлдыз таңдаңыз.")
            return redirect("portal:student_course_test_result", attempt_id=attempt.id)

        Review.objects.create(
            course=course,
            student=request.user,
            rating=rating,
            comment=comment,
        )
        messages.success(request, "Пікіріңіз сәтті сақталды. Рақмет!")
        return redirect("portal:student_course_test_result", attempt_id=attempt.id)

    band_message = _course_test_band_message(attempt.percentage)

    return render(
        request,
        "portal/student_course_test_result.html",
        {
            "attempt": attempt,
            "band_message": band_message,
            "existing_review": existing_review,
            "existing_certificate": existing_certificate,
            "can_get_certificate": attempt.percentage >= 60,
            "star_range": [1, 2, 3, 4, 5],
            "page_title": "Тест нәтижесі",
        },
    )


@login_required
def download_course_certificate(request, attempt_id):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")

    attempt = get_object_or_404(
        CourseTestAttempt.objects.select_related("test__course__teacher__user"),
        id=attempt_id,
        student=request.user,
    )
    if attempt.percentage < 60:
        messages.warning(request, "Сертификат алу үшін кемінде 60% жинау керек.")
        return redirect("portal:student_course_test_result", attempt_id=attempt.id)

    course = attempt.test.course
    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if enrollment is None:
        messages.warning(request, "Курсқа жазылу жазбасы табылмады.")
        return redirect("portal:student_course_test_result", attempt_id=attempt.id)

    certificate = Certificate.objects.filter(enrollment=enrollment).first()
    if certificate is None:
        certificate_code = _generate_certificate_code()
        try:
            certificate = Certificate.objects.create(
                enrollment=enrollment,
                certificate_code=certificate_code,
                issued_at=timezone.now(),
            )
        except IntegrityError:
            certificate = Certificate.objects.get(enrollment=enrollment)
    if not certificate.file:
        student_name = request.user.full_name or request.user.username
        teacher_name = (
            course.teacher.user.full_name
            if course.teacher and course.teacher.user.full_name
            else course.teacher.user.username
        )
        pdf_bytes = _build_certificate_pdf(
            student_name=student_name,
            course_title=course.title,
            teacher_name=teacher_name,
            percentage=attempt.percentage,
            certificate_code=certificate.certificate_code,
        )
        filename = f"certificate_{course.id}_{request.user.id}.pdf"
        certificate.file.save(filename, ContentFile(pdf_bytes), save=True)

    certificate.file.open("rb")
    return FileResponse(
        certificate.file,
        as_attachment=True,
        filename=f"{certificate.certificate_code}.pdf",
    )


def teachers_list(request):
    teachers = (
        TeacherProfile.objects.select_related("user")
        .annotate(courses_count=Count("courses", distinct=True))
        .order_by("-created_at")
    )
    teacher_cards = [{"profile": profile, "rating": _teacher_rating(profile)} for profile in teachers]
    return render(
        request,
        "portal/teachers_list.html",
        {"teacher_cards": teacher_cards, "page_title": "Оқытушылар"},
    )


def teacher_public_profile(request, teacher_id):
    profile = get_object_or_404(TeacherProfile.objects.select_related("user"), id=teacher_id)
    courses = profile.courses.order_by("-created_at")
    return render(
        request,
        "portal/teacher_public_profile.html",
        {
            "teacher_profile": profile,
            "courses": courses,
            "rating": _teacher_rating(profile),
            "page_title": "Оқытушы профилі",
        },
    )


@login_required
def enroll_course(request, course_id):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")
    if request.method != "POST":
        return redirect("portal:student_course_detail", course_id=course_id)

    course = get_object_or_404(Course, id=course_id)
    if course.price and float(course.price) > 0:
        messages.info(
            request,
            "Бұл ақылы курс. Төлем жасалғаннан кейін жазылу белсенді болады.",
        )
        return redirect("portal:student_course_detail", course_id=course.id)

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user, course=course, defaults={"is_active": True}
    )
    if not created and not enrollment.is_active:
        enrollment.is_active = True
        enrollment.save(update_fields=["is_active"])

    messages.success(request, "Курсқа сәтті жазылдыңыз. Оқуды бастауға болады!")

    return redirect("portal:student_dashboard")


@login_required
def complete_lesson(request, course_id, lesson_id):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")
    if request.method != "POST":
        return redirect("portal:student_lesson_detail", course_id=course_id, lesson_id=lesson_id)

    course = get_object_or_404(Course, id=course_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    enrollment = Enrollment.objects.filter(
        student=request.user, course=course, is_active=True
    ).first()
    if enrollment is None:
        messages.warning(request, "Алдымен курсқа жазылыңыз.")
        return redirect("portal:student_course_detail", course_id=course.id)

    progress_item, _ = Progress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    progress_item.is_completed = True
    progress_item.completed_at = timezone.now()
    progress_item.percentage = 100
    progress_item.save(update_fields=["is_completed", "completed_at", "percentage"])

    lesson_ids = list(course.lessons.values_list("id", flat=True))
    if lesson_ids:
        Progress.objects.filter(enrollment=enrollment, lesson_id__in=lesson_ids).exclude(
            lesson=lesson
        ).update(percentage=0)

    messages.success(request, "Сабақ аяқталды! Прогресс жаңартылды.")
    return redirect("portal:student_lesson_detail", course_id=course.id, lesson_id=lesson.id)


@login_required
def course_payment(request, course_id):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")

    course = get_object_or_404(Course, id=course_id)

    if not course.price or float(course.price) <= 0:
        return redirect("portal:student_course_detail", course_id=course.id)

    existing_enrollment = Enrollment.objects.filter(
        student=request.user, course=course, is_active=True
    ).first()
    if existing_enrollment:
        messages.info(request, "Сіз бұл курсқа жазылып қойғансыз.")
        return redirect("portal:student_course_detail", course_id=course.id)

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            import uuid

            with transaction.atomic():
                enrollment, _ = Enrollment.objects.get_or_create(
                    student=request.user,
                    course=course,
                    defaults={"is_active": True},
                )
                if not enrollment.is_active:
                    enrollment.is_active = True
                    enrollment.save(update_fields=["is_active"])

                Payment.objects.create(
                    enrollment=enrollment,
                    amount=course.price,
                    status=Payment.Status.PAID,
                    transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
                    paid_at=timezone.now(),
                )

            return redirect("portal:payment_success", course_id=course.id)
    else:
        form = PaymentForm()

    return render(
        request,
        "portal/payment.html",
        {
            "course": course,
            "form": form,
            "page_title": "Төлем",
        },
    )


@login_required
def payment_success(request, course_id):
    if request.user.role != User.Role.STUDENT:
        return redirect("portal:role_redirect")

    course = get_object_or_404(Course, id=course_id)
    return render(
        request,
        "portal/payment_success.html",
        {
            "course": course,
            "page_title": "Төлем сәтті өтті",
        },
    )


@login_required
def add_lesson_comment(request, course_id, lesson_id):
    if request.method != "POST":
        return redirect("portal:student_lesson_detail", course_id=course_id, lesson_id=lesson_id)

    course = get_object_or_404(Course, id=course_id)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    is_student = request.user.role == User.Role.STUDENT
    is_course_teacher = (
        request.user.role == User.Role.TEACHER
        and hasattr(request.user, "teacher_profile")
        and course.teacher_id == request.user.teacher_profile.id
    )
    if not is_student and not is_course_teacher:
        messages.error(request, "Сізге комментарий жазуға рұқсат жоқ.")
        return redirect("portal:student_lesson_detail", course_id=course.id, lesson_id=lesson.id)

    content = (request.POST.get("content") or "").strip()
    if not content:
        messages.warning(request, "Комментарий мәтінін жазыңыз.")
        return redirect("portal:student_lesson_detail", course_id=course.id, lesson_id=lesson.id)

    parent_id = request.POST.get("parent_id")
    parent = None
    if parent_id:
        parent = Comment.objects.filter(id=parent_id, lesson=lesson, parent__isnull=True).first()

    Comment.objects.create(
        lesson=lesson,
        user=request.user,
        content=content,
        parent=parent,
    )
    messages.success(request, "Комментарий сәтті жіберілді.")
    return redirect("portal:student_lesson_detail", course_id=course.id, lesson_id=lesson.id)


@login_required
def teacher_review_reply(request, course_id, review_id):
    if request.method != "POST":
        return redirect("portal:student_course_detail", course_id=course_id)

    if request.user.role != User.Role.TEACHER:
        return redirect("portal:role_redirect")

    course = get_object_or_404(Course, id=course_id)
    if not hasattr(request.user, "teacher_profile") or course.teacher_id != request.user.teacher_profile.id:
        messages.error(request, "Бұл курстың пікірлеріне жауап беруге рұқсатыңыз жоқ.")
        return redirect("portal:student_course_detail", course_id=course.id)

    review = get_object_or_404(Review, id=review_id, course=course)
    reply_text = (request.POST.get("teacher_reply") or "").strip()
    if not reply_text:
        messages.warning(request, "Жауап мәтінін жазыңыз.")
        return redirect("portal:student_course_detail", course_id=course.id)

    review.teacher_reply = reply_text
    review.save(update_fields=["teacher_reply"])
    messages.success(request, "Жауабыңыз сәтті сақталды.")
    return redirect("portal:student_course_detail", course_id=course.id)
