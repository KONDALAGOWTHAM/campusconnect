import logging
from smtplib import SMTPException

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Count, F, Q, Sum
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
    require_safe,
)

from .forms import (
    MessageForm,
    ProductForm,
    ProfileForm,
    RegistrationForm,
    ReportForm,
    SearchForm,
)
from .media import delete_after_commit, media_transaction, save_upload
from .models import (
    Category,
    Conversation,
    Message,
    Product,
    ProductImage,
    ProductReport,
    User,
    Wishlist,
)
from .services import rate_limit, send_verification, verification_token

logger = logging.getLogger(__name__)


@never_cache
@require_safe
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return HttpResponse("Unavailable", status=503, content_type="text/plain")
    return HttpResponse("OK", content_type="text/plain")


def home(request):
    public = Product.objects.public().cards()
    featured = list(public.filter(featured=True)[:4])
    if len(featured) < 4:
        featured += list(public.exclude(pk__in=[item.pk for item in featured])[: 4 - len(featured)])
    return render(
        request,
        "market/home.html",
        {
            "categories": Category.objects.all()[:9],
            "featured": featured,
            "recent": public.exclude(pk__in=[item.pk for item in featured])[:4],
        },
    )


def marketplace(request):
    form = SearchForm(request.GET)
    results = form.apply(Product.objects.public().cards())
    page = Paginator(results, 12).get_page(request.GET.get("page"))
    return render(request, "market/marketplace.html", {"form": form, "page": page})


def detail(request, pk):
    account = request.user
    allowed = Q(status__in=[Product.Status.ACTIVE, Product.Status.RESERVED], seller__is_active=True)
    if account.is_authenticated:
        allowed |= Q(seller=account)
    product = get_object_or_404(Product.objects.cards().filter(allowed), pk=pk)
    owned = account.is_authenticated and account.pk == product.seller_id
    if not owned:
        Product.objects.filter(pk=pk).update(views=F("views") + 1)
    saved = (
        account.is_authenticated and Wishlist.objects.filter(user=account, product=product).exists()
    )
    similar = Product.objects.public().cards().filter(category=product.category).exclude(pk=pk)[:4]
    return render(
        request,
        "market/detail.html",
        {
            "product": product,
            "owned": owned,
            "saved": saved,
            "similar": similar,
            "contactable": product.status == Product.Status.ACTIVE,
        },
    )


def queue_verification(request, user):
    try:
        send_verification(request, user)
    except (OSError, SMTPException):
        logger.exception("Could not send a verification email")
        messages.error(
            request, "Confirmation email could not be sent. Try resending from your profile."
        )
    else:
        messages.success(request, "Check your inbox for your confirmation link.")


