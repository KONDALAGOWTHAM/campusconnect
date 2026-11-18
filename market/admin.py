from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .models import Category, College, Product, ProductReport, User


@admin.register(User)
class StudentAdmin(UserAdmin):
    list_display = (
        "email",
        "first_name",
        "last_name",
        "college",
        "email_verified",
        "is_active",
        "is_staff",
    )
    search_fields = ("email", "first_name", "last_name")
    ordering = ("email",)
    readonly_fields = ("last_login", "date_joined", "email_verified")
    fieldsets = (
        (None, {"fields": ("email", "password", "email_verified")}),
        ("Profile", {"fields": ("first_name", "last_name", "college", "location", "bio")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if change and "email" in form.changed_data:
            obj.email_verified = False
        super().save_model(request, obj, form, change)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "featured_order")


@admin.register(College)
class CollegeAdmin(admin.ModelAdmin):
    search_fields = ("name", "city")
    list_display = ("name", "city")


@admin.register(Product)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "seller", "status", "category", "college", "views", "moderated_at")
    list_filter = ("status", "category", "college", "featured")
    search_fields = ("title", "seller__email")
    list_select_related = ("seller", "college", "category")
    readonly_fields = ("seller", "moderated_at", "created_at", "views")
    actions = ["remove"]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.moderated_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(permissions=["change"], description="Remove selected listings")
    def remove(self, request, queryset):
        count = queryset.update(status=Product.Status.REMOVED, moderated_at=timezone.now())
        self.message_user(request, f"Removed {count} listing(s).")


@admin.register(ProductReport)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("product", "reporter", "status", "created_at", "resolved_at")
    list_select_related = ("product", "reporter")
    list_filter = ("status",)
    readonly_fields = ("product", "reporter", "reason", "created_at", "resolved_at")
    actions = ["resolve"]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data:
            obj.resolved_at = (
                timezone.now() if obj.status == ProductReport.Status.RESOLVED else None
            )
        super().save_model(request, obj, form, change)

    @admin.action(permissions=["change"], description="Resolve selected reports")
    def resolve(self, request, queryset):
        count = queryset.filter(status=ProductReport.Status.OPEN).update(
            status=ProductReport.Status.RESOLVED,
            resolved_at=timezone.now(),
        )
        self.message_user(request, f"Resolved {count} report(s).")


def marketplace_counts(request):
    queries = [
        ("market.view_user", "Registered users", User.objects.all()),
        (
            "market.view_product",
            "Active listings",
            Product.objects.public().filter(status=Product.Status.ACTIVE),
        ),
        (
            "market.view_productreport",
            "Open reports",
            ProductReport.objects.filter(status=ProductReport.Status.OPEN),
        ),
    ]
    return [
        (label, queryset.count())
        for permission, label, queryset in queries
        if request.user.has_perm(permission)
    ]


default_index = admin.site.index


def marketplace_index(request, extra_context=None):
    return default_index(
        request, {**(extra_context or {}), "marketplace_counts": marketplace_counts(request)}
    )


admin.site.index_template = "admin/market_index.html"
admin.site.index = marketplace_index
