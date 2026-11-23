"""Step 1 of 2: add GenreCategory.slug and backfill it on rows that already exist.

The column is added nullable and not unique so existing rows stay valid, every row
is then given a readable unique slug (ids and all other columns are untouched), and
migration 0015 tightens the column to NOT NULL UNIQUE once no row lacks a value.
"""
from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs(apps, schema_editor):
    GenreCategory = apps.get_model("discovery", "GenreCategory")
    taken = set()
    for category in GenreCategory.objects.order_by("display_order", "pk"):
        base = slugify(category.name)[:70].strip("-") or "genre"
        slug, number = base, 2
        while slug in taken:
            slug, number = f"{base}-{number}", number + 1
        taken.add(slug)
        GenreCategory.objects.filter(pk=category.pk).update(slug=slug)


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0013_legacyadminaudit"),
    ]

    operations = [
        migrations.AddField(
            model_name="genrecategory",
            name="slug",
            # No index yet: SQL Server would otherwise create it under the name the unique constraint in 0015 needs.
            field=models.SlugField(max_length=80, null=True, blank=True, db_index=False),
        ),
        # Forward-only data step: the slug column is dropped with the field when reversing.
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
    ]
