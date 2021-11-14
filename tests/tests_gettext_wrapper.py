""" Tests of module pyswo.utils.gettext_wrapper """
import unittest

from pyswo.utils.gettext_wrapper import gettext, ngettext


class tests_gettext_wrapper(unittest.TestCase):
    def test_basic(self):
        """ very basic tests, mainly to check module can be imported"""
        self.assertEqual(gettext("a text"), "a text")
        self.assertEqual(ngettext("singular text", "plural text", 1), "singular text")
        self.assertEqual(ngettext("singular text", "plural text", 2), "plural text")
