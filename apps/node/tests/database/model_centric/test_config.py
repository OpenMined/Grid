import pytest
import sys

from . import BIG_INT
from .presets.config import configs

from random import randint
from grid_node.app.main.sfl.processes.config import Config

sys.path.append(".")


@pytest.mark.parametrize("client_config, server_config", configs)
def test_create_config_object(client_config, server_config, database):
    my_server_config = Config(id=randint(0, BIG_INT), config=server_config)
    my_client_config = Config(id=randint(0, BIG_INT), config=client_config)
    database.session.add(my_server_config)
    database.session.add(my_client_config)
    database.session.commit()
