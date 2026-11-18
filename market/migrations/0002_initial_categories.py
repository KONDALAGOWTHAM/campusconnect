from django.db import migrations

CATEGORIES = [
    ("Books & Study Materials", "books", "book-open"),
    ("Laptops & Electronics", "electronics", "laptop"),
    ("Phones & Accessories", "phones", "smartphone"),
    ("Bicycles", "bicycles", "bike"),
    ("Hostel Essentials", "hostel", "lamp-desk"),
    ("Furniture", "furniture", "armchair"),
    ("Sports Equipment", "sports", "dumbbell"),
    ("Fashion & Accessories", "fashion", "shirt"),
    ("Other Student Items", "other", "package"),
]


def create_categories(apps, schema_editor):
    categories = apps.get_model("market", "Category").objects.using(schema_editor.connection.alias)
    for index, (name, slug, icon) in enumerate(CATEGORIES, 1):
        categories.get_or_create(
            slug=slug, defaults={"name": name, "icon": icon, "featured_order": index}
        )


class Migration(migrations.Migration):
    dependencies = [("market", "0001_initial")]
    operations = [migrations.RunPython(create_categories, migrations.RunPython.noop)]
