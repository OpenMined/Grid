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
from syft.core.node.common.service.node_service import ImmediateNodeServiceWithoutReply
from syft.core.common.message import ImmediateSyftMessageWithReply

from syft.grid.messages.setup_messages import (
    CreateInitialSetUpMessage,
    CreateInitialSetUpResponse,
    GetSetUpMessage,
    GetSetUpResponse,
)

from ..exceptions import (
    MissingRequestKeyError,
    InvalidParameterValueError,
    AuthorizationError,
)
from ..database.setup.setup import SetupConfig
from ..database.utils import model_to_json

from ...core.database.environment.environment import states
from ...core.infrastructure import Config, Provider, AWS_Serverfull, AWS_Serverless


def create_initial_setup(
    msg: CreateInitialSetUpMessage, node: AbstractNode, verify_key: VerifyKey
) -> CreateInitialSetUpResponse:
    def deploy(config):
        deployment = None
        deployed = False

        if config.provider == "aws":
            deployment = (
                AWS_Serverless(config)
                if config.serverless
                else AWS_Serverfull(config=config)
            )
        elif config.provider == "azure":
            pass
        elif config.provider == "gcp":
            pass

        if deployment.validate():
            env_parameters = {
                "id": config.app.id,
                "app_name": msg.content.get("node_name", ""),
                "state": states["creating"],
                "provider": config.provider,
                "region": config.vpc.region,
                "instance_type": config.vpc.instance_type.InstanceType,
            }
            new_env = node.environments.register(**env_parameters)
            node.environments.association(user_id=_current_user_id, env_id=new_env.id)

            # deployed, output = deployment.deploy()  # Deploy
            # TODO(amr): remove this ... purpose for testing deployment only!
            deployed, output = True, {}

            if deployed:
                node.environments.set(
                    id=config.app.id,
                    created_at=datetime.now(),
                    state=states["success"],
                    # address=output["instance_0_endpoint"]["value"][0],
                )
            else:
                node.environments.set(id=config.app.id, state=states["failed"])
                raise Exception("Domain setup creation failed!")

        final_msg = "Domain created successfully!"
        return final_msg

    _email = msg.content.get("email", None)
    _password = msg.content.get("password", None)

    # Get Payload Content
    configs = {
        "node_name": msg.content.get("node_name", ""),
        "private_key": msg.content.get("private_key", ""),
        "aws_credentials": msg.content.get("aws_credentials", ""),
        "gcp_credentials": msg.content.get("gcp_credentials", ""),
        "azure_credentials": msg.content.get("azure_credentials", ""),
        "cache_strategy": msg.content.get("cache_strategy", ""),
        "replicate_db": msg.content.get("replicate_db", False),
        "auto_scale": msg.content.get("auto_scale", ""),
        "tensor_expiration_policy": msg.content.get("tensor_expiration_policy", -1),
        "allow_user_signup": msg.content.get("allow_user_signup", False),
    }

    _current_user_id = msg.content.get("current_user", None)

    users = node.users

    if not _current_user_id:
        try:
            _current_user_id = users.first(
                verify_key=verify_key.encode(encoder=HexEncoder).decode("utf-8")
            ).id
        except Exception:
            pass

    _admin_role = node.roles.first(name="Owner")

    _mandatory_request_fields = _email and _password and configs["node_name"]

    # Check if email/password/node_name fields are empty
    if not _mandatory_request_fields:
        raise MissingRequestKeyError(
            message="Invalid request payload, empty fields (email/password/node_name)!"
        )

    config_obj = SetupConfig(**configs)

    # Change Node Name
    node.name = config_obj.node_name

    # Change Node Root Key (if requested)
    if config_obj.private_key != "":
        try:
            private_key = SigningKey(config_obj.encode("utf-8"), encoder=HexEncoder)
        except Exception:
            raise InvalidParameterValueError("Invalid Signing Key!")
        node.root_key = private_key
        node.verify_key = private_key.verify_key

    # Create Admin User
    _node_private_key = node.signing_key.encode(encoder=HexEncoder).decode("utf-8")
    _verify_key = node.signing_key.verify_key.encode(encoder=HexEncoder).decode("utf-8")
    _admin_role = node.roles.first(name="Owner")
    _user = users.signup(
        email=_email,
        password=_password,
        role=_admin_role.id,
        private_key=_node_private_key,
        verify_key=_verify_key,
    )

    _mandatory_infra = msg.content.get("infra", None)
    if not _mandatory_infra:
        raise MissingRequestKeyError(
            message="Invalid infra request payload, empty fields (infra config)!"
        )

    deploy(Config(**_mandatory_infra))

    # Final status / message
    final_msg = "Running initial setup!"
    node.setup.register(**configs)
    return CreateInitialSetUpResponse(
        address=msg.reply_to,
        status_code=200,
        content={"msg": final_msg},
    )


def get_setup(
    msg: GetSetUpMessage, node: AbstractNode, verify_key: VerifyKey
) -> GetSetUpResponse:

    _current_user_id = msg.content.get("current_user", None)

    users = node.users

    if not _current_user_id:
        try:
            _current_user_id = users.first(
                verify_key=verify_key.encode(encoder=HexEncoder).decode("utf-8")
            ).id
        except Exception:
            pass

    if users.role(user_id=_current_user_id).name != "Owner":
        raise AuthorizationError("You're not allowed to get setup configs!")
    else:
        _setup = model_to_json(node.setup.first(node_name=node.name))

    return GetSetUpResponse(
        address=msg.reply_to,
        status_code=200,
        content=_setup,
    )


class SetUpService(ImmediateNodeServiceWithReply):

    msg_handler_map = {
        CreateInitialSetUpMessage: create_initial_setup,
        GetSetUpMessage: get_setup,
    }

    @staticmethod
    @service_auth(guests_welcome=True)
    def process(
        node: AbstractNode,
        msg: Union[
            CreateInitialSetUpMessage,
            GetSetUpMessage,
        ],
        verify_key: VerifyKey,
    ) -> Union[CreateInitialSetUpResponse, GetSetUpResponse,]:
        return SetUpService.msg_handler_map[type(msg)](
            msg=msg, node=node, verify_key=verify_key
        )

    @staticmethod
    def message_handler_types() -> List[Type[ImmediateSyftMessageWithReply]]:
        return [
            CreateInitialSetUpMessage,
            GetSetUpMessage,
        ]
