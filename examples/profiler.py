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

    elf_file = ELFFile(config.PROGRAM)

    if not elf_file.has_dwarf_info():
        print('  file has no DWARF info')

    dwarf_info = elf_file.get_dwarf_info()
    swo_feeder_generator = getattr(config, 'feeder_generator', None)
    if not swo_feeder_generator:
        parser.error('No SWO stream configured')
    swo_feeder = swo_feeder_generator.create()

    itm_decoder = ItmDecoder(feeder=swo_feeder)

    sleep_counter = 0
    pc_usage = defaultdict(lambda:0)
    total_pc_sample = 0
    try:
        print("Start reading SWO stream. Press CTRL-C to exit")

        while True:
            for pkt in itm_decoder:
                if isinstance(pkt, ItmPcSamplePacket):
                    total_pc_sample += 1
                    if pkt.sleep:
                        sleep_counter += 1
                    else:
                        pc_usage[pkt.program_counter] += 1
    except KeyboardInterrupt:
        print("Capture interrupted by user")
    except EOFError:
        print("End of SWO stream")


    print(f"total= {total_pc_sample}")
    print(f"sleep= {sleep_counter}")
    #print(f"pc= {pc_usage}")

    print_hottest_functions(elf_file, dwarf_info, pc_usage, total_pc_sample)

    print_hottest_lines(dwarf_info, pc_usage, total_pc_sample)

def print_hottest_functions(elf_file, dwarf_info, pc_usage, total_pc_sample):
    """ Display the function that use the most the MPU"""
    func_usage = get_usage_by_func(elf_file, dwarf_info, pc_usage)

    #print(f"func_usage={func_usage}")


    print("Hottest functions")
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

def print_hottest_lines(dwarf_info, pc_usage, total_pc_sample):
    """ Display the source code line that use the most the MPU"""

    print("Hottest lines")
    file_line_usage = get_usage_by_file_line(dwarf_info, pc_usage)
    sorted_file_line_usage = sorted(file_line_usage,
                                   key=lambda file_line: file_line_usage[file_line],
                                   reverse=True)
    for file_line in sorted_file_line_usage[0:10]:

        percentage_usage = 100.0*file_line_usage[file_line]/total_pc_sample
        print(f"{file_line:20s}: {percentage_usage:.2f}%")

def get_usage_by_func(elf_file, dwarf_info, pc_usage):
    """ Get CPU usage per function"""
    func_usage = defaultdict(lambda: 0)
    fnr = FuncNameRegistry(dwarf_info)

    func_symbols = get_all_func_symbols(elf_file)
    func_symbols.sort(key=lambda x: x['address'])
    func_addresses = [x['address'] for x in func_symbols]

    for pc in pc_usage:
        func_name = fnr.find_func(pc)

        # if we can't find info in DWARF, fallback to symbols table
        if func_name is None:
            idx = bisect.bisect(func_addresses, pc)
            if idx == 0:
                func_name = f"*unknown* ({pc:8x})"
            else:
                nearest_func = func_symbols[idx - 1]
                nearest_func_name = nearest_func['name']
                nearest_func_offset = pc-nearest_func['address']
                func_name = f"<{nearest_func_name}+{nearest_func_offset:x}>"

        func_usage[func_name] += pc_usage[pc]
    return func_usage

def get_usage_by_file_line(dwarf_info, pc_usage):
    """ Get CPU usage per source code line"""
    line_usage = defaultdict(lambda: 0)
    flr = FileLineRegistry(dwarf_info)

    for pc in pc_usage:
        file, line = flr.find_file_line(pc)

        file_line = ""
        if file is None:
            file_line = f"*unknown* ({pc:8x})"
        elif line is None:
            file_line = file
        else:
            file_line = str(file, 'utf8') + ":" + str(line)

        line_usage[file_line] += pc_usage[pc]
    return line_usage
