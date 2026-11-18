import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from market.models import (
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

PRODUCTS = [
    (
        "Everyday canvas backpack",
        "fashion",
        "backpack",
        690,
        "good",
        "Padded straps and a separate pocket for a 14-inch laptop. Small mark on the base.",
    ),
    (
        "Scientific calculator",
        "other",
        "calculator",
        650,
        "good",
        "Working scientific calculator with a slide-on cover. Batteries included.",
    ),
    (
        "Reading lamp for a hostel desk",
        "hostel",
        "lamp",
        480,
        "good",
        "Compact adjustable lamp with a warm LED bulb and a long cable.",
    ),
    (
        "Office task chair",
        "furniture",
        "chair",
        1900,
        "fair",
        "Height adjustment works. Light wear on the armrests. Pickup only.",
    ),
    (
        "Outdoor training basketball",
        "sports",
        "basketball",
        590,
        "new",
        "Unused standard-size rubber ball, inflated and ready for outdoor courts.",
    ),
    (
        "Database systems textbook bundle",
        "books",
        "books",
        920,
        "good",
        "Three reference books from my database systems course with a few notes in pencil.",
    ),
    (
        "Hybrid bicycle with front light",
        "bicycles",
        "bicycle",
        4700,
        "good",
        "Recently serviced brakes and gears. Comes with a working front light.",
    ),
    (
        "USB-C student laptop",
        "electronics",
        "laptop",
        26500,
        "good",
        "14-inch laptop with 8 GB RAM and a 256 GB SSD. Original charger included.",
    ),
    (
        "Wireless over-ear headphones",
        "phones",
        "headphones",
        1800,
        "like_new",
        "Bluetooth over-ear headphones with the charging cable and travel pouch.",
    ),
    (
        "Weekend daypack",
        "fashion",
        "backpack",
        860,
        "like_new",
        "Lightweight canvas daypack with an easy-access front pocket and adjustable straps.",
    ),
    (
        "Spare calculator for exams",
        "other",
        "calculator",
        440,
        "fair",
        "Reliable scientific calculator with visible scratches on the lid. Buttons are all responsive.",
    ),
    (
        "Adjustable study lamp",
        "hostel",
        "lamp",
        750,
        "like_new",
        "Low-glare desk lamp with an adjustable arm. Used for one semester.",
    ),
    (
        "Swivel chair for a dorm room",
        "furniture",
        "chair",
        2400,
        "good",
        "Black swivel chair with smooth castors. Fits neatly under a small desk.",
    ),
    (
        "Indoor basketball",
        "sports",
        "basketball",
        800,
        "like_new",
        "Size 7 composite ball used for a handful of indoor practice sessions.",
    ),
    (
        "Microeconomics and statistics books",
        "books",
        "books",
        1050,
        "good",
        "Core reading for first-year economics. Includes a basic probability reference.",
    ),
    (
        "Single-speed campus bicycle",
        "bicycles",
        "bicycle",
        3400,
        "fair",
        "Simple commuter. Some paint chips, with fresh tubes and working brakes.",
    ),
    (
        "Lightweight 13-inch notebook",
        "electronics",
        "laptop",
        23500,
        "fair",
        "Good for note-taking and browsing. Some corner scratches. Charger included.",
    ),
    (
        "Over-ear headphones with cable",
        "phones",
        "headphones",
        950,
        "good",
        "Comfortable headphones for lectures and calls. Includes the detachable cable.",
    ),
    (
        "Canvas book bag",
        "fashion",
        "backpack",
        420,
        "fair",
        "Room for a few textbooks and a water bottle. Clean inside, faded from use.",
    ),
    (
        "Engineering calculator with cover",
        "other",
        "calculator",
        720,
        "like_new",
        "Supports fractions, matrices and statistics. Includes original hard cover.",
    ),
    (
        "Compact bedside lamp",
        "hostel",
        "lamp",
        380,
        "good",
        "Small lamp ideal for a hostel bedside. Switch and bulb work.",
    ),
    (
        "Mesh study chair",
        "furniture",
        "chair",
        2600,
        "good",
        "Height-adjustable mesh chair with padded seat. Available for collection this week.",
    ),
    (
        "Practice basketball, size 7",
        "sports",
        "basketball",
        450,
        "fair",
        "Used for campus games. Still holds air and has plenty of grip.",
    ),
    (
        "Calculus & linear algebra bundle",
        "books",
        "books",
        850,
        "good",
        "Three semester reference books. Some chapters have neat margin notes.",
    ),
    (
        "Bluetooth noise-cancelling headphones",
        "phones",
        "headphones",
        2400,
        "like_new",
        "Lightly used set with noise cancellation and a USB-C cable.",
    ),
    (
        "City commuter bicycle",
        "bicycles",
        "bicycle",
        5200,
        "good",
        "Six-speed bicycle with a kickstand and bell. Test ride on campus before buying.",
    ),
    (
        "13-inch laptop, 256 GB SSD",
        "electronics",
        "laptop",
        28900,
        "like_new",
        "Clean 13-inch notebook for coursework. Includes original charger and soft sleeve.",
    ),
]


class Command(BaseCommand):
    help = "Seed local-only fictional users, 27 listings, messages and saved items."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data can only be seeded in development mode.")
        password = os.getenv("DEMO_PASSWORD", "CampusDemo2026!")
        colleges = [
            College.objects.get_or_create(name=name, defaults={"city": city})[0]
            for name, city in [
                ("IIT Delhi", "New Delhi"),
                ("BITS Pilani", "Pilani"),
                ("Christ University", "Bengaluru"),
                ("Manipal Institute of Technology", "Manipal"),
            ]
        ]
        students = []
        for index, (first, last) in enumerate(
            [("Aarav", "Mehta"), ("Diya", "Rao"), ("Isha", "Kapoor"), ("Kabir", "Shah")]
        ):
            email = f"{first.lower()}.demo@example.test"
            student, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "college": colleges[index],
                    "location": "Central Library",
                    "email_verified": True,
                },
            )
            if not created and (student.is_staff or student.is_superuser):
                raise CommandError(f"Demo address {email} belongs to a staff account.")
            if created:
                student.set_password(password)
                student.save(update_fields=["password"])
            students.append(student)

        categories = Category.objects.in_bulk(field_name="slug")
        listed = []
        for index, (title, slug, asset, price, condition, description) in enumerate(PRODUCTS):
            seller = students[index % len(students)]
            product, created = Product.objects.get_or_create(
                seller=seller,
                title=title,
                defaults={
                    "description": description,
                    "price": price,
                    "condition": condition,
                    "category": categories[slug],
                    "college": seller.college,
                    "location": [
                        "Library courtyard",
                        "Student activity centre",
                        "Campus café",
                        "Main gate",
                    ][index % 4],
                    "status": Product.Status.ACTIVE,
                    "featured": index >= len(PRODUCTS) - 4,
                    "views": 8 + index * 3,
                },
            )
            if created:
                ProductImage.objects.create(product=product, demo_asset=asset)
            listed.append(product)

        for buyer, product in [(students[0], listed[-1]), (students[3], listed[-2])]:
            Wishlist.objects.get_or_create(user=buyer, product=product)
            chat, created = Conversation.objects.get_or_create(
                product=product, buyer=buyer, seller=product.seller
            )
            if created:
                Message.objects.create(
                    conversation=chat,
                    sender=buyer,
                    body="Hi! Is the item still available for pickup this week?",
                )
                Message.objects.create(
                    conversation=chat,
                    sender=product.seller,
                    body="Yes! I can meet in a public spot on campus after class.",
                )
        ProductReport.objects.get_or_create(
            product=listed[1],
            reporter=students[0],
            defaults={"reason": "Demo report for the moderation workflow."},
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Seeded 27 fictional listings. Demo sign-in: aarav.demo@example.test (see README for password)."
            )
        )
