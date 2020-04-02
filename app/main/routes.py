"""
    All Gateway routes (REST API).
"""
import base64
from flask import render_template, Response, request, current_app, send_file
from math import floor
from typing import Union, Callable
import numpy as np
from scipy.stats import poisson
from . import main
import json
import jwt
import random
import os
import requests
import logging
import io

from .storage.manager import register_new_node, connected_nodes, delete_node
from .processes import processes
from .events import handler
from .events.fl_events import authenticate as fl_events_auth
from .auth import workers
from .events.fl_events import cycle_request, report
from .exceptions import InvalidRequestKeyError, PyGridError
from .codes import MSG_FIELD, CYCLE, RESPONSE_MSG
from requests_toolbelt import MultipartEncoder


# All grid nodes registered at grid network will be stored here
grid_nodes = {}

SMPC_HOST_CHUNK = 4  # Minimum nodes required to host an encrypted model
INVALID_JSON_FORMAT_MESSAGE = (
    "Invalid JSON format."  # Default message used to report Invalid JSON format.
)


@main.route("/", methods=["GET"])
def index():
    """ Main Page. """
    return render_template("index.html")


@main.route("/join", methods=["POST"])
def join_grid_node():
    """ Register a new grid node at grid network.
        TODO: Add Authentication process.
    """

    response_body = {"message": None}
    status_code = None

    try:
        data = json.loads(request.data)
        # Register new node
        if register_new_node(data["node-id"], data["node-address"]):
            response_body["message"] = "Successfully Connected!"
            status_code = 200
        else:  # Grid ID already registered
            response_body["message"] = "This ID has already been registered"
            status_code = 409

    # JSON format not valid.
    except ValueError or KeyError as e:
        response_body["message"] = INVALID_JSON_FORMAT_MESSAGE
        status_code = 400

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )


@main.route("/connected-nodes", methods=["GET"])
def get_connected_nodes():
    """ Get a list of connected nodes. """
    grid_nodes = connected_nodes()
    return Response(
        json.dumps({"grid-nodes": list(grid_nodes.keys())}),
        status=200,
        mimetype="application/json",
    )


@main.route("/delete-node", methods=["DELETE"])
def delete_grid_note():
    """ Delete a grid node at grid network"""

    response_body = {"message": None}
    status_code = None

    try:
        data = json.loads(request.data)

        # Register new node
        if delete_node(data["node-id"], data["node-address"]):
            response_body["message"] = "Successfully Deleted!"
            status_code = 200
        else:  # Grid ID was not found
            response_body["message"] = "This ID was not found in connected nodes"
            status_code = 409

    # JSON format not valid.
    except ValueError or KeyError as e:
        response_body["message"] = INVALID_JSON_FORMAT_MESSAGE
        status_code = 400

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )


@main.route("/choose-encrypted-model-host", methods=["GET"])
def choose_encrypted_model_host():
    """ Used to choose grid nodes to host an encrypted model
        PS: currently we perform this randomly
    """
    grid_nodes = connected_nodes()
    n_replica = current_app.config["N_REPLICA"]

    if not n_replica:
        n_replica = 1
    try:
        hosts = random.sample(list(grid_nodes.keys()), n_replica * SMPC_HOST_CHUNK)
        hosts_info = [(host, grid_nodes[host]) for host in hosts]
    # If grid network doesn't have enough grid nodes
    except ValueError:
        hosts_info = []

    return Response(json.dumps(hosts_info), status=200, mimetype="application/json")


@main.route("/choose-model-host", methods=["GET"])
def choose_model_host():
    """ Used to choose some grid node to host a model.
        PS: Currently we perform this randomly.
    """
    grid_nodes = connected_nodes()
    n_replica = current_app.config["N_REPLICA"]
    if not n_replica:
        n_replica = 1

    model_id = request.args.get("model_id")
    hosts_info = None

    # lookup the nodes already hosting this model to prevent hosting different model versions
    if model_id:
        hosts_info = _get_model_hosting_nodes(model_id)

    # no model id given or no hosting nodes found: randomly choose node
    if not hosts_info:
        hosts = random.sample(list(grid_nodes.keys()), n_replica)
        hosts_info = [(host, grid_nodes[host]) for host in hosts]

    return Response(json.dumps(hosts_info), status=200, mimetype="application/json")


