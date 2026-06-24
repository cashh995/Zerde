import re

from django import forms
from django.contrib.auth import authenticate

from .models import Course, Lesson, Skill, TeacherProfile, User


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_class} form-control".strip()


class StudentRegistrationForm(StyledFormMixin, forms.ModelForm):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Құпиясөз", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("full_name", "email", "password", "major", "group_name")
        labels = {
            "full_name": "Аты-жөні",
            "major": "Мамандығы",
            "group_name": "Тобы",
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if " " in email:
            raise forms.ValidationError("Email-де бос орын болмауы керек.")
        if "@" not in email:
            raise forms.ValidationError("Email-де @ белгісі болуы керек.")
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", email):
            raise forms.ValidationError("Email форматы дұрыс емес. Домені болуы керек (мысалы: .com, .kz, .ru).")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Бұл email бұрыннан тіркелген.")
        return email


class TeacherRegistrationForm(StyledFormMixin, forms.ModelForm):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Құпиясөз", widget=forms.PasswordInput)
    major = forms.CharField(label="Мамандығы", max_length=255)

    class Meta:
        model = User
        fields = ("full_name", "email", "password", "major")
        labels = {
            "full_name": "Аты-жөні",
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if " " in email:
            raise forms.ValidationError("Email-де бос орын болмауы керек.")
        if "@" not in email:
            raise forms.ValidationError("Email-де @ белгісі болуы керек.")
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$", email):
            raise forms.ValidationError("Email форматы дұрыс емес. Домені болуы керек (мысалы: .com, .kz, .ru).")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Бұл email бұрыннан тіркелген.")
        return email


class LoginForm(StyledFormMixin, forms.Form):
    email_or_username = forms.CharField(label="Email немесе логин")
    password = forms.CharField(label="Құпиясөз", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        email_or_username = cleaned_data.get("email_or_username", "").strip()
        password = cleaned_data.get("password")

        if not email_or_username or not password:
            return cleaned_data

        username = email_or_username
        if "@" in email_or_username:
            user = User.objects.filter(email__iexact=email_or_username).first()
            if user:
                username = user.username

        user = authenticate(username=username, password=password)
        if user is None:
            raise forms.ValidationError("Логин немесе құпиясөз қате.")

        cleaned_data["user"] = user
        return cleaned_data


def create_teacher_profile(user: User) -> None:
    TeacherProfile.objects.get_or_create(user=user)


class TeacherCourseCreateForm(StyledFormMixin, forms.ModelForm):
    CATEGORY_CHOICES = (
        ("programming", "Бағдарламалау"),
        ("design", "Дизайн"),
        ("marketing", "Маркетинг"),
        ("language", "Тілдер"),
        ("business", "Бизнес"),
        ("other", "Басқа"),
    )

    category = forms.ChoiceField(label="Категория", choices=CATEGORY_CHOICES)
    is_free = forms.BooleanField(label="Тегін курс", required=False)
    course_image = forms.ImageField(label="Курс суреті", required=False)

    class Meta:
        model = Course
        fields = ("title", "description", "price")
        labels = {
            "title": "Курс атауы",
            "description": "Сипаттама",
            "price": "Баға (₸)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 5
        self.fields["is_free"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_free"):
            cleaned_data["price"] = 0
        return cleaned_data


class TeacherProfileEditForm(StyledFormMixin, forms.ModelForm):
    skills_text = forms.CharField(
        label="Дағдылар (үтір арқылы)",
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "Python, Django, SQL, Data Analysis"}
        ),
    )

    class Meta:
        model = TeacherProfile
        fields = (
            "photo",
            "bio",
            "education_summary",
            "experience_summary",
            "achievements_summary",
            "linkedin",
            "github",
        )
        labels = {
            "photo": "Фото URL",
            "bio": "Өзіңіз туралы",
            "education_summary": "Білімі",
            "experience_summary": "Тәжірибесі",
            "achievements_summary": "Жетістіктері",
            "linkedin": "LinkedIn",
            "github": "GitHub",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bio"].widget.attrs["rows"] = 4
        self.fields["education_summary"].widget.attrs["rows"] = 4
        self.fields["experience_summary"].widget.attrs["rows"] = 4
        self.fields["achievements_summary"].widget.attrs["rows"] = 4

        if self.instance and self.instance.pk:
            skills = self.instance.skills.order_by("name").values_list("name", flat=True)
            self.fields["skills_text"].initial = ", ".join(skills)

    def save(self, commit=True):
        profile = super().save(commit=commit)
        raw_skills = self.cleaned_data.get("skills_text", "")
        names = [s.strip() for s in raw_skills.split(",") if s.strip()]
        unique_names = []
        for name in names:
            if name.lower() not in [x.lower() for x in unique_names]:
                unique_names.append(name)

        profile.skills.exclude(name__in=unique_names).delete()
        for skill_name in unique_names:
            Skill.objects.get_or_create(teacher=profile, name=skill_name)
        return profile


class TeacherLessonCreateForm(StyledFormMixin, forms.ModelForm):
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        label="Курс",
        empty_label="Курсты таңдаңыз",
    )

    class Meta:
        model = Lesson
        fields = ("course", "title", "content", "video_url", "image")
        labels = {
            "title": "Сабақ атауы",
            "content": "Сабақ мәтіні",
            "video_url": "Видео URL",
            "image": "Фото",
        }

    def __init__(self, *args, teacher_profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget.attrs["rows"] = 6
        if teacher_profile is not None:
            self.fields["course"].queryset = Course.objects.filter(
                teacher=teacher_profile
            ).order_by("-created_at")


class PaymentForm(StyledFormMixin, forms.Form):
    card_number = forms.CharField(
        label="Карта нөмірі",
        max_length=19,
        widget=forms.TextInput(attrs={"placeholder": "0000 0000 0000 0000", "maxlength": "19"}),
    )
    card_holder = forms.CharField(
        label="Карта иесінің аты",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "CARDHOLDER NAME"}),
    )
    expiry = forms.CharField(
        label="Мерзімі",
        max_length=5,
        widget=forms.TextInput(attrs={"placeholder": "MM/YY", "maxlength": "5"}),
    )
    cvv = forms.CharField(
        label="CVV",
        max_length=3,
        widget=forms.PasswordInput(attrs={"placeholder": "•••", "maxlength": "3"}),
    )

    def clean_card_number(self):
        value = self.cleaned_data["card_number"].replace(" ", "")
        if not value.isdigit() or len(value) != 16:
            raise forms.ValidationError("Карта нөмірі 16 саннан тұруы керек.")
        return value

    def clean_expiry(self):
        value = self.cleaned_data["expiry"].strip()
        if len(value) != 5 or value[2] != "/":
            raise forms.ValidationError("MM/YY форматында енгізіңіз.")
        mm, yy = value[:2], value[3:]
        if not mm.isdigit() or not yy.isdigit():
            raise forms.ValidationError("MM/YY форматында енгізіңіз.")
        if not (1 <= int(mm) <= 12):
            raise forms.ValidationError("Ай 01-ден 12-ге дейін болуы керек.")
        return value

    def clean_cvv(self):
        value = self.cleaned_data["cvv"].strip()
        if not value.isdigit() or len(value) != 3:
            raise forms.ValidationError("CVV 3 саннан тұруы керек.")
        return value


class TeacherCourseEditForm(StyledFormMixin, forms.ModelForm):
    CATEGORY_CHOICES = TeacherCourseCreateForm.CATEGORY_CHOICES
    category = forms.ChoiceField(label="Категория", choices=CATEGORY_CHOICES)
    is_free = forms.BooleanField(label="Тегін курс", required=False)
    course_image = forms.ImageField(label="Курс суреті", required=False)

    class Meta:
        model = Course
        fields = ("title", "description", "price")
        labels = {
            "title": "Курс атауы",
            "description": "Сипаттама",
            "price": "Баға (₸)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget.attrs["rows"] = 5
        self.fields["is_free"].widget.attrs["class"] = "form-check-input"

        if self.instance and self.instance.pk:
            self.fields["is_free"].initial = (self.instance.price or 0) == 0
            category_code = "other"
            description = (self.instance.description or "").strip()
            for code, label in self.CATEGORY_CHOICES:
                if f"Категория: {label}" in description:
                    category_code = code
                    break
            self.fields["category"].initial = category_code

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("is_free"):
            cleaned_data["price"] = 0
        return cleaned_data


class StudentProfileEditForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "email", "major", "group_name")
        labels = {
            "full_name": "Аты-жөні",
            "email": "Email",
            "major": "Мамандығы",
            "group_name": "Тобы",
        }


class TeacherLessonEditForm(StyledFormMixin, forms.ModelForm):
    remove_image = forms.BooleanField(label="Суретті өшіру", required=False)
    remove_video = forms.BooleanField(label="Видеоны өшіру", required=False)

    class Meta:
        model = Lesson
        fields = ("title", "content", "video_url", "image")
        labels = {
            "title": "Сабақ атауы",
            "content": "Сабақ мәтіні",
            "video_url": "Видео URL",
            "image": "Жаңа сурет",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget.attrs["rows"] = 6
        self.fields["video_url"].required = False
        self.fields["image"].required = False
        self.fields["remove_image"].widget.attrs["class"] = "form-check-input"
        self.fields["remove_video"].widget.attrs["class"] = "form-check-input"
        
        if "image" in self.fields:
            self.fields["image"].widget.initial_text = ""
            self.fields["image"].widget.clear_checkbox_label = ""

    def save(self, commit=True):
        lesson = super().save(commit=False)
        if self.cleaned_data.get("remove_image") and not self.cleaned_data.get("image"):
            lesson.image = None
        if self.cleaned_data.get("remove_video"):
            lesson.video_url = ""
        if commit:
            lesson.save()
        return lesson        