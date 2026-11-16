"""Reuse the original curated taxonomy; retain subsequent operator edits."""
import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from discovery.models import GenreCategory, GenreTag
from .import_subgenres import parse_bpm


class Command(BaseCommand):
    help = 'Seed curated categories and tags without replacing existing records.'

    @transaction.atomic
    def handle(self, *args, **options):
        fixtures = Path(__file__).resolve().parents[2] / 'fixtures'
        for record in json.loads((fixtures / 'genre_categories.json').read_text(encoding='utf-8')):
            fields = record['fields'].copy()
            name = fields.pop('name')
            GenreCategory.objects.get_or_create(name=name, defaults=fields)
        with (fixtures / 'electronic_subgenres_v1.csv').open(encoding='utf-8-sig', newline='') as source:
            for line, row in enumerate(csv.DictReader(source), 2):
                name = row['umbrella_genre'].strip()
                if name == 'EBM / Industrial':
                    name = 'Industrial / EBM'
                category = GenreCategory.objects.get(name=name)
                low, high = parse_bpm(row, line)
                GenreTag.objects.get_or_create(category=category, name=row['subgenre'].strip(), defaults={
                    'description': row['pitch'].strip(),
                    'bpm_min': low,
                    'bpm_max': high,
                })
        self.stdout.write('Curated Discovery taxonomy is present; existing rows retained.')
