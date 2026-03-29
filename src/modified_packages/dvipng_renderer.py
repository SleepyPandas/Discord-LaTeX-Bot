"""Fast inline LaTeX renderer using latex -> DVI -> dvipng."""

import subprocess
import sys
import tempfile
from pathlib import Path

from .exceptions import CompilationError
from .latex_compiler import (
    LatexCompiler,
    _MAIN_TEX_FILENAME,
    _format_compilation_error,
)

_MAIN_DVI_FILENAME = "main.dvi"
_OUTPUT_PATTERN = "output%d.png"


class InlineDviPngRenderer(LatexCompiler):
    """Compile conservative inline LaTeX directly to PNG bytes."""

    def compile(
            self,
            latex_code,
            images: list[tuple[str, str]] | None = None,
            transparent: bool = False,
            dpi: int = 300,
    ) -> bytes:
        working_dir = Path(
            tempfile.mkdtemp(prefix="latex-", dir=self._ensure_compile_dir())
        )

        try:
            (working_dir / _MAIN_TEX_FILENAME).write_text(
                latex_code,
                encoding="utf-8",
            )
            self._write_resources(working_dir, images or [])
            self._run_compiler("latex", working_dir)

            dvi_path = working_dir / _MAIN_DVI_FILENAME
            if not dvi_path.exists():
                raise CompilationError(
                    _format_compilation_error(
                        summary="Compiler completed without producing a DVI.",
                        working_dir=working_dir,
                    )
                )

            self._run_dvipng(working_dir, transparent=transparent, dpi=dpi)

            png_paths = sorted(working_dir.glob("output*.png"))
            if not png_paths:
                raise CompilationError(
                    _format_compilation_error(
                        summary="dvipng completed without producing a PNG.",
                        working_dir=working_dir,
                    )
                )

            return png_paths[0].read_bytes()
        finally:
            self._cleanup_working_dir(working_dir)

    def _run_dvipng(self, working_dir: Path, transparent: bool, dpi: int) -> None:
        background = "Transparent" if transparent else "White"
        command = [
            "dvipng",
            "-T",
            "tight",
            "-bg",
            background,
            "-D",
            str(dpi),
            "-o",
            _OUTPUT_PATTERN,
            _MAIN_DVI_FILENAME,
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
                    summary="Renderer executable 'dvipng' was not found.",
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
                    summary=f"Renderer 'dvipng' timed out after {self.timeout:.1f}s.",
                    working_dir=working_dir,
                    stdout=exc.stdout,
                    stderr=exc.stderr,
                )
            ) from exc
        finally:
            if process.poll() is None:
                self._terminate_process_group(process)

        if process.returncode != 0:
            raise CompilationError(
                _format_compilation_error(
                    summary=f"Renderer 'dvipng' exited with return code {process.returncode}.",
                    working_dir=working_dir,
                    stdout=stdout,
                    stderr=stderr,
                )
            )
