"""Local LaTeX-to-PDF compiler helpers."""

import asyncio
import base64
import binascii
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen

from .exceptions import CompilationError

_DEFAULT_COMPILER = os.getenv("LATEX_COMPILER_ENGINE", "pdflatex")
_DEFAULT_TIMEOUT_SECONDS = 12.0
_DEFAULT_COMPILE_DIR_NAME = "latex-bot"
_COMPILE_DIR_ENV_VARS = ("LATEX_COMPILE_DIR", "TMPDIR")
_MAIN_TEX_FILENAME = "main.tex"
_MAIN_PDF_FILENAME = "main.pdf"
_MAIN_LOG_FILENAME = "main.log"
_ERROR_PREFIX = "Compilation failed with error logs:"


class LatexCompiler:
    """Compile LaTeX source into PDF bytes using a local TeX engine."""

    api_url: str
    compile_dir: Path
    timeout: float

    def __init__(
            self,
            api_url: str = "",
            compile_dir: str | os.PathLike[str] | None = None,
            timeout: float | None = None,
    ):
        # Keep api_url for backward compatibility with older call sites.
        self.api_url = api_url
        self.compile_dir = Path(compile_dir) if compile_dir else _resolve_compile_dir()
        self.timeout = timeout if timeout is not None else _resolve_timeout()

    def compile(
            self,
            latex_code,
            images: Optional[list[tuple[str, str]]] = None,
            compiler="pdflatex",
    ):
        """Compile LaTeX code and return the resulting PDF bytes."""
        compiler = compiler or _DEFAULT_COMPILER
        working_dir = Path(
            tempfile.mkdtemp(prefix="latex-", dir=self._ensure_compile_dir())
        )

        try:
            (working_dir / _MAIN_TEX_FILENAME).write_text(
                latex_code,
                encoding="utf-8",
            )
            self._write_resources(working_dir, images or [])
            self._run_compiler(compiler, working_dir)

            pdf_path = working_dir / _MAIN_PDF_FILENAME
            if not pdf_path.exists():
                raise CompilationError(
                    _format_compilation_error(
                        summary="Compiler completed without producing a PDF.",
                        working_dir=working_dir,
                    )
                )

            return pdf_path.read_bytes()
        finally:
            shutil.rmtree(working_dir, ignore_errors=True)

    def _ensure_compile_dir(self) -> str:
        self.compile_dir.mkdir(parents=True, exist_ok=True)
        return str(self.compile_dir)

    def _write_resources(
            self,
            working_dir: Path,
            images: list[tuple[str, str]],
    ) -> None:
        for relative_path, content in images:
            output_path = _resolve_resource_path(working_dir, relative_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(self._resolve_resource_bytes(content))

    def _resolve_resource_bytes(self, content: str | bytes | os.PathLike[str]) -> bytes:
        if isinstance(content, bytes):
            return content

        if isinstance(content, os.PathLike):
            content = os.fspath(content)

        if not isinstance(content, str):
            raise CompilationError(
                _format_compilation_error(
                    summary=f"Unsupported resource content type: {type(content)!r}.",
                    working_dir=None,
                )
            )

        if content.startswith(("http://", "https://")):
            try:
                with urlopen(content, timeout=self.timeout) as response:
                    return response.read()
            except URLError as exc:
                raise CompilationError(
                    _format_compilation_error(
                        summary=f"Failed to download resource: {content}",
                        working_dir=None,
                        stderr=str(exc),
                    )
                ) from exc

        source_path = Path(content)
        if source_path.is_file():
            return source_path.read_bytes()

        try:
            return base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError):
            return content.encode("utf-8")

    def _run_compiler(self, compiler: str, working_dir: Path) -> None:
        command = [
            compiler,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "-no-shell-escape",
            f"-output-directory={working_dir}",
            _MAIN_TEX_FILENAME,
        ]
        popen_kwargs = {
            "cwd": str(working_dir),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = getattr(
                subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                0,
            )
        else:
            popen_kwargs["start_new_session"] = True

        try:
            process = subprocess.Popen(command, **popen_kwargs)
        except FileNotFoundError as exc:
            raise CompilationError(
                _format_compilation_error(
                    summary=f"Compiler executable '{compiler}' was not found.",
                    working_dir=None,
                    stderr=str(exc),
                )
            ) from exc

        try:
            stdout, stderr = process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            self._terminate_process_group(process)
            raise CompilationError(
                _format_compilation_error(
                    summary=f"Compiler '{compiler}' timed out after {self.timeout:.1f}s.",
                    working_dir=working_dir,
                    stdout=exc.stdout,
                    stderr=exc.stderr,
                )
            ) from exc

        if process.returncode != 0:
            raise CompilationError(
                _format_compilation_error(
                    summary=f"Compiler '{compiler}' exited with return code {process.returncode}.",
                    working_dir=working_dir,
                    stdout=stdout,
                    stderr=stderr,
                )
            )

    def _terminate_process_group(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return

        if os.name == "nt":
            ctrl_break_event = getattr(signal, "CTRL_BREAK_EVENT", None)
            if ctrl_break_event is not None:
                try:
                    process.send_signal(ctrl_break_event)
                    process.wait(timeout=1)
                except Exception:
                    pass
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            return

        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return

        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


class AsyncLatexCompiler(LatexCompiler):
    """Asynchronous wrapper around the local compiler."""

    def __init__(
            self,
            api_url: str = "",
            compile_dir: str | os.PathLike[str] | None = None,
            timeout: float | None = None,
    ):
        super().__init__(api_url=api_url, compile_dir=compile_dir, timeout=timeout)

    def compile(
            self,
            latex_code,
            images: list[tuple[str, str]] | None = None,
            compiler="pdflatex",
    ):
        """DON'T USE THIS METHOD. USE `acompile` INSTEAD."""
        raise NotImplementedError("Use acompile instead.")

    async def acompile(
            self,
            latex_code,
            images: Optional[list[tuple[str, str]]] = None,
            compiler="pdflatex",
    ):
        """Asynchronous version of the local compile method."""
        return await asyncio.to_thread(
            super().compile,
            latex_code,
            images,
            compiler,
        )


def _resolve_compile_dir() -> Path:
    for env_var in _COMPILE_DIR_ENV_VARS:
        value = os.getenv(env_var)
        if value:
            return Path(value)
    return Path(tempfile.gettempdir()) / _DEFAULT_COMPILE_DIR_NAME


def _resolve_timeout() -> float:
    raw_timeout = os.getenv("LATEX_COMPILER_TIMEOUT")
    if not raw_timeout:
        return _DEFAULT_TIMEOUT_SECONDS

    try:
        timeout = float(raw_timeout)
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS

    return timeout if timeout > 0 else _DEFAULT_TIMEOUT_SECONDS


def _resolve_resource_path(working_dir: Path, relative_path: str) -> Path:
    output_path = (working_dir / relative_path).resolve()
    try:
        output_path.relative_to(working_dir.resolve())
    except ValueError as exc:
        raise CompilationError(
            _format_compilation_error(
                summary=f"Invalid resource path: {relative_path}",
                working_dir=None,
            )
        ) from exc
    return output_path


def _format_compilation_error(
        summary: str,
        working_dir: Path | None,
        stdout: str | bytes | None = None,
        stderr: str | bytes | None = None,
) -> str:
    sections = [summary]

    normalized_stdout = _normalize_output(stdout)
    if normalized_stdout:
        sections.extend(["[stdout]", normalized_stdout])

    normalized_stderr = _normalize_output(stderr)
    if normalized_stderr:
        sections.extend(["[stderr]", normalized_stderr])

    if working_dir is not None:
        log_path = working_dir / _MAIN_LOG_FILENAME
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="replace").strip()
            if log_text:
                sections.extend(["[main.log]", log_text])

    joined_sections = "\n".join(section for section in sections if section)
    return f"{_ERROR_PREFIX} {joined_sections}"


def _normalize_output(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace").strip()
    return str(output).strip()
