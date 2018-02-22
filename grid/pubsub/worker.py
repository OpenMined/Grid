from grid.lib import OutputPipe, utils, strings
from . import base
from grid.pubsub import commands
from grid.pubsub import channels
from colorama import Fore, Back, Style

import json
import threading
from bitcoin import base58
import os
import numpy as np
import keras
import argparse

title = f"""{Fore.GREEN}   ____                             _                __   ______     _     __
  / __ \____  ___  ____  ____ ___  (_____  ___  ____/ /  / _________(_____/ /
 / / / / __ \/ _ \/ __ \/ __ `__ \/ / __ \/ _ \/ __  /  / / __/ ___/ / __  /
/ /_/ / /_/ /  __/ / / / / / / / / / / / /  __/ /_/ /  / /_/ / /  / / /_/ /
\____/ .___/\___/_/ /_/_/ /_/ /_/_/_/ /_/\___/\__,_/   \____/_/  /_/\__,_/
    /_/          {Style.RESET_ALL}{Fore.YELLOW}A distributed compute grid{Style.RESET_ALL}
"""

print(title)

program_desc = f"""
"""

# print(title)

parser = argparse.ArgumentParser(description=program_desc)
parser.add_argument('--compute', dest='compute', action='store_const',
                   const=True, default=False,
                   help='Run grid in compute mode')
parser.add_argument('--tree', dest='tree', action='store_const',
                   const=True, default=False,
                   help='Run grid in tree mode')

args = parser.parse_args()

"""
TODO: modify Client to store the source code for the model in IPFS.
      (think through logistics; introduces
      hurdles for packaging model source code)
TODO: figure out a convenient way to make robust training procedure for torch
      -- will probably want to use ignite for this
"""


