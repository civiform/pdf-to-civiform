# Government Form Crawl

## Program manifest

* clear_corpus.py: Deletes downloaded PDFs, leaving dir structure inact.
* crawl_cities.py: Crawl all cities in data/city_urls.txt.
* crawl_counties.py: Crawl all counties in data/counties.
* crawl_lib.py: Helper functions for the crawl.
* crawl_lib_test.py: Tests crawl_lib functions.
* crawl_states.py: Crawl all states in data/state_urls.txt.
* create_corpus.py: Creates corpus directory structure.
* download_forms.py: Download forms identified by the crawl.

## Instructions

### Setup

1. **Python Environment**: These scripts require Python 3.x.
2. Install googleapiclient.discovery with `pip install google-api-python-client`.
3. Create an API key for the Google Programmable/Custom Search Engine,
See https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list.
4. Create a Custom Search Engine ID.

### Create an empty corpus (in `./corpus`):

`python create_corpus.py`

### Download PDF forms from a government:

* `python download_forms.py -s Maryland -a [MY_API_KEY] -cse [MY_CSE_ID]`
* `python download_forms.py -s Maryland -q "WIC OR SNAP OR TANF" -a [MY_API_KEY] -cse [MY_CSE_ID]`

### Crawl all city governments:

`python crawl_cities.py -a [MY_API_KEY] -cse [MY_CSE_ID]`

### Crawl all county governments:

`python crawl_counties.py -a [MY_API_KEY] -cse [MY_CSE_ID]`

### Crawl all state governments:

`python crawl_states.py -a [MY_API_KEY] -cse [MY_CSE_ID]`



