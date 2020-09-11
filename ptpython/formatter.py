import string
import unicodedata
from itertools import groupby, cycle, chain
from functools import partial
import reprlib

from prompt_toolkit.formatted_text import  (
    FormattedText,
    PygmentsTokens,
    fragment_list_width,
    merge_formatted_text,
    to_formatted_text,
)
from pygments.lexers import PythonLexer, PythonTracebackLexer
from pygments.token import Token

MAX_LIST_DEPTH = reprlib.Repr().maxlevel

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
            self.set_obj_fmt_pretty()
        else:
            self.obj_fmt = obj_fmt

    def set_obj_fmt_simple(self):
        self.obj_fmt = lambda o: FormattedText([('', repr(o))])

    def set_obj_fmt_pretty(self):
        self.obj_fmt = partial(display_object, formatter=self)

    def set_bytes_fmt(self, show_index=True, show_ascii=True, line_items=16, index_color='class:blue', ascii_color='class:magenta'):
        self.bytes_fmt = partial(display_bytes, show_index=show_index,
            show_ascii=show_ascii,
            line_items=line_items,
            index_color='class:blue',
            ascii_color='class:magenta')

    def set_int_fmt(self, format_string='d', prefix='', base_width=1):
        self.int_fmt = partial(display_int, format_string=format_string, prefix=prefix, base_width=base_width)

    def format(self, o, list_depth=0, force_pretty_repr=False):
        if isinstance(o, bool):
            return FormattedText([('class:pygments.keyword.constant', str(o))])
        elif isinstance(o, int):
            return self.int_fmt(o)
        elif isinstance(o, str):
            return self.str_fmt(o)
        elif isinstance(o, bytes):
            return self.bytes_fmt(o, indent=list_depth)
        elif isinstance(o, (list, set, dict, tuple)):
            parens = '[]' if isinstance(o, list) else '()' if isinstance(o, tuple) else '{}'
            if len(o) == 0:
                return FormattedText([('', parens)])
            out = [
                    [('', parens[0])],
                    self.joindict(o, list_depth + 1) if isinstance(o, dict) else self.joinlist(o, list_depth + 1),
                    [('', parens[1])]
                ]
            return merge_formatted_text(out)()
        if force_pretty_repr or type(o).__repr__ is object.__repr__:
            return self.obj_fmt(o, indent=list_depth)
        return FormattedText([('', repr(o))])

    @staticmethod
    def _get_joiner(list_num_items, list_depth, inner_len, inner_num_items):
        joiner = (',\n' + '  ' * list_depth
                ) if (2 * (inner_num_items - 1) + inner_len > 6 * 78 and list_num_items < 400
                ) else ', '
        return FormattedText([('', joiner)])

    def joinlist(self, lst, list_depth):
        if list_depth > MAX_LIST_DEPTH:
            return FormattedText([('class:gray', '...')])
        inner = [ self.format(a, list_depth) for a in lst ]
        ln = get_formatted_text_length(merge_formatted_text(inner)())
        joiner = self._get_joiner(len(lst), list_depth, ln, len(inner))
        L = list(chain(*([l, joiner] for l in inner[:-1]), [inner[-1]]))
        return merge_formatted_text(L)()

    def joindict(self, dct, list_depth):
        if list_depth > MAX_LIST_DEPTH:
            return FormattedText([('class:gray', '...')])
        inner = list(
                chain(*(
                    [strip(self.format(k, list_depth)), FormattedText([('', ': ')]),
                        strip(self.format(v, list_depth))]
             for k, v in dct.items())))
        ln = get_formatted_text_length(merge_formatted_text(inner)())
        joiner = self._get_joiner(2 * len(dct), list_depth, ln, len(inner))
        L = list(chain(*([l] + ([joiner] if j % 3 == 2 else []) for j, l in enumerate(inner[:-1])), [inner[-1]]))
        return merge_formatted_text(L)()


def strip(x):
    out = to_formatted_text(x)
    if len(out) > 0 and out[-1][1] == '\n':
        out = FormattedText(out[:-1])
    return out

def get_formatted_text_length(x):
    fragments = to_formatted_text(x)
    return sum( (len(text) for _, text, *_ in fragments))

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
    out = to_formatted_text(merge_formatted_text(out))
    if not s.endswith('\n'):
        # strip newline added by the lexer
        out = strip(out)
    return out

def display_object(o, formatter, indent=0):
    try:
        type_name = o.__class__.__qualname__
    except AttributeError:
        return FormattedText([('', repr(o))])
    out = [ FormattedText([('class:gray', '<'), ('class:pygments.name.class', type_name), ('class:gray', '>'), ('', '\n')]) ]
    indent += 1
    for attr in sorted(dir(o)):
        if attr.startswith('_'):
            continue
        val = getattr(o, attr)
        if callable(val):
            continue
        out.append(FormattedText([('', '  ' * indent), ('class:pygments.name.attribute', attr), ('', ': ')]))
        out.append(strip(formatter.format(val, indent + 1)))
        out.append(FormattedText([('', '\n')]))
    return merge_formatted_text(out)()


def display_bytes(seq, show_index=True, show_ascii=True, line_items=16, index_color='class:blue', ascii_color='class:magenta', indent=0):
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
        if indent > 0:
            if line == 0:
                out.append(('', '\n'))
            out.append('  ' * indent)
        if show_index:
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
