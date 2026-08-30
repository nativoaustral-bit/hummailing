from django.contrib import admin
from .models import Campaign, CampaignTemplate, CampaignLink, TrackingEvent, CampaignSchedule

@admin.register(CampaignTemplate)
class CampaignTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')

class CampaignLinkInline(admin.TabularInline):
    model = CampaignLink
    extra = 1

class CampaignScheduleInline(admin.TabularInline):
    model = CampaignSchedule
    extra = 1

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'status', 'scheduled_at', 'created_by')
    list_filter = ('status',)
    search_fields = ('name', 'subject')
    inlines = [CampaignLinkInline, CampaignScheduleInline]

@admin.register(CampaignSchedule)
class CampaignScheduleAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'scheduled_at', 'status', 'sent_at')
    list_filter = ('status', 'scheduled_at')
    search_fields = ('campaign__name',)

@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ('contact', 'campaign', 'event_type', 'timestamp')
    list_filter = ('event_type', 'campaign')
    search_fields = ('contact__email',)

