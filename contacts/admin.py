from django.contrib import admin
from .models import Contact, Tag, Segment

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'status', 'created_at')
    list_filter = ('status', 'consent_status', 'region', 'tags')
    search_fields = ('email', 'first_name', 'last_name', 'company')
    filter_horizontal = ('tags',)
