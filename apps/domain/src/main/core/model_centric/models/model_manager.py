# PyGrid imports
# Syft dependencies
import syft as sy
from syft import deserialize, serialize
from syft.lib.python.list import List
from syft.proto.lib.python.list_pb2 import List as ListPB

from ...exceptions import ModelNotFoundError
from ...manager.database_manager import DatabaseManager
from ..models.ai_model import Model, ModelCheckPoint

# from syft.execution.placeholder import PlaceHolder
# from syft.execution.state import State
# from syft.serde import protobuf
# from syft_proto.execution.v1.state_pb2 import State as StatePB


class ModelCheckPointManager(DatabaseManager):

    schema = ModelCheckPoint

    def __init__(self, database):
        self._schema = ModelCheckPointManager.schema
        self.db = database


class _ModelManager(DatabaseManager):

    schema = Model

    def __init__(self, database):
        self._schema = _ModelManager.schema
        self.db = database


class ModelManager(DatabaseManager):
    def __init__(self, database):
        self.db = database
        self._models = _ModelManager(database)
        self._model_checkpoints = ModelCheckPointManager(database)

    def create(self, model, process):
        # Register new model
        _model_obj = self._models.register(flprocess=process)

        # Save model initial weights into ModelCheckpoint
        self._model_checkpoints.register(
            value=model, model=_model_obj, number=1, alias="latest"
        )

        return _model_obj

    def save(self, model_id: int, data: bin):
        """Create a new model checkpoint.

        Args:
            model_id: Model ID.
            data: Model data.
        Returns:
            model_checkpoint: ModelCheckpoint instance.
        """

        checkpoints_count = len(self._model_checkpoints.query(model_id=model_id))

        # Reset "latest" alias
        self._model_checkpoints.modify(
            {"model_id": model_id, "alias": "latest"}, {"alias": ""}
        )

        # Create new checkpoint
        new_checkpoint = self._model_checkpoints.register(
            model_id=model_id, value=data, number=checkpoints_count + 1, alias="latest"
        )
        return new_checkpoint

    def load(self, **kwargs):
        """Load model's Checkpoint."""
        _check_point = self._model_checkpoints.last(**kwargs)

        if not _check_point:
            raise ModelNotFoundError

        return _check_point

    def get(self, **kwargs):
        """Retrieve the model instance object.

        Args:
            process_id : Federated Learning Process ID attached to this model.
        Returns:
            model : SQL Model Object.
        Raises:
            ModelNotFoundError (PyGridError) : If model not found.
        """
        _model = self._models.last(**kwargs)

        if not _model:
            raise ModelNotFoundError

        return _model

    @staticmethod
    def serialize_model_params(params):
        """Serializes list of tensors into State/protobuf."""
        pb = serialize(List(params))
        serialized_params = pb.SerializeToString()
        return serialized_params

    @staticmethod
    def unserialize_model_params(bin: bin):
        """Unserializes model or checkpoint or diff stored in db to list of
        tensors."""
        state = ListPB()
        state.ParseFromString(bin)
        params = deserialize(state)
        return params
