# app/streams.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import Request

from app.constants import FILE_CHUNK_SIZE_BYTES
from app.errors import (
    S3ObjektBodyIncompleteError,
    S3ObjektTooLargeError,
)
from app.repositories.file import AsyncReadable

# NOTE (ADR-25): S3 upload bodies are decoded from aws-chunked framing.
# AWS SDKs and the AWS CLI stream PutObject bodies as sized frames
# carrying an optional chunk signature and trailing headers, announced
# by Content-Encoding: aws-chunked or by a STREAMING- payload marker in
# x-amz-content-sha256. Only the payload inside the frames is stored,
# and the declared object size is read from
# x-amz-decoded-content-length.

_AWS_CHUNKED_ENCODING = "aws-chunked"
_STREAMING_PAYLOAD_PREFIX = "STREAMING-"
_CHUNK_LINE_MAX_BYTES = 8 * 1024


def build_body_reader(
    request: Request,
    max_bytes: int,
    resource: str | None = None,
) -> AsyncReadable:
    """
    Build a reader over the body of an incoming request, unwrapping
    aws-chunked framing when the client streams the upload.
    """
    reader = RequestBodyReader(
        request,
        max_bytes=max_bytes,
        resource=resource,
    )

    if not _is_aws_chunked(request):
        return reader

    return AwsChunkedReader(reader, resource=resource)


def _is_aws_chunked(request: Request) -> bool:
    """Return whether the request body carries aws-chunked framing."""
    encoding = request.headers.get("content-encoding", "")
    if _AWS_CHUNKED_ENCODING in encoding.lower():
        return True

    payload_hash = request.headers.get("x-amz-content-sha256", "")
    return payload_hash.startswith(_STREAMING_PAYLOAD_PREFIX)


class RequestBodyReader:
    """
    Async reader over the body of an incoming request. Provides the
    read interface expected by the file repository and rejects bodies
    larger than the allowed maximum, both by the declared body length
    and by the bytes actually received.
    """

    def __init__(
        self,
        request: Request,
        max_bytes: int,
        resource: str | None = None,
    ) -> None:
        self._stream = request.stream().__aiter__()
        self._buffer = bytearray()
        self._exhausted = False
        self._received = 0
        self._max_bytes = max_bytes
        self._resource = resource

        self._assert_declared_length(request)

    async def read(self, size: int = -1) -> bytes:
        """
        Return up to size bytes of the body, or the whole remaining
        body when size is negative. An empty result means the body
        has been consumed completely.
        """
        while not self._exhausted and (
            size < 0 or len(self._buffer) < size
        ):
            await self._receive()

        if size < 0:
            data = bytes(self._buffer)
            self._buffer.clear()
            return data

        data = bytes(self._buffer[:size])
        del self._buffer[:size]

        return data

    async def _receive(self) -> None:
        """
        Pull the next chunk from the request stream into the buffer.
        """
        try:
            chunk = await anext(self._stream)
        except StopAsyncIteration:
            self._exhausted = True
            return

        self._received += len(chunk)

        if self._received > self._max_bytes:
            raise S3ObjektTooLargeError(self._resource)

        self._buffer.extend(chunk)

    def _assert_declared_length(self, request: Request) -> None:
        """
        Reject an oversized body before reading it. Chunked uploads
        declare the object size in x-amz-decoded-content-length; other
        uploads declare it in Content-Length. A missing or malformed
        header is ignored, since received bytes are counted anyway.
        """
        header = request.headers.get("x-amz-decoded-content-length")

        if header is None:
            header = request.headers.get("content-length")

        if header is None or not header.isdigit():
            return

        if int(header) > self._max_bytes:
            raise S3ObjektTooLargeError(self._resource)


class AwsChunkedReader:
    """
    Async reader that strips aws-chunked framing from a body. Each
    frame starts with a hexadecimal size line, optionally followed by
    a chunk signature, and the final zero-sized frame may be followed
    by trailing headers. Only payload bytes are returned.
    """

    def __init__(
        self,
        source: AsyncReadable,
        resource: str | None = None,
    ) -> None:
        self._source = source
        self._resource = resource
        self._framed = bytearray()
        self._payload = bytearray()
        self._drained = False
        self._finished = False

    async def read(self, size: int = -1) -> bytes:
        """
        Return up to size bytes of payload, or the whole remaining
        payload when size is negative. An empty result means the body
        has been consumed completely.
        """
        while not self._finished and (
            size < 0 or len(self._payload) < size
        ):
            await self._decode_frame()

        if size < 0:
            data = bytes(self._payload)
            self._payload.clear()
            return data

        data = bytes(self._payload[:size])
        del self._payload[:size]

        return data

    async def _decode_frame(self) -> None:
        """Decode the next frame into the payload buffer."""
        line = await self._read_line()

        if line is None:
            self._finished = True
            return
        if not line:
            return

        size = self._parse_frame_size(line)

        if size == 0:
            await self._skip_trailer()
            self._finished = True
            return

        self._payload.extend(await self._read_exact(size))
        await self._read_exact(len(b"\r\n"))

    def _parse_frame_size(self, line: bytes) -> int:
        """Parse the frame size from its size line."""
        header = line.split(b";", 1)[0].strip()

        try:
            return int(header, 16)
        except ValueError as exc:
            raise S3ObjektBodyIncompleteError(self._resource) from exc

    async def _skip_trailer(self) -> None:
        """Consume the trailing headers after the final frame."""
        while True:
            line = await self._read_line()

            if not line:
                return

    async def _read_line(self) -> bytes | None:
        """
        Return the next CRLF-terminated line without its terminator,
        or None once the framed body ends.
        """
        while True:
            index = self._framed.find(b"\r\n")

            if index >= 0:
                line = bytes(self._framed[:index])
                del self._framed[:index + 2]
                return line

            if len(self._framed) > _CHUNK_LINE_MAX_BYTES:
                raise S3ObjektBodyIncompleteError(self._resource)

            if not await self._receive():
                if self._framed:
                    raise S3ObjektBodyIncompleteError(self._resource)
                return None

    async def _read_exact(self, count: int) -> bytes:
        """Return exactly count bytes of the framed body."""
        while len(self._framed) < count:
            if not await self._receive():
                raise S3ObjektBodyIncompleteError(self._resource)

        data = bytes(self._framed[:count])
        del self._framed[:count]

        return data

    async def _receive(self) -> bool:
        """
        Pull the next chunk from the source into the framed buffer.
        Returns whether the source produced more data.
        """
        if self._drained:
            return False

        chunk = await self._source.read(FILE_CHUNK_SIZE_BYTES)

        if not chunk:
            self._drained = True
            return False

        self._framed.extend(chunk)

        return True
