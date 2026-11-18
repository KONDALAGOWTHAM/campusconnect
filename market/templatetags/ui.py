from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, css=""):
    return format_html(
        '<svg class="icon {}" aria-hidden="true" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><use href="{}#{}"></use></svg>',
        css,
        static("vendor/icons.svg"),
        name,
    )


@register.simple_tag
def photo_url(image):
    if image.demo_asset:
        return static(f"demo/{image.demo_asset}.webp")
    return image.file.url if image.file else ""


@register.filter
def inr(value):
    amount = f"{value:.2f}"
    rupees, paise = amount.split(".")
    groups = [rupees[-3:]]
    rest = rupees[:-3]
    while rest:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    suffix = f".{paise}" if paise != "00" else ""
    return f"₹{','.join(groups)}{suffix}"
