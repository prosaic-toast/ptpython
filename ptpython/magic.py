"""
Handles magic commands in a Python repl.

::
"""
import os
import sys
import traceback
import warnings
import shlex
import pdb
from functools import partial
import time
import re
from collections import namedtuple

from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import (
    FormattedText,
    PygmentsTokens,
    fragment_list_width,
    merge_formatted_text,
    to_formatted_text,
)
from prompt_toolkit.formatted_text.utils import fragment_list_width
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.patch_stdout import patch_stdout as patch_stdout_context
from prompt_toolkit.shortcuts import clear_title, print_formatted_text, set_title
from prompt_toolkit.utils import DummyContext
from pygments.lexers import PythonLexer, PythonTracebackLexer
from pygments.token import Token
from prompt_toolkit.completion import (
    CompleteEvent,
    Completer,
    Completion,
    PathCompleter,
)


from .completer import Completer
from .formatter import strip

class MagicHandler:

    def __init__(self, repl):
        self.repl = repl

    def run_command(self, line):
        args = shlex.split(line)
        cmd = args.pop(0)
        if cmd in MagicCompleter.magics:
            getattr(self, cmd)(*args)
        else:
            self.repl.print_error_message(
                    f'No such magic command: %{cmd}. List of available magic commands:\n')
            self.repl.output_text(MagicCompleter.get_magics_help())

    def run(self, *args):
        if len(args) == 0:
            self.repl.print_error_message('Invalid command. Usage:\n')
            self.repl.output_text(MagicCompleter.get_magics_help('run'))
            return
        for arg in args:
            alt = f'{arg}.py'
            if not os.path.exists(arg) and os.path.exists(alt):
                arg = alt
            try:
                code = compile(open(arg, 'rt').read(), arg, 'exec')
            except Exception as ex:
                self.repl.handle_exception(ex, store_traceback=False)
                return
            try:
                exec(code, self.repl.get_globals())
            except Exception as ex:
                self.repl.handle_exception(ex)

    def debug(self, *args):
        self.repl.debug()

    def cd(self, *args):
        if len(args) == 1:
            try:
                os.chdir(args[0])
            except Exception as ex:
                self.repl.print_error_message(f'Failed to change directory: {ex}')
        else:
            self.repl.print_error_message('Invalid command. Usage:\n')
            self.repl.output_text(MagicCompleter.get_magics_help('cd'))
    def pwd(self, *args):
            self.repl.output_text(FormattedText([('class:pygments.literal.string', f'{os.getcwd()}')]))

    def hex(self, *args):
        # TODO threshold
        self.repl.formatter.set_int_fmt('x', '0x', 2)

    def dec(self, *args):
        self.repl.formatter.set_int_fmt('d')

    def bin(self, *args):
        self.repl.formatter.set_int_fmt('b', '0b', 8)

    def oct(self, *args):
        self.repl.formatter.set_int_fmt('o', '0o')

    def who(self, *args):
        regex = []
        if args:
            for a in args:
                try:
                    regex.append(re.compile(a))
                except re.error as ex:
                    self.repl.print_error_message(f'Invalid regex {a}: {ex}')
                    return
        else:
            regex = [ re.compile('^[^_]')]
        out = []
        for name, o in sorted(self.repl.get_locals().items()):
            if all(r.search(name) for r in regex):
                out.extend([
                    ('class:pygments.name.variable', f'{name} '),
                    ('class:gray', '<'), ('class:pygments.name.class', o.__class__.__qualname__), ('class:gray', '>'),
                    ('', '\n')
                    ])
        self.repl.output_text(strip(FormattedText(out)))


class MagicCompleter(Completer):
    magic_tuple = namedtuple('magic_tuple', ('grammar', 'usage', 'help'))
    magics = {
            'run': magic_tuple(r'\s+ (?P<py_filename>[^\s]+)', 'PYTHONFILE [...]', 'Run one or more PYTHONFILES in the current session'),
            'debug': magic_tuple('', '', 'Start post-mortem debugging'),
            'who': magic_tuple('', '[REGEX ...]', 'List current global identifiers matching a list of regular expressions REGEX (default: ^[^_])'),
            'pwd' : magic_tuple('', '', 'Print current working directory'),
            'cd' : magic_tuple(r'\s+ (?P<directory>[^\s]+)', 'DIRECTORY', 'Change working directory to DIRECTORY'),
            'hex' : magic_tuple('', '[THRESHOLD]', 'Display integers larger than THRESHOLD (default: 100) as hex'),
            'dec' : magic_tuple('', '', 'Display integers as decimal'),
            'bin' : magic_tuple('', '', 'Display integers as binary'),
            'oct' : magic_tuple('', '', 'Display integers as octal'),
            }

    @classmethod
    def get_magics_help(cls, target_name=None):
        out = []
        for name, magic in cls.magics.items():
            if target_name is None or target_name == name:
                out.extend([
                    ('class:pygments.keyword', f'%{name} '),
                    ('class:pygments.name.variable', f'{magic.usage}\n'),
                    ('', f'    {magic.help}'),
                    ('', '\n')
                ])
        return strip(FormattedText(out))

    @classmethod
    def get_magic_grammar(cls):
        out = ['            (?P<percent>%)(']
        for name, magic in cls.magics.items():
            out.append(f'                (?P<magic>{name}) {magic.grammar} |')
        out.append(') |')
        return '\n'.join(out)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        for m in sorted(self.magics):
            if m.startswith(text):
                yield Completion("%s" % m, -len(text))

