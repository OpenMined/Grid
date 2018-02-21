import json
import twitter
import os
import sys

from colorama import Fore, Style

print(f'working in {os.getcwd()}')
if not os.path.exists('grid/adapters/config.json'):
    print(f'{Fore.RED}no {Fore.YELLOW}config.json{Fore.RED} file present in adapters directory.  Make sure the file exists{Style.RESET_ALL}')
    sys.exit()

config = json.load(open('grid/adapters/config.json'))

if not 'consumerKey' in config.keys():
    print(f'{Fore.RED}no {Fore.YELLOW}consumerKey{Fore.RED} specified in config.json.  Check {Fore.YELLOW}config.example.json{Fore.RED} for an example{Style.RESET_ALL}')
    sys.exit()
if not 'consumerSecret' in config.keys():
    print(f'{Fore.RED}no {Fore.YELLOW}consumerSecret{Fore.RED} specified in config.json.  Check {Fore.YELLOW}config.example.json{Fore.RED} for an example{Style.RESET_ALL}')
    sys.exit()
if not 'accessTokenKey' in config.keys():
    print(f'{Fore.RED}no {Fore.YELLOW}accessTokenKey{Fore.RED} specified in config.json.  Check {Fore.YELLOW}config.example.json{Fore.RED} for an example{Style.RESET_ALL}')
    sys.exit()
if not 'accessTokenSecret' in config.keys():
    print(f'{Fore.RED}no {Fore.YELLOW}accessTokenSecret{Fore.RED} specified in config.json.  Check {Fore.YELLOW}config.example.json{Fore.RED} for an example{Style.RESET_ALL}')
    sys.exit()

api = twitter.Api(consumer_key=config['consumerKey'],
    consumer_secret=config['consumerSecret'],
    access_token_key=config['accessTokenKey'],
    access_token_secret=config['accessTokenSecret'])

statuses = api.GetUserTimeline(screen_name='gavinuhma')
print(statuses)