@require_http_methods(["GET", "POST"])
@rate_limit("register", 12, 900, by_ip=True)
def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            form.add_error("email", "An account already uses this email address.")
        else:
            login(request, user)
            queue_verification(request, user)
            return redirect("dashboard")
    return render(request, "registration/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
@rate_limit("verify", 20, 900, by_ip=True)
def verify_email(request, pk, token):
    user = get_object_or_404(User, pk=pk, is_active=True)
    if user.email_verified or not verification_token.check_token(user, token):
        return render(request, "registration/verify.html", {"invalid": True}, status=400)
    if request.method == "POST":
        updated = User.objects.filter(
            pk=pk, email=user.email, password=user.password, is_active=True, email_verified=False
        ).update(email_verified=True)
        if updated:
            messages.success(request, "Your email address is confirmed.")
            return redirect("dashboard")
        return render(request, "registration/verify.html", {"invalid": True}, status=400)
    return render(request, "registration/verify.html")


@login_required
@require_POST
@rate_limit("resend", 4, 3600)
def resend(request):
    if not request.user.email_verified:
        queue_verification(request, request.user)
    return redirect("profile")


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    if request.method == "POST":
        with media_transaction() as uploaded:
            user = User.objects.select_for_update().get(pk=request.user.pk)
            previous_photo = user.photo
            form = ProfileForm(request.POST, request.FILES, instance=user)
            if form.is_valid():
                changed = form.save(commit=False)
                if "photo" in form.changed_data:
                    save_upload(changed.photo, form.cleaned_data["photo"], uploaded)
                changed.save(update_fields=form.fields.keys())
                if previous_photo.name != changed.photo.name:
                    delete_after_commit(previous_photo)
                messages.success(request, "Profile updated.")
                return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "market/profile.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
@rate_limit("listing", 30, 3600)
def listing(request, pk=None):
    if request.method == "POST":
        with media_transaction() as uploaded:
            return edit_listing(request, pk, uploaded)
    return edit_listing(request, pk)


def edit_listing(request, pk, uploaded=None):
    owned = Product.objects.filter(seller=request.user).exclude(status=Product.Status.REMOVED)
    if uploaded is not None:
        owned = owned.select_for_update()
    product = get_object_or_404(owned, pk=pk) if pk else None
    initial = {"college": request.user.college_id, "location": request.user.location}
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in {"draft", "publish", "save"} or (action == "save" and not product):
            return HttpResponseBadRequest("Choose a valid listing action.")
        status = {"draft": Product.Status.DRAFT, "publish": Product.Status.ACTIVE}.get(action)
        if status is None:
            status = product.status
        visible = status in {Product.Status.ACTIVE, Product.Status.RESERVED}
        form = ProductForm(request.POST, request.FILES, instance=product, publish=visible)
        if visible and not request.user.email_verified:
            form.add_error(None, "Confirm your email before publishing a listing.")
        if form.is_valid():
            item = form.save(commit=False)
            item.seller = request.user
            item.status = status
            item.save()
            item.images.exclude(pk__in=[photo.pk for photo in form.kept_images]).delete()
            for photo in form.cleaned_data.get("photos") or []:
                image = ProductImage(product=item)
                save_upload(image.file, photo, uploaded)
                image.save()
            messages.success(
                request, "Listing saved." if status == Product.Status.DRAFT else "Listing updated."
            )
            return redirect(item)
    else:
        form = ProductForm(instance=product, initial=initial if not product else None)
    return render(request, "market/listing.html", {"form": form, "product": product})


@login_required
@require_POST
def listing_state(request, pk):
    action = request.POST.get("action")
    with transaction.atomic():
        item = get_object_or_404(Product.objects.select_for_update(), seller=request.user, pk=pk)
        if item.status == Product.Status.REMOVED:
            raise Http404
        if action == "delete":
            item.delete()
            messages.success(request, "Listing deleted.")
            return redirect("dashboard")
        choices = {
            "sold": Product.Status.SOLD,
            "reserve": Product.Status.RESERVED,
            "activate": Product.Status.ACTIVE,
        }
        status = choices.get(action)
        if not status or item.status == Product.Status.DRAFT:
            return HttpResponseBadRequest("This transition is unavailable.")
        if status in {Product.Status.ACTIVE, Product.Status.RESERVED} and (
            not request.user.email_verified or not item.images.exists()
        ):
            return HttpResponseForbidden("Confirm your email and add a listing photo first.")
        item.status = status
        item.save(update_fields=["status", "updated_at"])
    messages.success(request, "Availability updated.")
    return redirect(item)


@login_required
def wishlist(request):
    products = (
        Product.objects.public()
        .cards()
        .filter(wishlist__user=request.user)
        .order_by("-wishlist__created_at")
    )
    page = Paginator(products, 12).get_page(request.GET.get("page"))
    return render(request, "market/wishlist.html", {"page": page})


@login_required
@require_POST
def favorite(request, pk):
    action = request.POST.get("action")
    saved = Wishlist.objects.filter(user=request.user, product_id=pk)
    if action == "remove":
        saved.delete()
        messages.success(request, "Removed from your saved items.")
    elif action == "add":
        item = get_object_or_404(Product.objects.public(), pk=pk)
        Wishlist.objects.get_or_create(user=request.user, product=item)
        messages.success(request, "Saved to your wishlist.")
    else:
        return HttpResponseBadRequest("Choose a valid wishlist action.")
    return (
        redirect("wishlist")
        if request.POST.get("source") == "wishlist"
        else redirect("detail", pk=pk)
    )


@login_required
@require_POST
@rate_limit("contact", 30, 900)
def contact(request, pk):
    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update(of=("self",)).public(),
            pk=pk,
            status=Product.Status.ACTIVE,
        )
        if product.seller_id == request.user.pk:
            return HttpResponseForbidden("You cannot contact yourself.")
        conversation, _ = Conversation.objects.get_or_create(
            product=product, buyer=request.user, seller=product.seller
        )
    return redirect("thread", pk=conversation.pk)


