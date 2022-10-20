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
