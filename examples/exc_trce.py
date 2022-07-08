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
""" Simple Cortex-M Exceptions & IRQ monitor using SWO.

The name comes from the bit to enable in DWT_CTRL register: DWT_CTRL_EXCTRCENA
for EXCeption TRaCes ENAble"""
import sys
import argparse

from pyswo.itmdecoder import TimeTrackingItmDecoder
from pyswo.itmpackets import ItmDwtExceptionEvent, ItmExceptionEventPacket
from pyswo.utils.feeder import add_all_feeders_to_argparse

# Max number of exceptions in Cortex M. ARM constraint
IRQ_COUNT = 128

# Max number of exceptions that are not IRQ (e.g. internal to Cortex core)
NVIC_USER_IRQ_OFFSET = 16

# IRQ number that identify the 'thread mode', aka the main loop aka the reset handler
THREAD_EXCEPTION_ID = 0

DEFAULT_EXCEPTIONS_NAME = [
    "Reset_Handler",
    "NMI",
    "HardFault",
    "MemManage",
    "BusFault",
    "UsageFault",
    "SecureFault",
    "rsvd",
    "rsvd",
    "rsvd",
    "SVC",
    "DebugMon",
    "rsvd",
    "PendSV",
    "SysTick",
]

# pylint: disable=too-many-instance-attributes
class ExceptionEventTracker():
    """ Track occurrence of a specific Exception (identified by it's exception_number)"""
    def __init__(self, exception_number, name="", print_event=False):
        self.exception_number = exception_number
        self.name = name
        self.print_event = print_event
        self.last_enter_date = None
        self.last_preempted_date = None
        self.count = 0
        self.preemptor = [ 0 for irq_num in range(IRQ_COUNT) ]
        self.preempted_duration = 0
        self.duration = 0

    def add_preemptor(self, itm_packet):
        """ Tracks when a new exception, defined in itm_packet, preempts this one """
        preemptor_exception_number = itm_packet.exception_number
        self.preemptor[ preemptor_exception_number] += 1
        try:
            self.last_preempted_date = itm_packet.timestamp
        except AttributeError:
            pass


    def enter(self, itm_packet):
        """ Tracks when an exception is triggered """
        self.count += 1
        date = ""
        try:
            self.last_enter_date = itm_packet.timestamp
            date = " @ %u" % itm_packet.timestamp
        except AttributeError:
            pass

        if self.print_event:
            print("→ %u%s" % (itm_packet.exception_number - NVIC_USER_IRQ_OFFSET, date))

    def exit(self, itm_packet):
        """ Tracks when the firmware exits this IRQ handler """
        date = ""
        try:
            exit_date = itm_packet.timestamp
            date = " @ %u" % itm_packet.timestamp

            if self.last_enter_date is not None:
                self.duration += exit_date - self.last_enter_date

            self.last_enter_date = None
        except AttributeError:
            pass

        if self.print_event:
            print("← %u%s" % (itm_packet.exception_number - NVIC_USER_IRQ_OFFSET, date))

    def return_from_exception(self, itm_packet):
        """ Tracks when the firmware returns to this IRQ handler
            after exiting another IRQ handler """

        date = ""
        try:
            return_date = itm_packet.timestamp
            date = " @ %u" % itm_packet.timestamp

            if self.last_preempted_date is not None:
                self.preempted_duration += return_date - self.last_preempted_date
            self.last_preempted_date = None

        except AttributeError:
            pass

        if self.print_event:
            print("↓ %u%s" % (itm_packet.exception_number - NVIC_USER_IRQ_OFFSET, date))

    def __str__(self) -> str:
        name = self.name
        total_preemptions = sum(self.preemptor)
        average_duration = self.duration / self.count if self.count else 0

        if total_preemptions:
            average_preempted_duration = self.preempted_duration / total_preemptions
        else:
            average_preempted_duration = 0


        return " %-16s %-4u %-5u %-12u %-14u %-12.2f %-12.2f" % (
            name,
            self.exception_number - NVIC_USER_IRQ_OFFSET,
            self.count,
            self.duration,
            total_preemptions,
            average_duration,
            average_preempted_duration)

