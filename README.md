# PYSWO - Python Library to read ARM Single Wire Output data

PYSWO is a python module to read and understand the binary stream output by a Single Wire Output pin on a ARM Cortex.

PYSWO is not a tool to configure SWO on ARM target or to acquires SWO data. You need some hardware and an adapter for
that such as openocd, a BlackMagicProbe, JLink tool. A simple UART converter may also do the job is SWO is configured
to output UART formatter frames.

This library handles ITM and DWT packets format according to section "Debug ITM and DWT packet protocol" in
 "ARM v7-M Architecture Reference Manual"

## Usage

PYSWO is dedicated to work with an ITM stream of bytes. However it does not implement specific logic to read such a
stream. This allows the user of the library to read the ITM stream from whatever source he/she wants.

The API is deadly simple. A single object of class `ItmDecoder` shall be instantiate. This decoder shall be feeded with
source data - e.g. binary data from ITM stream. Decoded ITM packets are retrieve from the decoder with an iterator API.

There is two ways to feed the decoder:

1. Call the `ItmDecoder.feed()` of the decoder each time there is new ITM data to provide to the decoder. Argument is
   a single `bytes` object representing new ITM binaries data.

2. provide a `feeder()` function at instantiation of the `ItmDecoder` object.
   This function takes no parameter and shall returns a `bytes` object representing new ITM binaries data.

If, at some point, the decoder is not feed the iterator will stop the iteration.
If later new data are coming in ITM stream, the iterator can be call again.
