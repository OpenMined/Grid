:mod:`grid.workers`
===================

.. py:module:: grid.workers


Submodules
----------
.. toctree::
   :titlesonly:
   :maxdepth: 1

   socketio_client/index.rst
   socketio_server/index.rst


Package Contents
----------------

.. py:class:: WebsocketIOServerWorker(hook, host: str, port: int, payload=None, id: Union[int, str] = 0, log_msgs: bool = False, verbose: bool = False, data: List[Union[torch.Tensor, AbstractTensor]] = None)

   Bases: :class:`syft.workers.virtual.VirtualWorker`

   Objects of this class can act as a remote worker or as a plain socket IO.

   By adding a payload to the object it will execute it forwarding the messages to the participants in the setup.

   If no payload is added, this object will be a plain socketIO sitting between two clients that implement the
   protocol.

   .. method:: start(self)



   .. method:: _send_msg(self, message: bin)



   .. method:: _recv_msg(self, message: bin)


      Forwards a message to the WebsocketIOClientWorker


   .. method:: _init_job_thread(self)



   .. method:: _start_job_loop(loop)
      :staticmethod:


      Switch to new event loop and run forever


   .. method:: _start_payload(self)



   .. method:: terminate(self)




.. py:class:: WebsocketIOClientWorker(hook, host: str, port: int, id: Union[int, str] = 0, is_client_worker: bool = False, log_msgs: bool = False, verbose: bool = False, data: List[Union[torch.Tensor, AbstractTensor]] = None)

   Bases: :class:`syft.workers.virtual.VirtualWorker`

   A worker that forwards a message to a SocketIO server and wait for its response.

   This client then waits until the server returns with a result or an ACK at which point it finishes the
   _recv_msg operation.

   .. method:: _send_msg(self, message: bin)



   .. method:: _recv_msg(self, message: bin)



   .. method:: connect(self)



   .. method:: disconnect(self)




