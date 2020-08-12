NETWORK_PORT = "5000"
NETWORK_URL = "http://localhost:{}".format(NETWORK_PORT)
NETWORK_WS_URL = "ws://localhost:{}".format(NETWORK_PORT)

PORTS = ["3000", "3001", "3002", "3003"]
IDS = ["alice", "bob", "charlie", "dan"]

worker_ports = {node_id: port for node_id, port in zip(IDS, PORTS)}
