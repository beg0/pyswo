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
""" Decode ITM binary stream send over SWO """
from __future__ import print_function

from pyswo.itmpackets import (
    ItmSwPacket,
    ItmOverflowPacket,
    ItmLocalTsPacket,
    ItmGlobalTsPacket,
    ItmDwtEventCounterPacket,
    ItmExceptionEventPacket,
    ItmPcSamplePacket,
    ItmDwtPcPacket,
    ItmDwtAddrOffsetPacket,
    ItmDwtDataValuePacket,
    ItmExtensionPacket,
    )

HEADER_SIZE = 1
MAX_PACKET_SIZE = 5
WORD_SIZE = 4

class ItmDecoder():
    """ Parse stream of ITM binaries packets and output python object representing input packets"""
    def __init__(self, feeder=None):
        assert feeder is None or callable(feeder)

        self.feeder = feeder
        self.byte_stream = b''

        self.sync_probe = b'\x00\x00\x00\x00\x00\x00'

        self.synced = False


    def feed(self, data):
        """ Enqueue new data stream to the ItmDecoder

        It is mandatory to 'feed' the ItmDecoder manually if no feeder function was provided at
        decoder instanciation.

        Data are not decoded here.
        """
        assert isinstance(data, bytes)
        self.byte_stream += data

    def __iter__(self):
        if self.feeder:
            new_data = self.feeder()
            self.byte_stream += new_data
        return self

    def source_pkt_decoder(self):
        """ Parse an ITM "source" packet, e.g. not a protocol packet.

        Source packets are identified with the last 2 bits of header byte not null

        There is 2 type of source packet, depending on value of bit #2:
          - Case of Instrumentation packet (Software source, application)
            Format is 0bAAAAA0SS, SS not 0b00
            SS = size of payload
            AAAAA = Source Address

          - Case of Hardware packet (Hardware source, diagnostics)
            Format is 0bAAAAA1SS, SS not 0b00
            SS = size of payload
            AAAAA = Packet type discriminator ID
        """
        header = self.byte_stream[0]

        assert header & 0x03 != 0, "Not a ITM source packet"

        # This is a SW packet
        if header & 0x04 == 0:
            return self.sw_source_pkt_decoder()

        return self.hw_source_pkt_decoder()

    def sw_source_pkt_decoder(self):
        """ Extract ItmSwPacket() packet from ITM byte stream """

        header = self.byte_stream[0]

        assert header & 0x03 != 0, "Not a ITM source packet"
        assert header & 0x04 == 0, "Not a ITM SW source packet"

        payload_size = (0, 1, 2, 4)[header & 0x03]
        src_addr = header >> 3

        packet_size = HEADER_SIZE + payload_size

        # if we can't read the full payload,
        if packet_size > len(self.byte_stream):
            return (0, None)

        payload = self.byte_stream[HEADER_SIZE:payload_size+HEADER_SIZE]

        return (packet_size, ItmSwPacket(src_addr, payload))

    def hw_source_pkt_decoder(self):
        """ Extract ItmDwt*Packet() packet from ITM byte stream """

        header = self.byte_stream[0]

        assert header & 0x03 != 0, "Not a ITM source packet"
        assert header & 0x04 != 0, "Not a ITM HW source packet"

        payload_size = (0, 1, 2, 4)[header & 0x03]
        src_addr = header >> 3

        packet_size = HEADER_SIZE + payload_size

        # if we can't read the full payload,
        if packet_size > len(self.byte_stream):
            return (0, None)

        payload = self.byte_stream[HEADER_SIZE:payload_size+HEADER_SIZE]

        pkt = None
        if src_addr == 0:
            if packet_size != 1:
                self.synced = False
                return (1, None)
            event = payload[0] & 0x2F
            pkt = ItmDwtEventCounterPacket(event)
        elif src_addr == 1:
            if packet_size != 2:
                self.synced = False
                return (1, None)
            exception_number = (payload[1] & 1) << 8 | payload[0]
            event_type = (payload[1] >> 4) & 3
            pkt = ItmExceptionEventPacket(exception_number, event_type)

        # Periodic PC sample packets
        elif  src_addr == 2:
            program_counter = None
            sleep = False
            if len(payload) == 1:
                sleep = True
                program_counter = None
            else:
                sleep = False
                program_counter = int.from_bytes(payload, "little")
            pkt = ItmPcSamplePacket(program_counter, sleep)
        else:
            # Data trace packets
            comp = int((src_addr & 0x6) >> 1)
            value = int.from_bytes(payload, "little")
            data_trace_pkt_id = src_addr & 0x19

            if data_trace_pkt_id == 0x8:
                pkt = ItmDwtPcPacket(
                    comp=comp,
                    program_counter=value)
            if data_trace_pkt_id == 0x09:
                pkt = ItmDwtAddrOffsetPacket(
                    comp=comp,
                    address_offset=value)
            elif data_trace_pkt_id in (0x10, 0x11):
                pkt = ItmDwtDataValuePacket(comp=comp,
                                            value=value,
                                            is_write=bool(data_trace_pkt_id & 0x01),
                                            size=len(payload))
            else:
                # other are reserved values, skip
                self.synced = False
                return(1, None)

        assert pkt is not None, "Can't identify packet type with header %.8X" % header
        return (packet_size, pkt)

    @staticmethod
    def is_continuation_bit_set(byte):
        """ Tell if "Continuation bit" C is set """
        return bool(byte & 0x80)

    @staticmethod
    def get_payload_with_continuation_byte(byte_stream):
        """ extract a packet which has continuation bit"""

        encoded_value = 0
        payload_idx = 0
        while payload_idx < WORD_SIZE:
            # Enough data?
            if len(byte_stream) <= HEADER_SIZE + payload_idx:
                raise StopIteration

            next_byte = byte_stream[HEADER_SIZE + payload_idx]

            encoded_value |= (next_byte & 0x7F) << (payload_idx*7)
            payload_idx += 1

            if not ItmDecoder.is_continuation_bit_set(next_byte):
                break

        return (payload_idx, encoded_value)

    def protocol_pkt_decoder(self):
        """ Parse an ITM "protocol" packet, e.g. not a source packet.

        A protocol packet has a header byte of 0bxxxxxx00, but not 0b00000000.
        """

        header = self.byte_stream[0]

        assert header & 0x03 == 0 and header != 0, "Not a ITM protocol packet"

        # ITM overflow
        # Format is 0b01110000
        # No payload
        if header == 0x70:
            return (1, ItmOverflowPacket())

        # Local timestamp
        # Format is 0bCDDD0000, DDD not 0b000 or 0b111
        # D = Data, C = Continuation.
        # Payload 0 to 4 bytes
        if (header & 0x0F) == 0:
            return self.local_ts_pkt_decoder()

        # Global timestamp packet
        # Format is 0b10T10100
        # T = Global timestamp packet type.
        # Payload 1 to 4 bytes
        if (header & 0xDF) == 0x94:
            return self.global_ts_pkt_decoder()

        # Extension packets
        # Format is 0bCDDD1S00
        # S = Source, D = Data, C = Continuation.
        if header & 0b00001000:
            return self.extension_pkt_decoder()

        # If we are here, it means we have a reserved packet
        # 0b0xxx0100, 0bx1110000, 0b10x00100, 0b11xx0100,
        # Just ignore it
        self.synced = False
        return (1, None)

    def local_ts_pkt_decoder(self):
        """ Extract ItmLocalTsPacket() packet from ITM byte stream """
        header = self.byte_stream[0]

        # Local timestamp
        # Format is 0bCDDD0000, DDD not 0b000 or 0b111
        # D = Data, C = Continuation.
        # Payload 0 to 4 bytes

        assert header & 0x0F == 0, "Not a Local Timestamp packet"

        # Local timestamp packet format 1, two to five bytes
        # Format is 0b 1 1    TC1   TC0  0    0    0    0
        #           0b C TS6  TS5   TS4  TS3  TS2  TS1  TS0
        #           0b C TS13 TS12  TS11 TS10 TS9  TS8  TS7
        #           0b C TS20 TS19  TS18 TS17 TS16 TS15 TS14
        #           0b 0 TS27 TS26  TS25 TS24 TS23 TS21 TS20
        if ItmDecoder.is_continuation_bit_set(header):
            time_control = int((header&0x30) >> 4)
            timestamp = 0
            try:
                payload_size, timestamp = \
                    ItmDecoder.get_payload_with_continuation_byte(self.byte_stream)
            except StopIteration:
                # Not enough data
                return (0, None)

            pkt = ItmLocalTsPacket(timestamp=timestamp, time_control=time_control)

        # Local timestamp packet format 2, single byte
        # Format is 0b0TTT0000
        else:
            time_control = 0
            timestamp = (header >> 4) & 0x07
            payload_size = 0

            # check for reserved values 0 & 7
            # 0 would means it's part of a sync packet
            # 7 would means it's part of a overflow packet
            if timestamp in (0x00, 0x07):
                self.synced = False
                return (1, None)

            pkt = ItmLocalTsPacket(timestamp, time_control)
        return (HEADER_SIZE + payload_size, pkt)

    def global_ts_pkt_decoder(self):
        """ Extract ItmGlobalTsPacket() packet from ITM byte stream """

        header = self.byte_stream[0]

        # Global timestamp packet
        # Format is 0b10T10100
        # T = Global timestamp packet type.
        # Payload 1 to 4 bytes
        assert (header & 0xDF) == 0x94, "Not a Global Timestamp packet"

        wrap = None
        clock_change = None
        gts_type = 1 if header & 0x20 else 2

        try:
            payload_size, timestamp = \
                ItmDecoder.get_payload_with_continuation_byte(self.byte_stream)
        except StopIteration:
            # Not enough data
            return (0, None)

        if gts_type == 1:
            # For GTS type 1, bits 26 and 27 has special meanings
            clock_change = bool((timestamp & 0x4000000)>>26)
            wrap = bool((timestamp & 0x8000000)>>27)
            timestamp = timestamp & 0xC000000

        pkt = ItmGlobalTsPacket(gts_type, timestamp, wrap=wrap, clock_change=clock_change)
        return (HEADER_SIZE + payload_size, pkt)

    def extension_pkt_decoder(self):
        """ Extract ItmExtensionPacket() packet from ITM byte stream """

        header = self.byte_stream[0]

        # Extension packets
        # Format is 0bCDDD1S00
        # S = Source, D = Data, C = Continuation.
        assert header & 0b00001000, "Not an extension packet"

        first_ext_bits = (header & 0x70) >> 4
        source = bool(header & 0x04 >> 2)
        if not ItmDecoder.is_continuation_bit_set(header):
            extension_info = int(first_ext_bits)
            pkt = ItmExtensionPacket(source, extension_info)
            return (HEADER_SIZE, pkt)

        try:
            payload_size, last_ext_bits = \
                ItmDecoder.get_payload_with_continuation_byte(self.byte_stream)
        except StopIteration:
            # Not enough data
            return (0, None)

        extension_info = last_ext_bits<<3 | first_ext_bits
        pkt = ItmExtensionPacket(source, extension_info)
        return (HEADER_SIZE + payload_size, pkt)

    def __next__(self):

        while self.byte_stream:

            self.sync_probe = self.sync_probe[1:] + self.byte_stream[0:1]

            if self.sync_probe == b'\x00\x00\x00\x00\x00\x80':
                self.synced = True
                self.byte_stream = self.byte_stream[1:]
                continue

            #if not self.synced:
            #    self.byte_stream = self.byte_stream[1:]
            #    continue

            # Parse header, on one byte
            header = self.byte_stream[0]

            # SYNC packet
            if header == 0:
                self.synced = False
                self.byte_stream = self.byte_stream[1:]
                continue


            if header & 0x03:
                pkt_decoder = self.source_pkt_decoder
            else:
                pkt_decoder = self.protocol_pkt_decoder

            (consumed_len, packet) = pkt_decoder()

            if consumed_len > 0:
                self.byte_stream = self.byte_stream[consumed_len:]

            if packet is not None:
                return packet

            # If above decoder was not able to consume a single byte,
            # it means we don't have enough data to decode a new packet
            # stop iteration now
            if consumed_len == 0:
                raise StopIteration

        # Buffer empty
        raise StopIteration


if __name__ == "__main__":
    import socket
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.connect(("localhost", 50003))

    def itm_feeder():
        """ Read ITM stream from TCP connection """
        data = []
        while not data:
            data = listen_socket.recv(1024)
            if not data:
                print("reconnect")
                listen_socket.shutdown(socket.SHUT_RDWR)
                listen_socket.connect(("localhost", 50003))
        return data


    decoder = ItmDecoder(itm_feeder)

    while True:
        for itm_packet in decoder:
            print(itm_packet)
