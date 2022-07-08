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
""" Reading ITM data from TCP connection"""

import socket
import time
from argparse import ArgumentTypeError
from pyswo.utils.gettext_wrapper import gettext as _
from ._feeder_argparse import AbstractFeederGenerator, CreateFeederAction

def host_str_to_tuple(option_string):
    """ Convert a "<host>:port" string to a tuple suitable for socket.connect() """
    pair = option_string.rsplit(":", 1)
    if len(pair) != 2:
        msg = _("Can't parse %r as a host:port pair")
        raise ArgumentTypeError(msg % option_string)

    try:
        pair[1] = int(pair[1], 0)
    except ValueError as err:
        msg = _("Can't parse %r as a port in %s")
        raise ArgumentTypeError(msg % (pair[1], option_string)) from err
    return tuple(pair)

#pylint: disable=too-few-public-methods
class TcpFeederGenerator(AbstractFeederGenerator):
    """ Feeder generator to create a TcpClient feeder"""
    def create(self):
        return TcpClient(self.config.tcp_host,
                         reconnect=self.config.tcp_reconnect,
                         address_family=self.config.tcp_address_family)


class TcpClient:
    """ A SWO feeder that read ITM data from a TCP connection """
    def __init__(self, host, reconnect=False, address_family=socket.AF_INET):
        self.host = host
        self.reconnect = reconnect
        self.address_family = address_family
        self.sock = None

        self._connect_to_host(self.host, address_family=address_family)

    def _connect_to_host(self, host, address_family=socket.AF_INET):
        """ Create a TCP socket and start the connection to an host """
        sock = socket.socket(address_family, socket.SOCK_STREAM)
        sock.connect(host)
        self.sock = sock
        return sock

    def __call__(self):
        """ Read ITM stream from TCP connection """
        data = bytes()
        sock = self.sock
        while not data:
            try:
                if sock:
                    data = sock.recv(1024)
                else:
                    data = bytes()
            except (ConnectionResetError, OSError):
                # Silent connection errors
                # If needed (e.g. self.reconnect is False), EOFError will be raise later
                data = bytes()

            if not data:
                # Try to shutdown connection in a clean way
                # but ignore errors
                if sock:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

                # Try to reconnect, but ignore connection error and retry later
                if self.reconnect:

                    #if sock:
                    #    print("reconnect")

                    try:
                        sock = self._connect_to_host(self.host, address_family=self.address_family)
                    except ConnectionRefusedError:
                        sock = None
                        self.sock = None
                        # Yield a bit if remote server is not ready to accept a new connection
                        time.sleep(0.1)
                else:
                    raise EOFError

        return data

    @staticmethod
    def add_to_argparser(parser):
        """
        Add command line arguments parsing to a argparse.ArgumentParser
        to generate TCP Feeder
        """
        group = parser.add_argument_group("tcp client")
        group.add_argument("--tcp-client",
                           type=host_str_to_tuple,
                           dest='tcp_host',
                           help=_("Receive SWO stream from a TCP server"),
                           action=CreateFeederAction,
                           feeder_generator=TcpFeederGenerator)

        group.add_argument("--reconnect",
                           action='store_true',
                           dest='tcp_reconnect',
                           help=_("automatically reconnect to TCP server"))
        group.add_argument("--ipv4",
                           action='store_const',
                           dest='tcp_address_family',
                           const=socket.AF_INET,
                           help=_("use IPv4 to connect to TCP server"))
        group.add_argument("--ipv6",
                           action='store_const',
                           dest='tcp_address_family',
                           const=socket.AF_INET6,
                           help=_("use IPv6 to connect to TCP server"))

        parser.set_defaults(tcp_address_family=socket.AF_INET)
