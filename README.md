# PYSWO - Python Library to read ARM Single Wire Output data

PYSWO is a python module to read and understand the binary stream output by a Single Wire Output pin on a ARM Cortex.

PYSWO is not a tool to configure SWO on ARM target or to acquires SWO data. You need some hardware and an adapter for
that such as openocd, a BlackMagicProbe, JLink tool. A simple UART converter may also do the job is SWO is configured
to output UART formatter frames.

This library handles ITM and DWT packets format according to section "Debug ITM and DWT packet protocol" in
 "ARM v7-M Architecture Reference Manual"
