import re
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import (
    Category,
    College,
    Conversation,
    Message,
    Product,
    ProductImage,
    ProductReport,
    User,
    Wishlist,
)

PASSWORD = "Password-for-test-125!"


def image_upload(name="listing.png", mime="image/png"):
    output = BytesIO()
    Image.new("RGB", (24, 24), "purple").save(output, "PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type=mime)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class MarketplaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.college = College.objects.create(name="Campus Test College", city="New Delhi")
        cls.category = Category.objects.get(slug="books")
        cls.seller = User.objects.create_user(
            "seller@example.test",
            PASSWORD,
            first_name="Asha",
            email_verified=True,
            college=cls.college,
            location="Library",
        )
        cls.buyer = User.objects.create_user(
            "buyer@example.test", PASSWORD, first_name="Ravi", college=cls.college
        )
        cls.outsider = User.objects.create_user(
            "outside@example.test", PASSWORD, college=cls.college
        )
        cls.item = Product.objects.create(
            title="Statistics textbook",
            seller=cls.seller,
            category=cls.category,
            college=cls.college,
            location="Lab",
            description="Reference on probability",
            price=250,
            condition=Product.Condition.GOOD,
            status=Product.Status.ACTIVE,
        )
        cls.item.images.create(demo_asset="books")

    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings_override = override_settings(MEDIA_ROOT=folder.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def listing_fields(self, **changes):
        return {
            "action": "publish",
            "title": "Campus reference bundle",
            "description": "Three reference books.",
            "price": "480.50",
            "category": self.category.pk,
            "college": self.college.pk,
            "condition": "good",
            "location": "Science building",
            "photos": image_upload(),
            **changes,
        }

    def test_registration_and_email_verification(self):
        response = self.client.post(
            reverse("register"),
            {
                "first_name": "New",
                "last_name": "Student",
                "email": "New@Example.test",
                "college": self.college.pk,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(email="new@example.test")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.email_verified)
        link = re.search(r"/account/confirm/\S+", mail.outbox[0].body)[0]
        self.assertEqual(self.client.get(link).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)
        self.assertRedirects(self.client.post(link), reverse("dashboard"))
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertEqual(self.client.post(link).status_code, 400)

    def test_duplicate_registration_is_case_insensitive(self):
        response = self.client.post(
            reverse("register"),
            {
                "first_name": "Duplicate",
                "email": "BUYER@Example.test",
                "college": self.college.pk,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertContains(response, "An account already uses this email")
        self.assertEqual(User.objects.filter(email__iexact="buyer@example.test").count(), 1)

    def test_login_safe_redirect_and_post_only_logout(self):
        response = self.client.post(
            reverse("login"),
            {"username": "BUYER@example.test", "password": PASSWORD, "next": "//evil.example"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        self.assertRedirects(
            self.client.get(reverse("dashboard")), f"{reverse('login')}?next=/dashboard/"
        )

    def test_password_reset(self):
        response = self.client.post(reverse("password_reset"), {"email": self.buyer.email})
        self.assertRedirects(response, reverse("password_reset_done"))
        link = re.search(r"/account/password/confirm/\S+", mail.outbox[0].body)[0]
        token_url = self.client.get(link).url
        new = "New-password-436!"
        self.assertRedirects(
            self.client.post(token_url, {"new_password1": new, "new_password2": new}),
            reverse("password_reset_complete"),
        )
        self.assertTrue(self.client.login(username=self.buyer.email, password=new))

    def test_profile_ignores_user_id_and_protected_fields(self):
        self.assertEqual(self.client.get(reverse("profile")).status_code, 302)
        self.client.force_login(self.buyer)
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "Ravi Edit",
                "college": self.college.pk,
                "location": "Main gate",
                "email": self.seller.email,
                "is_staff": True,
                "email_verified": True,
                "user_id": self.seller.pk,
                "photo": image_upload(),
            },
        )
        self.assertRedirects(response, reverse("profile"))
        self.buyer.refresh_from_db()
        self.seller.refresh_from_db()
        self.assertEqual(self.buyer.first_name, "Ravi Edit")
        self.assertTrue(self.buyer.photo.name.endswith(".webp"))
        self.assertFalse(self.buyer.is_staff)
        self.assertFalse(self.buyer.email_verified)
        self.assertEqual(self.seller.first_name, "Asha")

    def test_create_listing_with_multiple_images(self):
        self.client.force_login(self.seller)
        response = self.client.post(
            reverse("listing_new"), self.listing_fields(photos=[image_upload(), image_upload()])
        )
        item = Product.objects.get(title="Campus reference bundle")
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.status, "active")
        self.assertEqual(item.images.count(), 2)
        for photo in item.images.all():
            self.assertRegex(photo.file.name, r"^images/[a-f0-9]{32}\.webp$")
            with photo.file.open() as file:
                self.assertEqual(Image.open(file).format, "WEBP")

    def test_rollback_removes_upload_if_database_write_fails(self):
        self.client.force_login(self.seller)
        with patch.object(
            ProductImage, "save", side_effect=RuntimeError("simulated database failure")
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated database failure"):
                self.client.post(reverse("listing_new"), self.listing_fields())
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(list(Path(settings.MEDIA_ROOT).rglob("*.webp")), [])

    def test_retired_photo_is_deleted_after_commit(self):
        self.client.force_login(self.seller)
        self.client.post(reverse("listing_new"), self.listing_fields())
        item = Product.objects.get(title="Campus reference bundle")
        photo = item.images.get()
        path = Path(photo.file.path)
        self.assertTrue(path.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("listing_state", args=[item.pk]), {"action": "delete"})
        self.assertFalse(path.exists())

    def test_resend_email_rate_limit(self):
        self.client.force_login(self.buyer)
        for _ in range(4):
            self.assertRedirects(self.client.post(reverse("resend")), reverse("profile"))
        blocked = self.client.post(reverse("resend"))
        self.assertEqual(blocked.status_code, 429)
        self.assertTrue(blocked.get("Retry-After"))
        self.assertEqual(len(mail.outbox), 4)

    def test_upload_validation_rejects_fakes_mismatches_and_count(self):
        self.client.force_login(self.seller)
        for photo in [
            SimpleUploadedFile("fake.png", b"not an image", content_type="image/png"),
            image_upload("wrong.jpg"),
            image_upload(mime="text/plain"),
            [image_upload() for _ in range(6)],
        ]:
            with self.subTest(photo=photo):
                response = self.client.post(
                    reverse("listing_new"), self.listing_fields(photos=photo)
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("photos", response.context["form"].errors)
        self.assertEqual(Product.objects.count(), 1)

    def test_negative_price_and_missing_publish_photo(self):
        self.client.force_login(self.seller)
        data = self.listing_fields(price="-1", photos=[])
        response = self.client.post(reverse("listing_new"), data)
        self.assertIn("price", response.context["form"].errors)
        self.assertIn("photos", response.context["form"].errors)
        self.assertEqual(Product.objects.count(), 1)

    def test_unverified_user_can_save_private_draft(self):
        self.client.force_login(self.buyer)
        publish = self.client.post(reverse("listing_new"), self.listing_fields())
        self.assertContains(publish, "Confirm your email before publishing a listing.")
        self.client.post(reverse("listing_new"), self.listing_fields(action="draft", photos=[]))
        draft = Product.objects.get(seller=self.buyer)
        self.assertEqual(draft.status, "draft")
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 200)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("marketplace")), draft.title)

    def test_only_owner_can_edit_change_state_or_delete(self):
        edit = reverse("listing_edit", args=[self.item.pk])
        state = reverse("listing_state", args=[self.item.pk])
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.post(edit, self.listing_fields()).status_code, 404)
        self.assertEqual(self.client.post(state, {"action": "delete"}).status_code, 404)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(edit).context["form"]["location"].value(), "Lab")
        self.assertRedirects(
            self.client.post(edit, self.listing_fields(action="save", photos=[])),
            self.item.get_absolute_url(),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.title, "Campus reference bundle")
        self.client.post(state, {"action": "sold"})
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "sold")
        self.assertEqual(Client().get(self.item.get_absolute_url()).status_code, 404)
        self.assertRedirects(self.client.post(state, {"action": "delete"}), reverse("dashboard"))
        self.assertFalse(Product.objects.filter(pk=self.item.pk).exists())

    def test_search_price_and_pagination_keep_filters(self):
        for index in range(13):
            Product.objects.create(
                title=f"Campus probability guide {index}",
                description="Study guide",
                seller=self.seller,
                category=self.category,
                college=self.college,
                price=300 + index,
                location="Library",
                status="active",
                condition="good",
            )
        url = reverse("marketplace")
        response = self.client.get(
            url,
            {
                "q": "proBAbility",
                "min_price": 300,
                "max_price": 312,
                "sort": "low",
                "condition": "good",
            },
        )
        self.assertEqual(response.context["page"].paginator.count, 13)
        self.assertEqual(response.context["page"][0].price, 300)
        self.assertContains(response, "min_price=300")
        self.assertContains(response, "page=2")
        self.assertEqual(
            len(
                self.client.get(url, {"q": "probability", "min_price": 300, "page": 2}).context[
                    "page"
                ]
            ),
            1,
        )
        self.assertEqual(
            self.client.get(url, {"q": "statistics"}).context["page"].paginator.count, 1
        )
        self.assertContains(
            self.client.get(url, {"min_price": 7, "max_price": 3}),
            "Maximum price must be at least the minimum price.",
        )

    def test_inactive_seller_and_removed_products_are_hidden(self):
        User.objects.filter(pk=self.seller.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.item.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("marketplace")), self.item.title)
        User.objects.filter(pk=self.seller.pk).update(is_active=True)
        Product.objects.filter(pk=self.item.pk).update(status="removed")
        self.assertEqual(self.client.get(self.item.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("marketplace")), self.item.title)

    def test_wishlist_unique_post_only_and_csrf_protected(self):
        url = reverse("favorite", args=[self.item.pk])
        self.assertEqual(self.client.post(url, {"action": "add"}).status_code, 302)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(2):
            self.client.post(url, {"action": "add"})
        self.assertEqual(Wishlist.objects.filter(user=self.buyer, product=self.item).count(), 1)
        self.assertContains(self.client.get(reverse("wishlist")), self.item.title)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.buyer)
        self.assertEqual(strict.post(url, {"action": "remove"}).status_code, 403)
        self.client.post(url, {"action": "remove"})
        self.assertFalse(Wishlist.objects.exists())

    def test_message_participants_uniqueness_and_unread(self):
        self.client.force_login(self.seller)
        contact = reverse("contact", args=[self.item.pk])
        self.assertEqual(self.client.post(contact).status_code, 403)
        self.client.force_login(self.buyer)
        for _ in range(2):
            response = self.client.post(contact)
        thread = response.url
        self.assertEqual(Conversation.objects.count(), 1)
        self.client.post(thread, {"body": "Available?", "sender": self.seller.pk})
        self.assertEqual(Message.objects.get().sender, self.buyer)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(thread).status_code, 404)
        self.assertEqual(self.client.post(thread, {"body": "Unauthorized"}).status_code, 404)
        self.assertEqual(self.client.get(f"{thread}?fragment=messages").status_code, 404)
        self.client.force_login(self.seller)
        self.assertContains(self.client.get(reverse("inbox")), "1 unread")
        self.assertContains(self.client.get(f"{thread}?fragment=messages"), "Available?")
        self.assertIsNotNone(Message.objects.get().read_at)
        self.client.post(thread, {"body": "Yes, in the library."})
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(thread), "Yes, in the library.")
        self.assertNotContains(self.client.get(self.item.get_absolute_url()), self.seller.email)

    def test_report_uniqueness_and_staff_permissions(self):
        self.client.force_login(self.buyer)
        report_url = reverse("report", args=[self.item.pk])
        self.assertContains(self.client.get(report_url), "Report listing")
        for _ in range(2):
            self.client.post(report_url, {"reason": "The photo may be misleading."})
        report = ProductReport.objects.get()
        listing_admin = reverse("admin:market_product_changelist")
        report_admin = reverse("admin:market_productreport_changelist")
        action = {"action": "remove", "_selected_action": self.item.pk}
        self.assertEqual(self.client.post(listing_admin, action).status_code, 302)
        staff = User.objects.create_user("moderator@example.test", PASSWORD, is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(listing_admin, action).status_code, 403)
        staff.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="market",
                codename__in=["change_product", "change_productreport", "view_product"],
            )
        )
        self.assertEqual(self.client.post(listing_admin, action).status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, "removed")
        self.assertIsNotNone(self.item.moderated_at)
        self.assertEqual(
            self.client.post(
                report_admin, {"action": "resolve", "_selected_action": report.pk}
            ).status_code,
            302,
        )
        report.refresh_from_db()
        self.assertEqual(report.status, "resolved")
        self.assertIsNotNone(report.resolved_at)

    def test_dashboard_accounts_for_owned_products(self):
        self.client.force_login(self.seller)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(
            {label: value for label, value, _ in response.context["stats"]}["Total listings"], 1
        )
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(
            {label: value for label, value, _ in response.context["stats"]}["Total listings"], 0
        )

    @override_settings(DEBUG=True)
    def test_demo_seed_is_idempotent(self):
        for _ in range(2):
            call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Product.objects.exclude(pk=self.item.pk).count(), 27)
        self.assertEqual(Conversation.objects.count(), 2)
        self.assertEqual(Message.objects.count(), 4)
