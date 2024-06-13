from django.contrib import admin

from user_profile.models import PasswordResetToken, UserProfile

admin.site.register(UserProfile)
admin.site.register(PasswordResetToken)
