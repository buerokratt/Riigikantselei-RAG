import openai

OPENAI_EXCEPTIONS = (
    openai.InternalServerError,
    openai.RateLimitError,
    openai.UnprocessableEntityError,
    openai.APITimeoutError,
)
