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
""" Various pre-defined feeder to feed ItmDecoder"""
from importlib import import_module

#expose some interesting objects to caller
from ._feeder_argparse import add_default_feeder_to_argparse, AbstractFeederGenerator

def _import_feeders():
    """ Load all (supported) modules in this package declaring a feeder for ItmDecoder"""

    def looks_like_feeder(what):
        """ heuristic to tell if an object is a Feeder class """
        return type(what) == type and \
               callable(what) and \
               hasattr(what, 'add_to_argparser')

    feeder_classes = []
    for module_name in [
            "tcpclient",
            "file"]:
        try:
            module = import_module("." + module_name, __package__)
            for attr_name in dir(module):
                if attr_name.startswith('__'):
                    continue
                attr = getattr(module, attr_name)
                if looks_like_feeder(attr):
                    feeder_classes.append(attr)
        except ImportError:
            pass # ignore import error and assume user does not have the required dependencies
    return feeder_classes

FEEDER_CLASSES = _import_feeders()

def add_all_feeders_to_argparse(parser, default_feeder_generator=None):
    """
    Add command line arguments parsing to a argparse.ArgumentParser
    to generate any supported feeder
    """

    if default_feeder_generator:
        add_default_feeder_to_argparse(parser, default_feeder_generator)

    for feeder_class in FEEDER_CLASSES:
        method = getattr(feeder_class, "add_to_argparser")
        if method:
            assert callable(method) # Also assume staticmethod
            method(parser)
