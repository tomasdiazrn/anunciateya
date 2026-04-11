from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    """Hierarchical categories for listings (SEO-friendly slugs)."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, db_index=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
    )
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(
        default=0,
        db_index=True,
        help_text="Orden en home y selector de publicar (menor = primero).",
    )
    icon = models.CharField(
        max_length=120,
        blank=True,
        help_text="Clases CSS Font Awesome, ej. fa-solid fa-car-side",
    )
    image = models.ImageField(
        upload_to="categories/%Y/%m/",
        blank=True,
        null=True,
        help_text="Opcional: icono visual en lugar de Font Awesome.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["order", "name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["parent", "slug"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("category_landing", kwargs={"slug": self.slug})
