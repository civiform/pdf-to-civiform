""" Display word frequencies of a JSON corpus. """

import argparse
import generate_word_counts_lib as gwc


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='generate_word_counts',
        description='Counts the occurrences of words in a JSON corpus')

    parser.add_argument('-c', '--corpus', default = '../corpus')
    parser.add_argument('-t', '--threshold', default = 1)

    return(parser.parse_args())


def display_dictionary(dictionary, threshold):
    """ Displays the terms and their occurrences in descending order.

    Args:
      dictionary: A dictionary mapping words to their occurrences.
      threshold: An integer, below which occurrences will be ignored.
    """
    sorted_dict = dict(sorted(dictionary.items(),
                              key=lambda item: item[1], reverse=True))
    for (word, count) in sorted_dict.items():
        if count <= threshold:
            break
        print(f"{word}: {count}")


def main():
    args = parse_arguments()
    dictionary = gwc.compute_frequencies(args.corpus)
    display_dictionary(dictionary, args.threshold)


if __name__ == '__main__':
    main()
