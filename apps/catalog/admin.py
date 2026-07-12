from django.contrib import admin

from .models import Area, City, Subject


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "state", "is_active"]
    search_fields = ["name"]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "is_active"]
    list_filter = ["city", "is_active"]
    search_fields = ["name"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["name"]
