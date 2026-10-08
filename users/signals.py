# from django.contrib.auth.models import User
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from.models import Profile
#
# @receiver(post_save, sender=User)
# def create_user_profile(sender, instance, created, **kwargs):
#     # if the user is newly created
#     if created:
#         Profile.objects.create(user=instance)
#     # if the user exists and profile may or may not exist
#     else:
#         Profile.objects.get_or_create(user=instance)
