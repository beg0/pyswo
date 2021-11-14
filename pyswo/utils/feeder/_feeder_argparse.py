# This file is part of PYSWO
# vim: set fileencoding=utf-8 :
#
# MIT License
#
# Copyright (c) 2021 Cédric CARRÉE <beg0@free.fr>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
""" Helpers to add command line arguments parsing for feeder to argparse.ArgumentParser """

import argparse
from abc import ABC, abstractmethod
from pyswo.utils.gettext_wrapper import gettext as _

#pylint: disable=too-few-public-methods
class AbstractFeederGenerator(ABC):
    """ Abstract class for FeederGenerator.

    FeederGenerator are to be used in argparse.ArgumentParser.add_argument(), with parameter
    'feeder_generator', when action=CreateFeederAction
    Optionally, it can be used with add_default_feeder_to_argparse()
    """
    def __init__(self, config, option_string, optional=False):
        self.config = config
        self.option_string = option_string
        self.optional = optional

    @abstractmethod
    def create(self):
        """ Instantiate a feeder, based on config """

def add_default_feeder_to_argparse(parser, feeder_generator):
    """ Generate the default feeder_generator to be used if none is specified on command line"""
    assert issubclass(feeder_generator, AbstractFeederGenerator)
    parser.set_defaults(feeder_generator=feeder_generator(None, '', optional=True))

#pylint: disable=too-few-public-methods
class CreateFeederAction(argparse.Action):
    """ Argparse action used to generate the 'feeder_generator'

    This is the main mechanism to allow a program using argparse to support new SWO stream """
    def __init__(self, option_strings, dest, **kwargs):
        if 'feeder_generator' not in kwargs:
            raise KeyError("Missing parameter 'feeder_generator'")

        assert issubclass(kwargs['feeder_generator'], AbstractFeederGenerator) and \
            kwargs['feeder_generator'] is not AbstractFeederGenerator

        self.feeder_generator = kwargs['feeder_generator']
        del kwargs['feeder_generator']

        super(CreateFeederAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        feeder_generator = getattr(namespace, 'feeder_generator', None)

        if feeder_generator and not feeder_generator.optional:
            msg = _("%s not allowed. A stream was already selected with %s")
            raise argparse.ArgumentError(self,
                                         msg % (option_string, feeder_generator.option_string))

        # Create the feeder
        setattr(namespace,
                'feeder_generator',
                self.feeder_generator(namespace, option_string, False))

        # Be sue the dest attribute is set (even if nargs is 0)
        setattr(namespace, self.dest, values if self.nargs != 0 else True)

# class TwelveFeederGenerator(AbstractFeederGenerator):
#     def create(self):
#         return 12

# parser = argparse.ArgumentParser(exit_on_error=False)
# parser.add_argument('--another-stream', action=CreateFeederAction,
#             feeder_generator=TcpFeederGenerator)
# add_default_feeder_to_argparse(parser, TwelveFeederGenerator)
# args = parser.parse_args('--another-stream'.split())
