"""Shared response envelopes and error shape (spec's API contract).

Lists use ``PagedEnvelope`` (``data`` + ``meta``); single items use ``Envelope`` (``data``).
Errors use ``ErrorResponse`` (``error.code`` + ``error.message``).
"""

from pydantic import BaseModel


class Meta(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool


class Envelope[T](BaseModel):
    data: T


class PagedEnvelope[T](BaseModel):
    data: list[T]
    meta: Meta


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
