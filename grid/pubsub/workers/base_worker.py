from .. import base
from ..processes.broadcast_known_workers import BroadcastKnownWorkersProcess

class GridWorker(base.PubSub):

    def __init__(self):
        super().__init__('worker')

        # LAUNCH PROCESSES - these are non-blocking and run on their own threads

        # all process objects will live in this dictionary
        self.processes = {}

        # this process serves the purpose of helping other nodes find out about nodes on the network.
        # if someone queries the "list_worker" channel - it'll send a message directly to the querying node
        # with a list of the OpenMined nodes of which it is aware.
        self.processes['broadcast_known_workers'] = BroadcastKnownWorkersProcess(self)



