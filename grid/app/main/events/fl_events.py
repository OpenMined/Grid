# Events module import
from .socket_handler import SocketHandler

# PyGrid imports
from ..codes import MSG_FIELD, RESPONSE_MSG, CYCLE, FL_EVENTS
from ..exceptions import CycleNotFoundError, MaxCycleLimitExceededError
from ..controller import processes
from ..workers import worker_manager
from ..processes import process_manager

# Generic imports
import jwt
import uuid
import json
import base64
import requests
import traceback
from binascii import unhexlify


# Singleton socket handler
handler = SocketHandler()


def host_federated_training(message: dict, socket) -> str:
    """This will allow for training cycles to begin on end-user devices.
        Args:
            message : Message body sended by some client.
            socket: Socket descriptor.
        Returns:
            response : String response to the client
    """
    data = message[MSG_FIELD.DATA]
    response = {}

    try:
        # Retrieve JSON values
        serialized_model = unhexlify(
            data.get(MSG_FIELD.MODEL, None).encode()
        )  # Only one
        serialized_client_plans = {
            k: unhexlify(v.encode()) for k, v in data.get(CYCLE.PLANS, {}).items()
        }  # 1 or *
        serialized_client_protocols = {
            k: unhexlify(v.encode()) for k, v in data.get(CYCLE.PROTOCOLS, {}).items()
        }  # 0 or *
        serialized_avg_plan = unhexlify(
            data.get(CYCLE.AVG_PLAN, None).encode()
        )  # Only one
        client_config = data.get(CYCLE.CLIENT_CONFIG, None)  # Only one
        server_config = data.get(CYCLE.SERVER_CONFIG, None)  # Only one

        # Create a new FL Process
        processes.create_process(
            model=serialized_model,
            client_plans=serialized_client_plans,
            client_protocols=serialized_client_protocols,
            server_averaging_plan=serialized_avg_plan,
            client_config=client_config,
            server_config=server_config,
        )
        response[CYCLE.STATUS] = RESPONSE_MSG.SUCCESS
    except Exception as e:  # Retrieve exception messages such as missing JSON fields.
        response[RESPONSE_MSG.ERROR] = str(e) + traceback.format_exc()

    response = {MSG_FIELD.TYPE: FL_EVENTS.HOST_FL_TRAINING, MSG_FIELD.DATA: response}

    return json.dumps(response)


def assign_worker(message, socket):
    response = {}

    # Create a new worker instance and bind it with the socket connection.
    try:
        # Create new worker id
        worker_id = str(uuid.uuid4())

        # Create a link between worker id and socket descriptor
        handler.new_connection(worker_id, socket)

        # Create worker instance
        worker_manager.create(worker_id)

        response[CYCLE.STATUS] = RESPONSE_MSG.SUCCESS
        response[MSG_FIELD.WORKER_ID] = worker_id
    except Exception as e:  # Retrieve exception messages such as missing JSON fields.
        response[CYCLE.STATUS] = RESPONSE_MSG.ERROR
        response[RESPONSE_MSG.ERROR] = str(e)

    response = {MSG_FIELD.TYPE: FL_EVENTS.AUTHENTICATE, MSG_FIELD.DATA: response}
    return json.dumps(response)


def verify_token(auth_token, model_name):
    server, _ = process_manager.get_configs(name=model_name)

    """stub DB vars"""
    JWT_VERIFY_API = server.config.get("JWT_VERIFY_API", None)
    RSA = server.config.get("JWT_with_RSA", None)

    if RSA:
        pub_key = server.config.get("pub_key", None)
    else:
        SECRET = server.config.get("JWT_SECRET", "very long a$$ very secret key phrase")
    """end stub DB vars"""

    HIGH_SECURITY_RISK_NO_AUTH_FLOW = False if JWT_VERIFY_API is not None else True

    if not HIGH_SECURITY_RISK_NO_AUTH_FLOW:
        if auth_token is None:
            return {
                "error": "Authentication is required, please pass an 'auth_token'.",
                "status": RESPONSE_MSG.ERROR,
            }
        else:
            base64Header, base64Payload, signature = auth_token.split(".")
            header_str = base64.b64decode(base64Header)
            header = json.loads(header_str)
            _algorithm = header["alg"]

            if not RSA:
                payload_str = base64.b64decode(base64Payload)
                payload = json.loads(payload_str)
                expected_token = jwt.encode(
                    payload, SECRET, algorithm=_algorithm
                ).decode("utf-8")

                if expected_token != auth_token:
                    return {
                        "error": "The 'auth_token' you sent is invalid.",
                        "status": RESPONSE_MSG.ERROR,
                    }
            else:
                # we should check if RSA is true there is a pubkey string included during call to `host_federated_training`
                # here we assume it exists / no redundant check
                try:
                    jwt.decode(auth_token, pub_key, _algorithm)

                except Exception as e:
                    if e.__class__.__name__ == "InvalidSignatureError":
                        return {
                            "error": "The 'auth_token' you sent is invalid. " + str(e),
                            "status": RESPONSE_MSG.ERROR,
                        }

    external_api_verify_data = {"auth_token": f"{auth_token}"}
    verification_result = requests.get(
        "http://google.com"
    )  # test with get and google for now. using .post should result in failure
    # TODO:@MADDIE replace after we have a api to test with `verification_result = requests.post(JWT_VERIFY_API, data = json.dumps(external_api_verify_data))`

    if verification_result.status_code == 200:
        return {
            "auth_token": f"{auth_token}",
            "status": RESPONSE_MSG.SUCCESS,
        }
    else:
        return {
            "error": "The 'auth_token' you sent did not pass 3rd party verificaiton. ",
            "status": RESPONSE_MSG.ERROR,
        }


