#!/usr/bin/env python3

import sys
import textwrap
from typing import List, Optional

import click


def get_align_of(s: Optional[str]) -> str:
    if s is None:
        return '<'
    if '>' in s:
        return '>'
    if '^' in s:
        return '^'
    return '<'

class Column:
    def __init__(self, get_value, size: int, format: str = None, name: str = '') -> None:
        self.__get_value = get_value
        size = max(size, len(name))
        self.__size = size
        align = get_align_of(format)
        if size == 0:
            self.__format = '{}'
        else:
            self.__format = f'{{:{align}{size}.{size}}}'
        self.__value_format = format
        self.__name = name

    def get_align(self) -> str:
        return get_align_of(self.__value_format)

    def get_value(self, *args) -> any:
        if callable(self.__get_value):
            return self.__get_value(*args)
        else:
            return self.__get_value

    def get_str(self, *args) -> str:
        if self.__value_format is not None:
            value = self.get_value(*args)
            if isinstance(value, tuple):
                return self.__value_format.format(*value)
            else:
                return self.__value_format.format(value)
        else:
            return self.get_value(*args)

    @property
    def size(self):
        return self.__size

    @property
    def format(self):
        return self.__format

    @property
    def name(self):
        return self.__name

class RowPrinter:
    def __init__(self, columns: List[Column], file=sys.stdout) -> None:
        formats = []
        seps = []
        names = []
        hdr_formats = []
        for column in columns:
            formats.append(column.format)
            seps.append('-'*column.size)
            names.append(column.name)
        self.__columns = columns
        self.__file = file
        self.__format_str = '| ' + ' | '.join(formats) + ' |'
        self.__sep_str = '+-' + '-+-'.join(seps) + '-+'
        self.__header = self.__format_str.format(*names)

    def print_header(self, **kwargs):
        click.secho(self.__header, reverse=True, file=self.__file, **kwargs)

    def print_separater(self, **kwargs):
        click.secho(self.__sep_str, file=self.__file, **kwargs)

    def print_data(self, *args, **kwargs):
        values = []
        for column in self.__columns:
            values.append(column.get_str(*args))
        click.secho(self.__format_str.format(*values), file=self.__file, **kwargs)

    def print_spanned(self, idx: int, size: int, data: List[any], **kwargs):
        formats = []
        spanned = 0
        for i in range(len(self.__columns)):
            c = self.__columns[i]
            if i<idx:
                formats.append(f'{{:{c.size}}}')
            elif i<idx+size-1:
                spanned += c.size+3
            else:
                formats.append(f'{{:{c.size+spanned}}}')
                spanned = 0
        format_str = '| ' + ' | '.join(formats) + ' |'
        click.secho(format_str.format(*data), file=self.__file, **kwargs)

    def print_row(self, cols: list[tuple[int,any,str]], **kwargs):
        formats = []
        values = []
        spanned = 0
        idx = 0
        for col in cols:
            size, value, align = col if len(col)==3 else col + ('<',)
            spanned = 0
            for i in range(size):
                c = self.__columns[i+idx]
                spanned += c.size+3
            idx += size
            align = get_align_of(align)
            formats.append(f'{{:{align}{spanned-3}}}')
            values.append(value)
        format_str = '| ' + ' | '.join(formats) + ' |'
        click.secho(format_str.format(*values), file=self.__file, **kwargs)

    @property
    def columns(self) -> int:
        return len(self.__columns)

class Row(Column):
    pass

class Header(Row):
    pass

class MapPrinter:
    def __init__(self, rows: List[Row], file=sys.stdout) -> None:
        max_name = 0
        max_value = 0
        max_title = 0
        for row in rows:
            if isinstance(row, Header):
                max_title = max(max_title, row.size)
            else:
                max_name = max(max_name, len(row.name))
                max_value = max(max_value, row.size)

        max_width = max(max_title, max_value+max_name+3)
        max_value = max_width - (max_name+3)

        self.__rows = rows
        self.__max_width = max_width
        self.__max_name = max_name
        self.__max_value = max_value
        self.__sep_str = '+-' + '-'*max_name + '-+-' + '-'*max_value + '-+'
        self.__header = self.__name_value_format('^').format('Name', 'Value')
        self.__file = file

    def __title_format(self, align) -> str:
        return f'| {{:{align}{self.__max_width}.{self.__max_width}}} |'

    def __name_value_format(self, align) -> str:
        name_len = self.__max_name
        value_len = self.__max_value
        return f'| {{:>{name_len}.{name_len}}} | {{:{align}{value_len}.{value_len}}} |'

    def print_header(self, **kwargs) -> 'MapPrinter':
        click.secho(self.__header, reverse=True, file=self.__file, **kwargs)
        return self

    def print_separater(self, **kwargs) -> 'MapPrinter':
        click.secho(self.__sep_str, file=self.__file, **kwargs)
        return self

    def print_data(self, *args, **kwargs) -> 'MapPrinter':
        for row in self.__rows:
            value = row.get_str(*args)
            align = row.get_align()

            if isinstance(row, Header):
                format_str = self.__title_format(align)
                click.secho(
                    format_str.format(value),
                    file = self.__file,
                    reverse=True,
                    **kwargs)
            else:
                format_str = self.__name_value_format(align)

                name = row.name
                texts = value.splitlines(True)
                lines = []
                for text in texts:
                    text_lines = textwrap.wrap(text, self.__max_value)
                    lines += text_lines
                while len(lines) > 0:
                    line = lines.pop(0)
                    kwargs_line = dict(**kwargs)
                    if len(lines) > 0 and 'underline' in kwargs_line:
                        kwargs_line.pop('underline')

                    click.secho(
                        format_str.format(name, line),
                        file = self.__file,
                        **kwargs_line)
                    name = ''
        return self