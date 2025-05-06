import json
import logging
import regression_test_rules as rules
import unittest


class TestNumberOfQuestions(unittest.TestCase):

    def test_symmetry(self):
        self.assertEqual(
            rules.score_missed_questions(2, 5),
            rules.score_extra_questions(8, 5))
        self.assertEqual(
            rules.score_missed_questions(90, 100),
            rules.score_extra_questions(110, 100))
                            

class TestExtractQuestions(unittest.TestCase):

    def setUp(self):
        testfile = 'testdata/goldens/charlotte_leadsafe.json'
        # Charlotte must be using Windows, which annoyingly includes a
        # BOM (Byte Order Mark) when exporting JSON. That's why we need
        # to use encoding = 'utf-8-sig' below.
        try:
            with open(testfile, 'r', encoding = 'utf-8-sig') as f:
                self.json = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: File not found: {testfile}")
        except json.JSONDecodeError:
            logging.error(f"Error: Invalid JSON format in file: {testfile}")

    def test_extract_question(self):
        questions = rules.extract_questions(self.json)
        self.assertEqual(len(questions), 24)

        
if __name__ == '__main__':
    unittest.main()