class App():
    """ Main class for application """

    @staticmethod
    def build_argparse():
        """ Generate the Command Line argument parser using argparse """

        cli_parser = argparse.ArgumentParser(description=__doc__)

        cli_parser.add_argument("-t", "--timeline",
                                action='store_true',
                                help="Print IRQ event each time they occurs")
        add_all_feeders_to_argparse(cli_parser)
        return cli_parser

    def __init__(self):
        cli_parser = App.build_argparse()

        self.config = cli_parser.parse_args()

        try:
            swo_feeder = self.config.feeder_generator.create()
        except AttributeError:
            cli_parser.error("No SWO input stream defined")


        def get_irq_name(irq_num):
            if irq_num < len(DEFAULT_EXCEPTIONS_NAME):
                return DEFAULT_EXCEPTIONS_NAME[irq_num]
            return ""

        self.decoder = TimeTrackingItmDecoder(swo_feeder)
        self.last_irq_num = None
        self.exception_trackers = [
            ExceptionEventTracker(irq_num,
                                name=get_irq_name(irq_num),
                                print_event=self.config.timeline) \
                for irq_num in range(IRQ_COUNT)
        ]

    def run(self):
        """ Application main loop """

        # The main program is treated as exception 0
        reset_handler_tracker = self.exception_trackers[THREAD_EXCEPTION_ID]

        timestamp = None
        try:
            print("Start reading SWO stream. Press CTRL-C to exit")
            while True:
                for itm_packet in self.decoder:
                    timestamp = getattr(itm_packet, 'timestamp')
                    if timestamp is not None and  reset_handler_tracker.count == 0:
                        reset_handler_tracker.last_enter_date = timestamp
                        reset_handler_tracker.count += 1

                    if isinstance(itm_packet, ItmExceptionEventPacket):
                        self.handle_exception_event_packet(itm_packet)
        except KeyboardInterrupt:
            print("\nCapture interrupted by user")
        except EOFError:
            print("End of SWO stream")
        finally:

            if timestamp and reset_handler_tracker.count > 0:
                total_duration = timestamp - reset_handler_tracker.last_enter_date
                reset_handler_tracker.duration += total_duration
                reset_handler_tracker.last_enter_date = None


        if timestamp is None:
            print("Warning: Can't find timestamp in packets. Is ITM_TCR_TSENA set? " +
                  "Timestamp info not available.")

        print("")
        self.print_summary()
        return 0

    def print_summary(self):
        """ Print summary of exceptions"""

        fired_irq = [ irq for irq in self.exception_trackers \
            if irq.count > 0 and irq.exception_number != THREAD_EXCEPTION_ID ]

        if fired_irq:
            print(" name             " +
                  "nIRQ " +
                  "count " +
                  "tot_duration " +
                  "tot_preemption " +
                  "avg_duration " +
                  "avg_preemption")
            for irq in self.exception_trackers:
                if irq.count:
                    print(str(irq))
        else:
            print("No exception found. Is DWT_CTRL_EXCTRCENA set?")

    def handle_exception_event_packet(self, itm_packet):
        """ Manage SWO packet ItmExceptionEventPacket """

        cur_irq_num = itm_packet.exception_number
        cur_tracker = self.exception_trackers[cur_irq_num]
        if itm_packet.event_type == ItmDwtExceptionEvent.IDEE_ENTER:
            if self.last_irq_num is not None:
                self.exception_trackers[self.last_irq_num].add_preemptor(itm_packet)
            self.last_irq_num = cur_irq_num
            cur_tracker.enter(itm_packet)

        elif itm_packet.event_type == ItmDwtExceptionEvent.IDEE_EXIT:
            cur_tracker.exit(itm_packet)
            self.last_irq_num = None
        elif itm_packet.event_type == ItmDwtExceptionEvent.IDEE_RETURN:
            cur_tracker.return_from_exception(itm_packet)
            self.last_irq_num = cur_irq_num
        else:
            raise AssertionError("Unexpected IRQ event type %r" % itm_packet.event_tyê)


sys.exit(App().run())
