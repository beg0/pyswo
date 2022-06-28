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
""" Display if device is sleeping or running """
import sys
from argparse import ArgumentParser
from pyswo.itmdecoder import ItmDecoder
from pyswo.itmpackets import ItmPcSamplePacket
from pyswo.utils.feeder import add_all_feeders_to_argparse

def main():
    """ Program entry point """
    parser = ArgumentParser(description=__doc__)
    add_all_feeders_to_argparse(parser)

    config = parser.parse_args()


    swo_feeder_generator = getattr(config, 'feeder_generator', None)
    if not swo_feeder_generator:
        parser.error('No SWO stream configured')
    swo_feeder = swo_feeder_generator.create()

    itm_decoder = ItmDecoder(feeder=swo_feeder)

    sleep_counter = 0
    total_pc_sample = 0
    try:
        print("Start reading SWO stream. Press CTRL-C to exit")

        while True:
            for pkt in itm_decoder:
                if isinstance(pkt, ItmPcSamplePacket):
                    sys.stdout.write("\r")
                    total_pc_sample += 1
                    if pkt.sleep:
                        sleep_counter += 1
                        sys.stdout.write("\rSleep")
                    else:
                        sys.stdout.write("\rRun  ")

                    run_counter = total_pc_sample - sleep_counter
                    run_percent = run_counter*100.0/total_pc_sample
                    sleep_percent = sleep_counter*100.0/total_pc_sample
                    sys.stdout.write(" (R: %.2f %%, S: %.2f %%)" % (run_percent, sleep_percent))
                    sys.stdout.flush()

    except KeyboardInterrupt:
        print("Capture interrupted by user")
    except EOFError:
        print("End of SWO stream")



main()
