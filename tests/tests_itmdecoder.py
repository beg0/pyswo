""" Tests of module pyswo.itmdecoder """
# This file is part of PYSWO
import unittest

from pyswo.itmdecoder import ItmDecoder
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
    ItmGtsType,
    ItmDwtExceptionEvent
    )


INPUT_PACKETS = [
    (b'\x70', ItmOverflowPacket()),
    (b'\x30', ItmLocalTsPacket(3, 0)),
    (b'\xA0\x44', ItmLocalTsPacket(0x44, 2)),
    (b'\xB0\xC4\x22', ItmLocalTsPacket(0x1144, 3)),
    (b'\x80\xC4\xA2\x11', ItmLocalTsPacket(0x45144, 0)),
    (b'\x90\xC4\xA2\x91\x77', ItmLocalTsPacket(0xEE45144, 1)),
    (b'\xB4\xC4\xA2\x91\x77', ItmGlobalTsPacket(ItmGtsType.IGTS_1,
                                                0x2E45144,
                                                wrap=True, clock_change=True)),
    (b'\xB4\xC4\xA2\x91\x57', ItmGlobalTsPacket(ItmGtsType.IGTS_1,
                                                0x2E45144,
                                                wrap=True, clock_change=False)),
    (b'\xB4\xC4\xA2\x91\x37', ItmGlobalTsPacket(ItmGtsType.IGTS_1,
                                                0x2E45144,
                                                wrap=False, clock_change=True)),
    (b'\xB4\xC4\xA2\x91\x17', ItmGlobalTsPacket(ItmGtsType.IGTS_1,
                                                0x2E45144,
                                                wrap=False, clock_change=False)),
    (b'\x94\xC4\xA2\x91\x77', ItmGlobalTsPacket(ItmGtsType.IGTS_2,
                                                0xEE45144,
                                                wrap=None, clock_change=None)),
    (b'\x78', ItmExtensionPacket(source=False, extension_info=7)),
    (b'\x3C', ItmExtensionPacket(source=True, extension_info=3)),
    (b'\xF8\x32', ItmExtensionPacket(source=False, extension_info=0x197)),
    (b'\xBC\xB2\x1A', ItmExtensionPacket(source=True, extension_info=0x6993)),
    (b'\x13abcd', ItmSwPacket(2, b'abcd')),
    (b'\x1Aab', ItmSwPacket(3, b'ab')),
    (b'\x05\x0a', ItmDwtEventCounterPacket(0x0a)),
    (b'\x0E\x05\x21', ItmExceptionEventPacket(0x105, ItmDwtExceptionEvent.IDEE_EXIT)),
    (b'\x15\x00', ItmPcSamplePacket(None, True)),
    (b'\x17\xAA\xBB\xCC\xDD', ItmPcSamplePacket(0xDDCCBBAA, False)),
    (b'\x57\xAA\xBB\xCC\xDD', ItmDwtPcPacket(comp=1, program_counter=0xdDCCBBAA)),
    (b'\x6F\xAB\xCD\xEF\x01', ItmDwtAddrOffsetPacket(comp=2, address_offset=0x01EFCDAB)),
    (b'\xA6\xAB\xCD', ItmDwtDataValuePacket(comp=2, value=0xCDAB, is_write=False, size=2)),
    (b'\xAD\xAB', ItmDwtDataValuePacket(comp=2, value=0xAB, is_write=True,  size=1)),
]

class FeederClassFromString():
    """ feeder for ItmDecoder which data are added manually

    Only useful for test purpose

    This allows to check that ItmDecoder can accept object from such a class as argument
    """
    def __init__(self, chunk_size=0, data=bytes()):
        self.data = data
        self.chunk_size = chunk_size

    def append_data(self, new_data):
        """ add new data to feeder """
        self.data += new_data

    def clear(self):
        """ remove all previously appended data """
        self.data = bytes()

    def set_data(self, data):
        """ replace feeder data with new ones """
        self.data = data

    def __call__(self):
        if self.data:
            if self.chunk_size:
                ret = self.data[:self.chunk_size]
                self.data=self.data[self.chunk_size:]
            else:
                ret = self.data
                self.data = bytes()
            return ret

        raise EOFError


#Pylint is wrong, this is not a constant. It is used in feeder_func_from_global()
#pylint: disable=invalid-name
feeder_func_data = bytes()

def feeder_func_from_global():
    """ feeder for ItmDecoder which data came from a global variable

    Only useful for test purpose

    This allows to check that ItmDecoder can accept functions as argument
    """

    # pylint: disable=global-statement
    # Yes global statement is bad, but here, it's only for test purpose
    global feeder_func_data

    if feeder_func_data:
        ret = feeder_func_data
        feeder_func_data = bytes()
        return ret
    raise EOFError


class tests_itmdecoder(unittest.TestCase):
    """ Tests for class pyswo.itmdecoder.ItmDecoder """

    def test_xtor(self):
        """ test constructor arguments """

        # Feeder as a callable class is ok
        ItmDecoder(feeder=FeederClassFromString())

        # Feeder as a function is ok
        ItmDecoder(feeder=feeder_func_from_global)

        # Feeder as a lambda is ok
        ItmDecoder(feeder=lambda: b'foo')

        # No feeder is ok
        ItmDecoder(feeder=None)

        # feeder can't be a scalar
        with self.assertRaises(AssertionError):
            ItmDecoder(feeder=True)

        # feeder can't be a list
        with self.assertRaises(AssertionError):
            ItmDecoder(feeder=[])

    def test_feed(self):
        """ test ItmDecoder.feed() function """
        decoder = ItmDecoder()

        # Ok to append 0-len bytes stream
        decoder.feed(bytes())

        # Ok to append bytes
        decoder.feed(b'1234')

        # Can't append anything else
        with self.assertRaises(AssertionError):
            ItmDecoder(feeder=1)

    def test_iter(self):
        """ test ItmDecoder.__iter__() function """

        feeder = FeederClassFromString()

        decoder = ItmDecoder(feeder=feeder)

        feeder.append_data(b'1')

        # First iter does not raise EOFError
        iter_decoder = iter(decoder)

        #data was consumed by call to iter
        self.assertFalse(feeder.data)

        # data was consumed data from feeder
        self.assertEqual(iter_decoder.byte_stream, b'1')

        # 2nd iter raise EOFError as no more data
        with self.assertRaises(EOFError):
            iter(decoder)

    def test_decoder_unitary(self):
        """ test decoding of every single ITM packets"""

        feeder = FeederClassFromString()

        decoder = ItmDecoder(feeder=feeder)

        for pkt_desc in INPUT_PACKETS:

            input_stream = pkt_desc[0]
            expected_pkt = pkt_desc[1]
            feeder.append_data(input_stream)

            iter_decoder = iter(decoder)
            decoded_pkt = next(iter_decoder)

            # Hack: use repr() to compare 2 packets...
            #  this may not be very accurate
            self.assertEqual(repr(decoded_pkt), repr(expected_pkt))

            # Be sure only one packet is decoded
            with self.assertRaises(StopIteration):
                next(iter_decoder)