@main.route("/search-encrypted-model", methods=["POST"])
def search_encrypted_model():
    """ Search for an encrypted plan model on the grid network, if found,
        returns host id, host address and SMPC workers infos.
    """

    response_body = {"message": None}
    status_code = None

    try:
        body = json.loads(request.data)

        grid_nodes = connected_nodes()
        match_nodes = {}
        for node in grid_nodes:
            try:
                response = requests.post(
                    os.path.join(grid_nodes[node], "search-encrypted-models"),
                    data=request.data,
                )
            except requests.exceptions.ConnectionError:
                continue

            response = json.loads(response.content)

            # If workers / crypto_provider fields in response dict
            if not len({"workers", "crypto_provider"} - set(response.keys())):
                match_nodes[node] = {"address": grid_nodes[node], "nodes": response}

            response_body = match_nodes
            status_code = 200

    # JSON format not valid.
    except ValueError or KeyError as e:
        response_body["message"] = INVALID_JSON_FORMAT_MESSAGE
        status_code = 400

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )


@main.route("/search-model", methods=["POST"])
def search_model():
    """ Search for a plain text model on the grid network. """

    response_body = {"message": None}
    status_code = None

    try:
        body = json.loads(request.data)

        model_id = body["model_id"]
        match_nodes = _get_model_hosting_nodes(model_id)

        # It returns a list[ (id, address) ]  with all grid nodes that have the desired model
        response_body = match_nodes
        status_code = 200

    except ValueError or KeyError:
        response_body["message"] = INVALID_JSON_FORMAT_MESSAGE
        status_code = 400

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )


@main.route("/search-available-models", methods=["GET"])
def available_models():
    """ Get all available models on the grid network. Can be useful to know what models our grid network have. """
    grid_nodes = connected_nodes()
    models = set()
    for node in grid_nodes:
        try:
            response = requests.get(grid_nodes[node] + "/models/").content
        except requests.exceptions.ConnectionError:
            continue
        response = json.loads(response)
        models.update(set(response.get("models", [])))

    # Return a list[ "model_id" ]  with all grid nodes
    return Response(json.dumps(list(models)), status=200, mimetype="application/json")


@main.route("/search-available-tags", methods=["GET"])
def available_tags():
    """ Returns all available tags stored on grid nodes. Can be useful to know what dataset our grid network have. """
    grid_nodes = connected_nodes()
    tags = set()
    for node in grid_nodes:
        try:
            response = requests.get(grid_nodes[node] + "/dataset-tags").content
        except requests.exceptions.ConnectionError:
            continue
        response = json.loads(response)
        tags.update(set(response))

    # Return a list[ "#tags" ]  with all grid nodes
    return Response(json.dumps(list(tags)), status=200, mimetype="application/json")


@main.route("/search", methods=["POST"])
def search_dataset_tags():
    """ Search for information on all known nodes and return a list of the nodes that own it. """

    response_body = {"message": None}
    status_code = None

    try:
        body = json.loads(request.data)
        grid_nodes = connected_nodes()

        # Perform requests (HTTP) to all known nodes looking for the desired data tag
        match_grid_nodes = []
        for node in grid_nodes:
            try:
                response = requests.post(
                    grid_nodes[node] + "/search",
                    data=json.dumps({"query": body["query"]}),
                ).content
            except requests.exceptions.ConnectionError:
                continue
            response = json.loads(response)
            # If contains
            if response["content"]:
                match_grid_nodes.append((node, grid_nodes[node]))

        # It returns a list[ (id, address) ]  with all grid nodes that have the desired data
        response_body = match_grid_nodes
        status_code = 200

    except ValueError or KeyError as e:
        response_body["message"] = INVALID_JSON_FORMAT_MESSAGE
        status_code = 400

    return Response(json.dumps(response_body), status=200, mimetype="application/json")


