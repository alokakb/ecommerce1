from rest_framework import permissions

class IsVerifiedSellers(permissions.BasePermission):
    def has_permission(self, request, view):
        permission_val = bool(
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'seller_profile') and
            request.user.seller_profile.is_verified
        )
        print(f"check permission : {permission_val}" )
        return permission_val