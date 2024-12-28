from typing import Union
from sympy import preview


def text_to_latex(expr: str, output_file: str, dpi=250) -> bool | str:
    """
    Converts a text to LaTeX png
    returning True if it succeeds, False otherwise.

    Precondition: The text must be properly formatted in LaTeX.

    TODO Should return different errors given:
    improper formatting or unsupported LaTeX syntax.

    """
    # TODO always returns true no matter what

    # Remove Superfluous Latex text

    if 'latex' in expr:
        expr = expr.replace('latex', '', 1)
        expr = expr.replace(r'\maketitle', "")
        expr = expr.replace(r'\author', r'\bf')
        expr = expr.replace(r'\title', r'\bf')

    # set preamble for Latex

    extra_preamble = "\\usepackage{xcolor, pagecolor, amsmath, amssymb, amsthm}\n" \
                     "\\definecolor{customtext}{HTML}{FFFFFF}\n" \
                     "\\color{customtext}"

    # Set custom name for file
    output_file = f"{output_file}.png"

    try:
        preview(expr,
                viewer='file',
                filename=output_file,
                output='png',
                euler=False,
                fontsize=15,
                dvioptions=[
                    '-D', str(dpi),
                    '-bg', 'Transparent'
                ],
                extra_preamble=extra_preamble,
                # document=False
                )
        return True
    except Exception as log:
        print(f'Failed to convert text to LaTeX: {log}')
        error = find_latex_error(log)
        if error:
            return error
        else:
            return "Failed to Compile Unknown Error 💀💀💀"


def find_latex_error(error_log: str | Exception | bytes) -> str:
    if isinstance(error_log, Exception):
        error_log = str(error_log)
    elif isinstance(error_log, bytes):
        error_log = error_log.decode("utf-8")
    error_log = error_log.replace("\\r\\n", "\n")
    error_log = error_log.replace("\\n", "\n")

    for line in error_log.split("\n"):
        # Strip leading/trailing whitespace
        stripped_line = line.strip()
        # Check if it starts with '!' and ends with '.'
        if stripped_line.startswith('!') and stripped_line.endswith('.'):
            return stripped_line
    return ""