@main.route("/federated/get-protocol", methods=["GET"])
def download_protocol():
    """Request a download of a protocol"""

    response_body = {}
    status_code = None
    try:
        worker_id = request.args.get("worker_id", None)
        request_key = request.args.get("request_key", None)
        protocol_id = request.args.get("protocol_id", None)

        # Retrieve Process Entities
        _protocol = processes.get_protocol(id=protocol_id)
        _cycle = processes.get_cycle(_protocol.fl_process_id)
        _worker = workers.get(id=worker_id)
        _accepted = processes.validate(_worker.id, _cycle.id, request_key)

        if not _accepted:
            raise InvalidRequestKeyError

        status_code = 200  # Success
        response_body[CYCLE.PROTOCOLS] = _protocol.value
    except InvalidRequestKeyError as e:
        status_code = 401  # Unauthorized
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except PyGridError as e:
        status_code = 400  # Bad request
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except Exception as e:
        status_code = 500  # Internal Server Error
        response_body[RESPONSE_MSG] = str(e)

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )


@main.route("/federated/get-model", methods=["GET"])
def download_model():
    """Request a download of a model"""

    response_body = {}
    status_code = None
    try:
        worker_id = request.args.get("worker_id", None)
        request_key = request.args.get("request_key", None)
        model_id = request.args.get("model_id", None)

        # Retrieve Process Entities
        _model = processes.get_model(id=model_id)
        _cycle = processes.get_cycle(_model.fl_process_id)
        _worker = workers.get(id=worker_id)
        _accepted = processes.validate(_worker.id, _cycle.id, request_key)

        if not _accepted:
            raise InvalidRequestKeyError

        _last_checkpoint = processes.get_model_checkpoint(model_id=model_id)

        return send_file(
            io.BytesIO(_last_checkpoint.values), mimetype="application/octet-stream"
        )

    except InvalidRequestKeyError as e:
        status_code = 401  # Unauthorized
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except PyGridError as e:
        status_code = 400  # Bad request
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except Exception as e:
        status_code = 500  # Internal Server Error
        response_body[RESPONSE_MSG.ERROR] = str(e)

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )


@main.route("/federated/speed-test", methods=["GET", "POST"])
def connection_speed_test():
    """ Connection speed test. """
    response_body = {}
    status_code = None

    try:
        _worker_id = request.args.get("worker_id", None)
        _random = request.args.get("random", None)

        if not _worker_id or not _random:
            raise PyGridError

        # If GET method
        if request.method == "GET":
            # Download data sample (1MB)
            data_sample = b"x" * 67108864  # 64 Megabyte
            response = {"sample": data_sample}
            form = MultipartEncoder(response)
            return Response(form.to_string(), mimetype=form.content_type)
        elif request.method == "POST":  # Otherwise, it's POST method
            if request.file:
                status_code = 200  # Success
            else:
                raise PyGridError
    except PyGridError as e:
        status_code = 400  # Bad Request
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except Exception as e:
        status_code = 500  # Internal Server Error
        response_body[RESPONSE_MSG.ERROR] = str(e)

    return Response(
        json.dumps(response_body), status_code=status_code, mimetype="application/json"
    )


