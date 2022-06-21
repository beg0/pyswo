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
import sys
import argparse

from pyswo.itmdecoder import ItmDecoder
from pyswo.itmpackets import ItmSwPacket
from pyswo.utils.feeder import add_all_feeders_to_argparse


DEFAULT_OUTPUT_STREAM = sys.stdout
if hasattr(DEFAULT_OUTPUT_STREAM, 'buffer'):
    DEFAULT_OUTPUT_STREAM = DEFAULT_OUTPUT_STREAM.buffer


cli_parser = argparse.ArgumentParser()
cli_parser.add_argument("-c", "--swo-channel",
                        type=int,
                        nargs='*',
                        default=[0],
                        help="SWO channel to display")
cli_parser.add_argument("-o", "--output-file",
                        type=argparse.FileType('wb'),
                        default=DEFAULT_OUTPUT_STREAM,
                        help="Save console to file")
add_all_feeders_to_argparse(cli_parser)

config = cli_parser.parse_args()

try:
    swo_feeder = config.feeder_generator.create()
except AttributeError:
    cli_parser.error("No SWO input stream defined")

decoder = ItmDecoder(swo_feeder)

while True:
    for itm_packet in decoder:
        if isinstance(itm_packet, ItmSwPacket) and itm_packet.channel in config.swo_channel:
            config.output_file.write(itm_packet.payload)
