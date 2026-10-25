from django.core.exceptions import PermissionDenied

from .permissions import is_viewer

# Pantallas que un Visualizador (solo lectura) puede abrir. Todo lo demás responde 403,
# incluidos los POST (comandos, edición de gadgets, tokens, alta de dispositivos, etc.).
VIEWER_ALLOWED_VIEWS = {
    "monitoring:dashboard",
    "monitoring:api-latest",
    "monitoring:devices-map",
    "login",
    "logout",
}
VIEWER_ALLOWED_PATH_PREFIXES = ("/media/",)


class ViewerReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated or not is_viewer(user):
            return None
        if request.path == "/" or request.path.startswith(VIEWER_ALLOWED_PATH_PREFIXES):
            return None
        if request.resolver_match.view_name in VIEWER_ALLOWED_VIEWS:
            return None
        raise PermissionDenied
