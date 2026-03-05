from myapp.models import Card, Tag


def _normalize_tag_names(raw_tags):
    if not raw_tags:
        return []

    if isinstance(raw_tags, str):
        values = raw_tags.split(',')
    elif isinstance(raw_tags, (list, tuple, set)):
        values = raw_tags
    else:
        values = [raw_tags]

    seen = set()
    names = []
    for value in values:
        tag_name = str(value).strip()
        if not tag_name:
            continue
        lowered = tag_name.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        names.append(tag_name)
    return names


def serialize_cards(cards_queryset):
    cards_data = []
    for card in cards_queryset.prefetch_related('tags'):
        cards_data.append(
            {
                'title': card.title,
                'description': card.description,
                'category': card.category,
                'tags': [tag.name for tag in card.tags.all()],
            }
        )
    return cards_data


def import_cards(card_payloads, replace_existing=False):
    if replace_existing:
        Card.objects.all().delete()

    created = 0
    updated = 0
    skipped = 0

    for row in card_payloads:
        if not isinstance(row, dict):
            skipped += 1
            continue

        title = str(row.get('title', '')).strip()
        if not title:
            skipped += 1
            continue

        description = str(row.get('description', '')).strip()
        category = str(row.get('category', '')).strip()

        card, was_created = Card.objects.update_or_create(
            title=title,
            defaults={
                'description': description,
                'category': category,
            },
        )

        tag_names = _normalize_tag_names(row.get('tags', []))
        tag_objects = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
        card.tags.set(tag_objects)

        if was_created:
            created += 1
        else:
            updated += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'total': created + updated,
    }
