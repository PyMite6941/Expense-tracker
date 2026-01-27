# Generates a syntax-highlighted PDF of the project code using Catppuccin Mocha theme
# Usage: python generate_pdf.py

from fpdf import FPDF
from fpdf.enums import XPos, YPos
import pygments
from pygments.lexers import PythonLexer
from pygments.token import Token

lexer = PythonLexer()

# Catppuccin Mocha
BG = (30, 30, 46)
COLORS = {
    Token.Keyword: (203, 166, 247),          # Mauve
    Token.Keyword.Constant: (209, 154, 102), # Peach
    Token.Keyword.Namespace: (203, 166, 247),# Mauve
    Token.Name.Function: (137, 180, 250),    # Blue
    Token.Name.Function.Magic: (137, 180, 250),
    Token.Name.Class: (249, 226, 175),       # Yellow
    Token.Name.Decorator: (249, 226, 175),   # Yellow
    Token.Name.Builtin: (249, 226, 175),     # Yellow
    Token.Name.Builtin.Pseudo: (243, 139, 168), # Red
    Token.Literal.String: (166, 227, 161),   # Green
    Token.Literal.String.Single: (166, 227, 161),
    Token.Literal.String.Double: (166, 227, 161),
    Token.Literal.String.Doc: (108, 112, 134),# Overlay0
    Token.Literal.String.Affix: (203, 166, 247),
    Token.Literal.String.Interpol: (250, 179, 135),
    Token.Literal.String.Escape: (148, 226, 213), # Teal
    Token.Literal.Number: (250, 179, 135),   # Peach
    Token.Literal.Number.Integer: (250, 179, 135),
    Token.Literal.Number.Float: (250, 179, 135),
    Token.Comment: (108, 112, 134),          # Overlay0
    Token.Comment.Single: (108, 112, 134),
    Token.Operator: (137, 220, 235),         # Sky
    Token.Operator.Word: (203, 166, 247),    # Mauve
    Token.Punctuation: (180, 190, 254),      # Lavender
    Token.Name: (205, 214, 244),             # Text
    Token.Text: (205, 214, 244),             # Text
}

FONT_SIZE = 8
LINE_H = 3.5

SOURCE_FILES = [
    ("main.py", "main.py"),
    ("menu.py", "menu.py"),
]
OUTPUT_FILE = "program_code.pdf"


def get_color(ttype):
    while ttype:
        if ttype in COLORS:
            return COLORS[ttype]
        ttype = ttype.parent
    return (205, 214, 244)


class CodePDF(FPDF):
    def header(self):
        self.set_fill_color(*BG)
        self.rect(0, 0, 216, 280, 'F')

    def footer(self):
        self.set_y(-12)
        self.set_font('Courier', '', 7)
        self.set_text_color(108, 112, 134)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')


def generate():
    pdf = CodePDF('P', 'mm', 'Letter')
    pdf.set_auto_page_break(auto=True, margin=14)

    for filepath, label in SOURCE_FILES:
        with open(filepath, 'r') as f:
            code = f.read()

        pdf.add_page()
        pdf.set_xy(10, 10)
        pdf.set_font('Courier', 'B', 11)
        pdf.set_text_color(137, 180, 250)
        pdf.cell(0, 6, f'// {label}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_xy(10, 18)

        pdf.set_font('Courier', '', FONT_SIZE)
        tokens = list(pygments.lex(code, lexer))

        line_num = 1
        x_start = 10
        num_w = pdf.get_string_width('0000  ')

        pdf.set_text_color(108, 112, 134)
        pdf.set_xy(x_start, pdf.get_y())
        pdf.cell(num_w, LINE_H, f'{line_num:>4}  ')
        pdf.set_xy(x_start + num_w, pdf.get_y())

        for ttype, value in tokens:
            lines = value.split('\n')
            for i, part in enumerate(lines):
                if i > 0:
                    line_num += 1
                    pdf.ln(LINE_H)
                    if pdf.get_y() > 266:
                        pdf.add_page()
                        pdf.set_xy(10, 10)
                        pdf.set_font('Courier', '', FONT_SIZE)
                    pdf.set_text_color(108, 112, 134)
                    pdf.set_xy(x_start, pdf.get_y())
                    pdf.cell(num_w, LINE_H, f'{line_num:>4}  ')
                    pdf.set_xy(x_start + num_w, pdf.get_y())

                if part:
                    safe = part.encode('latin-1', errors='replace').decode('latin-1')
                    r, g, b = get_color(ttype)
                    pdf.set_text_color(r, g, b)
                    w = pdf.get_string_width(safe)
                    pdf.cell(w, LINE_H, safe)

    pdf.output(OUTPUT_FILE)
    print(f'PDF saved to {OUTPUT_FILE}')


if __name__ == '__main__':
    generate()
