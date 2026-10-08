from logging import raiseExceptions
from multiprocessing.managers import Token

from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.mixins import CreateModelMixin
from rest_framework.generics import GenericAPIView
from rest_framework import viewsets, status, mixins, generics
from django.contrib.auth.models import User
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Profile
from .serializers import ProfileSerializer, UserSerializer


# Create your views here.

# class ProfileViewSet(viewsets.ModelViewSet):
#     serializer_class = ProfileSerializer
#     authentication_classes = [JWTAuthentication]
#     permission_classes = [IsAuthenticated]
#
#     def get_queryset(self):
#         return Profile.objects.filter(user=self.request.user)

class MyProfileView(generics.RetrieveUpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.profile



class RegisterView(GenericAPIView, CreateModelMixin):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({ "success": True,"message": "User registered successfully"}, status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({'error':e}, status.HTTP_400_BAD_REQUEST)









