""" Create an empty corpus directory structure.

Assumes the existence of:
  ./data/city_urls.txt
  ./data/state_urls.txt
  ./data/counties/*/county_urls.txt

Does not overwrite any existing directories or files.
"""

import os
import re

corpus = './corpus'

def mkdir_unless_exists(directory):
    if not os.path.isdir(directory):
        os.mkdir(directory)


def create_cities(city_urls):
    mkdir_unless_exists(corpus + '/cities')
    with open(city_urls, 'r') as f:
        for line in f:
            city = re.search('^(.*?):', line).groups(0)[0]
            city = re.sub(', ', ',', city)
            mkdir_unless_exists(corpus + '/cities/' + city)


def create_states(state_urls):
    mkdir_unless_exists(corpus + '/states')
    with open(state_urls, 'r') as f:
        for line in f:
            state = re.search('^(.*?):', line).groups(0)[0]
            mkdir_unless_exists(corpus + '/states/' + state)


def create_counties(county_dir):
    mkdir_unless_exists(corpus + '/counties')
    states = os.listdir(county_dir)
    for state in states:
        if re.search('.txt$', state):
            continue
        print("State: ", state)
        mkdir_unless_exists(corpus + '/counties/' + state)
        with open(county_dir + state + '/county_urls.txt', 'r') as f:
            for line in f:
                county = re.search('^(.*?):', line).groups(0)[0]
                mkdir_unless_exists(corpus + '/counties/' + state +
                                    '/' + county)


def main():
    mkdir_unless_exists(corpus)
    create_cities('./data/city_urls.txt')
    create_states('./data/state_urls.txt')
    create_counties('./data/counties/')

if __name__ == '__main__':
    main()

