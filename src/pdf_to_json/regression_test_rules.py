""" Regression test rules for the PDF->CiviForm pipeline.

Each rule should output a number between 0.0 (worst) and 1.0 (best).

The name of every rule begins with "rule_". 

These are called by regression_test() in regression_test.py.
"""

import json
# "pip install scikit-learn" to install these.
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# When mapping questions from one program to another, this constant
# is used to ensure that the questions aren't too far away.
# The lower this constant, the more likely that a question close to
# the beginning of one program will be mapped to a question at the end
# of the other.
_INDEX_PENALTY_EXPONENT = 0.9

def score_missed_questions(num_json_questions, num_golden_questions):
    """ Score the number of missed questions.

    Let J be the number of questions in the JSON to be evaluated,
    and G the number of questions in the golden JSON.

    G must be greater than J.

    We want the score to be proportional to J/G, and inversely
    proportional to G-J. Our metric multiplies these two expressions:
    J / G(G-J).

    Args:
      num_json_questions: The number of questions in the evaluation JSON.
      num_golden_questions: The number of questions in the golden JSON.

    Returns:
      Float in [0.0, 1.0] indicating the fidelity of the JSON to be evaluated.
    """
    if num_json_questions >= num_golden_questions:
        logging.error(
            "score_missed_questions called with no missing questions")
    
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
    
    Args:
      num_json_questions: The number of questions in the evaluation JSON.
      num_golden_questions: The number of questions in the golden JSON.

    Returns:
      Float in [0.0, 1.0] indicating the fidelity of the JSON to be evaluated.
    """
    if num_json_questions < num_golden_questions:
        logging.error(
            "score_extra_questions called with no extra questions")
        
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
      Float in [0.0, 1.0] indicating similarity.
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
    """
    Args:
      json_golden_str: A JSON string of the golden program.
      json_eval_str: A JSON string of the program to be evaluated.

    Returns:
      Float in [0.0, 1.0] indicating the similarity of the question texts.
    """
    golden_questions = extract_questions(json.loads(json_golden_str))
    json_questions = extract_questions(json.loads(json_eval_str))
    # TODO(orwant): Implement this.
    return 0.5


def extract_question_texts(json_str):
    """ Given JSON, extract the most informative question text.
    
    Args:
      json_str: A JSON string of a program.

    Returns:
      A list of question (or description) strings.
    """
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


def generate_question_similarity_matrix(json_golden_str, json_eval_str):
    """ Generate the similarity matrix of questions in two programs.

    The similarity matrix has dimension N x M, where N is the number of
    questions with text in the golden program, and M the number of questions
    with text in the eval program. When the pipeline is operating
    perfectly, that matrix will be the identity matrix, and so the return
    value of this method will be 1.0.

    Args:
      json_golden_str: A JSON string of the golden program.
      json_eval_str: A JSON string of the program to be evaluated.

    Returns:
      A 2D matrix of the similarities between program questions.
    """
    # First, extract the question texts.
    questions_golden = extract_question_texts(json_golden_str)
    questions_eval = extract_question_texts(json_eval_str)

    if len(questions_golden) == 0 or len(questions_eval) == 0:
        return [[]]

    # Create a joint question corpus for TF-IDF calculations.
    # If we knew that the number of questions in each program was the same,
    # we wouldn't have to do this.
    questions_joint = questions_golden + questions_eval

    # Create the embedding, ignoring English stopwords.
    tfidf_vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_vectorizer.fit_transform(questions_joint)
    tfidf_matrix_golden = tfidf_vectorizer.transform(questions_golden)
    tfidf_matrix_eval= tfidf_vectorizer.transform(questions_eval)

    # Compute the similarity matrix.
    similarity_matrix = cosine_similarity(
        tfidf_matrix_golden, tfidf_matrix_eval)

    return similarity_matrix


def generate_question_mapping(json_golden_str, json_eval_str):
    """ Map the questions between programs using question texts.

    Args:
      json_golden_str: A JSON string of the golden program.
      json_eval_str: A JSON string of the program to be evaluated.

    Returns:
      Two arrays, one mapping questions from the golden to the eval,
      and the other mapping from eval to the golden.
    """

    similarity_matrix = generate_question_similarity_matrix(
        json_golden_str, json_eval_str)

    def index_penalty(index1, index2):
        return _INDEX_PENALTY_EXPONENT ** abs(index1 - index2)

    # First, loop by row to find the golden->eval mappings.
    # This gets a little complicated. Instead of always picking the question
    # with the highest similarity, we penalize based on distance in the array,
    # so that if there are two questions that seem similar based on wording,
    # we choose the one whose index is closest to the golden index.
    golden_to_eval = [None] * len(similarity_matrix)
    for golden_index in range(len(similarity_matrix)):
        best_index = -1
        best_value = 0
        for eval_index in range(len(similarity_matrix[0])):
            penalized_value = (index_penalty(golden_index, eval_index) *
                               similarity_matrix[golden_index][eval_index])
            if (best_value <= penalized_value):
                best_index = eval_index
                best_value = penalized_value
        golden_to_eval[golden_index] = best_index

    # Now, the converse: loop by column to find the eval->golden mappings.
    # These are not guaranteed to be symmetrical!
    eval_to_golden = [None] * len(similarity_matrix[0])
    for eval_index in range(len(similarity_matrix[0])):
        best_index = -1
        best_value = 0
        for golden_index in range(len(similarity_matrix)):
            penalized_value = (index_penalty(golden_index, eval_index) *
                               similarity_matrix[golden_index][eval_index])
            if (best_value <= penalized_value):
                best_index = eval_index
                best_value = penalized_value
        eval_to_golden[eval_index] = best_index

    return(golden_to_eval, eval_to_golden)

def rule_help_text_similarity(json_golden_str, json_eval_str):
    """ Compute the similarity of the help texts in two programs.

    This rule compares the help texts of two programs. Often the
    PDF->CiviForm pipeline will generate a different number of questions
    than the "golden" CiviForm -- and even generate a different number
    of questions from run to run.

    We therefore need a way to establish a mapping between the questions
    in the two programs. To do this, we create a TF-IDF embedding and use
    the highest values in the similarity matrix to establish that mapping.

    When the pipeline is not perfect, it may generate a different number
    of questions than the golden program. In that case the highest value
    of the appropriate column in the matrix is the closest question, and
    its magnitude indicates the similarity of the texts in those two
    questions.

    Args:
      json_golden_str: A JSON string of the golden program.
      json_eval_str: A JSON string of the program to be evaluated.

    Returns:
      Float in [0.0, 1.0] indicating the similarity of the question texts.
    """
    similarity_matrix = generate_question_similarity_matrix(
        json_golden_str, json_eval_str)

    # Average the highest scores.
    sum = 0.0
    for i in range(len(similarity_matrix)):
        highest = 0.0
        for j in range(len(similarity_matrix[0])):
            if similarity_matrix[i][j] > highest:
                highest = similarity_matrix[i][j]
        sum += highest

    return(sum / len(similarity_matrix))
