"""Utilities for the CiviForm form crawl.

The primary user of this module is download_forms.py.

A sample retrieved result follows.
See https://developers.google.com/custom-search/v1/reference/rest/v1/Search.

{'kind': 'customsearch#result',
 'title': '22-14 AT - Attachment - '
          'Consolidated-Work-Notice-Sample-.pdf',
 'htmlTitle': '22-14 AT - Attachment - '
              'Consolidated-Work-Notice-Sample-.pdf',
 'link': 'https://dhs.maryland.gov/documents/FIA/Action%20Transmittals-AT%20-%20Information%20Memo-IM/AT-IM2022/22-14%20AT%20-%20Attachment%20-%20Consolidated-Work-Notice-Sample-.pdf',
 'displayLink': 'dhs.maryland.gov',
 'snippet': 'The SNAP E&T program offers training to qualify '
            'participants for employment in the following areas: '
            'IT/Cybersecurity, Warehousing, Diesel Tech, CDL,\xa0'
            '...',
 'htmlSnippet': 'The <b>SNAP</b> E&amp;T program offers training to '
                'qualify participants for employment in the '
                'following areas: IT/Cybersecurity, Warehousing, '
                'Diesel Tech, CDL,&nbsp;...',
 'formattedUrl': 'https://dhs.maryland.gov/.../22-14%20AT%20-%20Attachment%20-%20C...',
 'htmlFormattedUrl': 'https://dhs.maryland.gov/.../22-14%20AT%20-%20Attachment%20-%20C...',
 'pagemap': {'cse_thumbnail': [{'src': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS-rEJSqQ4s549rvUM3jxL8VcGAelmLSkLd_wuP_n5EShKmt3B3dRh3MeU&s',
                                           'width': '280',
                                           'height': '180'}],
             'metatags': [{'producer': 'Skia/PDF m100 Google Docs '
                                       'Renderer',
                           'title': 'Consolidated Work Notice '
                                               '(Sample)'}],
             'cse_image': [{'src': 'x-raw-image:///05e109018a35aaa98d1eb143f2ddd651d892774a8ef4b282dfbdaa099d31b9e2'}]},
 'mime': 'application/pdf',
 'fileFormat': 'PDF/Adobe Acrobat'},
"""

from googleapiclient.discovery import build

import os
import re
import subprocess

# The maximum number of words allowed in a Google search query is 32,
# including search terms and operators.
# Stop words are not included in this limit. 
large_query_default = 'CHIP OR SSI OR WIC OR TANF OR TAFDC OR SNAP OR housing OR assistance OR benefit OR application OR form OR "apply for"'
query_default = 'WIC OR TANF OR SNAP'

# Location of the list of likely benefit forms.
likely_forms = './data/likely_benefit_forms.txt'

# Split a path into three parts: directory, basename, and extension.
def path_pieces(path):
    (extless_path, extension) = os.path.splitext(path)
    basename = os.path.basename(extless_path)
    directory = os.path.dirname(extless_path)
    return {'basename': basename,
            'directory': directory,
            'extension': extension}

# Return the filetype: 'pdf', 'docx', or nothing.
def filetype(filename):
    """Identifies the file type (e.g., docx, pdf) of a file.

    Args:
      filename: A full pathname.

    Returns:
      'pdf', 'docx', or nothing (indicating the file is neither PDF nor DOCX).
    """
    filetype = subprocess.run(["file", filename], capture_output=True)
    if re.search('PDF document', str(filetype.stdout)):
        return('pdf')
    elif re.search('Microsoft Word', str(filetype.stdout)):
        return('docx')
    return


def rename_file_for_clarity(filename):
    if re.search('\.(?:docx|pdf)', filename):
        return
    if filetype(filename) == 'pdf':
        os.rename(filename, filename + '.pdf')
    elif filetype(filename) == 'docx':
        os.rename(filename, filename + '.docx')


def google_search(search_term, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    if 'items' in res:
      return res['items']
    else:
      return []


def generate_double_positive_search_query():
    """Returns a search query with only the most likely trigger words.

    Args:
      None.

    Returns:
      A query string that ORs the "++" search terms.
    """
    f = open('./data/search_terms.txt', 'r')
    lines = f.readlines()
    query = ''
    terms = []
    f.close()
    for line in lines:
        if line[0:2] == '++':
            term = line[2:].rstrip("\n")
            term = re.sub('\s*#.*', '', term)
            terms.append(term)
    # Consider "allinanchor:" and "allintext:".
    return(' OR '.join(terms))


def generate_positive_search_regex():
  f = open("./data/search_terms.txt", "r")
  lines = f.readlines()
  f.close()
  positive_string = ''
  for line in lines:
    if line[0] == '+':
      term = line[1:].rstrip("\n")
      term = re.sub('\s*#.*', '', term)
      positive_string += r'(?:(?:\b|_)' + term + r'(?:\b|_))|'
  positive_string = positive_string.rstrip('|')
  positive_re = re.compile(positive_string, re.IGNORECASE)
  return(positive_re)


def generate_negative_search_regex():
  f = open("./data/search_terms.txt", "r")
  lines = f.readlines()
  negative_string = ''
  for line in lines:
    if line[0] == '-':
      term = line[1:].rstrip("\n")
      negative_string += r'(?:(?:\b|_)' + term + r'(?:\b|_))|'
  negative_string = negative_string.rstrip('|')
  negative_re = re.compile(negative_string, re.IGNORECASE)
  return(negative_re)

