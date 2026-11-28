"""Step 1 of 2: add GenreTag.slug and backfill it on subgenres that already exist.

The column is added nullable and not unique so existing rows stay valid, every row
is then given a readable unique slug (ids and all other columns are untouched), and
migration 0018 tightens the column to NOT NULL UNIQUE once no row lacks a value.
"""
from django.db import migrations, models
from django.utils.text import slugify


def backfill_slugs(apps, schema_editor):
    GenreTag = apps.get_model("discovery", "GenreTag")
    taken = set()
    for pk, name in GenreTag.objects.order_by("pk").values_list("pk", "name"):
        base = slugify(name)[:70].strip("-") or "subgenre"
        slug, number = base, 2
        while slug in taken:
            slug, number = f"{base}-{number}", number + 1
        taken.add(slug)
        GenreTag.objects.filter(pk=pk).update(slug=slug)
    # Printed into the startup log, next to Django's own "Applying ..." line.
    print(f"\n    discovery_genretag: {len(taken)} existing rows given a slug", flush=True)


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0016_report_hide_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="genretag",
            name="slug",
            # No index yet: SQL Server would otherwise create it under the name the unique constraint in 0018 needs.
            field=models.SlugField(max_length=80, null=True, blank=True, db_index=False),
        ),
        # Forward-only data step: the slug column is dropped with the field when reversing.
        migrations.RunPython(backfill_slugs, migrations.RunPython.noop),
    ]
