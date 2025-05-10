
import re
from typing import Optional

import click
from rich.style import Style
from rich.text import Text


def as_int(v: Optional[any]) -> Optional[int]:
    if v is None:
        return None
    return int(v)


def get_align_of(s: Optional[str]) -> str:
    if s is None:
        return '<'
    if '>' in s:
        return '>'
    if '^' in s:
        return '^'
    return '<'


def as_rich_style(v: dict):
    kwargs = {}
    if 'fg' in v:
        kwargs['color'] = v['fg']
    if 'bg' in v:
        kwargs['bgcolor'] = v['bg']
    if 'bold' in v:
        kwargs['bold'] = v['bold']
    if 'reverse' in v:
        kwargs['reverse'] = v['reverse']
    if 'dim' in v:
        kwargs['dim'] = v['dim']
    if 'underline' in v:
        kwargs['underline'] = v['underline']
    return Style(**kwargs)


class Styled:
    def __new__(cls, value: any, **kwargs):
        if len(kwargs) == 0:
            return value
        return super().__new__(cls)

    def __init__(self, value: any, **kwargs) -> None:
        if isinstance(value, Styled):
            self.__value = value.value
            self.__style = value.style.copy()
            self.__style.update(kwargs)
        else:
            self.__value = value
            self.__style = kwargs

    @property
    def value(self) -> any:
        return self.__value

    @property
    def style(self) -> dict:
        return self.__style

    def __format__(self, format_spec):
        s = self.__value.__format__(format_spec)
        return click.style(s, **self.__style)

    def rich_style(self):
        return as_rich_style(self.__style)
    

    @staticmethod
    def wrap(value: any, style: Optional[dict] = None) -> any:
        return Styled(value, **style) if style is not None else value

    @classmethod
    def unwrap(cls, v: any) -> tuple[any, dict]:
        if isinstance(v, Styled):
            return v.__value, v.__style
        else:
            return v, None

__align_map = (
    ('<', '>', '^'),
    ('left', 'right', 'center'),
)
def align_f2r(align: str):
    idx = __align_map[0].index(align)
    return __align_map[1][idx]

__format_detail = r'^(?P<align>[<>\^])?((?P<size>[0-9]+)?(\.(?P<precision>[0-9]+))?)?s?$'
def __rich_format__(value:Text, fmt: str) -> Text:
    mo = re.compile(__format_detail).match(fmt)
    if mo:
        align = align_f2r(mo.group('align') or '<')
        size = as_int(mo.group('size'))
        precision = as_int(mo.group('precision'))
        #print(f'align={align} size={size} precision={precision}')
        if size is not None or precision is not None:
            value = value.copy()
            p_size = len(value)
            if precision is not None and p_size > precision:
                value.truncate(precision)
                p_size = precision
            if size is not None and p_size < size:
                value.align(align, size)
        return value
    raise ValueError(f'Unknown format {fmt!r} for {value!r}')

__format_regex = r'{(?P<var>[^:}]*)(:(?P<fmt>[^}]*))?}'
def format(s: str, *args, **kwargs) -> Text:
    arg_idx = 0
    def get_arg(var: str) -> any:
        nonlocal arg_idx
        if var == '':
            if arg_idx >= len(args):
                raise ValueError('Lack of arguments')
            value = args[arg_idx]
            arg_idx += 1
            return value
        elif var in kwargs:
            return kwargs[var]
        else:
            try:
                a_idx = int(var)
            except:
                raise ValueError(f'Unknown variable {var}')
            if a_idx >= len(args):
                raise ValueError('Lack of arguments')
            return args[a_idx]

    result: Text = Text()
    idx: int = 0
    for match in re.compile(__format_regex).finditer(s):
        start = match.start()
        if idx < start:
            result.append(s[idx:start])
        idx  = match.end()

        var = match.group('var')
        fmt = match.group('fmt') or ""

        value = get_arg(var)

        if isinstance(value, Text):
            result.append_text(__rich_format__(value, fmt))
            continue
        elif isinstance(value, Styled):
            s_value = value.value.__format__(fmt)
            result.append(s_value, value.rich_style())
            continue
        else:
            if not hasattr(value, '__format__'):
                s_value = str(value)
            else:
                s_value = value.__format__(fmt)
            result.append(s_value)
    result.append(s[idx:])
    return result