@main.route("/federated/authenticate", methods=["POST"])
def auth():
    """uses JWT (HSA/RSA) to authenticate"""
    response_body = {}
    status_code = 200
    data = json.loads(request.data)
    _auth_token = data["auth_token"]
    model_name = data.get("model_name", None)

    """stub DB vars"""
    JWT_VERIFY_API = 1  # maybe processes._processes.last()["server_config"].get("JWT_VERIFY_API", None)
    RSA = False
    # maybe processes._processes.last(name=model_name)["server_config"].get("JWT_with_RSA", True)
    if RSA:
        pub_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDAswWWr/kU9Z5kj7KIQEs54B9x1MaEhEp4WDZPJ+PGONfg2tD4BKuGtDl345f4zgx7EPZL7EZRApLq6HxcznVbLleIbyqKkzvR88zHLBaxQ9GBRx+0kH8VqZspmMI/6fDBVm/SDtG1GOAYPwX1zK3DZZFMkkA2v8oGZ3U791jd9gy7S5CxewJrFMcFMStj9x8x3tW07OAdC7/HZpa5zKE2rWN01tytxbsl9/coMNBAfWIWEflhZgRz2+Onp2uDaXez7RNTe4m0+tQlx2FD0Pb7rFvlKwsgziKBReO8wwCQXWqcAPLsIXCOfUZXlBNpvPvp9I4HPEffaHyR1FC2eRoj4hzUibEu0+OQNj7QM5P9KsMV9k4wxURFxsd78rlFF8cnbKwIMf5nB8/FbqL/IyJOggxtntHr1Gum44QnG794GtSQHZNlWKKak2z/u2O++flxfZ9dBBAYWjJYM5kIT+X9NVYbWWryBqupHYipwP8f3vovKWVacOMMm3S0z76O5IDiIp5Gjnsifbnz57FWQok0HrSv8l3QMRPCxi3SjIFyI2ZusFC/4VLy9zZXQe07qI6l7s91UN6W8VW1YUFQ7nLGffkpAd/bLZSOueYQrf5tslQjZf3Jon5C/MkTJ7PGyOUmoAYya2kyKi4izMg/ODRIloVbWjU6tEPWyhzK8VMsXw== root@388da63cf68e"
        # @TODO: remove when hooked up to DB
        # maybe processes._processes.last(name=model_name)["server_config"].get("pub_key", None)
    else:
        SECRET = "very long a$$ very secret key phrase"  #  TODO:@PRTFW remove after hookup to DB  # maybe processes._processes.last(name=model_name)["server_config"].get("JWT_SECRET", "very long a$$ very secret key phrase")

    """end stub DB vars"""

    HIGH_SECURITY_RISK_NO_AUTH_FLOW = False if JWT_VERIFY_API is not None else True

    try:
        if not HIGH_SECURITY_RISK_NO_AUTH_FLOW:
            if _auth_token is None:

                status_code = 400
                return Response(
                    json.dumps(
                        {
                            "error": "Authentication is required, please pass an 'auth_token'."
                        }
                    ),
                    status=status_code,
                    mimetype="application/json",
                )
            else:
                base64Header, base64Payload, signature = _auth_token.split(".")
                header_str = base64.b64decode(base64Header)
                header = json.loads(header_str)
                _algorithm = header["alg"]

                if not RSA:
                    payload_str = base64.b64decode(base64Payload)
                    payload = json.loads(payload_str)
                    expected_token = jwt.encode(
                        payload, SECRET, algorithm=_algorithm
                    ).decode("utf-8")

                    if expected_token != _auth_token:
                        status_code = 400
                        return Response(
                            json.dumps(
                                {"error": "The 'auth_token' you sent is invalid."}
                            ),
                            status=status_code,
                            mimetype="application/json",
                        )
                else:
                    # we should check if RSA is true there is a pubkey string included during call to `host_federated_training`
                    # here we assume it exists / no redundant check
                    try:
                        jwt.decode(_auth_token, pub_key, _algorithm)

                    except Exception as e:
                        if e.__class__.__name__ == "InvalidSignatureError":
                            status_code = 400
                            return Response(
                                json.dumps(
                                    {
                                        "error": "The 'auth_token' you sent is invalid. "
                                        + str(e)
                                    }
                                ),
                                status=status_code,
                                mimetype="application/json",
                            )
        external_api_verify_data = {"auth_token": f"{_auth_token}"}
        verification_result = requests.get(
            "http://google.com"
        )  # test with get and google for now. using .post should result in failure
        # TODO:@MADDIE replace after we have a api to test with `verification_result = requests.post(JWT_VERIFY_API, data = json.dumps(external_api_verify_data))`
        if verification_result.status_code == 200:
            resp = fl_events_auth({"auth_token": _auth_token}, None)
            response_body = json.loads(resp)["data"]
        else:
            status_code = 400
            return Response(
                json.dumps(
                    {
                        "error": "The 'auth_token' you sent did not pass 3rd party verificaiton. "
                    }
                ),
                status=status_code,
                mimetype="application/json",
            )
    except Exception as e:
        status_code = 401
        response_body = {"error_auth_failed": str(e)}

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )


