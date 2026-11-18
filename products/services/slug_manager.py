from django.utils.text import slugify

def create_slug(instance):
    name_changed = True

    if instance.pk:
        old_name = (instance.__class__.objects.
                    filter(pk=instance.pk).values_list('name', flat=True).first())
        name_changed = old_name != instance.name

    if not instance.slug or name_changed:
        base_slug = slugify(instance.name) or 'item'
        candidate = base_slug
        suffix = 2

        queryset = instance.__class__.objects.all()

        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)

        while queryset.filter(slug=candidate).exists():
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        instance.slug = candidate

    return instance
