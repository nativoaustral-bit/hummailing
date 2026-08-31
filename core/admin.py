from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Lead

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'role')

admin.site.register(User, CustomUserAdmin)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'company_name', 'email', 'phone', 'status', 'source', 'utm_source', 'created_at')
    list_filter = ('status', 'source', 'utm_source', 'created_at')
    search_fields = ('name', 'company_name', 'email', 'phone', 'notes')
    readonly_fields = ('created_at', 'updated_at', 'ip_address', 'source', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content')
    list_editable = ('status',)

