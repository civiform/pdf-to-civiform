""" Helper functions for generate_word_counts. """

import json
import logging
import os
import re


def find_best_text(question):
    """ Find the best field from the JSON, and return its text.

    The "best field" is (somewhat arbitrarily) chosen to be:
      question['config']['questionText']['translations']['en_US'] if exists,
    or
      question['config']['description'] otherwise.

    Args:
      question: A JSON question object.

    Returns:
      A string of words containing the "best text" from the question.
    """
    if 'config' in question:
        if ('questionText' in question['config'] and
            'translations' in question['config']['questionText'] and
            'en_US' in question['config']['questionText']['translations']):
            return question['config']['questionText']['translations']['en_US']
    elif 'description' in question['config']:
        return question['config']['description']
    else:
        logging.warning(f"No text found in question.")
        return ''


def extract_question_words(questions):
    """ Given a list of questions, creates dictionary with their counts.

    Args:
      questions: A list of JSON question objects.

    Returns:
      A dictionary mapping words to their occurrences.
    """
    dictionary = {}
    for question in questions:
        text = find_best_text(question).lower()

        # Remove instances of $this, HTTP URLs, and non-letters.
        text = text.replace("$this's", '')
        text = text.replace('$this', '')
        http_re = re.compile('https?:\\S+')
        text = http_re.sub('', text)
        lower_re = re.compile('[^a-z ]')
        text = lower_re.sub('', text)

        words = text.split()

        for word in words:
            if word in dictionary:
                dictionary[word] += 1
            else:
                dictionary[word] = 1

    return dictionary

def display_dictionary(dictionary, threshold):
    """ Displays the terms and their occurrences in descending order.

    Args:
      dictionary: A dictionary mapping words to their occurrences.
      threshold: An integer, below which occurrences will be ignored.
    """
    sorted_dict_desc = dict(sorted(dictionary.items(),
                                   key=lambda item: item[1], reverse=True))
    for (word, count) in sorted_dict_desc.items():
        if count <= threshold:
            break
        print(f"{word}: {count}")


def merge_dictionaries(dict1, dict2):
    for (word, count) in dict1.items():
        if word in dict2:
            dict1[word] += dict2[word]
    for (word, count) in dict2.items():
        if word not in dict1:
            dict1[word] = dict2[word]
    return dict1


def compute_frequencies(dictionary, directory):
    """ Build a dictionary of term occurrences in a corpus.

    Recursively descend through the corpus, looking for JSON.
    
    Args:
      dictionary: A dict mapping terms to counts.
      directory: The relative filepath to a JSON corpus.
    """
    entries = os.listdir(directory)

    for entry in entries:
        if os.path.isdir(os.path.join(directory, entry)):
            dictionary = compute_frequencies(
                dictionary, directory + '/' + entry)
        elif os.path.isfile(os.path.join(directory, entry)):

            # The "len(entry) - 5" is to ensure that we don't evaluate
            # filenames ending in .json~, .json-bak, etc.
            if entry.find('.json') == len(entry) - 5:
                with open(os.path.join(directory, entry), 'r') as file:
                    json_string = file.read()

                    # The pipeine output can wrap the JSON in
                    # "```json ... ```" so if that's the case, we remove that.
                    if json_string[0:7] == '```json':
                        json_string = json_string[8:]
                    if json_string[-3:] == '```':
                        json_string = json_string[0:-3]

                    try:
                        json_obj = json.loads(json_string)
                    except json.decoder.JSONDecodeError:
                        logging.warning(
                            f"JSON decode error for {entry}; skipping.")
                        continue

                    if 'questions' in json_obj:
                        dictionary = merge_dictionaries(
                            dictionary,
                            extract_question_words(json_obj['questions']))
                    else:
                        logging.warning(f"No questions found for {entry}")

    return dictionary


