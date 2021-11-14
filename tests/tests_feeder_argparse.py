""" Tests of module pyswo.utils.feeder._feeder_argparse """
from argparse import FileType
import unittest

from pyswo.utils.feeder._feeder_argparse import *

class tests_feeder_argparse(unittest.TestCase):
    class DefaultFeeder():
        pass

    class AnotherFeeder():
        pass

    class DefaultFeederGenerator(AbstractFeederGenerator):
        def create(self):
            return tests_feeder_argparse.DefaultFeeder()

    class AnotherFeederGenerator(AbstractFeederGenerator):
        def create(self):
            return tests_feeder_argparse.AnotherFeeder()

    def test_bad_inputs(self):
        parser = argparse.ArgumentParser()

        with self.assertRaises(TypeError):
            add_default_feeder_to_argparse(parser, None)

        with self.assertRaises(AssertionError):
            add_default_feeder_to_argparse(parser, FileType)

        # with self.assertRaises(AssertionError):
        #     add_default_feeder_to_argparse(parser, AbstractFeederGenerator)


    def test_use_default_when_no_other_feeder(self):
        parser = argparse.ArgumentParser()
        add_default_feeder_to_argparse(parser, tests_feeder_argparse.DefaultFeederGenerator)

        config = parser.parse_args([])
        self.assertTrue(hasattr(config, 'feeder_generator'))
        self.assertIsInstance(config.feeder_generator, tests_feeder_argparse.DefaultFeederGenerator)
        self.assertTrue(config.feeder_generator.optional)

    def test_use_default_when_other_feeder(self):
        parser = argparse.ArgumentParser()
        add_default_feeder_to_argparse(parser, tests_feeder_argparse.DefaultFeederGenerator)
        parser.add_argument("--another-feeder",
            action=CreateFeederAction,
            feeder_generator=tests_feeder_argparse.AnotherFeederGenerator,
            nargs=0)

        config = parser.parse_args([])
        self.assertTrue(hasattr(config, 'feeder_generator'))
        self.assertIsInstance(config.feeder_generator, tests_feeder_argparse.DefaultFeederGenerator)
        self.assertTrue(config.feeder_generator.optional)

    def test_do_not_use_default_when_other_feeder(self):
        parser = argparse.ArgumentParser()
        add_default_feeder_to_argparse(parser, tests_feeder_argparse.DefaultFeederGenerator)
        parser.add_argument("--another-feeder",
            action=CreateFeederAction,
            feeder_generator=tests_feeder_argparse.AnotherFeederGenerator,
            nargs=0)

        config = parser.parse_args(["--another-feeder"])
        self.assertIsInstance(config.feeder_generator, tests_feeder_argparse.AnotherFeederGenerator)
        self.assertFalse(config.feeder_generator.optional)

