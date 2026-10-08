"""
URL configuration for ecommerce1 project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from rest_framework.routers import DefaultRouter

from products.serializers.public import GlobalMenuCategorySerializer
from products.views.public import CategoryDrillDownAPIView, ProductDetailAPIView, GlobalMenuAPIView, \
    ProductSearchFilterAPIView
from products.views.seller import SellerProductCreateView
from users.views import MyProfileView, RegisterView, LogoutView
from sellers.views import SellerRegisterView

# create router object
router = DefaultRouter()

# register the views with router object
# router.register('profile', MyProfileView, basename='profile')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls', namespace = 'rest_framework')),

    path('api/v1/auth/register/', RegisterView.as_view(), name='customer-register'),
    path('api/v1/auth/seller/register/', SellerRegisterView.as_view(), name='seller-register'),

    path('api/v1/auth/login/', TokenObtainPairView.as_view()),
    path('api/v1/auth/refresh/', TokenRefreshView.as_view()),
    path('api/v1/auth/logout/', LogoutView.as_view()),
    path('profile/', MyProfileView.as_view()),

    path('api/v1/seller/products/create/', SellerProductCreateView.as_view(), name='seller-product-create'),

    # Catalog Navigation Engine
    path('api/v1/catalog/', CategoryDrillDownAPIView.as_view(), name='catalog-root'),
    path('api/v1/global-menu/', GlobalMenuAPIView.as_view(), name='global-menu'),

    path('api/v1/catalog/<int:category_id>/', CategoryDrillDownAPIView.as_view(), name='catalog-drilldown'),

    path('api/v1/products/<int:id>/', ProductDetailAPIView.as_view(), name='product-detail'),

    path('api/v1/products/filter/', ProductSearchFilterAPIView.as_view(), name='product-search-filter'),

    # Cart
    path('api/v1/cart/', include('cart.urls'), name='cart'),

    # Order
    path('api/v1/orders/', include('orders.urls'), name='order'),

    # Payments
    path('api/v1/payments/', include('payments.urls'), name='payments')
]