@main.route("/federated/report", methods=["POST"])
def report_diff():
    """Allows reporting of (agg/non-agg) model diff after worker completes a cycle"""
    response_body = {}
    status_code = None

    try:
        body = json.loads(request.data)
        response_body = report({MSG_FIELD.DATA: body}, None)
    except PyGridError or json.decoder.JSONDecodeError as e:
        status_code = 400  # Bad Request
        response_body[RESPONSE_MSG.ERROR] = str(e)
        response_body = json.dumps(response_body)
    except Exception as e:
        status_code = 500  # Internal Server Error
        response_body[RESPONSE_MSG.ERROR] = str(e)

    if isinstance(response_body, str):
        # Consider just data field as a response
        response_body = json.loads(response_body)[MSG_FIELD.DATA]

    response_body = json.dumps(response_body)
    return Response(response_body, status=status_code, mimetype="application/json")


def _get_model_hosting_nodes(model_id):
    """ Search all nodes if they are currently hosting the model.

    :param model_id: The model to search for
    :return: An array of the nodes currently hosting the model
    """
    grid_nodes = connected_nodes()
    match_nodes = []
    for node in grid_nodes:
        try:
            response = requests.get(grid_nodes[node] + "/models/").content
        except requests.exceptions.ConnectionError:
            continue
        response = json.loads(response)
        if model_id in response.get("models", []):
            match_nodes.append((node, grid_nodes[node]))

    return match_nodes


@main.route("/federated/cycle-request", methods=["POST"])
def worker_cycle_request():
    """" This endpoint is where the worker is attempting to join an active federated learning cycle. """
    response_body = {}
    status_code = None

    try:
        body = json.loads(request.data)
        response_body = cycle_request({MSG_FIELD.DATA: body}, None)
    except PyGridError or json.decoder.JSONDecodeError as e:
        status_code = 400  # Bad Request
        response_body[RESPONSE_MSG.ERROR] = str(e)
        response_body = json.dumps(response_body)
    except Exception as e:
        status_code = 500  # Internal Server Error
        response_body[RESPONSE_MSG.ERROR] = str(e)

    if isinstance(response_body, str):
        # Consider just data field as a response
        response_body = json.loads(response_body)[MSG_FIELD.DATA]

    response_body = json.dumps(response_body)
    return Response(response_body, status=status_code, mimetype="application/json")


