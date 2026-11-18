from io import BytesIO
from pathlib import Path

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Category, College, Product, User

MAX_IMAGES = 5
ALLOWED_TYPES = {
    "JPEG": ({"jpg", "jpeg"}, "image/jpeg"),
    "PNG": ({"png"}, "image/png"),
    "WEBP": ({"webp"}, "image/webp"),
}


def clean_image(upload):
    if upload.size > 5 * 1024 * 1024:
        raise forms.ValidationError("Each image must be 5 MB or smaller.")
    extension = Path(upload.name).suffix.lower().lstrip(".")
    try:
        with Image.open(upload, formats=list(ALLOWED_TYPES)) as source:
            extensions, mime_type = ALLOWED_TYPES[source.format]
            if extension not in extensions or upload.content_type != mime_type:
                raise forms.ValidationError(
                    "The file extension and content type must match the image."
                )
            if source.width * source.height > 20_000_000 or getattr(source, "is_animated", False):
                raise forms.ValidationError("Use a still image under 20 megapixels.")
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1600, 1600))
            clean = BytesIO()
            image.save(clean, format="WEBP", quality=86)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as error:
        raise forms.ValidationError("Upload a valid JPG, PNG or WebP image.") from error
    return ContentFile(clean.getvalue(), name="photo.webp")


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label="First name")
    college = forms.ModelChoiceField(queryset=College.objects.all())

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "college"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already uses this email address.")
        return email


class ProfileForm(forms.ModelForm):
    photo = forms.FileField(
        required=False, widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "college", "location", "bio", "photo"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if photo and hasattr(photo, "content_type"):
            return clean_image(photo)
        return photo


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ProductForm(forms.ModelForm):
    photos = forms.Field(
        required=False,
        widget=MultiFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
                "data-photos": "",
            }
        ),
    )
    remove_photos = forms.MultipleChoiceField(required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Product
        fields = ["title", "description", "price", "category", "condition", "college", "location"]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Describe the item, its condition and what’s included.",
                }
            ),
            "title": forms.TextInput(attrs={"placeholder": "e.g. Casio scientific calculator"}),
        }

    def __init__(self, *args, publish=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.publish = publish
        self.current_images = list(self.instance.images.all()) if self.instance.pk else []
        self.fields["remove_photos"].choices = [
            (str(photo.pk), f"Remove photo {index}")
            for index, photo in enumerate(self.current_images, 1)
        ]

    def clean(self):
        cleaned = super().clean()
        uploads = cleaned.get("photos") or []
        removals = set(cleaned.get("remove_photos") or [])
        self.kept_images = [photo for photo in self.current_images if str(photo.pk) not in removals]
        count = len(self.kept_images) + len(uploads)
        if count > MAX_IMAGES:
            self.add_error("photos", "A listing can have up to five images.")
        elif self.publish and count == 0:
            self.add_error("photos", "Add at least one photo before publishing.")
        elif uploads:
            try:
                cleaned["photos"] = [clean_image(photo) for photo in uploads]
            except forms.ValidationError as error:
                self.add_error("photos", error)
        return cleaned


class SearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=120)
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        to_field_name="slug",
        required=False,
        empty_label="All categories",
    )
    college = forms.ModelChoiceField(
        queryset=College.objects.all(), required=False, empty_label="All colleges"
    )
    condition = forms.ChoiceField(
        choices=[("", "Any condition"), *Product.Condition.choices], required=False
    )
    min_price = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2, label="Minimum price"
    )
    max_price = forms.DecimalField(
        required=False, min_value=0, max_digits=10, decimal_places=2, label="Maximum price"
    )
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ("newest", "Newest first"),
            ("oldest", "Oldest first"),
            ("low", "Price: low to high"),
            ("high", "Price: high to low"),
        ],
    )

    def clean(self):
        cleaned = super().clean()
        minimum, maximum = cleaned.get("min_price"), cleaned.get("max_price")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("max_price", "Maximum price must be at least the minimum price.")
        return cleaned

    def apply(self, products):
        if not self.is_valid():
            return products.none()
        data = self.cleaned_data
        if data["q"]:
            from django.db.models import Q

            products = products.filter(
                Q(title__icontains=data["q"]) | Q(description__icontains=data["q"])
            )
        for field in ("category", "college", "condition"):
            if data[field]:
                products = products.filter(**{field: data[field]})
        for field, lookup in (("min_price", "price__gte"), ("max_price", "price__lte")):
            if data[field] is not None:
                products = products.filter(**{lookup: data[field]})
        ordering = {
            "oldest": ("created_at", "pk"),
            "low": ("price", "-pk"),
            "high": ("-price", "-pk"),
        }
        return products.order_by(*ordering.get(data["sort"], ("-created_at", "-pk")))


class MessageForm(forms.Form):
    body = forms.CharField(
        label="Message",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Write a message…"}),
    )


class ReportForm(forms.Form):
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"rows": 5}))
