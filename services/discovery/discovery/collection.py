# Copyright © 2026 Xander Chen. All rights reserved.
"""A person's event cards and the achievements those cards prove.

Only event cards are stored. Achievements are worked out from them on every read, so an
achievement can only appear while the cards that prove it are in the collection. A card
for an event that is no longer public is left out, which also removes it from the proof.
"""
from .models import EventCard, EventFollow
from .services import public_events

NAME = "Collection"
TOTAL_SLOTS = 20
CARD_LIMIT = 200

# Events attended needed for each tier, lowest first.
TIERS = ((3, "Bronze"), (5, "Silver"), (10, "Gold"), (15, "Platinum"), (20, "Diamond"))
# Special names for some genres; any other genre is called "<genre> Fan".
GENRE_TITLES = {"Drum & Bass": "DnB Lover", "Techno": "Techno Head", "House": "House Regular", "Trance": "Trance Voyager"}
ALL_TITLE = "Scene Regular"


def achievements(cards):
    """Achievements earned by these cards, highest tier first, each listing the events that prove it."""
    groups = [(ALL_TITLE, None, cards)]
    for genre in dict.fromkeys(card["genre"] for card in cards if card["genre"]):
        groups.append((GENRE_TITLES.get(genre, f"{genre} Fan"), genre, [c for c in cards if c["genre"] == genre]))
    earned = []
    for title, genre, proof in groups:
        reached = [rank for rank, (needed, _) in enumerate(TIERS) if len(proof) >= needed]
        if reached:
            earned.append((reached[-1], {"title": title, "genre": genre or "", "tier": TIERS[reached[-1]][1],
                                         "event_ids": [card["event_id"] for card in proof]}))
    earned.sort(key=lambda pair: -pair[0])
    return [badge for _, badge in earned]


def _card(row):
    event = row.event
    categories = sorted(event.categories.all(), key=lambda c: c.pk)
    return {"event_id": event.pk, "title": event.title,
            "genre": categories[0].name if categories else "", "color": categories[0].color if categories else "#8d95a6",
            "venue": event.venue.name, "timezone": event.venue.timezone, "starts_at": event.starts_at}


def collection_for(user):
    """The signed-in person's own collection; newest event first."""
    rows = (EventCard.objects.filter(user=user, event__in=public_events()).select_related("event__venue")
            .prefetch_related("event__categories").order_by("-event__starts_at", "-id")[:CARD_LIMIT])
    cards = [_card(row) for row in rows]
    return {"name": NAME, "total_slots": TOTAL_SLOTS,
            "followed": EventFollow.objects.filter(user=user, event__in=public_events()).count(),
            "cards": cards, "achievements": achievements(cards)}
