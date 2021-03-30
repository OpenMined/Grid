from functools import wraps
from json import dumps
from json.decoder import JSONDecodeError

from syft.core.node.common.node import DuplicateRequestException
from flask import Response, request
from flask import current_app as app
import jwt

from ..core.codes import RESPONSE_MSG
from ..core.exceptions import (
    PyGridError,
    UserNotFoundError,
    RoleNotFoundError,
    GroupNotFoundError,
    AuthorizationError,
    MissingRequestKeyError,
    InvalidCredentialsError,
)
from ..core.database import User, db

def token_required_factory(get_token, format_result, optional=False):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            status_code = 200
            mimetype = "application/json"
            response_body = {}
            try:
                token = get_token(optional=optional)
            except Exception as e:
                status_code = 400  # Bad Request
                response_body[RESPONSE_MSG.ERROR] = str(e)
                return format_result(response_body, status_code, mimetype)
            try:
                current_user = None
                if token:
                    data = jwt.decode(
                        token, app.config["SECRET_KEY"], algorithms="HS256"
                    )
                    current_user = User.query.get(data["id"])
                if current_user is None and not optional:
                    raise UserNotFoundError
            except Exception as e:
                status_code = 403  # Unauthorized
                response_body[RESPONSE_MSG.ERROR] = str(InvalidCredentialsError())
                return format_result(response_body, status_code, mimetype)

            return f(current_user, *args, **kwargs)

        return wrapper

    return decorator


def get_token(optional=False):
    token = request.headers.get("token", None)
    if token is None and not optional:
        raise MissingRequestKeyError

    return token


def format_result(response_body, status_code, mimetype):
    return Response(dumps(response_body), status=status_code, mimetype=mimetype)


token_required = token_required_factory(get_token, format_result)
optional_token = token_required_factory(get_token, format_result, optional=True)


def error_handler(f, *args, **kwargs):
    status_code = 200  # Success
    response_body = {}

    try:
        response_body = f(*args, **kwargs)
    except (
        InvalidCredentialsError,
        AuthorizationError,
        DuplicateRequestException,
    ) as e:
        status_code = 403  # Unathorized
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except (GroupNotFoundError, RoleNotFoundError, UserNotFoundError) as e:
        status_code = 404  # Resource not found
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except (TypeError, MissingRequestKeyError, PyGridError, JSONDecodeError) as e:
        status_code = 400  # Bad Request
        response_body[RESPONSE_MSG.ERROR] = str(e)
    except Exception as e:
        print(type(e), str(e))
        status_code = 500  # Internal Server Error
        response_body[RESPONSE_MSG.ERROR] = str(e)

    return status_code, response_body
