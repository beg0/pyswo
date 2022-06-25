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
""" Extract usage information from PC sampling of ITM stream """
from collections import defaultdict
from argparse import ArgumentParser, FileType
import bisect

from elftools.dwarf.descriptions import describe_form_class
from elftools.elf.elffile import ELFFile

from pyswo.itmdecoder import ItmDecoder
from pyswo.itmpackets import ItmPcSamplePacket
from pyswo.utils.feeder import add_all_feeders_to_argparse

def main():
    """ Program entry point """
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("PROGRAM", type=FileType("rb"))
    add_all_feeders_to_argparse(parser)

    config = parser.parse_args()

    elffile = ELFFile(config.PROGRAM)

    if not elffile.has_dwarf_info():
        print('  file has no DWARF info')

    dwarfinfo = elffile.get_dwarf_info()
    swo_feeder_generator = getattr(config, 'feeder_generator', None)
    if not swo_feeder_generator:
        parser.error('No SWO stream configured')
    swo_feeder = swo_feeder_generator.create()

    itmdecoder = ItmDecoder(feeder=swo_feeder)

    sleep_counter = 0
    pc_usage = defaultdict(lambda:0)
    total_pc_sample = 0
    for pkt in itmdecoder:
        if isinstance(pkt, ItmPcSamplePacket):
            total_pc_sample += 1
            if pkt.sleep:
                sleep_counter += 1
            else:
                pc_usage[pkt.program_counter] += 1

    print(f"total= {total_pc_sample}")
    print(f"sleep= {sleep_counter}")
    #print(f"pc= {pc_usage}")

    print_hotest_functions(elffile, dwarfinfo, pc_usage, total_pc_sample)

    print_hotest_lines(dwarfinfo, pc_usage, total_pc_sample)

def print_hotest_functions(elffile, dwarfinfo, pc_usage, total_pc_sample):
    """ Display the function that use the most the MPU"""
    func_usage = get_usage_by_func(elffile, dwarfinfo, pc_usage)

    #print(f"func_usage={func_usage}")


    print("Hotest functions")
    sorted_func_usage = sorted(func_usage,
                               key=lambda func_name: func_usage[func_name],
                               reverse=True)
    for func_name in sorted_func_usage[0:10]:

        percentage_usage = 100.0*func_usage[func_name]/total_pc_sample
        if isinstance(func_name, bytes):
            func_name_latin = str(func_name, 'latin1')
        else:
            func_name_latin = func_name

        print(f"{func_name_latin:20s}: {percentage_usage:.2f}%")
    print("")

def print_hotest_lines(dwarfinfo, pc_usage, total_pc_sample):
    """ Display the source code line that use the most the MPU"""

    print("Hotest lines")
    fileline_usage = get_usage_by_file_line(dwarfinfo, pc_usage)
    sorted_fileline_usage = sorted(fileline_usage,
                                   key=lambda fileline: fileline_usage[fileline],
                                   reverse=True)
    for fileline in sorted_fileline_usage[0:10]:

        percentage_usage = 100.0*fileline_usage[fileline]/total_pc_sample
        print(f"{fileline:20s}: {percentage_usage:.2f}%")

def get_usage_by_func(elffile, dwarfinfo, pc_usage):
    """ Get CPU usage per function"""
    func_usage = defaultdict(lambda: 0)
    fnr = FuncNameRegistry(dwarfinfo)

    func_symbols = get_all_func_symbols(elffile)
    func_symbols.sort(key=lambda x: x['address'])
    func_addresses = [x['address'] for x in func_symbols]

    for pc in pc_usage:
        funcname = fnr.find_func(pc)

        # if we can't find info in DWARF, fallback to symbols table
        if funcname is None:
            idx = bisect.bisect(func_addresses, pc)
            if idx == 0:
                funcname = f"*unknown* ({pc:8x})"
            else:
                nearest_func = func_symbols[idx - 1]
                nearest_func_name = nearest_func['name']
                nearest_func_offset = pc-nearest_func['address']
                funcname = f"<{nearest_func_name}+{nearest_func_offset:x}>"

        func_usage[funcname] += pc_usage[pc]
    return func_usage

def get_usage_by_file_line(dwarfinfo, pc_usage):
    """ Get CPU usage per source code line"""
    line_usage = defaultdict(lambda: 0)
    flr = FileLineRegistry(dwarfinfo)

    for pc in pc_usage:
        file, line = flr.find_file_line(pc)

        fileline = ""
        if file is None:
            fileline = f"*unknown* ({pc:8x})"
        elif line is None:
            fileline = file
        else:
            fileline = str(file, 'utf8') + ":" + str(line)

        line_usage[fileline] += pc_usage[pc]
    return line_usage
