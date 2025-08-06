#!/usr/local/bin/python35
import logging
import os
import os.path as osp
import json
import textwrap
from pprint import pformat
from itertools import zip_longest, chain

NOTSET = '-UNSET-'
NOTSET_DEFAULT = '-UNSET-DEFAULT({})-'

OUR_RT_DIR = os.getcwd() 

DATE_TIME_FORMAT = '%y%m%d-%H:%M:%S'
TIME_FORMAT = '%H:%M:%S'


DEBUG_LEVEL = logging.DEBUG # 10
VAR_LEVEL = 11
FF_LEVEL = 12
UF_LEVEL = 13
INFO_LEVEL = logging.INFO #20
TESTS_LEVEL = 21
TESTE_LEVEL = 22
PASS_LEVEL = 23
FAIL_LEVEL = 24
DATA_LEVEL = 25
SEQS_LEVEL = 26
SEQE_LEVEL = 27
OPS_LEVEL = 28
OPE_LEVEL = 29
WARN_LEVEL = logging.WARN #30
ATTNS_LEVEL = 31
ATTNE_LEVEL = 32
EXC_LEVEL = 33
IT_LEVEL = 34
ERROR_LEVEL = logging.ERROR #40


log_level_to_name = {logging.DEBUG    : 'DEBUG',
                     VAR_LEVEL        : 'VAR  ',
                     FF_LEVEL         : 'FF   ',
                     UF_LEVEL         : 'UF   ',
                     SEQS_LEVEL       : 'SEQS ',
                     SEQE_LEVEL       : 'SEQE ',
                     OPS_LEVEL        : 'OPS  ',
                     OPE_LEVEL        : 'OPE  ',
                     logging.INFO     : 'INFO ',
                     TESTS_LEVEL      : 'TESTS',
                     TESTE_LEVEL      : 'TESTE',
                     PASS_LEVEL       : 'PASS ',
                     FAIL_LEVEL       : 'FAIL ',
                     DATA_LEVEL       : 'DATA ',
                     logging.WARNING  : 'WARN ',
                     ATTNS_LEVEL      : 'ATTNS',
                     ATTNE_LEVEL      : 'ATTNE',
                     EXC_LEVEL        : 'EXC**',
                     logging.ERROR    : 'ERR* ',
                     logging.CRITICAL : 'ERR* ',
                     IT_LEVEL         : '',  # Special case where tag is variable (but must be len(logging.WARNING))
}

section_max_len = 99
section_inner_len = section_max_len - 4
section_msg_format = '| {{:^{0}.{0}s}} |'.format(section_inner_len)
subsection_msg_format = '{{:-^{0}.{0}s}}'.format(section_max_len)

def create_section(msg):
    # Looks like
    # --------------------------------------------------------------------------------
    # |                               Config check HDD                               |
    # --------------------------------------------------------------------------------
    #
    return '\n'.join(['-'*section_max_len] + 
                     [section_msg_format.format(l) for line in msg.splitlines() for l in textwrap.wrap(line, section_inner_len)] + 
                     ['-'*section_max_len])


def create_subsection(msg):
    # Looks like
    # ----------------------------- Config check HDD ---------------------------------
    #
    return '\n'.join([subsection_msg_format.format(l) for line in msg.splitlines() for l in textwrap.wrap(line, section_inner_len)])


def create_table(header, rows, footer=False, name=None, str_is_str=False, max_col_width=35):
    """!  Create an ascii table

    ##################################################################
    #                     On-Board Temperatures                      # <--- optional
    ##################################################################
    # Encl ID | Sensor                              | Value | Status #
    #================================================================#
    # 0       | On-Board Temperature 1-Ctlr A       | 25 C  | OK     #
    # 0       | On-Board Temperature 1-Ctlr B       | 26 C  | OK     #
    # 0       | On-Board Temperature 2-Ctlr A       | 28 C  | OK     #
    #================================================================#
    # Encl ID | Sensor                              | Value | Status # <--- optional
    ##################################################################
    """
    def _pformat(obj, width, str_is_str=str_is_str):
        if str_is_str and isinstance(obj, str):
            return obj
        return pformat(obj, width=width)

    # Make the arguments into lists and lists of lists
    # We assume that any header or row element can have embedded newlines
    # In addition we want to wrap any lines exceeding our max col width
    # So we treat each cell and header entry as set of rows within it's
    # own box to print.   To derive the rows, we first format the entry
    # with _pformat, which will create a pprint represtation or the object,
    # unless the object is a string and str_is_str is set, in which case
    # nothing is done.

    # First format each entry
    header = [_pformat(head, width=max_col_width, str_is_str=str_is_str) for head in header]
    rows = [[_pformat(cell, width=max_col_width, str_is_str=str_is_str) for cell in row] for row in rows]

    # Split on newlines, after this point, an entry is a list of rows, not a string
    header = [head.splitlines() for head in header]
    rows = [[cell.splitlines() for cell in row] for row in rows]

    # Finally wrap any lines that are too long, note there are no '\n' in any one line now
