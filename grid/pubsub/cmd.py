from . import base
from . import workers
from colorama import Fore, Back, Style
from pathlib import Path

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
                   const=True, default=True,
                   help='Run grid in compute mode')

parser.add_argument('--tree', dest='tree', action='store_const',
                   const=True, default=False,
                   help='Run grid in tree mode')

parser.add_argument('--anchor', dest='anchor', action='store_const',
                   const=True, default=False,
                   help='Run grid in anchor mode')

args = parser.parse_args()

"""
TODO: modify Client to store the source code for the model in IPFS.
      (think through logistics; introduces
      hurdles for packaging model source code)
TODO: figure out a convenient way to make robust training procedure for torch
      -- will probably want to use ignite for this
"""


print("\n\n")

if(args.tree):
    w = workers.tree.GridTree()
elif(args.anchor):
    w = workers.anchor.GridAnchor()
else:
    w = workers.compute.GridCompute()



#     """
#     Grid Tree Implementation

#     Methods for Grid tree down here
#     """

#     def work(self):
#         print('\n\n')
#         if args.tree:
            

#         elif args.anchor:
#             print(strings.anchor)
#             self.anchor()
#         else:
            


#     def anchor(self):
#         """
#         Use as anchor node for faster initial IPFS connections.
#         """
#         def just_listen(message):
#             ""

        


    