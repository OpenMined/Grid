from .blueprint import setup_blueprint as setup_route
from flask import request, Response
import json

from syft.grid.messages.setup_messages import (
    CreateInitialSetUpMessage,
    GetSetUpMessage,
)

from ..auth import error_handler, token_required, optional_token, setup_token
from ...core.task_handler import route_logic

from main.core.node import get_node


@setup_route.route("/", methods=["POST"])
@setup_token
def initial_setup(current_user):
    # Get request body
    content = request.get_json()
    if not content:
        content = {}

    status_code, response_msg = error_handler(
        route_logic, CreateInitialSetUpMessage, current_user, content
    )

    response = response_msg if isinstance(response_msg, dict) else response_msg.content

    return Response(
        json.dumps(response),
        status=status_code,
        mimetype="application/json",
    )


@setup_route.route("/", methods=["GET"])
@token_required
def get_setup(current_user):
    # Get request body
    content = request.get_json()
    if not content:
        content = {}

    status_code, response_msg = error_handler(
        route_logic, GetSetUpMessage, current_user, content
    )

    response = response_msg if isinstance(response_msg, dict) else response_msg.content

    return Response(
        json.dumps(response),
        status=status_code,
        mimetype="application/json",
    )


@setup_route.route("/status", methods=["GET"])
def get_status():
    response = {"node_name": get_node().name, "init": len(get_node().users) > 0}

    return Response(
        json.dumps(response), status=status_code, mimetype="application/json"
    )
