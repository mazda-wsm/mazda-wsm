from dataclasses import dataclass
from io import StringIO

from bs4.element import NavigableString, Tag
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

    @classmethod
    def blank(cls):
        return cls(colspan=0, rowspan=0, size=0, text="")

class Grid:
    def __init__(self):
        self._cells: list[list[Cell]] = [[]]

    @property
    def empty(self):
        return len(self._cells) == 0 or len(self._cells[0]) == 0

    @property
    def col_count(self):
        return len(self._cells[0])

    @property
    def row_count(self):
        return len(self._cells)

    def _add_column(self) -> None:
        for row in self._cells:
            row.append(Cell.blank())

    def _add_row(self) -> None:
        self._cells.append([Cell.blank() for _ in range(self.col_count)])

    def cell(self, row: int, col: int) -> Cell:
        while row >= self.row_count:
            self._add_row()

        while col >= self.col_count:
            self._add_column()

        return self._cells[row][col]

    def set(self, row: int, col: int, cell: Cell) -> None:
        while row >= self.row_count:
            self._add_row()

        while col >= self.col_count:
            self._add_column()

        self._cells[row][col] = cell

class TableConverter(MarkdownConverter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_row: int = 0
        self._current_col: int = 0
        self._current_table: Grid = Grid()

    def convert_table(self, el, text, parent_tags):
        if 'table' in parent_tags or not self._current_table.col_count:
            text = text.strip().strip('|')

            if '|' not in text:
                self._reset_table()
                return text

            raise NotImplementedError("Nested tables are not supported")

        column_sizes = []
        for col in range(self._current_table.col_count):
            max_col_size = 0
            for row in range(self._current_table.row_count):
                if self._current_table.cell(row, col).size > max_col_size:
                    max_col_size = self._current_table.cell(row, col).size
            column_sizes.append(max_col_size)

        result = StringIO()
        for row in range(self._current_table.row_count):
            data_line = ''
            top_border = ''
            bottom_border = ''

            for col in range(self._current_table.col_count):
                cell = self._current_table.cell(row, col)
                if not cell.spans_left:
                    data_line     += '|' + cell.text.ljust(column_sizes[col])
                    top_border    += '+' + '-' * column_sizes[col]
                    bottom_border += '+' + '-' * column_sizes[col]
                else:
                    data_line   += ' ' * (column_sizes[col] + 1)
                    top_border  += '-' * (column_sizes[col] + 1)

                    if row < self._current_table.row_count - 1 and not self._current_table.cell(row + 1, col).spans_left:
                        bottom_border += '+' + '-' * column_sizes[col]
                    else:
                        bottom_border += '-' * (column_sizes[col] + 1)

            data_line     += '|'
            top_border    += '+'
            bottom_border += '+'

            if row == 0:
                print(top_border, file=result)
                if self._current_table.row_count > 1:
                    bottom_border = bottom_border.replace('-', '=')
            print(data_line, file=result)
            print(bottom_border, file=result)

        self._reset_table()

        return '\n\n' + result.getvalue()

    def _convert_cell(self, el, text):
        colspan = rowspan = 1
        if 'colspan' in el.attrs and el['colspan'].isdigit():
            colspan = int(el['colspan'])
        if 'rowspan' in el.attrs and el['rowspan'].isdigit():
            rowspan = int(el['rowspan'])
        text = ' ' + text.strip().replace('\n', ' ') + ' '

        while self._current_table.cell(self._current_row, self._current_col).spans_up:
            self._current_col += 1

        self._current_table.set(self._current_row, self._current_col, Cell(colspan, rowspan, len(text), text))

        for i in range(1, colspan):
            self._current_table.cell(self._current_row, self._current_col + i).spans_left = True

        for i in range(1, rowspan):
            self._current_table.cell(self._current_row + i, self._current_col).spans_up = True

        self._current_col += colspan
        return text

    def convert_td(self, el, text, parent_tags):
        return self._convert_cell(el, text)

    def convert_th(self, el, text, parent_tags):
        return self._convert_cell(el, text)

    def convert_tr(self, el, text, parent_tags):
        self._current_row += 1
        self._current_col = 0
        return '|' + text + '\n'

    def convert_a(self, el, text, parent_tags):
        if el.get('href'):
            return super().convert_a(el, text, parent_tags)
        elif name := el.get('name'):
            if not el.next_sibling:
                return super().convert_a(el, f'{{: #{name}}}', parent_tags)
            else:
                while el.next_sibling:
                    el = el.next_sibling
                    if isinstance(el, NavigableString):
                        continue

                    if el.get_text().strip():
                        break

                    if [1 for descendant in el.descendants if isinstance(descendant, Tag) and descendant.name in ["img"]]:
                        break
                else:
                    return f'[](){{: id="{name}"}}'

                el.insert(1, Tag(name="a", attrs={"name": name}))
                return ""
        else:
            raise NotImplementedError(f"Anchor without `href` or `name` found!")

    def _reset_table(self):
        self._current_row = 0
        self._current_col = 0
        self._current_table = Grid()

    def convert(self, html):
        self._reset_table()
        return super().convert(html)
