#!/usr/bin/env python3

import abc
from functools import reduce
import math
import sys
import textwrap
from typing import List, Optional, Union

import click


def get_align_of(s: Optional[str]) -> str:
    if s is None:
        return '<'
    if '>' in s:
        return '>'
    if '^' in s:
        return '^'
    return '<'

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

    @staticmethod
    def wrap(value: any, style: Optional[dict] = None) -> any:
        return Styled(value, **style) if style is not None else value

    @classmethod
    def unwrap(cls, v: any) -> tuple[any, dict]:
        if isinstance(v, Styled):
            return v.__value, v.__style
        else:
            return v, None

class Column:
    def __init__(self, get_value, size: int, format: str = None, name: str = '', *, span: int = 1) -> None:
        self.__get_value = get_value
        size = max(size, len(name))
        self.__size = size
        align = get_align_of(format)
        if size == 0:
            raise ValueError(f'Invalid {size=}')
        self.__format = f'{{:{align}{size}.{size}}}'
        self.__value_format = format
        self.__name = name
        self.__span = span

    def get_align(self) -> str:
        return get_align_of(self.__value_format)

    def get_value(self, *args) -> any:
        if callable(self.__get_value):
            return self.__get_value(*args)
        else:
            return self.__get_value

    def get_str(self, *args) -> str:
        if self.__value_format is not None:
            value, style = Styled.unwrap(self.get_value(*args))
            if isinstance(value, tuple):
                ss = self.__value_format.format(*value)
            else:
                ss = self.__value_format.format(value)
            return Styled.wrap(ss, style)
        else:
            return self.get_value(*args)

    @property
    def size(self):
        return self.__size

    @property
    def span(self):
        return self.__span

    @property
    def format(self):
        return self.__format
    
    def format_for(self, size: int) -> str:
        align = get_align_of(self.__format)
        return f'{{:{align}{size}.{size}}}'

    @property
    def name(self):
        return self.__name


def get_column_sizes(*rows: List[Column]) -> tuple[List[int]]:
    sizes = None
    for row in rows:
        if isinstance(row, Separater):
            continue
        cnt = reduce(lambda cnt, col: cnt+col.span, row, 0)
        if sizes is None:
            sizes = [None] * cnt
        elif len(sizes) != cnt:
            raise ValueError(f'InvalidColumnCount({len(sizes)}!={cnt})')

    constraints = {}
    for row in rows:
        if isinstance(row, Separater):
            continue
        idx = 0
        for col in row:
            if col.span == 1:
                sizes[idx] = max(col.size, sizes[idx] or 0)
            else:
                ckey = (idx, col.span)
                constraints[ckey] = max(constraints.get(ckey, 0), col.size)
            idx += col.span

    constraints_map: dict[int,list] = {}
    for (start, span), size in constraints.items():
        filled = reduce(
            lambda s, c: s+(c is not None),
            sizes[start:start+span], 0)
        reserved = reduce(
            lambda s, c: s+(c or 0),
            sizes[start:start+span], 0) + (span-1)*3

        if filled == span:
            if reserved >= size:
                continue
            new_size = size - reserved
            constraint = [start, span, new_size]
            for idx in range(start, start+span):
                constraints_map.setdefault(idx, [])
                constraints_map[idx].append(constraint)
        else:
            new_size = size - reserved
            new_cols = span - filled
            new_base = new_size // new_cols
            ex_cnt = new_size % new_cols

            for idx in range(start, start+span):
                if sizes[idx] is not None:
                    continue
                sizes[idx] = new_base
                if ex_cnt > 0:
                    sizes[idx] += 1
                    ex_cnt -= 1

    # To minimize total columns, it expands the columns with maximum
    # count of constraints by the same size. Then repeat it until
    # there is no constraints to handle.

    cons_by_col = list(constraints_map.items())
    cons_by_col.sort(key=lambda c: len(c[1]), reverse=True)
    while len(cons_by_col) > 0:
        # fetch items with same depth
        depth = len(cons_by_col[0][1])
        group = list(filter(lambda c: len(c[1]) == depth, cons_by_col))
        del cons_by_col[0:len(group)]

        # get minimum average column size to expand
        size = math.ceil(min([
            min(map(lambda con: con[2]/con[1], cons)) for _, cons in group
        ]))

        # expand columns as possible as much
        for idx, cons in group:
            sizes[idx] += size
            ncons = []
            for con in cons:
                con[2] -= size
                if con[2] > 0:
                    ncons.append(con)
            if len(ncons) > 0:
                cons_by_col.append((idx, ncons))

        cons_by_col.sort(key=lambda c: len(c[1]), reverse=True)

    size_db = []
    for row in rows:
        if isinstance(row, Separater):
            size_db.append(None)
            continue
        idx = 0
        row_sizes = []
        for col in row:
            size = sum(sizes[idx:idx+col.span]) + (col.span-1)*3
            row_sizes.append(size)
            idx += col.span
        size_db.append(row_sizes)
    return size_db

