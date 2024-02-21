"""Utility functions used by Nendo."""
import hashlib
from typing import Any, Callable

from fastapi import APIRouter as FastAPIRouter
from fastapi.types import DecoratedCallable


# this APIRouter will allow the calling of paths with or without trailing slash
# without causing a 307 redirect (which gets stuck with some ingress controllers)
# e.g. /api/assets AND /api/assets/ will both map to the same route
# see https://github.com/tiangolo/fastapi/discussions/7298
class APIRouter(FastAPIRouter):
    def api_route(
        self,
        path: str,
        *,
        include_in_schema: bool = True,
        **kwargs: Any,
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        if path.endswith("/"):
            path = path[:-1]

        add_path = super().api_route(
            path,
            include_in_schema=include_in_schema,
            **kwargs,
        )

        alternate_path = path + "/"
        add_alternate_path = super().api_route(
            alternate_path,
            include_in_schema=False,
            **kwargs,
        )

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            add_alternate_path(func)
            return add_path(func)

        return decorator


def md5sum(file_path):
    """Compute md5 checksum of file found under the given file_path."""
    hash_md5 = hashlib.md5()  # noqa: S324
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


class AudioFileUtils:
    """Utility class for handling audio files."""

    def is_supported_filetype(self, filepath):
        """Check if the filetype of the file given as filepath is supported."""
        supported_filetypes = ["wav", "mp3", "aiff", "flac", "ogg", "m4a"]
        return filepath.lower().split(".")[-1] in supported_filetypes
