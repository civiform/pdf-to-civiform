import json
import logging
import regression_test_rules as rules
import unittest

def read_file_into_string(path):
    try:
        # Windows includes a BOM (Byte Order Mark) when exporting JSON.
        # That's why we need to use encoding = 'utf-8-sig' below.
        with open(path, 'r', encoding = 'utf-8-sig') as f:
            json_str = f.read()
    except FileNotFoundError:
        logging.error(f"Error: File not found: {path}")
    return json_str

def read_file_into_obj(path):
    try:
        with open(path, 'r', encoding = 'utf-8-sig') as f:
            json_obj = json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: File not found: {path}")
    except json.JSONDecodeError:
        logging.error(f"Error: Invalid JSON format in file: {path}")
    return json_obj


class TestRuleNumberOfQuestions(unittest.TestCase):

    def test_symmetry(self):
        self.assertEqual(
            rules.score_missed_questions(2, 5),
            rules.score_extra_questions(8, 5))
        self.assertEqual(
            rules.score_missed_questions(90, 100),
            rules.score_extra_questions(110, 100))
                            

class TestExtractQuestions(unittest.TestCase):

    def setUp(self):
        self.json = read_file_into_obj(
            'testdata/goldens/charlotte_leadsafe.json')

    def test_extract_question(self):
        questions = rules.extract_questions(self.json)
        self.assertEqual(len(questions), 24)


class TestRuleHelpTextSimilarity(unittest.TestCase):

    def setUp(self):
        self.homerepair_str = read_file_into_string(
            'testdata/goldens/seattle_home_repair_loan.json')
        self.homewise_str = read_file_into_string(
            'testdata/goldens/seattle_homewise.json')
        self.business_str = read_file_into_string(
            'testdata/goldens/charlotte_business.json')
        self.leadsafe_str = read_file_into_string(
            'testdata/goldens/charlotte_leadsafe.json')
        self.leadsafe_tweaked_str = read_file_into_string(
            'testdata/programs/charlotte_leadsafe_question_tweak.json')

    def test_self_similarity(self):
        self.assertGreater(
            rules.rule_help_text_similarity(self.homerepair_str,
                                            self.homerepair_str), 0.99)
    def test_high_similarity(self):
        self.assertGreater(
            rules.rule_help_text_similarity(self.leadsafe_str,
                                            self.leadsafe_tweaked_str), 0.8)

    def test_medium_similarity(self):
        self.assertGreater(
            rules.rule_help_text_similarity(self.homerepair_str,
                                            self.homewise_str), 0.5)
    def test_low_similarity(self):
        self.assertLess(
            rules.rule_help_text_similarity(self.homewise_str,
                                            self.business_str), 0.5)


class TestGenerateQuestionMapping(unittest.TestCase):

    def setUp(self):
        self.homerepair_str = read_file_into_string(
            'testdata/goldens/seattle_home_repair_loan.json')
        self.homewise_str = read_file_into_string(
            'testdata/goldens/seattle_homewise.json')
        self.tree_canopy_str = read_file_into_string(
            'testdata/goldens/charlotte_tree_canopy.json')
        self.leadsafe_str = read_file_into_string(
            'testdata/goldens/charlotte_leadsafe.json')

    def test_self_similarity(self):
        (golden_to_eval, eval_to_golden) = (
            rules.generate_question_mapping(self.homerepair_str,
                                            self.homerepair_str))
        self.assertEqual(golden_to_eval[0], 0)
        self.assertEqual(golden_to_eval[15], 15)

if __name__ == '__main__':
    unittest.main()
