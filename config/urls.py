from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path, reverse_lazy
from django.views.generic import TemplateView

from market import views
from market.services import rate_limit

admin.site.site_header = "CampusConnect administration"
admin.site.site_title = "CampusConnect"
admin.site.index_title = "Marketplace management"
admin.site.login = rate_limit("admin-login", 60, 900, by_ip=True)(admin.site.login)

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("marketplace/", views.marketplace, name="marketplace"),
    path("safety/", TemplateView.as_view(template_name="market/safety.html"), name="safety"),
    path("listings/new/", views.listing, name="listing_new"),
    path("listings/<int:pk>/", views.detail, name="detail"),
    path("listings/<int:pk>/edit/", views.listing, name="listing_edit"),
    path("listings/<int:pk>/state/", views.listing_state, name="listing_state"),
    path("listings/<int:pk>/save/", views.favorite, name="favorite"),
    path("listings/<int:pk>/contact/", views.contact, name="contact"),
    path("listings/<int:pk>/report/", views.report, name="report"),
    path("saved/", views.wishlist, name="wishlist"),
    path("inbox/", views.inbox, name="inbox"),
    path("inbox/<int:pk>/", views.thread, name="thread"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("account/profile/", views.profile, name="profile"),
    path("account/register/", views.register, name="register"),
    path("account/confirm/<int:pk>/<str:token>/", views.verify_email, name="verify_email"),
    path("account/resend/", views.resend, name="resend"),
    path(
        "account/login/",
        rate_limit("login", 60, 900, by_ip=True)(auth.LoginView.as_view()),
        name="login",
    ),
    path("account/logout/", auth.LogoutView.as_view(), name="logout"),
    path(
        "account/password/reset/",
        rate_limit("reset", 15, 900, by_ip=True)(
            auth.PasswordResetView.as_view(
                success_url=reverse_lazy("password_reset_done"),
                extra_email_context={
                    "domain": settings.PUBLIC_BASE_URL.removeprefix("https://")
                    if settings.PUBLIC_BASE_URL
                    else None,
                }
                if settings.PUBLIC_BASE_URL
                else None,
            )
        ),
        name="password_reset",
    ),
    path(
        "account/password/sent/", auth.PasswordResetDoneView.as_view(), name="password_reset_done"
    ),
    path(
        "account/password/confirm/<uidb64>/<token>/",
        rate_limit("reset-confirm", 30, 900, by_ip=True)(auth.PasswordResetConfirmView.as_view()),
        name="password_reset_confirm",
    ),
    path(
        "account/password/complete/",
        auth.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