def conversations(account):
    return Conversation.objects.filter(Q(buyer=account) | Q(seller=account)).select_related(
        "product", "buyer", "seller"
    )


@login_required
@never_cache
def inbox(request):
    threads = conversations(request.user).annotate(
        unread=Count(
            "messages", filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=request.user)
        ),
    )
    page = Paginator(threads.order_by("-updated_at", "-pk"), 20).get_page(request.GET.get("page"))
    return render(request, "market/inbox.html", {"page": page})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@rate_limit("message", 45, 60)
def thread(request, pk):
    conversation = get_object_or_404(conversations(request.user), pk=pk)
    form = MessageForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        with transaction.atomic():
            Message.objects.create(
                conversation=conversation, sender=request.user, body=form.cleaned_data["body"]
            )
            conversation.save(update_fields=["updated_at"])
        return redirect("thread", pk=pk)
    history = conversation.messages.select_related("sender").order_by("-pk")
    page = Paginator(history, 50).get_page(request.GET.get("page"))
    entries = list(reversed(list(page.object_list)))
    Message.objects.filter(
        pk__in=[entry.pk for entry in entries if entry.sender_id != request.user.pk],
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    context = {"conversation": conversation, "entries": entries, "page": page, "form": form}
    template = (
        "market/message_list.html"
        if request.GET.get("fragment") == "messages"
        else "market/thread.html"
    )
    return render(request, template, context)


@login_required
@require_http_methods(["GET", "POST"])
@rate_limit("report", 12, 3600)
def report(request, pk):
    product = get_object_or_404(Product.objects.public().exclude(seller=request.user), pk=pk)
    form = ReportForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        _, created = ProductReport.objects.get_or_create(
            product=product, reporter=request.user, defaults={"reason": form.cleaned_data["reason"]}
        )
        messages.success(
            request, "Report sent for review." if created else "You already reported this listing."
        )
        return redirect(product)
    return render(request, "market/report.html", {"form": form, "product": product})


@login_required
def dashboard(request):
    products = Product.objects.filter(seller=request.user)
    counts = products.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(status="active")),
        sold=Count("pk", filter=Q(status="sold")),
        views=Sum("views", default=0),
    )
    received = Message.objects.filter(conversation__in=conversations(request.user)).exclude(
        sender=request.user
    )
    stats = [
        ("Total listings", counts["total"], "package"),
        ("Active listings", counts["active"], "circle-check"),
        ("Sold listings", counts["sold"], "badge-check"),
        (
            "Saved items",
            Product.objects.public().filter(wishlist__user=request.user).count(),
            "heart",
        ),
        ("Messages received", received.count(), "message-circle"),
        ("Listing views", counts["views"], "eye"),
    ]
    grouped = dict(
        products.order_by()
        .values("status")
        .annotate(count=Count("pk"))
        .values_list("status", "count")
    )
    breakdown = {
        "labels": [label for _, label in Product.Status.choices],
        "values": [grouped.get(key, 0) for key in Product.Status.values],
    }
    page = Paginator(products.cards(), 10).get_page(request.GET.get("page"))
    return render(
        request,
        "market/dashboard.html",
        {
            "stats": stats,
            "breakdown": breakdown,
            "page": page,
            "status_counts": zip(breakdown["labels"], breakdown["values"]),
            "activity": received.order_by("-pk").select_related("conversation__product", "sender")[
                :4
            ],
        },
    )
