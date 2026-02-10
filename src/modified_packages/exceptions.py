""" Exceptions for the compiler. """


class CompilationError(Exception):
    """ Exception raised when the compilation fails. """


class PDFInfoNotInstalledError:
    pass


class PDFPageCountError:
    pass


class PDFSyntaxError:
    pass


class PDFPopplerTimeoutError:
    pass
