""" Regression test rules for the PDF->CiviForm pipeline.

Each rule should output a number between 0.0 (worst) and 1.0 (best).

The name of every rule begins with "rule_". 

These are called by regression_test() in regression_test.py.
"""

import json

def rule_json_length(json_golden, json):
    """ A placeholder rule that compares JSON lengths. Don't use it! """
    if len(json_golden) > len(json):
        return len(json) / len(json_golden)
    else:
        return len(json_golden) / len(json)


def score_missed_questions(num_json_questions, num_golden_questions):
    """ Score the number of missed questions. """
    return (num_json_questions /
            (num_golden_questions *
             (num_golden_questions - num_json_questions)))


def score_extra_questions(num_json_questions, num_golden_questions):
    """ Score the number of extra questions. """
    return ((num_json_questions - 2 * num_golden_questions) /
            (num_golden_questions *
             (num_golden_questions - num_json_questions)))


def rule_number_of_questions(json_golden, json):
    """ Compares the number of questions in the JSONs. """
    missed_question_penalty = 1.0
    extraneous_question_penalty = 0.1
    # We count occurrences of "questionText" to determine the number
    # of questions in the JSON.
    num_golden_questions = json_golden.count('questionText')
    num_json_questions = json.count('questionText')

    if num_golden_questions == num_json_questions:
        score = 1.0
    elif num_golden_questions > num_json_questions:
        # Missed some questions. We want the score to be proportional to
        # both the percentage and the absolute number of questions.
        score = (missed_question_penalty *
                 score_missed_questions(num_json_questions,
                                        num_golden_questions))
    else:
        # Extraneous questions. We want the score to be symmetric with
        # the above case, but allow for a different penalty.
        score = (extraneous_question_penalty *
                 score_extra_questions(num_json_questions,
                                       num_golden_questions))
    return score


def same_question(question1, question2):
    """ Likelihood that two JSON question objects ask the same question.

    Args:
      question1: JSON of the first question.
      question2: JSON of the second question.

    Returns:
      Float between 0.0 and 1.0 indicating similarity.
    """
    # TODO(orwant): Implement this.
    return 0.5


def extract_questions(json_obj):
    """ Extract the question block from a JSON string.

    Args:
      json_obj: CiviForm JSON (perhaps an entire CiviForm, perhaps a subset)

    Returns:
      A list of JSON objects, one per question.
    """
    questions = json_obj['questions']
    return questions


def rule_correct_field_types(json_golden, json):
    golden_questions = extract_questions(json_golden)
    json_questions = extract_questions(json)
    # TODO(orwant): Implement this.
    return 0.5
