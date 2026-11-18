from uuid import uuid4

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse


def image_path(instance, filename):
    return f"images/{uuid4().hex}.webp"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username.strip())

    def _create_user(self, email, password, **fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email.strip().lower(), **fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **fields):
        return self._create_user(email, password, **fields)

    def create_superuser(self, email, password=None, **fields):
        fields.setdefault("is_staff", True)
        fields.setdefault("is_superuser", True)
        if not fields["is_staff"] or not fields["is_superuser"]:
            raise ValueError("Superusers require staff and superuser permissions.")
        return self._create_user(email, password, **fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    college = models.ForeignKey("College", null=True, blank=True, on_delete=models.PROTECT)
    location = models.CharField("campus location", max_length=100, blank=True)
    bio = models.CharField(max_length=500, blank=True)
    photo = models.ImageField(upload_to=image_path, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="unique_normalized_email")]

    @property
    def display_name(self):
        return self.get_full_name() or "CampusConnect member"


class College(models.Model):
    name = models.CharField(max_length=120, unique=True)
    city = models.CharField(max_length=80)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=32, default="package")
    featured_order = models.PositiveSmallIntegerField(default=99)

    class Meta:
        ordering = ["featured_order", "name"]

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status__in=["active", "reserved"], seller__is_active=True)

    def cards(self):
        return self.select_related("seller", "college", "category").prefetch_related("images")


class Product(models.Model):
    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like new"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"
        REMOVED = "removed", "Removed"

    title = models.CharField(max_length=120)
    description = models.TextField(max_length=4000)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    condition = models.CharField(max_length=12, choices=Condition.choices)
    college = models.ForeignKey(College, on_delete=models.PROTECT)
    location = models.CharField("campus pickup location", max_length=100)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    views = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["status", "category", "-created_at"]),
            models.Index(fields=["status", "college", "-created_at"]),
            models.Index(fields=["status", "price"]),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="nonnegative_price")
        ]

    @property
    def cover(self):
        return next(iter(self.images.all()), None)

    def get_absolute_url(self):
        return reverse("detail", args=[self.pk])

    def __str__(self):
        return self.title


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    file = models.ImageField(upload_to=image_path, blank=True)
    demo_asset = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["pk"]


class Wishlist(models.Model):
    user = models.ForeignKey(User, related_name="wishlist", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_saved_product")
        ]


class Conversation(models.Model):
    product = models.ForeignKey(Product, related_name="conversations", on_delete=models.CASCADE)
    buyer = models.ForeignKey(User, related_name="purchases", on_delete=models.CASCADE)
    seller = models.ForeignKey(User, related_name="inquiries", on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "buyer", "seller"], name="unique_product_conversation"
            ),
            models.CheckConstraint(
                condition=~models.Q(buyer=models.F("seller")), name="distinct_participants"
            ),
        ]

    def __str__(self):
        return f"Conversation about {self.product}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["pk"]
        indexes = [models.Index(fields=["conversation", "read_at"])]


class ProductReport(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    product = models.ForeignKey(Product, related_name="reports", on_delete=models.CASCADE)
    reporter = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.CharField(max_length=1000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "reporter"], name="one_report_per_student")
        ]


class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    count = models.PositiveIntegerField(default=0)
