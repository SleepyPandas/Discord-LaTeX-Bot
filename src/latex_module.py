import re

from sympy import preview

from Modified_Packages import Latex2PNG


# Should Fork or was it pork :)


def text_to_latex(expr: str, output_file: str, dpi=1000) -> bool | str:
    """
    Converts a text to LaTeX png
    returning a str if it succeeds, False otherwise.

    Precondition: The text must be properly formatted in LaTeX.

    Attributes:
     expr: str
     output_file: str
     dpi=(1000 , optional) int | sets resolution
    """

    # TODO : /Nodes has strange interaction with preview() from sympy
    # TODO : Consider using Latex2PNG from tex2img to replace all of sympy preview()

    # Latex2Png requires a full document structure a solution
    # is to always add a \begin and document class and load a standard set of packages
    #

    if len(expr) > 2000:
        return "Too Complex"

    if r"\documentclass" in expr and r"\begin{tikzpicture}" in expr:
        latex_code = expr.replace(r"\documentclass{article}", r'\documentclass[border=1mm]{standalone} ')
        if 'latex' in latex_code:
            latex_code = latex_code.replace('latex', '', 1)
        renderer = Latex2PNG()
        try:
            png_data = renderer.compile(latex_code, transparent=False, compiler='pdflatex', dpi=dpi)
        except Exception as log:
            print(f'Failed to convert text to LaTeX: {log}')
            return "Failed to Compile Unknown Error 💀💀💀 or Unsupported code \n if using '/' commands remove comments"

        # Convert png_data to bytes
        if isinstance(png_data, list):
            try:
                png_bytes = b''.join(png_data)
            except TypeError:
                print("Error: png_data list contains non-bytes items.")
                png_bytes = b''.join([item if isinstance(item, bytes) else b'' for item in png_data])
        elif isinstance(png_data, bytes):
            png_bytes = png_data
        else:
            raise TypeError("png_data is neither a list nor bytes.")

        # Write to file
        with open(output_file + '.png', 'wb') as f:
            f.write(png_bytes)

        print("PNG generated: output.png")
        return True
    else:
        expr = remove_superfluous(expr)

        extra_preamble = "\\usepackage{xcolor, pagecolor, amsmath, amssymb, amsthm}\n" \
                         "\\definecolor{customtext}{HTML}{FFFFFF}\n" \
                         "\\color{customtext}\n"

        dvioptions = '-D', str(dpi), '-bg', 'Transparent'

        # Set custom name for file

        output_file = f"{output_file}.png"

        try:
            preview(expr,
                    viewer='file',
                    filename=output_file,
                    output='png',
                    euler=False,
                    fontsize=14,
                    dvioptions=dvioptions,
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
                return "Failed to Compile Unknown Error 💀💀💀 or Unsupported code"


def find_latex_error(error_log: str | Exception | bytes) -> str:
    """
    Will take an exception error, and parse the error into a str

    -NOTE- | Attributes are str, exception and bytes
    for different operating system compatability issues

    Attributes
        error_log: str | Exception | bytes
    """
    if isinstance(error_log, Exception):
        error_log = str(error_log)
    elif isinstance(error_log, bytes):
        error_log = error_log.decode("utf-8")
    error_log = error_log.replace("\\r\\n", "\n")
    error_log = error_log.replace("\\n", "\n")
    # OR splitlines()
    for line in error_log.split("\n"):
        # Strip leading/trailing whitespace
        stripped_line = line.strip()
        # Check if it starts with '!' and ends with '.'
        if stripped_line.startswith('!') and stripped_line.endswith('.'):
            return stripped_line
    return ""


def remove_superfluous(expr: str) -> str:
    """
    Takes a raw expression string and removes
    specified strings or uses alternate LaTeX syntax for
    compatability

    Attributes
        expr: str

    """

    # Remove any comments
    # Remove any latex str
    # Replace  \fill[blue] with \draw[fill=blue]

    if 'latex' in expr:
        expr = expr.replace('latex', '', 1)
        expr = expr.replace(r'\maketitle', "")
        expr = expr.replace(r'\author', r'\bf')
        expr = expr.replace(r'\title', r'\bf')

    if r'\fill' in expr:
        expr = expr.replace(r'\fill[', r'\draw[fill=')

    return expr