class Printer(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def print_data(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def print_separater(self, **kwargs):
        pass

    @abc.abstractmethod
    def print_header(self):
        pass

class Separater:
    def __init__(self, **kwargs):
        self.__style = kwargs

    @property
    def style(self) -> dict:
        return self.__style

class SeparatorPrinter(Printer):
    def __init__(self, printer: Printer, sep: "Separater") -> None:
        if printer is None:
            raise ValueError(f'InvalidPrinter({printer})')
        self.__printer = printer
        self.__separator = sep
    
    def print_header(self):
        pass

    def print_data(self, *args, **kwargs):
        self.__printer.print_separater(**self.__separator.style, **kwargs)

    def print_separater(self, **kwargs):
        return self.__printer.print_separater(**kwargs)


RowFormat = Union[List[Column],Separater]

class MultiRowPrinter(Printer):
    def __init__(self, rows: List[RowFormat], file=sys.stdout) -> None:
        if len(rows) == 0:
            raise ValueError(f'InvalidRowCount({len(rows)})')
        size_db = get_column_sizes(*rows)
        self.__printers: list[Printer] = []
        self.__primary = None
        for idx, row in enumerate(rows):
            if isinstance(row, Separater):
                printer = SeparatorPrinter(self.__primary, row)
            else:
                printer = RowPrinter(row, size_db[idx], file)
                if self.__primary is None:
                    self.__primary = printer
            self.__printers.append(printer)
        if self.__primary is None:
            raise ValueError(f'NoPrimaryRow')

    def print_header(self):
        self.__primary.print_header()

    def print_data(self, *args, **kwargs):
        for p in self.__printers:
            p.print_data(*args, **kwargs)

    def print_separater(self, **kwargs):
        return self.__primary.print_separater(**kwargs)


class RowPrinter:
    def __init__(self, columns: List[Column], sizes: List[int]=None, file=sys.stdout) -> None:
        formats = []
        seps = []
        names = []
        for idx, column in enumerate(columns):
            if sizes is None:
                size = column.size
                format = column.format
            else:
                size = sizes[idx]
                format = column.format_for(size)
            formats.append(format)
            seps.append('-'*size)
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

    def print_custom(self, cols: list[Column], *args, **kwargs):
        row = []
        for col in cols:
            row.append((col.span, col.get_str(*args), col.get_align()))
        self.print_row(row, **kwargs)

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
            spanned -= 3
            idx += size
            align = get_align_of(align)
            formats.append(f'{{:{align}{spanned}.{spanned}}}')
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
            value, style = Styled.unwrap(row.get_str(*args))
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
                value_style = style if len(kwargs) == 0 else None

                name = row.name
                texts = value.splitlines(True)
                lines = []
                for text in texts:
                    text_lines = textwrap.wrap(text, self.__max_value)
                    lines += text_lines
                while len(lines) > 0:
                    line = Styled.wrap(lines.pop(0), value_style)
                    kwargs_line = dict(**kwargs)
                    if len(lines) > 0 and 'underline' in kwargs_line:
                        kwargs_line.pop('underline')

                    click.secho(
                        format_str.format(name, line),
                        file = self.__file,
                        **kwargs_line)
                    name = ''
        return self
