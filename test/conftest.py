import pytest
import torch
from multiprocessing import Process
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import os
import sys

# We need to add our rest api as a path since it is a separate application
# deployed on Heroku:
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../app/pg_rest_api")
from pg_app import create_app

import syft
from syft import TorchHook
from test import IDS, PORTS, GATEWAY_URL
import time
import requests
import json
import os
import grid as gr


@pytest.fixture()
def start_proc():  # pragma: no cover
    """ helper function for spinning up a websocket participant """

    def _start_proc(participant, kwargs):
        def target():
            server = participant(**kwargs)
            server.start()

        p = Process(target=target)
        p.start()
        return p

    return _start_proc


@pytest.fixture(scope="session", autouse=True)
def node_infos():
    return zip(IDS, PORTS)


@pytest.fixture(scope="session", autouse=True)
def init_gateway():
    def setUpGateway(port):
        os.environ["SECRET_KEY"] = "Secretkeyhere"
        from gateway.app import create_app

        app = create_app(debug=False)
        app.run(host="0.0.0.0", port="8080")

    # Init Grid Gateway
    p = Process(target=setUpGateway, args=("8080",))
    p.start()
    time.sleep(5)

    yield

    p.terminate()


@pytest.fixture(scope="session", autouse=True)
def init_nodes(node_infos):
    def setUpNode(port, node_id):
        from app.websocket.app import create_app as ws_create_app
        from app.websocket.app import socketio

        requests.post(
            GATEWAY_URL + "/join",
            data=json.dumps(
                {"node-id": node_id, "node-address": "http://localhost:" + port + "/"}
            ),
        )
        socketio.async_mode = "threading"
        app = ws_create_app(debug=False)
        socketio.run(app, host="0.0.0.0", port=port)

    jobs = []
    # Init Grid Nodes
    for (node_id, port) in node_infos:
        config = (node_id, port)
        p = Process(target=setUpNode, args=(port, node_id))
        p.start()
        jobs.append(p)
    time.sleep(5)

    yield

    for job in jobs:
        job.terminate()


@pytest.fixture(scope="function")
def connected_node(hook):
    nodes = {}
    for (node_id, port) in zip(IDS, PORTS):
        node = gr.WebsocketGridClient(
            hook, "http://localhost:" + port + "/", id=node_id
        )
        node.connect()
        time.sleep(0.1)
        nodes[node_id] = node

    yield nodes

    for node in nodes:
        nodes[node].disconnect()
        time.sleep(0.1)


@pytest.fixture(scope="function")
def grid_network():
    my_grid = gr.GridNetwork(GATEWAY_URL)

    yield my_grid

    my_grid.disconnect_nodes()


@pytest.fixture(scope="session", autouse=True)
def hook():
    hook = TorchHook(torch)
    return hook
