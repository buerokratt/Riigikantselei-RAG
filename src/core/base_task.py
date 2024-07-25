import celery
import tiktoken
from django.conf import settings
from tiktoken import Encoding

from api.utilities.vectorizer import Vectorizer
from core.models import CoreVariable


class ResourceTask(celery.Task):
    def __init__(self) -> None:
        # The cache is initialized here. It can be access though all child
        # tasks whose base is ResourceTask.
        # The cache will get initialized when celery is initialized.
        self.vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )
        self.vectorizer.load_model_interface()
        self.encoder = ResourceTask.generate_encoder()

    @staticmethod
    def generate_encoder() -> Encoding:
        model = CoreVariable.get_core_setting('OPENAI_API_CHAT_MODEL')
        encoder = tiktoken.encoding_for_model(model)
        return encoder
