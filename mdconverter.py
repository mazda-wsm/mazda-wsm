import re
from dataclasses import dataclass
from io import StringIO

from markdownify import MarkdownConverter


@dataclass
class Cell:
    colspan: int
    rowspan: int
    size: int
    text: str
    spans_left: bool = False
    spans_up: bool = False

    @property
    def spans_right(self) -> bool:
        return self.colspan > 1

    @property
    def spans_down(self) -> bool:
        return self.rowspan > 1

    @classmethod
    def new(cls):
        return cls(colspan=0, rowspan=0, size=0, text="")

class TableConverter(MarkdownConverter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def convert_table(self, el, text, parent_tags):
        if 'table' in parent_tags:
            text = text.strip().strip('|')

            if '|' not in text:
                return re.sub(r"^\(\d+,\d+,\d+\)", "", text, count=1)

            raise NotImplementedError("Nested tables are not supported")

        def get_cell_metadata(cell):
            match = re.match(r"^\((?P<colspan>\d+),(?P<rowspan>\d+),(?P<size>\d+)\)(?P<value>.*)", cell)
            return Cell(
                int(match.group("colspan")),
                int(match.group("rowspan")),
                int(match.group("size")),
                match.group("value"))

        lines = text.strip().splitlines()
        rows = len(lines)
        columns = sum([get_cell_metadata(cell).colspan for cell in lines[0].strip('|').split('|')])
        cells: list[list[Cell]] = []
        for _ in range(rows):
            row = []
            for _ in range(columns):
                row.append(Cell.new())
            cells.append(row)

        row_sizes = [0] * rows
        for row, line in enumerate(lines):
            col = 0
            for cell in line.strip('|').split('|'):
                data = get_cell_metadata(cell)

                while cells[row][col].spans_up or cells[row][col].spans_left:
                    row_sizes[row] += cells[row][col].size
                    col += 1

                cells[row][col] = data
                row_sizes[row] += cells[row][col].size

                for i in range(1, data.colspan):
                    cells[row][col + i].spans_left = cells[row][col]

                for i in range(1, data.rowspan):
                    cells[row + i][col].spans_up = cells[row][col]
                    cells[row + i][col].size = cells[row][col].size

                col += 1

        column_sizes = []
        for col in range(columns):
            max_col_size = 0
            for row in range(rows):
                if cells[row][col].size > max_col_size:
                    max_col_size = cells[row][col].size
            column_sizes.append(max_col_size)

        result = StringIO()
        for row in range(rows):
            data_line = ''
            top_border = ''
            bottom_border = ''

            for col in range(columns):
                cell = cells[row][col]
                if not cell.spans_left:
                    data_line     += '|' + cell.text.ljust(column_sizes[col])
                    top_border    += '+' + '-' * column_sizes[col]
                    bottom_border += '+' + '-' * column_sizes[col]
                else:
                    data_line   += ' ' * (column_sizes[col] + 1)
                    top_border  += '-' * (column_sizes[col] + 1)

                    if row < rows - 1 and not cells[row + 1][col].spans_left:
                        bottom_border += '+' + '-' * column_sizes[col]
                    else:
                        bottom_border += '-' * (column_sizes[col] + 1)

            data_line     += '|'
            top_border    += '+'
            bottom_border += '+'

            if row == 0:
                print(top_border, file=result)
                bottom_border = bottom_border.replace('-', '=')
            print(data_line, file=result)
            print(bottom_border, file=result)

        return result.getvalue()

    @staticmethod
    def _convert_cell(el, text):
        colspan = rowspan = 1
        if 'colspan' in el.attrs and el['colspan'].isdigit():
            colspan = int(el['colspan'])
        if 'rowspan' in el.attrs and el['rowspan'].isdigit():
            rowspan = int(el['rowspan'])
        gross_value = ' ' + text.strip().replace('\n', ' ') + ' '
        return f'({colspan},{rowspan},{len(gross_value)})' + gross_value + '|'

    def convert_td(self, el, text, parent_tags):
        return self._convert_cell(el, text)

    def convert_th(self, el, text, parent_tags):
        return self._convert_cell(el, text)

    def convert_tr(self, el, text, parent_tags):
        return '|' + text + '\n'