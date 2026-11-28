"""Step 2 of 2: make GenreTag.slug required and unique after the 0017 backfill."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0017_genretag_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="genretag",
            name="slug",
            field=models.SlugField(blank=True, help_text="Stable key for linking to this subgenre; generated from the name.",
                                   max_length=80, unique=True),
        ),
    ]
