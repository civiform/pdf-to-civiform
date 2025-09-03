""" crawl_counties: Crawl county web sites and download likely service forms.
"""

import argparse
import os
import re
import subprocess

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='crawl_counties',
        description='Crawl and download forms from counties')

    parser.add_argument('-a', '--api_key')
    parser.add_argument('-cse', '--cse_id') # Custom Search Engine ID.
    return(parser.parse_args())


def crawl_counties(api_key, cse_id):
    states = os.listdir('./data/counties')
    states.sort()
    for state in states:
        # Remove entries like "Maryland.txt".
        if state.find('.') != -1:
            continue
        print(state)
        counties = os.listdir('./data/counties/' + state)
        with open('./data/counties/' + state + '/county_urls.txt') as f:
            for line in f:
                county_info = re.search('^(.*): (.*)$', line)
                county = county_info.groups(0)[0]
                url = county_info.groups(0)[1]
                if not url:
                    continue
                print('Downloading forms from', url)
                subprocess.run(['./download_forms.py',
                                '-c', county, '-s', state, '-u', url,
                                '-a', api_key, '-cse', cse_id])


def main():
    args = parse_arguments()
    crawl_counties(args.api_key, args.cse_id)


if __name__ == '__main__':
    main()


