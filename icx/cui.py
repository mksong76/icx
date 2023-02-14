#!/usr/bin/env python3

import sys
from typing import List

import click


class Column:
    def __init__(self, get_value, size: int, format: str = None, name: str = '') -> None:
        self.__get_value = get_value
        self.__size = size
        self.__format = format if format is not None else f'{{:{size}}}'
        self.__name = name

    def get_value(self, *args) -> any:
        return self.__get_value(*args)

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
            values.append(column.get_value(*args))
        click.secho(self.__format_str.format(*values), file=self.__file, **kwargs)

class Row(Column):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

class Header(Row):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

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
        if max_width > max_title:
            max_value = max_width - (max_name+3)

        self.__rows = rows
        self.__format_title = '| '+f'{{:^{max_width}}}' + ' |'
        self.__sep_str = '+-' + '-'*max_name + '-+-' + '-'*max_value + '-+'
        self.__format_left = '| ' + f'{{:>{max_name}}}' + ' | ' + f'{{:<{max_value}}}' + ' |'
        self.__format_right = '| ' + f'{{:>{max_name}}}' + ' | ' + f'{{:>{max_value}}}' + ' |'
        self.__format_center = '| ' + f'{{:^{max_name}}}' + ' | ' + f'{{:^{max_value}}}' + ' |'
        self.__header = self.__format_center.format('Name', 'Value')
        self.__file = file

    def print_header(self, **kwargs) -> 'MapPrinter':
        click.secho(self.__header, reverse=True, file=self.__file, **kwargs)
        return self

    def print_separater(self, **kwargs) -> 'MapPrinter':
        click.secho(self.__sep_str, file=self.__file, **kwargs)
        return self

    def print_data(self, *args, **kwargs) -> 'MapPrinter':
        for row in self.__rows:
            value = row.get_value(*args)
            row_format = row.format
            if '>' in row_format:
                format_str = self.__format_right
                value_str = row_format.format(value)[-row.size:]
            else:
                format_str = self.__format_left
                value_str = row_format.format(value)[:row.size]

            if isinstance(row, Header):
                click.secho(
                    self.__format_title.format(value_str),
                    file = self.__file,
                    reverse=True,
                    **kwargs)
            else:
                click.secho(
                    format_str.format(row.name, value_str),
                    file = self.__file,
                    **kwargs)
        return self