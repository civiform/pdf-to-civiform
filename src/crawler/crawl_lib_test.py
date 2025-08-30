import crawl_lib
import re
import unittest

class TestPositiveRegex(unittest.TestCase):
    def setUp(self):
        self.regex = crawl_lib.generate_positive_search_regex()

    def test_regex(self):
        self.assertTrue(re.search(self.regex, 'WIC'))
        self.assertTrue(re.search(self.regex, 'SNAP-Application.pdf'))
        self.assertTrue(re.search(self.regex,
                                  'Instructions for TANF_Application.pdf'))
        self.assertFalse(re.search(self.regex, 'SANDWICH REQUEST'))

if __name__ == '__main__':
    unittest.main()