#    print([list(chain(*[textwrap.wrap(line, replace_whitespace=False, drop_whitespace=False) for line in head])) for head in header])
    header = [list(chain(*[textwrap.wrap(line, width=max_col_width, replace_whitespace=False, drop_whitespace=False) for line in head])) for head in header]

    rows = [[list(chain(*[textwrap.wrap(line, width=max_col_width, replace_whitespace=False, drop_whitespace=False) for line in cell])) for cell in row] for row in rows]
    
    assert all(len(row) == len(rows[0]) for row in rows), ('Argument rows must be iterable with '
                                                           'equal length elements')
    assert not rows or len(header) == len(rows[0]), 'Header (wrong len={}) must be same len as row (len={})'.format(
        len(header), len(rows[0]))

    # Calc max width
    col_width = [0]*len(header)

    for row in rows:
        for i in range(len(col_width)):
            if not row[i]:
                continue
            col_width[i] = min(max(col_width[i], len(max(row[i], key=len))), max_col_width)

    for i in range(len(col_width)):
        if  not header[i]:
            continue
        col_width[i] = min(max(col_width[i], len(max(header[i], key=len))), max_col_width)

    row_format = '#' + '|'.join([' {{:<{0}.{0}s}} '.format(w) for w in col_width]) + '#'
    header_format = row_format.replace('<', '^')

    header_rows = [header_format.format(*heads) for heads in zip_longest(*header, fillvalue='')]
    table_width = len(header_rows[0]) 

    table = ['#'*table_width]
    if name is not None:
        name_format = '#{{:^{0}.{0}}}#'.format(table_width-2)
        table.extend([name_format.format(name_line) for name_line in textwrap.wrap(name, table_width-4)])
        table.append('#'*table_width)
    table.extend(header_rows)
    table.append('#' + '='*(table_width - 2) + '#')
    table.extend(row_format.format(*cells) for row in rows for cells in zip_longest(*row, fillvalue='') )
    if footer:
        table.append('#' + '='*(table_width-2) + '#')
        table.extend(header_rows)
    table.append('#'*table_width)

    return '\n'.join(table)
        

