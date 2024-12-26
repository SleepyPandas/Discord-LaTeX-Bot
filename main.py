from sympy import preview

from latex_module import *

if __name__ == '__main__':
    expr = r'$$\int_0^1 e^x\,dx$$'
    text_to_latex(expr, "latex_image_test.png")


    # preview(r'$$\int_0^1 e^x\,dx$$', viewer='file', filename='test.png', euler=False)