#!env python
# This file is part of PYSWO
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
""" Simple SWO log trace viewer """
import os
import sys
import argparse
import re
import functools

from pyswo.itmdecoder import ItmDecoder
from pyswo.itmpackets import ItmSwPacket
from pyswo.utils.feeder import add_all_feeders_to_argparse

PRINT_ALL = "all"
PRINT_MATCH_LINE = "matched-line"
PRINT_MATCH_PATTERN = "matched-pattern"
PRINT_MATCH_GROUPS = "matched-groups"
PRINT_MATCH_PATTERN_AND_GROUPS = "matched-pattern-groups"

def encoding(what):
    """ Check encoding is valid - argparse compatible """
    try:
        b'\x00'.decode(what)
    except LookupError as exception:
        raise argparse.ArgumentTypeError("Not a valid encoding %r" % what) from exception
    return what

def compiled_pcre(what):
    """ Check regexp is valid - argparse compatible """
    try:
        return re.compile(what)
    except re.error as exception:
        raise argparse.ArgumentTypeError(str(exception))

def  cmp_range(range1, range2):
    """ Compare 2 ranges"""
    # First sort with start position
    if range1[0] != range2[0]:
        return range1[0] - range2[0]

    # Then sort by (inverted) range (e.g. larger ranges comes first)
    return range2[1] - range1[1]

class App():
    """ Main class for application """

    @staticmethod
    def build_argparse():
        """ Generate the Command Line argument parser using argparse """

        default_output_stream = sys.stdout
        if hasattr(default_output_stream, 'buffer'):
            default_output_stream = default_output_stream.buffer

        cli_parser = argparse.ArgumentParser(description=__doc__)
        cli_parser.add_argument("-c", "--swo-channel",
                                type=int,
                                nargs='*',
                                default=[0],
                                help="SWO channel to display")
        cli_parser.add_argument("-o", "--output-file",
                                type=argparse.FileType('wb'),
                                default=default_output_stream,
                                help="Save console to file")

        pattern_matching_group = cli_parser.add_argument_group("pattern matching")
        pattern_matching_group.add_argument("--encoding",
                                            type=encoding,
                                            default='latin',
                                            help="String encoding (only used for regexp lookup")
        pattern_matching_group.add_argument("-p", "--print",
                                            choices=[
                                                PRINT_ALL,
                                                PRINT_MATCH_LINE,
                                                PRINT_MATCH_PATTERN,
                                                PRINT_MATCH_GROUPS,
                                                PRINT_MATCH_PATTERN_AND_GROUPS,
                                            ],
                                            default=PRINT_ALL,
                                            help="control what to display")
        pattern_matching_group.add_argument("--match-group-separator",
                                            default=";",
                                            help="separator to use when --print is one of %s" % \
                                                ', '.join([
                                                    PRINT_MATCH_PATTERN,
                                                    PRINT_MATCH_GROUPS,
                                                    PRINT_MATCH_PATTERN_AND_GROUPS
                                                ]))
        pattern_matching_group.add_argument("-r", "--regexp",
                                            type=compiled_pcre,
                                            action='append',
                                            help="text (as PCRE) to look for")

        add_all_feeders_to_argparse(cli_parser)

        return cli_parser

    def __init__(self):
        cli_parser = App.build_argparse()

        self.config = cli_parser.parse_args()

        try:
            swo_feeder = self.config.feeder_generator.create()
        except AttributeError:
            cli_parser.error("No SWO input stream defined")

        self.decoder = ItmDecoder(swo_feeder)

        self.patterns = self.config.regexp or []

        self.log_line = b''


    def run(self):
        """ Application main loop """

        self.log_line = b''

        try:
            print("Start reading SWO stream. Press CTRL-C to exit")
            while True:
                for itm_packet in self.decoder:
                    if isinstance(itm_packet, ItmSwPacket) and \
                        itm_packet.channel in self.config.swo_channel:
                        self.handle_sw_packet(itm_packet)
        except KeyboardInterrupt:
            print("Capture interrupted by user")
        except EOFError:
            print("End of SWO stream")
        return 0

    def handle_sw_packet(self, itm_packet):
        """ Manage SWO packet ItmSwPacket """
        config = self.config # Alias for lazy people

        if config.print == PRINT_ALL:
            config.output_file.write(itm_packet.payload)

        self.log_line += itm_packet.payload
        if itm_packet.payload == b'\n':
            log_line_str = self.log_line.decode(config.encoding)
            matches = []
            for pattern in self.patterns:
                matches += list(pattern.finditer(log_line_str))

            if matches:
                if config.print == PRINT_MATCH_LINE:
                    config.output_file.write(self.log_line)
                elif config.print in [
                                      PRINT_MATCH_PATTERN,
                                      PRINT_MATCH_GROUPS,
                                      PRINT_MATCH_PATTERN_AND_GROUPS
                                      ]:

                    include_group0 = config.print in [
                                                      PRINT_MATCH_PATTERN,
                                                      PRINT_MATCH_PATTERN_AND_GROUPS
                                                      ]
                    include_other_groups = config.print in [
                                                            PRINT_MATCH_GROUPS,
                                                            PRINT_MATCH_PATTERN_AND_GROUPS
                                                           ]
                    flat_groups = []
                    for compare_result in matches:
                        if include_group0:
                            flat_groups.append((compare_result.regs[0], compare_result.group(0)))
                        if include_other_groups:
                            for pos, txt in zip(compare_result.regs[1:], compare_result.groups()):
                                flat_groups.append((pos, txt))

                    flat_groups.sort(key=functools.cmp_to_key(
                        lambda pos_txt1, pos_txt2: cmp_range(pos_txt1[0], pos_txt2[0])))

                    flat_captured_txt = [pos_txt[1] for pos_txt in flat_groups]
                    output_str = config.match_group_separator.join(flat_captured_txt) + os.linesep
                    config.output_file.write(output_str.encode(config.encoding))

            self.log_line = b''

            # Flush on new line
            config.output_file.flush()

sys.exit(App().run())
