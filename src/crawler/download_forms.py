#!/usr/bin/python3

""" Download service forms from a government web site.

Sample usages:
  download_forms.py -s Maryland -a [MY_API_KEY] -cse [MY_CSE_ID]
  download_forms.py -s Maryland -q "WIC OR SNAP OR TANF" -a [MY_API_KEY] -cse [MY_CSE_ID]
  download_forms.py -s Maryland -u maryland.gov -q "WIC OR SNAP OR TANF -a [MY_API_KEY] -cse [MY_CSE_ID]

Assumes a (possibly empty) corpus exists. You can create an empty corpus
with create_corpus.py.

Also see:
https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list
"""

# TODO: See if there's a way to require that the search terms appear
# in the anchor text or the link title.

# To install googleapiclient.discovery:
# pip install google-api-python-client
from googleapiclient.discovery import build

import argparse
import crawl_lib
import json
import re
import subprocess
import time

# Curl parameter max_time, in seconds.
# Since we're running in one process, we don't want to block the
# entire crawl if a server is unresponsive, so we timeout after
# this many seconds.
timeout = "60"

# Number of links to download on each request.
# Custom search restricts this to 10, so we use the CGI "start"
# parameter in retrieve_results.
num_links = 10

# Some of these documents are big!
max_file_size = "2097152"

# How long to wait between requests, in seconds.
delay = 0.6

# These are used to filter out links with these terms in the filenames,
# so that we don't download inappropriate files.
#
# Returns a regex that ORs all the terms together.
#
def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='download_forms',
        description='Download forms from a site')

    parser.add_argument('-a', '--api_key')
    parser.add_argument('-c', '--county')
    parser.add_argument('-cs', '--citystate') # E.g., "Houston,TX".
    parser.add_argument('-cse', '--cse_id') # Custom Search Engine ID.
    parser.add_argument('-s', '--state')
    parser.add_argument('-q', '--query',
                        default =
                        crawl_lib.generate_double_positive_search_query())
    parser.add_argument('-u', '--url')
    return(parser.parse_args())

def identify_site(government, government_type):
    print("Identifying site for:", government)
    if government_type == 'state':
        with open('./data/state_urls.txt', 'r') as f:
            for line in f:
                line_parse = re.match('^([a-zA-Z0-9 ]+): (.*)$', line)
                if line_parse and line_parse.groups(0)[0] == government:
                    print("Site: ", line_parse.groups(0)[1])
                    return(line_parse.groups(0)[1])
        return('')
    elif government_type == 'city':
        print('Error: city should come with URL.')
    
def identify_directory(government, government_type):
    if government_type == 'state':
        return('./corpus/states/' + government)
    elif government_type == 'city':
        return('./corpus/cities/' + government)

def identify_county_directory(county, state):
    return('./corpus/counties/' + state + '/' + county)

def extract_filename_from_link(link):
    link_parse = re.match('^.*/(.*?)$', link)
    return(re.sub('%20', ' ', link_parse.groups(0)[0]))

def download_results(results, directory):
    for result in results:
        print(result['title'])
        filename = directory + '/' + result['title']
        subprocess.run(["curl", "-s", "-L", "--max-time", timeout,
                        "--max-filesize", max_file_size,
                        "--output", directory + '/' + result['title'],
                        result['link']])
        filetype = crawl_lib.filetype(filename)
        crawl_lib.rename_file_for_clarity(filename)


# TODO: Put more thought into term boundaries.
# Example: foo-manual passes through, I think.
# Passes through: 21.0902-Tri-Fold-Brochure_ERA-Cycle-3-v3.pdf
# Passes through: MOR-Certificate-of-Authority-application.pdf
def filter_results(results, negative_search_regex):
  filtered_results = [x for x in results
                      if not re.search(negative_search_regex, x['title'])]
  filtered_results = [x for x in filtered_results
                      if re.search('[A-Za-z]{3}', x['title'])]
  if len(results) != len(filtered_results):
    print("Filtered:", len(results) - len(filtered_results))
  return(filtered_results)

def retrieve_results(site, query, negative_search_regex, api_key, cse_id):
  results = []
  if not site:
      return(results)
  pdf_query = query + ' site:' + site + ' filetype:pdf'
  print(pdf_query)
  for i in range(10):
    page_results = crawl_lib.google_search(pdf_query, api_key, cse_id,
                                           num=num_links, start=i*10+1)
    if not page_results:
      break
    results.extend(filter_results(page_results, negative_search_regex))
    time.sleep(delay)
    
  docx_query = query + ' site:' + site + ' filetype:docx'
  for i in range(10):
    page_results = crawl_lib.google_search(docx_query, api_key, cse_id,
                                           num=num_links, start=i*10+1)
    if not page_results:
      break
    results.extend(filter_results(page_results, negative_search_regex))
    time.sleep(delay)

  return(results)

def main():
    args = parse_arguments()
    negative_search_regex = crawl_lib.generate_negative_search_regex()

    # Cities and counties will come with the URL.
    if args.citystate:
        site = args.url
        directory = identify_directory(args.citystate, 'city')
        results = retrieve_results(site, args.query, negative_search_regex,
                                   args.api_key, args.cse_id)
        if results:
            download_results(results, directory)
        else:
            print('No results for', args.citystate)

    elif args.county:
        if args.url:
          site = args.url
        else:
          site = identify_site(args.county, 'county')
        directory = identify_county_directory(args.county, args.state)
        results = retrieve_results(site, args.query, negative_search_regex,
                                   args.api_key, args.cse_id)
        if results:
            download_results(results, directory)
        else:
            print("No results for", site)
            
    elif args.state:
        if args.url:
          site = args.url
        else:
          site = identify_site(args.state, 'state')
        directory = identify_directory(args.state, 'state')
        results = retrieve_results(site, args.query, negative_search_regex,
                                   args.api_key, args.cse_id)
        if results:
            download_results(results, directory)
        else:
            print("No results for", site)

if __name__ == '__main__':
    main()


