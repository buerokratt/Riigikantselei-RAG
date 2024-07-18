from django.contrib import admin

from text_search.models import TextSearchConversation, TextSearchQueryResult

# Register your models here.
admin.site.register(TextSearchConversation)
admin.site.register(TextSearchQueryResult)
