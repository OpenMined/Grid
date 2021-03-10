from typing import Union
from typing import List
from datetime import datetime

from .database_manager import DatabaseManager
from ..database.requests.request import Request
from .role_manager import RoleManager
from ..exceptions import RequestError


class RequestManager(DatabaseManager):

    schema = Request

    def __init__(self, database):
        self._schema = RequestManager.schema
        self.db = database

    def first(self, **kwargs) -> Union[None, List]:
        result = super().first(**kwargs)
        if not result:
            raise RequestError

        return result

    def create_request(self, user_id, object_id, reason, request_type):
        date = datetime.now()

        return self.register(
            user_id=user_id,
            object_id=object_id,
            date=date,
            reason=reason,
            request_type=request_type,
        )

    def set(self, request_id, status):
        self.modify({"id": request_id}, {"status": status})
