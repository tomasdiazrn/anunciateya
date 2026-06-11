"""Public sitemap definitions for search engines and AI crawlers."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.categories.models import Category
from apps.listings.category_engine_validation import EXPECTED_CONTRACT_SLUGS
from apps.listings.models import Listing


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    static_routes = (
        ("root_home", "daily", 1.0),
        ("browse", "hourly", 0.9),
        ("publish", "weekly", 0.7),
        ("core:terms", "yearly", 0.3),
        ("core:privacy", "yearly", 0.3),
    )

    def items(self):
        return [name for name, _changefreq, _priority in self.static_routes]

    def location(self, item):
        return reverse(item)

    def changefreq(self, item):
        return self._item_meta(item)[0]

    def priority(self, item):
        return self._item_meta(item)[1]

    def _item_meta(self, item):
        for name, changefreq, priority in self.static_routes:
            if name == item:
                return changefreq, priority
        return "weekly", 0.7


class CategorySitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Category.objects.filter(
            slug__in=EXPECTED_CONTRACT_SLUGS,
        ).order_by("order", "name")

    def lastmod(self, obj):
        return obj.updated_at


class ListingSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.6
    limit = 1000

    def items(self):
        return (
            Listing.objects.published()
            .select_related("category")
            .order_by("-updated_at", "-created_at")
        )

    def lastmod(self, obj):
        return obj.updated_at


sitemaps = {
    "static": StaticViewSitemap,
    "categories": CategorySitemap,
    "listings": ListingSitemap,
}
