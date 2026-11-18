from datetime import datetime
from datetime import timezone as utc
from functools import wraps
from hashlib import sha256

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db.models import F
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from .models import RateBucket


class VerificationToken(PasswordResetTokenGenerator):
    key_salt = "market.email.verification"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}:{user.email}:{user.password}:{user.email_verified}:{timestamp}"


verification_token = VerificationToken()


def send_verification(request, user):
    path = reverse("verify_email", args=[user.pk, verification_token.make_token(user)])
    url = (
        settings.PUBLIC_BASE_URL + path
        if settings.PUBLIC_BASE_URL
        else request.build_absolute_uri(path)
    )
    send_mail(
        "Confirm your CampusConnect email",
        f"Open this link to confirm your email address:\n\n{url}\n",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )


def rate_limit(scope, count, seconds, *, by_ip=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST":
                now = int(timezone.now().timestamp())
                window = now // seconds
                identity = request.META.get("REMOTE_ADDR", "unknown")
                if request.user.is_authenticated and not by_ip:
                    identity = request.user.pk
                key = sha256(f"{scope}:{identity}:{window}".encode()).hexdigest()
                bucket, _ = RateBucket.objects.get_or_create(
                    key=key,
                    defaults={
                        "expires_at": datetime.fromtimestamp((window + 1) * seconds, utc.utc)
                    },
                )
                accepted = RateBucket.objects.filter(pk=bucket.pk, count__lt=count).update(
                    count=F("count") + 1
                )
                if not accepted:
                    return HttpResponse(
                        "Too many attempts. Please try again later.",
                        status=429,
                        headers={"Retry-After": str((window + 1) * seconds - now)},
                    )
            return view(request, *args, **kwargs)

        return wrapped

    return decorate