class Log:
    def __init__(self, logger, scope):
        self.logger = logger
        self.scope = scope

    def sequence_start(self, name):
        """! Log the start of a test sequence

        @param name   The name of the sequence file

        @note Intended for internal  platform use
        """
        self.logger.log(SEQS_LEVEL, '{}'.format(name), extra={'scope':self.scope})

    def sequence_end(self, result, name):
        """! Log the completion of a test sequence

        @param result  Must be 'PASS'|'FAIL'
        @param name    The name of the sequence file that has stopped running

        @note Intended for internal  platform use
        """
        assert result in ('PASS', 'FAIL')
        self.logger.log(SEQE_LEVEL, '{} {}'.format(result, name), extra={'scope':self.scope})

    def operation_start(self, name):
        """! Log the start of an operation

        @param name    The name of the operation

        @note Intended for internal  platform use
        """
        self.logger.log(OPS_LEVEL, '{}'.format(name), extra={'scope':self.scope})

    def operation_end(self, result, name):
        """ Log the completion

        @param  result  Must be 'PASS'|'FAIL'
        @param  name    The name of the operation

        @note Intended for internal  platform use
        """
        assert result in ('PASS', 'FAIL')
        self.logger.log(OPE_LEVEL, '{} {}'.format(result, name), extra={'scope':self.scope})

    def test_start(self, command):
        """! Log the start of a test command

        @param command    The full command line of how this test was called

        @note Intended for internal  platform use
        """
        self.logger.log(TESTS_LEVEL, '{}'.format(command), extra={'scope':self.scope})

    def test_end(self, result, command):
        """! Log the completion of a test command

        @param result      Must be 'PASS'|'FAIL'
        @param command:    The full command line of how this test was called

        @note Intended for internal  platform use
        """
        assert result in ('PASS','FAIL')
        self.logger.log(TESTE_LEVEL, '{} {}'.format(result, command), extra={'scope':self.scope})

    def variable(self, what, name, value, media=None):
        """! Log the name and value of a variable

        @param what  Must start with 'GET'|'SET'|'DEL'
        @param name  Variable name
        @param value Variable value
        @param media The operation happened on alternate UUT

        @note Intended for internal  platform use
        """

        assert what in ('GET', 'SET', 'DEL')

        self.logger.log(VAR_LEVEL, '{}{} {} {}'.format(
                what,
                '@{}'.format(media) if media else '',
                name,
                # print NOTSET as non-string
                (json.dumps(value) if isinstance(value, str) and not value.startswith(NOTSET) else value)  \
                    if what != 'DEL' else ''), 
                extra={'scope':self.scope})

    def find_file(self, name, path, media=None):
        """! Log the result of finding a file

        @param name  The basename of a file to find
        @param path  The full path of where the 'name' is found
        @param media The operation happened on alternate media

        @note Intended for internal  platform use
        """
        self.logger.log(FF_LEVEL, '{}{} {}'.format(name, '@{}'.format(media) if media else '', path),
                        extra={'scope':self.scope})

    def unlink_file(self, path):
        """! Log the unlinking (delete) of file path

        @param path  The full path of where the file unlinked (deleted)

        @note Intended for internal  platform use
        """
        self.logger.log(UF_LEVEL, path, extra={'scope':self.scope})


    def pass_(self):
        """! Log test completion as PASS at end of test if there are no errors

        @note Intended for internal  platform use
        """
        self.logger.log(PASS_LEVEL, 'PASS', extra={'scope':self.scope})

    def fail(self):
        """! Log test completion as FAIL at end of test if any critical errors

        @note Intended for internal  platform use
        """
        self.logger.log(FAIL_LEVEL, 'FAIL', extra={'scope':self.scope})

    def attention_start(self, screen_id):
        """! Log when an attention screen has been posted

        @param screen_id    A label to identify the screen
        """
        self.logger.log(ATTNS_LEVEL, '{}'.format(screen_id), extra={'scope':self.scope})

    def attention_end(self, screen_id):
        """! Log when an attention screen has been completed

        @param screen_id    A label to identify the screen
        """
        self.logger.log(ATTNE_LEVEL, '{}'.format(screen_id), extra={'scope':self.scope})

    def data(self, name, value, datatype):
        """! Log some parametric data to logdata.utp

        @param name     Name of data
        @param value    Value of data
        @param datatype Type of data, should be a non-zero-length string
                        if given as 'TESTDATA' then the key/value will sent on to PEW DB
        """
        assert datatype and isinstance(datatype, str), 'parameter datatype must be non-zero len string'
        assert isinstance(value, str) and isinstance(name, str) and name.strip() and value.strip(), \
                'parameters value and name must be non-zero length, strings and cannot contain only whitespace'
        self.logger.log(DATA_LEVEL, '{}~{}~{}'.format(datatype, name, value), extra={'scope':self.scope})

    def section(self, message, level='info'):
        """! Log a message centered in a ascii box for visual yumminess
        
        @param message   A message to write.  Keep it shortish or it will be wrapped.
        @param level     Defaults to info, but should be a legal logging.* function name
        """
        getattr(self.logger, level)(create_section(message))

    def subsection(self, message, level='info'):
        """! Log a message centered in a ascii box for visual yumminess
        
        @param message   A message to write.  Keep it shortish or it will be wrapped.
        @param level     Defaults to info, but should be a legal logging.* function name
        """
        getattr(self.logger, level)(create_subsection(message))

    def table(self, header, rows, level='info', footer=False, name=None):
        """! Log data in an ascii table
        
        @param header   List with name of each columen
        @param rows     List of lists, each element of list should have same length equal to header length
        @param level     Defaults to info, but should be a legal logging.* function name
        """
        getattr(self.logger, level)(create_table(header, rows, footer=footer, name=name))

    def it(self, log_type, *bares):
        """! Log a generic record

        A generic method to create a log record.
        
        @param log_type       First param is log type. It must be string and be lenth == len('DEBUG')
        @param *bares         Turned into ~ separated string and passed as message
        """
        assert len(log_type) == len(log_level_to_name[logging.WARNING]), 'log_type param must be {} chars long '\
            '(pad right with space if you have to)'.format(len(log_level_to_name[logging.WARNING]))

        assert log_type.upper().strip() not in (x.strip() for x in log_level_to_name.values()), \
            'log_type cannot be an existing tag: {}'.format(', '.join(x.strip() for x in log_level_to_name.values()))

        msg = '~'.join(str(x) for x in bares)
        assert len(msg.splitlines()) == 1, 'There can be no embedded newlines in parameters to this function'
        self.logger.log(IT_LEVEL, msg, extra={'tag':log_type, 'scope':self.scope})

    def firmware(self, name, vendor_pn, vendor_sn, value):
        """! Log a firmware record
        @param name       str: A keyword to index the data
        @param vendor_pn  str: The vendor part number, taken from device
        @param vendor_sn  str: the vendor serial number, take from device
        @param value      str: A value reprsenting the firmware level
        """
        for n in ('name', 'vendor_pn', 'vendor_sn'):
            v = locals()[n] 
            assert isinstance(v, str) and '~' not in v, "param <{}> must be str and cannot contain '~'".format(n)
        self.it('FIRMW', name, vendor_pn, vendor_sn, str(value))
