import pytest
import requests
import grid as gr
import unittest
import json
import syft as sy
import torch as th
from test import PORTS, IDS, GATEWAY_URL
import torch.nn.functional as F

hook = sy.TorchHook(th)


class GridAPITest(unittest.TestCase):
    def setUp(self):
        self.my_grid = gr.GridNetwork(GATEWAY_URL)

    def tearDown(self):
        self.my_grid.disconnect_nodes()

    def connect_nodes(self):
        nodes = {}

        for (node_id, port) in zip(IDS, PORTS):
            if node_id not in sy.hook.local_worker._known_workers:
                node = gr.WebsocketGridClient(
                    hook, "http://localhost:" + port + "/", id=node_id
                )
            else:
                node = sy.hook.local_worker._known_workers[node_id]
            node.connect()
            nodes[node_id] = node

        return nodes

    def disconnect_nodes(self, nodes):
        for node_id in nodes:
            nodes[node_id].disconnect()

    def test_connected_nodes(self):
        response = json.loads(requests.get(GATEWAY_URL + "/connected-nodes").content)
        self.assertEqual(len(response["grid-nodes"]), len(IDS))
        for node_id in IDS:
            self.assertTrue(node_id in response["grid-nodes"])

    def test_grid_host_query_jit_model(self):
        toy_model = th.nn.Linear(2, 5)
        data = th.zeros((5, 2))
        traced_model = th.jit.trace(toy_model, data)

        self.my_grid.host_model(traced_model, "test")
        assert None != self.my_grid.query_model("test")
        assert None == self.my_grid.query_model("unregistered-model")

    def test_host_plan_model(self):
        class Net(sy.Plan):
            def __init__(self):
                super(Net, self).__init__()
                self.fc1 = th.nn.Linear(2, 1)
                self.bias = th.tensor([1000.0])
                self.state += ["fc1", "bias"]

            def forward(self, x):
                x = self.fc1(x)
                return F.log_softmax(x, dim=0) + self.bias

        model = Net()
        model.build(th.tensor([1.0, 2]))

        self.my_grid.host_model(model, model_id="plan-model")

        # Call one time
        worker = self.my_grid.query_model("plan-model")
        prediction = worker.run_inference(
            model_id="plan-model", data=th.tensor([1.0, 2])
        )["prediction"]
        assert th.tensor(prediction) == th.tensor([1000.0])

        # Call one more time
        prediction = worker.run_inference(
            model_id="plan-model", data=th.tensor([1.0, 2])
        )["prediction"]
        assert th.tensor(prediction) == th.tensor([1000.0])

    def test_grid_search(self):
        nodes = self.connect_nodes()
        alice, bob, james = nodes["alice"], nodes["bob"], nodes["james"]

        simple_tensor = (
            th.tensor([1, 2, 3, 4, 5]).tag("#simple-tensor").describe("Simple tensor")
        )
        ptr_simple_tensor = simple_tensor.send(alice)
        ptr_simple_tensor.child.garbage_collect_data = False

        tensor_2d = th.tensor([[4], [5], [7], [8]]).tag("#2d-tensor").describe("2d")
        ptr_tensor_2d = tensor_2d.send(alice)
        ptr_tensor_2d.child.garbage_collect_data = False

        zero_tensor1 = (
            th.tensor([[0, 0, 0, 0, 0]])
            .tag("#zeros-tensor")
            .describe("tensor with zeros")
        )
        zero_tensor2 = (
            th.tensor([[0, 0, 0, 0, 0]])
            .tag("#zeros-tensor")
            .describe("tensor with zeros")
        )

        ptr_zero_tensor1 = zero_tensor1.send(bob)
        ptr_zero_tensor2 = zero_tensor2.send(james)
        ptr_zero_tensor1.child.garbage_collect_data = False
        ptr_zero_tensor2.child.garbage_collect_data = False

        self.disconnect_nodes(nodes)

        search_simple_tensor = self.my_grid.search("#simple-tensor")
        self.assertEqual(len(search_simple_tensor), 1)

        search_tensor_2d = self.my_grid.search("#2d-tensor")
        self.assertEqual(len(search_tensor_2d), 1)

        search_zeros_tensor = self.my_grid.search("#zeros-tensor")
        self.assertEqual(len(search_zeros_tensor), 2)

        search_nothing = self.my_grid.search("#nothing")
        self.assertEqual(len(search_nothing), 0)
