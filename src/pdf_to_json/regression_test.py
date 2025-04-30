""" Regression test for the PDF->CiviForm pipeline.
"""

import argparse
import glob
import llm_lib as llm
import logging
import os
from pathlib import Path


def parse_arguments():
    """ Parse regression test arguments.

    Returns:
      An argparse argument structure.
    """
    parser = argparse.ArgumentParser(
        prog='regression_test',
        description='Calculate quality improvement of PDF->CiviForm pipeline')

    parser.add_argument('-d', '--directory',
                        default = 'testdata/goldens')
    parser.add_argument('-m', '--model',
                        default = 'gemini-2.0-flash')

    return(parser.parse_args())


def calculate_score(json_golden, json):
    """ Calculate the fidelity of the LLM-generated JSON to the golden JSON.

    Args:
      json_golden: the known-good JSON, as a string.
      json: the JSON to be evaluated, as a string.

    Returns:
      A number from 0.0 to 1.0 indicating fidelity of the JSON to the golden.
    """
    # A silly placeholder metric: compare JSON lengths.
    if len(json_golden) > len(json):
        return len(json) / len(json_golden)
    else:
        return len(json_golden) / len(json)


def regression_test(llm_client, directory):
    """ Evaluate all of the PDF/JSON pairs in a directory.

    Args:
      llm_client: An initialized LLM object.
      directory: The name of the directory containing golden PDF/JSON pairs.

    Returns:
      A dict mapping the PDF filepaths to their regression scores.
    """
    pdfs = glob.glob(directory + '/*.pdf')
    jsons = glob.glob(directory + '/*.json')
    scores = {}
    for pdf in pdfs:
        (root, _) = os.path.splitext(pdf)
        if root + '.json' in jsons:
            pdf_filepath = Path(pdf)
            pdf_string = pdf_filepath.read_bytes()
            json_filepath = Path(root + '.json')
            json_string = json_filepath.read_bytes()
            json = llm.process_pdf_text_with_llm(
                llm_client, args.model, pdf_string,
                'pdf_civiform_regression_test', '/tmp')[0]
            scores[root] = calculate_score(json_string, json)
        else:
            logging.warning(f"No JSON found for {pdf}")
    return scores


def display_scores(scores):
    """ Print the regression test results.

    Args:
      scores: A dict mapping each PDF pathname to its regression score.
    """
    for pdf, score in scores.items():
        basename = os.path.basename(pdf)
        print(f"{basename}: {score}")


if __name__ == '__main__':
    args = parse_arguments()
    llm_client = llm.initialize_gemini_model(model_name = args.model)
    scores = regression_test(llm_client, args.directory)
    display_scores(scores)
        
