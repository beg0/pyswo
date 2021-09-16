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
""" Python class to represent decoded ITM packets """

import enum

MAX_PACKET_SIZE=5

class ItmTimeControl(enum.IntEnum):
    """ Values for Time Control (TC) field in ITM timestamp packets """
    ITC_SYNC = 0
    ITC_DELAYED_DATA = 1
    ITC_DELAYED_EVENT = 2
    ITC_DELAYED_DATA_EVENT = 3

class ItmGtsType(enum.IntEnum):
    """ Values for types of ITM Global Typestamp packets """
    IGTS_1 = 1
    IGTS_2 = 2
    IGTS_LOWER_BITS = 1
    IGTS_UPPER_BITS = 2

class ItmDwtCounterWrap(enum.IntFlag):
    """DWT Event counter packet payload bit assignments """
    IDCW_CYC = 0x20
    IDCW_FOLD = 0x10
    IDCW_LSU = 0x08
    IDCW_SLEEP = 0x04
    IDCW_EXE = 0x02
    IDCW_CPI = 0x01

class ItmDwtExceptionEvent(enum.IntEnum):
    """ Action taken by the processor when it enters, exits, or returns to an exception """
    IDEE_RSVD = 0
    IDEE_ENTER = 0x01
    IDEE_EXIT = 0x02
    IDEE_RETURN = 0x03

class ItmPacket():
    """ Base class for all ITM packets """

class ItmSourcePacket(ItmPacket):
    """ Base class for all ITM "source" packets, e.g. an Instrumentation packet or a Hardware
    source packet.

    Source packets have a header byte of 0bxxxxxxSS, where SS is not 0b00. They always have
    a payload of 1, 2 or 4 bytes.
    """

class ItmProtocolPacket(ItmPacket):
    """ Base class for all ITM "protocol" packets

    Protocol packets have a header byte of 0bxxxxxxSS, where SS is 0b00 but header byte is not
    0b00000000.
    """

class ItmDwtEventCounterPacket(ItmSourcePacket):
    """ ITM DWT Event Counter packet

    The DWT unit generates an Event counter packet when a counter value wraps round to zero, that
    is, when:

        - a countup, or incrementing, counter overflows
        - a countdown, or decrementing, counter underflows.

    The packet has a single payload byte, containing a set of bits that show which counters have
    wrapped. Typically a single counter wraps, however the DWT can generate this packet with
    multiple payload bits set to 1, indicating a combination of counters wrapping to zero.
    """
    def __init__(self, event):
        self.event = ItmDwtCounterWrap(event)

    def __repr__(self):
        return "<ItmDwtEventCounterPacket(event=%r)>" % (self.event)

class ItmExceptionEventPacket(ItmSourcePacket):
    """ ITM Exception Event packet

    Issued by DWT when the core enter an exception state
    """
    def __init__(self, exception_number, event_type):
        self.exception_number = exception_number
        self.event_type = ItmDwtExceptionEvent(event_type)

    def __repr__(self):
        return "<ItmExceptionEventPacket(exception_number=%d, event_type=%r>" % \
            (self.exception_number, self.event_type)

class ItmPcSamplePacket(ItmSourcePacket):
    """ ITM PC Sampling packet

    Issued by DWT at regular interval
    """
    def __init__(self, program_counter, sleep=False):
        self.program_counter = program_counter
        self.sleep = sleep
    def __repr__(self):
        if self.sleep:
            return "<ItmPcSamplePacket(sleep=%r)>" % self.sleep
        # otherwise it's a packet with a PC
        return "<ItmPcSamplePacket(program_counter=0x%.8x)>" % self.program_counter

class ItmDwtPcPacket(ItmSourcePacket):
    """ ITM DWT Data trace PC value packet

    Issued by DWT when a comparator in DWT is trigger
    """

    def __init__(self, comp, program_counter):
        self.comp = comp
        self.program_counter = program_counter

    def __repr__(self):
        return "<ItmDataTracePcValue(comp=%d, PC=%.8x)>" % (self.comp, self.program_counter)

class ItmDwtAddrOffsetPacket(ItmSourcePacket):
    """ ITM DWT Data trace address offset packet

    Issued by DWT when a comparator in DWT is trigger
    """

    def __init__(self, comp, address_offset):
        self.comp = comp
        self.address_offset = address_offset

    def __repr__(self):
        return "<ItmDwtAddrOffsetPacket(comp=%d, addr_offset=%.8x)>" % \
            (self.comp, self.address_offset)

