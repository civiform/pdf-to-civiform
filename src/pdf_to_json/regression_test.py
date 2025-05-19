""" Regression test for the PDF->CiviForm pipeline.

See https://github.com/civiform/civiform/issues/9975:
"Automated test case(s) for PDF form extraction and understanding"
"""

import argparse
import glob
import json
import llm_lib as llm
import logging
import os
from pathlib import Path
import regression_test_rules as rules
import subprocess
import sys

logging.basicConfig(level=logging.INFO)

# Weights will be normalized so that they sum to 1.0.
# Rules can be turned off by assigning them a weight of 0.0.
RULE_WEIGHTS = {'rule_json_length': 0.0,
                'rule_number_of_questions': 0.2,
                'rule_correct_field_types': 0.3,
                'rule_help_text_similarity': 0.5,
                }

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


def normalize_weights(rule_weights):
    """ Ensure that weights sum to 1.0.

    Mutates the input.

    Args:
      rule_weights: a dict mapping names of rules to floating point weights.
    """
    sum = 0.0
    for (rule, weight) in rule_weights.items():
        sum += weight

    for (rule, weight) in rule_weights.items():
        rule_weights[rule] = weight / sum
    
def calculate_score(json_golden_str, json_eval_str):
    """ Calculate the fidelity of the LLM-generated JSON to the golden JSON.

    Args:
      json_golden_str: the known-good JSON, as a string.
      json_eval_str: the JSON to be evaluated, as a string.

    Returns:
      A number from 0.0 to 1.0 indicating fidelity of the JSON to the golden.
    """
    score = 0
    normalize_weights(RULE_WEIGHTS)
    for (rule, weight) in RULE_WEIGHTS.items():
        if weight == 0.0:
            continue
        logging.info(f"\tChecking {rule} with weight {weight}")
        eval_string = 'rules.' + rule + '(json_golden_str, json_eval_str)'
        score += weight * eval(eval_string)
    return score


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

        # Ignore PDFs for which we don't have corresponding JSON.
        if root + '.json' in jsons:

            logging.info(f"Evaluating {root}")

            json_filepath = Path(root + '.json')
            json_golden_str = json_filepath.read_text()

            # Run the pipeline.
            subprocess.run(['python3', './pdf_to_civiform_gemini.py',
                            '--input-file', pdf])

            # TODO(orwant): Fix pdf_to_civiform_gemini to take
            # work directories & filenames as arguments. Otherwise,
            # we have to do this:
            work_dir = os.path.expanduser("~/pdf_to_civiform")
            default_upload_dir = os.path.join(work_dir, 'uploads')
            output_json_dir = os.path.join(work_dir, "output-json")

            # pdf_to_civiform_gemini should also provide a way to
            # return the filepath of the generated Civiform JSON. Instead,
            # we have to duplicate its logic here.
            # TODO(orwant): Fix this.
            filename = os.path.basename(pdf)
            base_name, _ = os.path.splitext(filename)
            base_name = base_name[:15]
            output_suffix = f"civiform-{args.model}"
            eval_filename = os.path.join(
                output_json_dir, f"{base_name}-{output_suffix}.json")

            pipeline_file = open(eval_filename, 'r')
            json_eval_str = pipeline_file.read()

            scores[root] = calculate_score(json_golden_str, json_eval_str)
            logging.info(f"Score for {root}: {scores[root]}")
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
        print(f"{basename}: ", "{:.2f}".format(score))


if __name__ == '__main__':
    args = parse_arguments()
    llm_client = llm.initialize_gemini_model(model_name = args.model)
    scores = regression_test(llm_client, args.directory)
    display_scores(scores)
        
