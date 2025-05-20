""" Regression test rules for the PDF->CiviForm pipeline.

Each rule should output a number between 0.0 (worst) and 1.0 (best).

The name of every rule begins with "rule_". 

These are called by regression_test() in regression_test.py.
"""

import json
# "pip install scikit-learn" to install these.
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def rule_json_length(json_golden_str, json_eval_str):
    """ A placeholder rule that compares JSON lengths. Don't use it! """
    if len(json_golden_str) > len(json_eval_str):
        return len(json_eval_str) / len(json_golden_str)
    else:
        return len(json_golden_str) / len(json_eval_str)


def score_missed_questions(num_json_questions, num_golden_questions):
    """ Score the number of missed questions.

    Let J be the number of questions in the JSON to be evaluated,
    and G the number of questions in the golden JSON.

    We want the score to be proportional to J/G, and inversely
    proportional to G-J. Our metric multiplies these two expressions:
    J / G(G-J)
    """
    return (num_json_questions /
            (num_golden_questions *
             (num_golden_questions - num_json_questions)))


def score_extra_questions(num_json_questions, num_golden_questions):
    """ Score the number of extra questions.

    We want the score for the number of extra questions to be symmetrical
    to the score for missed questions. (Weights are applied later to
    punish missed questions more than extra questions.)

    That symmetry comes from substituting 2G - J for J
    into the score for missed questions. Factoring reduces that to:
    (J-2G) / G(G-J)
    """
    return ((num_json_questions - 2 * num_golden_questions) /
            (num_golden_questions *
             (num_golden_questions - num_json_questions)))


def rule_number_of_questions(json_golden_str, json_eval_str):
    """ Compares the number of questions in the JSONs.

    Args:
      json_golden_str: A JSON string of the golden CiviForm. 
      json_eval_str: A JSON string of the CiviForm to be evaluated.

    Returns:
      Float in [0.0, 1.0] indicating the fidelity of the JSON to be evaluated.
    """
    missed_question_penalty = 1.0
    extraneous_question_penalty = 0.1

    # We count occurrences of "questionText" to determine the number
    # of questions in the JSON.
    num_golden_questions = json_golden_str.count('questionText')
    num_json_questions = json_eval_str.count('questionText')

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



def rule_correct_field_types(json_golden_str, json_eval_str):
    golden_questions = extract_questions(json.loads(json_golden_str))
    json_questions = extract_questions(json.loads(json_eval_str))
    # TODO(orwant): Implement this.
    return 0.5


def extract_question_texts(json_str):
    questions = extract_questions(json.loads(json_str))
    result = []
    for question in questions:
        if 'config' in question:
            if ('questionText' in question['config'] and
                'translations' in question['config']['questionText'] and
                'en_US' in question['config']['questionText']['translations']):
                result.append(
                    question['config']['questionText']
                    ['translations']['en_US'])
            elif 'description' in question['config']:
                result.append(question['config']['description'])
    return result

def rule_help_text_similarity(json_golden_str, json_eval_str):
    # First, extract the question texts.
    questions_golden = extract_question_texts(json_golden_str)
    questions_eval = extract_question_texts(json_eval_str)

    if len(questions_golden) == 0 or len(questions_eval) == 0:
        return 0.0

    questions_joint = questions_golden + questions_eval

    tfidf_vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_vectorizer.fit_transform(questions_joint)
    tfidf_matrix_golden = tfidf_vectorizer.transform(questions_golden)
    tfidf_matrix_eval= tfidf_vectorizer.transform(questions_eval)

    # Compute the similarity matrix.
    similarity_matrix = cosine_similarity(
        tfidf_matrix_golden, tfidf_matrix_eval)

    # Average the highest scores.
    sum = 0.0
    for i in range(len(similarity_matrix)):
        highest = 0.0
        for j in range(len(similarity_matrix[0])):
            if similarity_matrix[i][j] > highest:
                highest = similarity_matrix[i][j]
        sum += highest

    return(sum / len(similarity_matrix))
