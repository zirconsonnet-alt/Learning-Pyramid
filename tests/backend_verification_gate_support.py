from pathlib import Path
from contextlib import contextmanager
from tempfile import TemporaryDirectory
from typing import Iterator


class TemporaryWorkspace:
    def __enter__(self) -> Path:
        self._tmp = TemporaryDirectory()
        return Path(self._tmp.name)

    def __exit__(self, exc_type, exc, tb) -> None:
        self._tmp.cleanup()


@contextmanager
def temporary_workspace() -> Iterator[Path]:
    with TemporaryWorkspace() as path:
        yield path
