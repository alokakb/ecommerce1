from django.shortcuts import render
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from sellers.serializers import SellerRegistrationSerializer


# Create your views here.
class SellerRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Checkpoint A: Inspect what is coming directly out of the test client
        print("--- CHECKPOINT A (RAW REQUEST DATA) ---")
        print(request.data)

        serializer = SellerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Checkpoint B: Inspect what the serializer kept after validation
        print("--- CHECKPOINT B (VALIDATED SERIALIZER DATA) ---")
        print(serializer.validated_data)

        serializer.save()

        return Response({
            "Success": True,
            "message": "Seller's account has been created. Pending Administrative review"
        }, status=status.HTTP_201_CREATED)
