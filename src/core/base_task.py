import celery
import tiktoken
from django.conf import settings
from tiktoken import Encoding

from api.utilities.vectorizer import Vectorizer
from core.models import CoreVariable

# Mypy for some reason can not handle the fact that the
# variables are None in the beginning but get initialized
# during the property. Heck it.

# mypy: ignore-errors


# Ye who hark this path from the wilderness, beware the dangers within
# Celery tasks are initiated as a singleton during worker boot-up
# and whenever you put model loading into the init of a base class
# the results will become devoid of reason. Tasks refuse to launch,
# your RAM makes pacts with darker forces to reach new heights and
# the Celery master process simply refuses to die. Also gives the
# developer a headache.


class ResourceTask(celery.Task):
    def __init__(self) -> None:
        # The cache is initialized here. It can be access though all child
        # tasks whose base is ResourceTask.
        # The cache will get initialized when celery is initialized.
        self._vectorizer = None
        self._encoder = None

    @property
    def vectorizer(self) -> Vectorizer:
        if self._vectorizer:
            return self._vectorizer

        # If not in cache, initialize it.
        self._vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )
        self._vectorizer.load_model_interface()
        return self._vectorizer

    @property
    def encoder(self) -> Encoding:
        if self._encoder:
            return self._encoder

        self._encoder = ResourceTask.generate_encoder()
        return self._encoder

    @staticmethod
    def generate_encoder() -> Encoding:
        model = CoreVariable.get_core_setting('OPENAI_API_CHAT_MODEL')
        encoder = tiktoken.encoding_for_model(model)
        return encoder
