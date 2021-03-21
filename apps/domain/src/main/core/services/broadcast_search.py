# stdlib
import secrets
from typing import List
from typing import Type
from typing import Union
from datetime import datetime

# third party
from nacl.signing import VerifyKey
from nacl.encoding import HexEncoder
from nacl.signing import SigningKey

# syft relative
from syft.core.node.abstract.node import AbstractNode
from syft.core.node.common.service.auth import service_auth
from syft.core.node.common.service.node_service import ImmediateNodeServiceWithReply
from syft.core.common.message import ImmediateSyftMessageWithReply

from syft.grid.messages.network_search_message import (
    NetworkSearchMessage,
    NetworkSearchResponse,
)

from ..exceptions import (
    MissingRequestKeyError,
    InvalidParameterValueError,
    AuthorizationError,
)

from ..database.utils import model_to_json
from syft.grid.client.client import connect
from syft.grid.client.grid_connection import GridHTTPConnection
from syft.core.node.domain.client import DomainClient


class BroadcastSearchService(ImmediateNodeServiceWithReply):
    @staticmethod
    @service_auth(guests_welcome=True)
    def process(
        node: AbstractNode,
        msg: NetworkSearchMessage,
        verify_key: VerifyKey,
    ) -> NetworkSearchResponse:
        queries = set(msg.content.get("query", []))
        associations = node.association_requests.associations()

        def filter_domains(url):
            domain = connect(
                url=url,  # Domain Address
                conn_type=GridHTTPConnection,  # HTTP Connection Protocol
                client_type=DomainClient,
            )

            for data in domain.store:
                if queries.issubset(set(data.tags)):
                    return True
            return False

        filtered_nodes = list(filter(lambda x: filter_domains(x.address), associations))

        match_nodes = [node.address for node in filtered_nodes]

        return NetworkSearchResponse(
            address=msg.reply_to, status_code=200, content={"msg": match_nodes}
        )

    @staticmethod
    def message_handler_types() -> List[Type[ImmediateSyftMessageWithReply]]:
        return [NetworkSearchMessage]
