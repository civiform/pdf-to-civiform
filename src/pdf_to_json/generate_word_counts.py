""" Display word frequencies of a JSON corpus. """

import argparse
import json
import logging
import os
import re


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='generate_word_counts',
        description='Counts the occurrences of words in a JSON corpus')

    parser.add_argument('-c', '--corpus', default = '../corpus')
    parser.add_argument('-t', '--threshold', default = 1)

    return(parser.parse_args())


def find_best_text(question):
    """ Find the best field from the JSON, and return its text.

    The "best field" is (somewhat arbitrarily) chosen to be:
      question['config']['questionText']['translations']['en_US'] if exists,
    and
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


def add_question_words_to_dict(questions, dictionary):
    """ Given a list of questions, builds up dictionary with their counts.

    Args:
      questions: A list of JSON question objects.
      dictionary: A dictionary mapping words to their occurrences.

    Mutates dictionary.
    """
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


def compute_frequencies(directory):
    """ Build a dictionary of term occurrences in a corpus.

    Recursively descend through the corpus, looking for JSON.
    
    Args:
      directory: The relative filepath to a JSON corpus.
    """
    entries = os.listdir(directory)
    dictionary = {}
    for entry in entries:
        if os.path.isdir(os.path.join(directory, entry)):
            compute_frequencies(directory + '/' + entry)
        elif os.path.isfile(os.path.join(directory, entry)):

            # The "len(entry) - 5" is to ensure that we don't evaluate
            # filenames ending in .json~.
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
                        add_question_words_to_dict(json_obj['questions'],
                                                   dictionary)
                    else:
                        logging.warning(f"No questions found for {entry}")
    return dictionary


def main():
    args = parse_arguments()
    dictionary = compute_frequencies(args.corpus)
    display_dictionary(dictionary, args.threshold)


if __name__ == '__main__':
    main()
