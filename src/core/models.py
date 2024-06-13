from django.db import models


class CoreVariable(models.Model):
    name = models.CharField(max_length=100)
    value = models.TextField(default=None, null=True)

    def __str__(self) -> str:
        return f'{self.name} - {self.value}'