def authenticate(message: dict, socket) -> str:
    """ New workers should receive a unique worker ID after authenticate on PyGrid platform.
        Args:
            message : Message body sended by some client.
            socket: Socket descriptor.
        Returns:
            response : String response to the client
    """
    response = {}
    _auth_token = message.get("auth_token")
    model_name = message.get("model_name", None)

    verification_result = verify_token(_auth_token, model_name)

    if verification_result["status"] == RESPONSE_MSG.SUCCESS:
        response = assign_worker({"auth_token": _auth_token}, None)
    else:
        response[RESPONSE_MSG.ERROR] = verification_result["error"]

    return json.dumps(response)


def cycle_request(message: dict, socket) -> str:
    """This event is where the worker is attempting to join an active federated learning cycle.
        Args:
            message : Message body sended by some client.
            socket: Socket descriptor.
        Returns:
            response : String response to the client
    """
    data = message[MSG_FIELD.DATA]
    response = {}

    try:
        # Retrieve JSON values
        worker_id = data.get(MSG_FIELD.WORKER_ID, None)
        name = data.get(MSG_FIELD.MODEL, None)
        version = data.get(CYCLE.VERSION, None)
        ping = int(data.get(CYCLE.PING, None))
        download = float(data.get(CYCLE.DOWNLOAD, None))
        upload = float(data.get(CYCLE.UPLOAD, None))

        # Retrieve the worker
        worker = worker_manager.get(id=worker_id)

        worker.ping = ping
        worker.avg_download = download
        worker.avg_upload = upload
        worker_manager.update(worker)  # Update database worker attributes

        # The last time this worker was assigned for this model/version.
        last_participation = processes.last_cycle(worker_id, name, version)

        # Assign
        response = processes.assign(name, version, worker, last_participation)
    except CycleNotFoundError:
        # Nothing to do
        response[CYCLE.STATUS] = CYCLE.REJECTED
    except MaxCycleLimitExceededError as e:
        response[CYCLE.STATUS] = CYCLE.REJECTED
        response[MSG_FIELD.MODEL] = e.name
    except Exception as e:
        print("Exception: ", str(e))
        response[CYCLE.STATUS] = CYCLE.REJECTED
        response[RESPONSE_MSG.ERROR] = str(e) + traceback.format_exc()

    response = {MSG_FIELD.TYPE: FL_EVENTS.CYCLE_REQUEST, MSG_FIELD.DATA: response}
    return json.dumps(response)


def report(message: dict, socket) -> str:
    """ This method will allow a worker that has been accepted into a cycle
        and finished training a model on their device to upload the resulting model diff.
        Args:
            message : Message body sended by some client.
            socket: Socket descriptor.
        Returns:
            response : String response to the client
    """
    data = message[MSG_FIELD.DATA]
    response = {}

    try:
        worker_id = data.get(MSG_FIELD.WORKER_ID, None)
        request_key = data.get(CYCLE.KEY, None)

        # It's simpler for client (and more efficient for bandwidth) to use base64
        # diff = unhexlify()
        diff = base64.b64decode(data.get(CYCLE.DIFF, None).encode())

        # Submit model diff and run cycle and task async to avoid block report request
        # (for prod we probably should be replace this with Redis queue + separate worker)
        processes.submit_diff(worker_id, request_key, diff)

        response[CYCLE.STATUS] = RESPONSE_MSG.SUCCESS
    except Exception as e:  # Retrieve exception messages such as missing JSON fields.
        response[RESPONSE_MSG.ERROR] = str(e) + traceback.format_exc()

    response = {MSG_FIELD.TYPE: FL_EVENTS.REPORT, MSG_FIELD.DATA: response}
    return json.dumps(response)