@main.route("/req_join", methods=["GET"])
def fl_cycle_application_decision():
    """
        use the temporary req_join endpoint to mockup:
        - reject if worker does not satisfy 'minimum_upload_speed' and/or 'minimum_download_speed'
        - is a part of current or recent cycle according to 'do_not_reuse_workers_until_cycle'
        - selects according to pool_selection
        - is under max worker (with some padding to account for expected percent of workers so do not report successfully)
    """

    # parse query strings (for now), evetually this will be parsed from the request body
    model_id = request.args.get("model_id")
    up_speed = request.args.get("up_speed")
    down_speed = request.args.get("down_speed")
    worker_id = request.args.get("worker_id")
    worker_ping = request.args.get("ping")
    _cycle = processes.get_cycle(model_id)
    _accept = False
    """
    MVP variable stubs:
        we will stub these with hard coded numbers first, then make functions to dynaically query/update in subsquent PRs
    """
    # this will be replaced with a function that check for the same (model_id, version_#) tuple when the worker last participated
    last_participation = 1
    # how late is too late into the cycle time to give a worker "new work", if only 5 seconds left probably don't bother, set this intelligently later
    MINIMUM_CYCLE_TIME_LEFT = 500
    # the historical amount of workers that fail to report (out of time, offline, too slow etc...),
    # could be modified to be worker/model specific later, track across overall pygrid instance for now
    EXPECTED_FAILURE_RATE = 0.2

    dummy_server_config = {
        "max_workers": 100,
        "pool_selection": "random",  # or "iterate"
        "num_cycles": 5,
        "do_not_reuse_workers_until_cycle": 4,
        "cycle_length": 8 * 60 * 60,  # 8 hours
        "minimum_upload_speed": 2000,  # 2 mbps
        "minimum_download_speed": 4000,  # 4 mbps
    }

    """  end of variable stubs """

    _server_config = dummy_server_config

    up_speed_check = up_speed > _server_config["minimum_upload_speed"]
    down_speed_check = down_speed > _server_config["minimum_download_speed"]
    cycle_valid_check = (
        (
            last_participation + _server_config["do_not_reuse_workers_until_cycle"]
            >= _cycle.get(
                "cycle_sequence", 99999
            )  # this should reuturn current cycle sequence number
        )
        * (_cycle.get("cycle_sequence", 99999) <= _server_config["num_cycles"])
        * (_cycle.cycle_time > MINIMUM_CYCLE_TIME_LEFT)
        * (worker_id not in _cycle._workers)
    )

    if up_speed_check * down_speed_check * cycle_valid_check:
        if _server_config["pool_selection"] == "iterate" and len(
            _cycle._workers
        ) < _server_config["max_workers"] * (1 + EXPECTED_FAILURE_RATE):
            """ first come first serve selection mode """
            _accept = True
        elif _server_config["pool_selection"] == "random":
            """
                probabilistic model for rejction rate:
                    - model the rate of worker's request to join as lambda in a poisson process
                    - set probabilistic reject rate such that we can expect enough workers will request to join and be accepted
                        - between now and ETA till end of _server_config['cycle_length']
                        - such that we can expect (,say with 95% confidence) successful completion of the cycle
                        - while accounting for EXPECTED_FAILURE_RATE (% of workers that join cycle but never successfully report diff)

                EXPECTED_FAILURE_RATE = moving average with exponential decay based on historical data (maybe: noised up weights for security)

                k' = max_workers * (1+EXPECTED_FAILURE_RATE) # expected failure adjusted max_workers = var: k_prime

                T_left = T_cycle_end - T_now # how much time is left (in the same unit as below)

                normalized_lambda_actual = (recent) historical rate of request / unit time

                lambda' = number of requests / unit of time that would satisfy the below equation

                probability of receiving at least k' requests per unit time:
                    P(K>=k') = 0.95 = e ^ ( - lambda' * T_left) * ( lambda' * T_left) ^ k' / k'! = 1 - P(K<k')

                var: lambda_approx = lambda' * T_left

                solve for lambda':
                    use numerical approximation (newton's method) or just repeatedly call prob = poisson.sf(x, lambda') via scipy

                reject_probability = 1 - lambda_approx / (normalized_lambda_actual * T_left)
            """

            # time base units = 1 hr, assumes lambda_actual and lambda_approx have the same unit as T_left
            k_prime = _server_config["max_workers"] * (1 + EXPECTED_FAILURE_RATE)
            T_left = _cycle.get("cycle_time", 0)

            # TODO: remove magic number = 5 below... see block comment above re: how
            normalized_lambda_actual = 5
            lambda_actual = (
                normalized_lambda_actual * T_left
            )  # makes lambda_actual have same unit as lambda_approx
            # @hyperparam: valid_range => (0, 1) | (+) => more certainty to have completed cycle, (-) => more efficient use of worker as computational resource
            confidence = 0.95  # P(K>=k')
            pois = lambda l: poisson.sf(k_prime, l) - confidence

            """
            _bisect_approximator because:
                - solving for lambda given P(K>=k') has no algebraic solution (that I know of) => need approxmiation
                - scipy's optimizers are not stable for this problem (I tested a few) => need custom approxmiation
                - at this MVP stage we are not likely to experince performance problems, binary search is log(N)
            refactor notes:
                - implmenting a smarter approximiator using lambert's W or newton's methods will take more time
                - if we do need to scale then we can refactor to the above ^
            """
            # @hyperparam: valid_range => (0, 1) | (+) => get a faster but lower quality approximation
            _search_tolerance = 0.01

            def _bisect_approximator(arr, search_tolerance=_search_tolerance):
                """ uses binary search to find lambda_actual within search_tolerance"""
                n = len(arr)
                L = 0
                R = n - 1

                while L <= R:
                    mid = floor((L + R) / 2)
                    if pois(arr[mid]) > 0 and pois(arr[mid]) < search_tolerance:
                        return mid
                    elif pois(arr[mid]) > 0 and pois(arr[mid]) > search_tolerance:
                        R = mid - 1
                    else:
                        L = mid + 1
                return None

            """
            if the number of workers is relatively small:
                - approximiation methods is not neccessary / we can find exact solution fast
                - and search_tolerance is not guaranteed because lambda has to be int()
            """
            if k_prime < 50:
                lambda_approx = np.argmin(
                    [abs(pois(x)) for x in range(floor(k_prime * 3))]
                )
            else:
                lambda_approx = _bisect_approximator(range(floor(k_prime * 3)))

            rej_prob = (
                (1 - lambda_approx / lambda_actual)
                if lambda_actual > lambda_approx
                else 0  # don't reject if we expect to be short on worker requests
            )

            # additional security:
            if (
                k_prime > 50
                and abs(poisson.sf(k_prime, lambda_approx) - confidence)
                > _search_tolerance
            ):
                """something went wrong, fall back to safe default"""
                rej_prob = 0.1
                WARN = "_bisect_approximator failed unexpectedly, reset rej_prob to default"
                logging.exception(WARN)  # log error

            if random.random_sample() < rej_prob:
                _accept = True

    if _accept:
        return Response(
            json.dumps(
                {"status": "accepted"}
            ),  # leave out other accpet keys/values for now
            status=200,
            mimetype="application/json",
        )

    # reject by default
    return Response(
        json.dumps(
            {"status": "rejected"}
        ),  # leave out other accpet keys/values for now
        status=400,
        mimetype="application/json",
    )


