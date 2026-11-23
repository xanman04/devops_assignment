"""Step 2 of 2: make GenreCategory.slug required and unique after the 0014 backfill."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("discovery", "0014_genrecategory_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="genrecategory",
            name="slug",
            field=models.SlugField(blank=True, help_text="Stable URL key; generated from the name.", max_length=80, unique=True),
        ),
    ]
