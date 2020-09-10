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

class MagicHandler:

    def __init__(self, repl):
        self.repl = repl

    def run_command(self, line):
        try:
            args = shlex.split(line)
            cmd = args.pop(0)
            if cmd == 'run':
                if args:
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
                else:
                    print('TODO Usage: %run SCRIPT [...]')
            elif cmd == 'debug':
                self.repl.debug()
            elif cmd == 'cd':
                if len(args) == 1:
                    os.chdir(args[0])
                else:
                    print('TODO Usage: %cd NEW_WORKING_DIRECTORY')
            elif cmd == 'pwd':
                print_formatted_text(FormattedText([
                    ('class:pygments.literal.string', f'{os.getcwd()}')]))
            elif cmd == 'hex':
                self.repl.formatter.set_int_fmt('x', '0x', 2)
            elif cmd == 'dec':
                self.repl.formatter.set_int_fmt('d')
            elif cmd == 'bin':
                self.repl.formatter.set_int_fmt('b', '0b', 8)
            elif cmd == 'oct':
                self.repl.formatter.set_int_fmt('o', '0o')
            else:
                raise RuntimeError(f'Invalid magic command {cmd}')
        except Exception:
            traceback.print_exc()


class MagicCompleter(Completer):
    magics = {
            'cd' : r'\s+ (?P<directory>[^\s]+)',
            'run': r'\s+ (?P<py_filename>[^\s]+)',
            'debug': '',
            'pwd' : '',
            'hex' : '',
            'dec' : '',
            'bin' : '',
            'oct' : ''
            }

    @classmethod
    def get_magic_grammar(cls):
        out = ['            (?P<percent>%)(']
        for k, v in cls.magics.items():
            out.append(f'                (?P<magic>{k}) {v} |')
        out.append(') |')
        return '\n'.join(out)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        for m in sorted(self.magics):
            if m.startswith(text):
                yield Completion("%s" % m, -len(text))

