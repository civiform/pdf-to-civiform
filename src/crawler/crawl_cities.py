""" crawl_cities: Crawl city web sites and download likely service forms.
"""

import argparse
import re
import subprocess

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='crawl_cities',
        description='Crawl and download forms from cities')

    parser.add_argument('-a', '--api_key')
    parser.add_argument('-cse', '--cse_id') # Custom Search Engine ID.
    return(parser.parse_args())

def crawl_cities(api_key, cse_id):
    with open('./data/city_urls.txt') as f:
        for line in f:
            city_info = re.search('^(.*,) ([A-Z]{2}): (.*)$', line)
            citystate = city_info.groups(0)[0] + city_info.groups(0)[1]
            url = city_info.groups(0)[2]
            print('Downloading forms from', url)
            subprocess.run(['./download_forms.py',
                            '-cs', citystate,
                            '-u', url,
                            '-a', api_key,
                            '-cse', cse_id])


def main():
    args = parse_arguments()
    crawl_cities(args.api_key, args.cse_id)


if __name__ == '__main__':
    main()
