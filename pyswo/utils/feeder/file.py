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
""" Reading ITM data from plain file"""

from argparse import FileType
from pyswo.utils.gettext_wrapper import gettext as _
from ._feeder_argparse import AbstractFeederGenerator, CreateFeederAction

#pylint: disable=too-few-public-methods
class FileFeederGenerator(AbstractFeederGenerator):
    """ Feeder generator to create a FileFeeder feeder"""
    def create(self):
        return FileFeeder(self.config.input_file, self.config.file_read_size)


class FileFeeder:
    """ A SWO feeder that read ITM data from a plain file """
    def __init__(self, input_file, chunk_size=-1):
        self.file = input_file
        self.chunk_size = chunk_size

    def __call__(self):
        """ Read ITM stream from plain file """
        data =  self.file.read(self.chunk_size)
        if not data:
            raise EOFError()
        return data

    @staticmethod
    def add_to_argparser(parser):
        """
        Add command line arguments parsing to a argparse.ArgumentParser
        to generate File Feeder
        """
        group = parser.add_argument_group(_("plain file input"))
        group.add_argument("--file",
                           type=FileType("rb"),
                           dest='input_file',
                           help=_("Read SWO stream from a plain file"),
                           action=CreateFeederAction,
                           feeder_generator=FileFeederGenerator)

        group.add_argument("--file-read-size",
                           type=int,
                           dest='file_read_size',
                           default=-1,
                           help=_("Number of bytes to read in file at a time. " +
                           "Set to -1 to read as much data as possible at a time."))
