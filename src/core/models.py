from django.db import models


class CoreVariable(models.Model):
    name = models.CharField(max_length=100)
    value = models.TextField(default=None, null=True)

    def __str__(self):
        return f"{self.name} - {self.value}"


class LLMResult(models.Model):
    celery_task_id = models.TextField()

    response = models.TextField()
    system_input = models.TextField()
    user_input = models.TextField()

    model = models.CharField(max_length=100)
    input_tokens = models.IntegerField()
    output_tokens = models.IntegerField()
    headers = models.JSONField()

    @property
    def ratelimit_requests(self):
        return int(self.headers.get("x-ratelimit-limit-requests"))

    @property
    def ratelimit_tokens(self):
        return int(self.headers.get("x-ratelimit-limit-tokens"))

    @property
    def remaining_requests(self):
        return int(self.headers.get("x-ratelimit-remaining-requests"))

    @property
    def remaining_tokens(self):
        return int(self.headers.get("x-ratelimit-remaining-tokens"))

    @property
    def reset_requests_at_ms(self) -> str:
        return self.headers.get("x-ratelimit-reset-requests")

    @property
    def reset_tokens_at_ms(self) -> str:
        return self.headers.get("x-ratelimit-reset-tokens")

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __str__(self):
        return f"{self.response} / {self.total_tokens} tokens used"
