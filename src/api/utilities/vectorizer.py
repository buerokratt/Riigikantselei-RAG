import logging
import pathlib
from typing import List, Optional

from FlagEmbedding import BGEM3FlagModel
from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)


def download_vectorization_resources(model_name: str, model_directory: pathlib.Path) -> None:
    model = model_name.split('/')[-1]

    for file in model_directory.rglob('*'):
        if model.lower() in str(file.name).lower():
            return

    Vectorizer(
        model_name,
        system_configuration={},
        inference_configuration={},
        model_directory=model_directory,
    ).download_model(model_name)


def _model_exists(model_directory: pathlib.Path, model_name: str) -> bool:
    return (model_directory / model_name).exists()


class Vectorizer:
    def __init__(
        self,
        model_name: str,
        system_configuration: dict,
        inference_configuration: dict,
        model_directory: pathlib.Path,
    ):
        self.model_directory = model_directory
        self.model_name = model_name
        self.system_configuration = system_configuration
        self.inference_configuration = inference_configuration

        self.model_interface: Optional[BGEM3FlagModel] = None

    @property
    def _model_path(self) -> pathlib.Path:
        return self.model_directory / self.model_name

    def download_model(self, model_name: Optional[str]) -> None:
        if model_name is None:
            model_name = self.model_name

        if not _model_exists(self.model_directory, model_name):
            # This method is used within FlagEmbedding to download the model.
            snapshot_download(
                repo_id=model_name,
                local_dir=str(self._model_path),
                ignore_patterns=['flax_model.msgpack', 'rust_model.ot', 'tf_model.h5'],
            )

    def _load_model_interface(self, **kwargs: dict) -> None:
        self.model_interface = BGEM3FlagModel(
            str(self._model_path), **self.system_configuration, **kwargs
        )

    # Adding additional kwargs here to support overloading the parameters by hand.
    def vectorize(self, texts: List[str], **kwargs: dict) -> dict:
        if self.model_interface is None:
            logger.warning(
                'Trying to vectorize without initialising the interference interface, '
                'loading it automatically!'
            )
            self._load_model_interface()

        if self.model_interface is None:
            raise RuntimeError

        result = self.model_interface.encode(texts, **self.inference_configuration, **kwargs)

        return {
            'vectors': result['dense_vecs'],
            'dtype': str(result['dense_vecs'].dtype),
            'shape': result['dense_vecs'].shape,
        }
