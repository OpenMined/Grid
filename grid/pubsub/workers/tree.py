from . import base_worker
from ...lib import strings
from .. import channels
from .. import commands
from bitcoin import base58
import os
from pathlib import Path

class GridTree(base_worker.GridWorker):

    """
    This class runs a worker whose purpose is to do the following:
       - PRIMARY: to facilitate federated learning of a public model on many nodes
       - PRIMARY: to version control gradients in a branching tree of updates - facilitating the federated learning
       - SECONDARY: learn about the existence of other nodes on the network - and help others to do so when asked
    """

    def __init__(self):
        super().__init__()

        # prints a pretty picture of a tree
        print(strings.tree)

        # LAUNCH PROCESSES - these are non-blocking and run on their own threads

        # Blocking until this node has found at least one other OpenMined node
        # This functionality queries https://github.com/OpenMined/BootstrapNodes for Anchor nodes
        # then asks those nodes for which other OpenMined nodes they know about on the network.
        self.listen_for_openmined_nodes(1)

        # this process serves the purpose of helping other nodes find out about nodes on the network.
        # if someone queries the "list_worker" channel - it'll send a message directly to the querying node
        # with a list of the OpenMined nodes of which it is aware.
        self.listen_to_channel(channels.list_workers,self.list_workers)

        # listens to the network and tells other nodes what tasks you'e working on if they ask
        self.listen_to_channel(channels.list_tasks, self.list_tasks)

        # listens for folks who want to add tasks to be trained to the network
        self.listen_to_channel(channels.add_task, self.discovered_tasks)

        # responds to tasks you're specificalyl asked to do
        self.listen_to_channel(channels.list_tasks_callback(self.id), self.discovered_tasks)

        # listens in case someone asks what models i've got
        self.listen_to_channel(channels.list_models, self.list_models)

        # if i'm turning on after having done some previous work - it publishes previous work to the network
        self.publish(channels.list_tasks, commands.list_all)


    def list_tasks(self, message):
        fr = base58.encode(message['from'])

        if not os.path.exists(f"{Path.home()}/.openmined/tasks.json"):
            return

        with open(f"{Path.home()}/.openmined/tasks.json", "r") as task_list:
            string_list = task_list.read()
            tasks = json.loads(string_list)
            # for t in tasks:
                # self.listen_for_models(t['name'])

        callback_channel = channels.list_tasks_callback(fr)
        print(f'?!?!?!?!?! {callback_channel} {string_list}')
        self.publish(callback_channel, string_list)


    ############################### BEGIN PROCESS FUNCTIONS ########################

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
                self.listen_for_models(name)
                utils.store_task(name, addr)

                self.load_adapter(t['adapter'])


    def list_models(self, message):
        task = message['data']
        fr = base58.encode(message['from'])

        print(f'listing models {fr} {self.id}')

        if fr == self.id:
            return

        my_best = utils.best_model_for_task(task)
        if my_best is not None:
            self.send_model(task, my_best)


    def listen_for_models(self, task_name):
        self.listen_to_channel(channels.add_model(task_name), self.added_model)
        self.publish(channels.list_models, task_name)

    ############################### BEGIN SUBPROCESSES FUNCTIONS ########################

    def train_model(self, model, input, target, name, task_name, task_addr):
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
            self.train_model(model, input, name, taraget, task_name, task_addr)

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
        print('load next input')
        n_test, n_target = grid_adapter.next_input()
        self.train_model(model, n_test, n_target, name, task_name, task_addr)


    def added_model(self, info):
        info = self.api.get_json(info['data'])

        task_addr = info['task']
        task_info = self.api.get_json(task_addr)

        print(f'added model {task_info}')

        if 'data_dir' in task_info.keys():
            self.added_local_data_model(info)
        elif 'adapter' in task_info.keys():
            self.added_adapter_model(info)


    def load_adapter(self, addr):
        b = self.api.cat(addr)
        utils.ensure_exists(f'{Path.home()}/.openmined/grid/adapters/t.py', b)
        exec(open(f'{Path.home()}/.openmined/grid/adapters/t.py').read())


    