class FuncNameRegistry():
    """ Find function names from DWARF debug info """
    def __init__(self, dwarfinfo = None, skip_pc_zero=True):
        self.func_infos = []
        self.func_lowpc = []

        if dwarfinfo:
            self.update_dwarf_info(dwarfinfo, skip_pc_zero=skip_pc_zero)

    def update_dwarf_info(self, dwarfinfo, skip_pc_zero=True):
        """ Update function names from DWARF info"""

        func_infos = []
        # Go over all DIEs in the DWARF information, looking for a subprogram
        # entry with an address range that includes the given address. Note that
        # this simplifies things by disregarding subprograms that may have
        # split address ranges.
        for CU in dwarfinfo.iter_CUs():
            for DIE in CU.iter_DIEs():
                try:
                    if DIE.tag == 'DW_TAG_subprogram':
                        lowpc = DIE.attributes['DW_AT_low_pc'].value
                        if skip_pc_zero and lowpc == 0:
                            continue

                        # DWARF v4 in section 2.17 describes how to interpret the
                        # DW_AT_high_pc attribute based on the class of its form.
                        # For class 'address' it's taken as an absolute address
                        # (similarly to DW_AT_low_pc); for class 'constant', it's
                        # an offset from DW_AT_low_pc.
                        highpc_attr = DIE.attributes['DW_AT_high_pc']
                        highpc_attr_class = describe_form_class(highpc_attr.form)
                        if highpc_attr_class == 'address':
                            highpc = highpc_attr.value
                        elif highpc_attr_class == 'constant':
                            highpc = lowpc + highpc_attr.value
                        else:
                            print('Error: invalid DW_AT_high_pc class:',
                                highpc_attr_class)
                            continue

                        func_infos.append(
                            {
                                'lowpc': lowpc,
                                'highpc': highpc,
                                'func_name': DIE.attributes['DW_AT_name'].value
                            }
                        )
                except KeyError:
                    continue

        self.func_infos = sorted(func_infos, key=lambda x: x['lowpc'])
        self.func_lowpc = [ x['lowpc'] for x in self.func_infos ]

    def find_func(self, address):
        """ Resolve function name from code address """
        idx = bisect.bisect_right(self.func_lowpc, address)
        if idx == 0:
            return None
        func_info = self.func_infos[idx - 1]
        if func_info['lowpc'] <= address < func_info['highpc']:
            return func_info['func_name']
        return None

class FileLineRegistry():
    """ Find source code line of a PC address using DWARF debug info """

    def __init__(self, dwarfinfo = None, skip_pc_zero=True):
        self.file_line_infos = []
        self.file_line_lowpc = []

        if dwarfinfo:
            self.update_dwarf_info(dwarfinfo, skip_pc_zero=skip_pc_zero)

    def update_dwarf_info(self, dwarfinfo, skip_pc_zero=True):
        """ Update source code line info from DWARF info"""
        file_line_infos=[]
        # Go over all the line programs in the DWARF information, looking for
        # one that describes the given address.
        for CU in dwarfinfo.iter_CUs():
            # First, look at line programs to find the file/line for the address
            lineprog = dwarfinfo.line_program_for_CU(CU)
            prevstate = None
            for entry in lineprog.get_entries():
                # We're interested in those entries where a new state is assigned
                if entry.state is None:
                    continue
                # Looking for a range of addresses in two consecutive states that
                # contain the required address.
                if prevstate and not (skip_pc_zero and prevstate.address == 0):
                    file_line_infos.append(
                        {
                            'lowpc': prevstate.address,
                            'highpc': entry.state.address,
                            'filename': lineprog['file_entry'][prevstate.file - 1].name,
                            'line': prevstate.line
                        }
                    )
                if entry.state.end_sequence:
                    # For the state with `end_sequence`, `address` means the address
                    # of the first byte after the target machine instruction
                    # sequence and other information is meaningless. We clear
                    # prevstate so that it's not used in the next iteration. Address
                    # info is used in the above comparison to see if we need to use
                    # the line information for the prevstate.
                    prevstate = None
                else:
                    prevstate = entry.state
        self.file_line_infos = sorted(file_line_infos, key=lambda x: x['lowpc'])
        self.file_line_lowpc = [ x['lowpc'] for x in self.file_line_infos ]

    def find_file_line(self, address):
        """ Resolve source code line from code address """
        idx = bisect.bisect_right(self.file_line_lowpc, address)
        if idx == 0:
            return None, None
        func_info = self.file_line_infos[idx - 1]
        if func_info['lowpc'] <= address < func_info['highpc']:
            return (func_info['filename'], func_info['line'])
        return None, None

def get_all_func_symbols(elffile):
    """ Extract all symbols related to functions from an ELF file

    These symbols are a good indicator of where a function start.
    """
    func_symbols = []
    symtab_section=elffile.get_section_by_name(".symtab")
    if not symtab_section:
        return []

    for symbol in symtab_section.iter_symbols():
        try:
            if symbol['st_info']['type'] == 'STT_FUNC':
                func_symbols.append({'name': symbol.name, 'address': symbol['st_value']})
        except KeyError:
            continue
    return func_symbols

main()
