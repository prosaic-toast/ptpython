import string
import unicodedata
from itertools import groupby
from functools import partial
from prompt_toolkit.formatted_text import  (
    FormattedText,
    PygmentsTokens,
    fragment_list_width,
    merge_formatted_text,
    to_formatted_text,
)
from pygments.lexers import PythonLexer, PythonTracebackLexer
from pygments.token import Token



class PtPyFormatter:
    def __init__(self, int_fmt=None, str_fmt=None, bytes_fmt=None, obj_fmt=None):
        if int_fmt is None:
            self.set_int_fmt()
        elif isinstance(int_fmt, str):
            self.set_int_fmt(int_fmt)
        else:
            self.int_fmt = int_fmt

        if str_fmt is None:
            self.str_fmt = display_string
        else:
            self.str_fmt = str_fmt

        if bytes_fmt is None:
            self.set_bytes_fmt()
        else:
            self.bytes_fmt = bytes_fmt

        if obj_fmt is None:
            self.obj_fmt = lambda x: FormattedText([('', repr(x))])
        else:
            self.obj_fmt = obj_fmt

    def set_bytes_fmt(self, show_index=True, show_ascii=True, line_items=16, index_color='class:blue', ascii_color='class:magenta'):
        self.bytes_fmt = partial(hexdump, show_index=show_index,
            show_ascii=show_ascii,
            line_items=line_items,
            index_color='class:blue',
            ascii_color='class:magenta')

    def set_int_fmt(self, format_string='d', prefix='', base_width=1):
        self.int_fmt = partial(display_int, format_string=format_string, prefix=prefix, base_width=base_width)

    def format(self, o):
        if isinstance(o, int):
            return self.int_fmt(o)
        elif isinstance(o, str):
            return self.str_fmt(o)
        elif isinstance(o, bytes):
            return self.bytes_fmt(o)
        if type(o).__repr__ is object.__repr__:
            return self.obj_fmt(o)
        return FormattedText([('', repr(o))])


def display_int(x, format_string='d', prefix='', base_width=1):
    x = f'{x:{format_string}}'
    num_zeros = (base_width - len(x) % base_width) % base_width
    return PygmentsTokens([(Token.Number.Integer, f'{prefix}{"0" * num_zeros}{x}')])

def display_string(s):
    lexer = PythonLexer()
    isprint = lambda ch: ch.isprintable() or ch == '\t' or ch == '\n'
    out = []
    for k, g in groupby(s, isprint):
        g = ''.join(g)
        if k:
            out.append(PygmentsTokens(lexer.get_tokens(g)))
        else:
            out.append([('class:gray', repr(g).replace("'", ""))])
    return merge_formatted_text(out)

def hexdump(seq, show_index=True, show_ascii=True, line_items=16, index_color='class:blue', ascii_color='class:magenta'):
    half_line_items = line_items // 2

    num_lines = (len(seq) + line_items - 1) // line_items
    max_index_len = 2 * ((num_lines * line_items + 255) // 256)
    index_template = ('%%0%dx  ' % max_index_len) if show_index else ''

    out = []
    ascii_offset = 0
    for line in range(num_lines):
        offset = line * line_items
        items = seq[offset:offset+line_items]
        num_items = len(items)
        if show_ascii:
            out.append((index_color, f'{index_template % offset}'))

        right_len = num_items - half_line_items
        hex_template = ('%02x ' * min(half_line_items, num_items) + ' ' + ('%02x ' * max(0, right_len)))
        out_line = f'{hex_template % tuple(items)} '

        if num_items == line_items:
            ascii_offset = len(out_line)
        if show_ascii:
            out_line = out_line.ljust(ascii_offset, ' ')
            out.append(('', out_line))
            out_line = ''.join( ( chr(ch) if (ch < 127 and ch > 31) else '.' for ch in items))
            out_line += ' ' * (line_items - num_items)
            out.append((ascii_color, out_line))
            out_line = ''
        out.append(('', out_line + '\n'))
    return FormattedText(out)
