""" crawl_states: Crawl state web sites and download likely service forms.
"""

import argparse
import re
import subprocess

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='crawl_states',
        description='Crawl and download forms from states')

    parser.add_argument('-a', '--api_key')
    parser.add_argument('-cse', '--cse_id') # Custom Search Engine ID.
    return(parser.parse_args())


def crawl_states(api_key, cse_id):
    with open('./data/state_urls.txt') as f:
        for line in f:
            state_info = re.search('(.*): (.*)$', line)
            state = state_info.groups(0)[0]
            url = state_info.groups(0)[1]
            print('Downloading from', url)
            subprocess.run(['./download_forms.py', '-s', state, '-u', url,
                            '-q', 'application OR form',
                            '-a', api_key,
                            '-cse', cse_id])


def main():
    args = parse_arguments()
    crawl_states(args.api_key, args.cse_id)


if __name__ == '__main__':
    main()
            
