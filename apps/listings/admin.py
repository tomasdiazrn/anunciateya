from django.contrib import admin

from .models import MarketZone


@admin.register(MarketZone)
class MarketZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "zone_type", "is_active", "sort_order")
    list_filter = ("city", "zone_type", "is_active")
    search_fields = ("name", "slug", "city")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")
