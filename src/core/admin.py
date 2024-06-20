from django.contrib import admin

from core.models import CoreVariable, TextSearchConversation, TextSearchQueryResult

admin.site.register(CoreVariable)
admin.site.register(TextSearchConversation)
admin.site.register(TextSearchQueryResult)