class ItmDwtDataValuePacket(ItmSourcePacket):
    """ ITM DWT Data value packet

    Issued by DWT when a comparator in DWT is trigger
    """

    def __init__(self, comp, value, is_write, size):
        self.comp = comp
        self.value = value
        self.size = size
        self.is_write = is_write

    def __repr__(self):
        return "<ItmDwtDataValuePacket(comp=%d, value=%x (%d bits), write=%s)>" % \
            (self.comp, self.value, self.size*8, self.is_write)

class ItmSwPacket(ItmSourcePacket):
    """ ITM Software packet

    Packet used for instrumentation. Issued when software write the corresponding stimulis port
    """
    def __init__(self, channel, payload):
        self.channel = channel
        self.payload = payload

    def __repr__(self):
        return "<ItmSwPacket(channel=%d, payload=%r)>" % (self.channel, self.payload)

class ItmOverflowPacket(ItmProtocolPacket):
    """ ITM Overflow packet

    The ITM outputs an Overflow packet if:

        - software writes to a Stimulus Port register when the stimulus port output buffer is full
        - the DWT attempts to generate a Hardware source packet when the DWT output buffer is full
        - the Local timestamp counter overflows.
    """

class ItmLocalTsPacket(ItmProtocolPacket):
    """ ITM Local Timestamp packet

    A Local timestamp packet encodes timestamp information, for generic control and
    synchronization, based on a timestamp counter in the ITM. To reduce the trace bandwidth:

        - The local timestamping scheme uses delta timestamps, meaning each local timestamp value
          gives the interval since the generation of the previous Local timestamp packet.
        - The Local timestamp packet length, 1-5 bytes, depends on the required timestamp value.

    Whenever the ITM outputs a Local timestamp packet, it clears its timestamp counter to zero.
    """
    def __init__(self, timestamp, time_control):
        self.timestamp = timestamp
        self.time_control = ItmTimeControl(time_control)

    def __repr__(self):
        return "<ItmLocalTsPacket(timestamp=%d, time_control=%s (0x%x))" % \
            (self.timestamp, self.time_control.name, self.time_control.value)

class ItmGlobalTsPacket(ItmProtocolPacket):
    """ ITM Global Timestamp packet

    If an implementation supports global timestamping, the ITM generates Global timestamp packets
    based on a global timestamp clock. A full global timestamp is a 48-bit value. This means
    global timestamping uses two timestamp packet formats:

        - GTS1 packets transmit bits [25:0] of the timestamp value, and the ITM compresses these
          by not transmitting high-order bytes that are unchanged from the previous timestamp value.
        - GTS2 packets transmit bits [47:26] of the timestamp values, and when a GTS2 packet is
          required the ITM always transmits it in full, as a five-byte packet.
    """
    def __init__(self, gts_type, timestamp, wrap=None, clock_change=None):
        self.gts_type=ItmGtsType(gts_type)
        self.timestamp=timestamp
        self.wrap=wrap
        self.clock_change=clock_change

        assert (self.gts_type == ItmGtsType.IGTS_1 and self.wrap is not None) or \
            ((self.gts_type == ItmGtsType.IGTS_2 and self.wrap is None)), \
            "wrap can only be set with GTS type 1"

        assert (self.gts_type == ItmGtsType.IGTS_1 and self.clock_change is not None) or \
            ((self.gts_type == ItmGtsType.IGTS_2 and self.clock_change is None)), \
                "clock_change can only be set with GTS type 1"

    def __repr__(self):
        if self.gts_type == ItmGtsType.IGTS_1:
            return "<ItmGlobalTsPacket(type=%s, timestamp=%d, wrap=%r, clock_change=%r)" % \
                (self.gts_type, self.timestamp, self.wrap, self.clock_change)

        return "<ItmGlobalTsPacket(type=%s, timestamp=%d)" % (self.gts_type, self.timestamp)

class ItmExtensionPacket(ItmProtocolPacket):
    """ ITM Extension packet

    An Extension packet provides additional information about the identified source.
    """
    def __init__(self, source, extension_info):
        self.source = source
        self.extension_info = extension_info

    def __repr__(self):
        return "<ItmExtensionPacket(source=%r, payload=%r)>" % (self.source, self.extension_info)