@main.route("/federated/get-plan", methods=["GET"])
def download_plan():
    """Request a download of a plan"""

    response_body = {}
    status_code = None

    try:
        worker_id = request.args.get("worker_id", None)
        request_key = request.args.get("request_key", None)
        plan_id = request.args.get("plan_id", None)
        receive_operations_as = request.args.get("receive_operations_as", None)

        # Retrieve Process Entities
        _plan = processes.get_plan(id=plan_id, is_avg_plan=False)
        _cycle = processes.get_cycle(fl_process_id=_plan.fl_process_id)
        _worker = workers.get(id=worker_id)
        _accepted = processes.validate(_worker.id, _cycle.id, request_key)

        if not _accepted:
            raise InvalidRequestKeyError

        status_code = 200  # Success

        if receive_operations_as == "torchscript":
            # TODO leave only torchscript plan
            pass
        else:
            # TODO leave only list of ops plan
            pass

        return send_file(io.BytesIO(_plan.value), mimetype="application/octet-stream")

    except InvalidRequestKeyError as e:
        status_code = 401  # Unauthorized
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except PyGridError as e:
        status_code = 400  # Bad request
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except Exception as e:
        status_code = 500  # Internal Server Error
        response_body[RESPONSE_MSG.ERROR] = str(e)

    return Response(
        json.dumps(response_body), status=status_code, mimetype="application/json"
    )
