def organization_context(request):
    """
    Inyecta la organización activa y el estado de soporte en todas las plantillas.
    """
    return {
        'current_organization': getattr(request, 'organization', None),
        'is_impersonating': getattr(request, 'is_impersonating', False),
    }
