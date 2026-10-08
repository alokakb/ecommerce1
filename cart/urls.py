from cart.views import CartAPIView
from django.urls import path

app_name = 'cart'

urlpatterns = [
    path('', CartAPIView.as_view(), name='cart-detail'),
]