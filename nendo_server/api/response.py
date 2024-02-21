from typing import Any

from pydantic import BaseModel


class NendoHTTPResponse(BaseModel):
    data: Any
    error: Any = None
    has_next: bool = False
    cursor: int = 0
