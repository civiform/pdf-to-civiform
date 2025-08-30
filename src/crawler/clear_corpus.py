""" Remove form files from the Form Corpus, keeping directory structure intact.
"""

import glob
import os

corpus = './corpus'

def clear_cities(corpus):
    cities = os.listdir(corpus + '/cities')
    for city in cities:
        filepaths = glob.glob(corpus + '/cities/' + city + '/*')
        for path in filepaths:
            os.remove(path)

def clear_states(corpus):
    states = os.listdir(corpus + '/states')
    for state in states:
        filepaths = glob.glob(corpus + '/states/' + state + '/*')
        for path in filepaths:
            os.remove(path)

def clear_counties(corpus):
    states = os.listdir(corpus + '/counties')
    for state in states:
        counties = os.listdir(corpus + '/counties/' + state)
        for county in counties:
            filepaths = glob.glob(corpus + '/counties/' + state +
                                  '/' + county + '/*')
            for path in filepaths:
                os.remove(path)

def main():
    clear_cities(corpus)
    clear_states(corpus)
    clear_counties(corpus)

if __name__ == '__main__':
    main()