class Worker(base.PubSub):

    def __init__(self):
        super().__init__('worker')

    def anchor(self):
        """
        Use as anchor node for faster initial IPFS connections.
        """
        self.listen_to_channel(channels.openmined)


    def train_meta(self, message):
        decoded = json.loads(message['data'])
        if 'op_code' not in decoded:
            return

        self.learner_callback.stop_training = decoded['op_code'] == 'quit'

    # TODO: torch
    def fit_worker(self, message):

        decoded = json.loads(message['data'])

        if(decoded['framework'] == 'keras'):

            model = utils.ipfs2keras(decoded['model_addr'])

            try:
                np_strings = json.loads(self.api.cat(decoded['data_addr']))
            except NotImplementedError:
                raise NotImplementedError("The IPFS API only supports Python 3.6. Please modify your environment.")

            input, target, valid_input, valid_target = list(map(lambda x: self.deserialize_numpy(x),np_strings))
            train_channel = decoded['train_channel']

            self.learner_callback = OutputPipe(
                id=self.id,
                publisher=self.publish,
                channel=train_channel,
                epochs=decoded['epochs'],
                model_addr=decoded['model_addr'],
                model=model
            )

            args = (self.train_meta, train_channel + ':' + self.id)
            monitor_thread = threading.Thread(target=self.listen_to_channel,
                                              args=args)
            monitor_thread.start()

            print('training model')

            model.fit(
                input,
                target,
                batch_size=decoded['batch_size'],
                validation_data=(valid_input, valid_target),
                verbose=False,
                epochs=decoded['epochs'],
                callbacks=[self.learner_callback]
            )

            print('done')

        else:
            raise NotImplementedError("Only compatible with Keras at the moment")

    """
    Grid Tree Implementation

    Methods for Grid tree down here
    """

    def work(self):
        print('\n\n')
        if args.tree:
            print(strings.tree)
            print('discovered tasks????')
            # self.discovered_tasks({
            #     'data': '[{"name": "tweets3", "address": "QmPWSksj65wwXunnbwtx8cg2Zmna2LQNHYrAjLWPYxF8eN"}]',
            #     'from': 'benny'
            # })

            self.added_model({
                'data': 'QmY8PmgZLFPh4u9wHCwMPq8P21LM9TrwomX69RfPLQVG5W',
                'from': 'benny'
            })

            # self.added_model({
            #     'data': {
            #         'task': 'QmPWSksj65wwXunnbwtx8cg2Zmna2LQNHYrAjLWPYxF8eN',
            #         'name': 'tweets3',
            #         'model': 'QmSiYaF6ww7XBd3W3JBrCzmTw97K7C82MyPijRTJUZsXfC',
            #         'creator': 'benny'
            #     }
            # })
            # self.listen_to_channel(channels.list_tasks, self.list_tasks)
            # self.listen_to_channel(channels.add_task, self.discovered_tasks)
            # self.listen_to_channel(channels.list_tasks_callback(self.id), self.discovered_tasks)
            # self.listen_to_channel(channels.list_models, self.list_models)
            # self.publish(channels.list_tasks, commands.list_all)


        else:
            print(strings.compute)
            self.listen_to_channel(channels.openmined, self.fit_worker)

    def listen_for_models(self, model_name):
        self.listen_to_channel(channels.add_model(model_name), self.added_model)
        self.publish(channels.list_models, model_name)

    def list_models(self, message):
        task = message['data']
        fr = base58.encode(message['from'])

        if fr == self.id:
            return

        my_best = utils.best_model_for_task(task)
        if my_best is not None:
            self.send_model(task, my_best)

    def list_tasks(self, message):
        fr = base58.encode(message['from'])

        if not os.path.exists("~/.openmined/tasks.json"):
            return

        with open("~/.openmined/tasks.json", "r") as task_list:
            string_list = task_list.read()
            tasks = json.loads(string_list)
            # for t in tasks:
                # self.listen_for_models(t['name'])

        callback_channel = channels.list_tasks_callback(fr)

        self.publish(callback_channel, string_list)

    def added_local_data_model(self, info):
        task_addr = info['task']
        task_info = self.api.get_json(task_addr)

        task_name = info['name']
        model_addr = info['model']

        data_dir = task_info['data_dir']
        name = task_info['name']
        creator = info['creator']

        print(f'FOUND NEW MODEL: {task_addr}, {model_addr}, {data_dir}, {name}, {creator}')

        if os.path.exists(f'data/{data_dir}') and creator != self.id:
            model = utils.ipfs2keras(model_addr)
            input = None
            target = None
            for filename in os.listdir(f'data/{data_dir}'):
                temp_data = np.load(f'data/{data_dir}/{filename}')

                temp_input = temp_data['x_train']
                temp_target = temp_data['y_train']

                if input is None:
                    input = temp_input
                else:
                    input = np.append(input, temp_input)
                    input = np.reshape(input, (-1, 28, 28))

                if target is None:
                    target = temp_target
                else:
                    target = np.append(target, temp_target)

            # TODO specifically mnist?!?!?!?!?!?
            input = input.reshape(input.shape[0], 784)
            input = input.astype('float32')
            input /= 255

            target = keras.utils.to_categorical(target, 10)

            hist = model.fit(
                input,
                target,
                batch_size=100, # TODO config?!?!?!?!
                verbose=True,
                epochs=10, # TODO config?!??!??!?
                validation_split=0.1 # TODO config??!?!?!?!?!?
            )

            loss = hist.history.get('loss')[-1]
            print(f'{Fore.GREEN}Finished training {Fore.YELLOW} -- {loss}{Style.RESET_ALL}')

            my_best_model = utils.best_model_for_task(task_name, return_model=True)
            best_loss = 100000000
            if not my_best_model == None:
                best_loss = my_best_model.evaluate(input, target, batch_size=100)[0]
                print(f'{Fore.YELLOW}Best Evaluated at: {best_loss}{Style.RESET_ALL}')
                if best_loss < loss:
                    print(f'{Fore.RED}Trained model worse than best trained.  Ignoring.{Style.RESET_ALL}')
                    return

            if loss < best_loss:
                print(f'New best loss of {Fore.GREEN}{loss}{Style.RESET_ALL} for task {Fore.GREEN}{task_name}{Style.RESET_ALL}')
                utils.save_best_model_for_task(task_name, model)

            self.add_model(name, model, parent=task_addr)
        else:
            print("Can't train your own model so soon!!!!!")

    def added_adapter_model(self, info):
        task_addr = info['task']
        task_info = self.api.get_json(task_addr)

        task_name = info['name']
        model_addr = info['model']

        adapter = task_info['adapter']
        name = task_info['name']
        creator = info['creator']

        model = utils.ipfs2keras(model_addr)

        utils.save_adapter(adapter)
        import grid.adapters.adapter as grid_adapter
        n = grid_adapter.next_input()

        print(f'next input!!! {n}')

    def added_model(self, info):
        info = self.api.get_json(info['data'])

        task_addr = info['task']
        task_info = self.api.get_json(task_addr)

        if 'data_dir' in task_info.keys():
            self.added_local_data_model(info)
        elif 'adapter' in task_info.keys():
            self.added_adapter_model(info)

    def load_adapter(self, addr):
        b = self.api.cat(addr)
        with open('grid/adapters/t.py', 'wb') as a:
            a.write(b)
            a.close()

        print(f'working in ... {os.getcwd()}')
        exec(open('grid/adapters/t.py').read())


    def discovered_tasks(self, tasks):
        print(f'{Fore.WHITE}{Back.BLACK} TASKS {Style.RESET_ALL}')
        print(f'From\t\t\t\tName\t\t\t\tAddress')
        print('==================================================================')

        data = json.loads(tasks['data'])
        fr = tasks['from'] # base58.encode(tasks['from'])

        for task in data:
            name = task['name']
            addr = task['address']

            print(f'{fr}\t{name}\t{addr}')

            t = self.api.get_json(addr)
            if 'data_dir' in t.keys():
                data_dir = t['data_dir']
                if os.path.exists(f'data/{data_dir}'):
                    self.listen_for_models(name)
                    utils.store_task(name, addr)
                else:
                    print(f"DON'T HAVE DATA FOR {name} DATA DIRECTORY: {data_dir}")
            elif 'adapter' in t.keys():
                print('got an adapter task!!!!!')
                self.load_adapter(t['adapter'])