class FuncNameRegistry():
    """ Find function names from DWARF debug info """
    def __init__(self, dwarf_info = None, skip_pc_zero=True):
        self.func_infos = []
        self.func_low_pc = []

        if dwarf_info:
            self.update_dwarf_info(dwarf_info, skip_pc_zero=skip_pc_zero)

    def update_dwarf_info(self, dwarf_info, skip_pc_zero=True):
        """ Update function names from DWARF info"""

        func_infos = []
        # Go over all DIEs in the DWARF information, looking for a subprogram
        # entry with an address range that includes the given address. Note that
        # this simplifies things by disregarding subprograms that may have
        # split address ranges.
        for CU in dwarf_info.iter_CUs():
            for DIE in CU.iter_DIEs():
                try:
                    if DIE.tag == 'DW_TAG_subprogram':
                        low_pc = DIE.attributes['DW_AT_low_pc'].value
                        if skip_pc_zero and low_pc == 0:
                            continue

                        # DWARF v4 in section 2.17 describes how to interpret the
                        # DW_AT_high_pc attribute based on the class of its form.
                        # For class 'address' it's taken as an absolute address
                        # (similarly to DW_AT_low_pc); for class 'constant', it's
                        # an offset from DW_AT_low_pc.
                        high_pc_attr = DIE.attributes['DW_AT_high_pc']
                        high_pc_attr_class = describe_form_class(high_pc_attr.form)
                        if high_pc_attr_class == 'address':
                            high_pc = high_pc_attr.value
                        elif high_pc_attr_class == 'constant':
                            high_pc = low_pc + high_pc_attr.value
                        else:
                            print('Error: invalid DW_AT_high_pc class:',
                                high_pc_attr_class)
                            continue

                        func_infos.append(
                            {
                                'low_pc': low_pc,
                                'high_pc': high_pc,
                                'func_name': DIE.attributes['DW_AT_name'].value
                            }
                        )
                except KeyError:
                    continue

        self.func_infos = sorted(func_infos, key=lambda x: x['low_pc'])
        self.func_low_pc = [ x['low_pc'] for x in self.func_infos ]

    def find_func(self, address):
        """ Resolve function name from code address """
        idx = bisect.bisect_right(self.func_low_pc, address)
        if idx == 0:
            return None
        func_info = self.func_infos[idx - 1]
        if func_info['low_pc'] <= address < func_info['high_pc']:
            return func_info['func_name']
        return None

class FileLineRegistry():
    """ Find source code line of a PC address using DWARF debug info """

    def __init__(self, dwarf_info = None, skip_pc_zero=True):
        self.file_line_infos = []
        self.file_line_low_pc = []

        if dwarf_info:
            self.update_dwarf_info(dwarf_info, skip_pc_zero=skip_pc_zero)

    def update_dwarf_info(self, dwarf_info, skip_pc_zero=True):
        """ Update source code line info from DWARF info"""
        file_line_infos=[]
        # Go over all the line programs in the DWARF information, looking for
        # one that describes the given address.
        for CU in dwarf_info.iter_CUs():
            # First, look at line programs to find the file/line for the address
            line_prog = dwarf_info.line_program_for_CU(CU)
            prev_state = None
            for entry in line_prog.get_entries():
                # We're interested in those entries where a new state is assigned
                if entry.state is None:
                    continue
                # Looking for a range of addresses in two consecutive states that
                # contain the required address.
                if prev_state and not (skip_pc_zero and prev_state.address == 0):
                    file_line_infos.append(
                        {
                            'low_pc': prev_state.address,
                            'high_pc': entry.state.address,
                            'filename': line_prog['file_entry'][prev_state.file - 1].name,
                            'line': prev_state.line
                        }
                    )
                if entry.state.end_sequence:
                    # For the state with `end_sequence`, `address` means the address
                    # of the first byte after the target machine instruction
                    # sequence and other information is meaningless. We clear
                    # prev_state so that it's not used in the next iteration. Address
                    # info is used in the above comparison to see if we need to use
                    # the line information for the prev_state.
                    prev_state = None
                else:
                    prev_state = entry.state
        self.file_line_infos = sorted(file_line_infos, key=lambda x: x['low_pc'])
        self.file_line_low_pc = [ x['low_pc'] for x in self.file_line_infos ]

    def find_file_line(self, address):
        """ Resolve source code line from code address """
        idx = bisect.bisect_right(self.file_line_low_pc, address)
        if idx == 0:
            return None, None
        func_info = self.file_line_infos[idx - 1]
        if func_info['low_pc'] <= address < func_info['high_pc']:
            return (func_info['filename'], func_info['line'])
        return None, None

def get_all_func_symbols(elf_file):
    """ Extract all symbols related to functions from an ELF file

    These symbols are a good indicator of where a function start.
    """
    func_symbols = []
    sym_tab_section=elf_file.get_section_by_name(".symtab")
    if not sym_tab_section:
        return []

    for symbol in sym_tab_section.iter_symbols():
        try:
            if symbol['st_info']['type'] == 'STT_FUNC':
                func_symbols.append({'name': symbol.name, 'address': symbol['st_value']})
        except KeyError:
            continue
    return func_symbols

main()
