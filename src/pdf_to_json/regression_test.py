""" Regression test for the PDF->CiviForm pipeline.

See https://github.com/civiform/civiform/issues/9975:
"Automated test case(s) for PDF form extraction and understanding"
"""

import argparse
import glob
import llm_lib as llm
import logging
import os
from pathlib import Path
import regression_test_rules as rules

logging.basicConfig(level=logging.INFO)

# Weights will be normalized so that they sum to 1.0.
# Rules can be turned off by assigning them a weight of 0.0.
RULE_WEIGHTS = {'rule_json_length': 0.0,
                'rule_number_of_questions': 1.0,
                'rule_correct_field_types': 0.5,
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
    
def calculate_score(json_golden, json):
    """ Calculate the fidelity of the LLM-generated JSON to the golden JSON.

    Args:
      json_golden: the known-good JSON, as bytes.
      json: the JSON to be evaluated, as bytes.

    Returns:
      A number from 0.0 to 1.0 indicating fidelity of the JSON to the golden.
    """
    score = 0
    json_golden_str = str(json_golden)
    json_str = str(json)
    normalize_weights(RULE_WEIGHTS)
    for (rule, weight) in RULE_WEIGHTS.items():
        if weight == 0.0:
            continue
        logging.info(f"\tChecking {rule} with weight {weight}")
        eval_string = 'rules.' + rule + '(json_golden_str, json_str)'
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
        if root + '.json' in jsons:
            pdf_filepath = Path(pdf)
            logging.info('Evaluating', pdf_filepath)
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
        
