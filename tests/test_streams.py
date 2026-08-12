# tests/test_streams.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import (  # noqa: E402
    S3ObjektBodyIncompleteError,
    S3ObjektTooLargeError,
)
from app.streams import (  # noqa: E402
    AwsChunkedReader,
    RequestBodyReader,
    build_body_reader,
)


class FakeRequest:
    """Minimal stand-in for a Starlette request with a body stream."""

    def __init__(
        self,
        chunks: list[bytes],
        headers: dict[str, str] | None = None,
    ) -> None:
        self._chunks = chunks
        self.headers = headers or {}

    def stream(self):
        async def iterator():
            for chunk in self._chunks:
                yield chunk

        return iterator()


class TestRequestBodyReader(unittest.IsolatedAsyncioTestCase):
    async def test_reads_requested_sizes_across_chunks(self):
        reader = RequestBodyReader(
            FakeRequest([b"abc", b"def"]),
            max_bytes=1024,
        )

        self.assertEqual(await reader.read(2), b"ab")
        self.assertEqual(await reader.read(3), b"cde")
        self.assertEqual(await reader.read(3), b"f")
        self.assertEqual(await reader.read(3), b"")

    async def test_reads_whole_body_when_size_is_negative(self):
        reader = RequestBodyReader(
            FakeRequest([b"abc", b"def"]),
            max_bytes=1024,
        )

        self.assertEqual(await reader.read(), b"abcdef")
        self.assertEqual(await reader.read(), b"")

    async def test_reads_empty_body(self):
        reader = RequestBodyReader(FakeRequest([]), max_bytes=1024)

        self.assertEqual(await reader.read(64), b"")

    async def test_rejects_body_exceeding_max_bytes(self):
        reader = RequestBodyReader(
            FakeRequest([b"abc", b"def"]),
            max_bytes=4,
            resource="/photos/cat.png",
        )

        with self.assertRaises(S3ObjektTooLargeError) as cm:
            await reader.read(64)

        self.assertEqual(cm.exception.resource, "/photos/cat.png")
        self.assertEqual(cm.exception.status_code, 400)

    async def test_rejects_declared_content_length(self):
        request = FakeRequest([b"abc"], {"content-length": "9000"})

        with self.assertRaises(S3ObjektTooLargeError):
            RequestBodyReader(request, max_bytes=1024)

    async def test_rejects_declared_decoded_content_length(self):
        request = FakeRequest(
            [b"abc"],
            {
                "content-length": "10",
                "x-amz-decoded-content-length": "9000",
            },
        )

        with self.assertRaises(S3ObjektTooLargeError):
            RequestBodyReader(request, max_bytes=1024)

    async def test_accepts_declared_content_length_within_limit(self):
        request = FakeRequest([b"abc"], {"content-length": "3"})
        reader = RequestBodyReader(request, max_bytes=1024)

        self.assertEqual(await reader.read(), b"abc")

    async def test_ignores_malformed_content_length(self):
        request = FakeRequest([b"abc"], {"content-length": "many"})
        reader = RequestBodyReader(request, max_bytes=1024)

        self.assertEqual(await reader.read(), b"abc")


class FakeSource:
    """Async readable serving prepared bytes in fixed slices."""

    def __init__(self, data: bytes, slice_size: int = 4096) -> None:
        self._data = data
        self._slice_size = slice_size
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        count = self._slice_size if size < 0 else min(size, self._slice_size)
        data = self._data[self._offset:self._offset + count]
        self._offset += len(data)
        return data


class TestAwsChunkedReader(unittest.IsolatedAsyncioTestCase):
    async def test_decodes_single_frame(self):
        reader = AwsChunkedReader(
            FakeSource(b"5\r\nhello\r\n0\r\n\r\n"),
        )

        self.assertEqual(await reader.read(), b"hello")

    async def test_decodes_frames_split_across_source_reads(self):
        reader = AwsChunkedReader(
            FakeSource(b"5\r\nhello\r\n5\r\nworld\r\n0\r\n\r\n", 3),
        )

        self.assertEqual(await reader.read(), b"helloworld")

    async def test_decodes_signed_frames_with_trailer(self):
        body = (
            b"5;chunk-signature=" + b"a" * 64 + b"\r\nhello\r\n"
            b"0;chunk-signature=" + b"b" * 64 + b"\r\n"
            b"x-amz-checksum-crc32:AAAAAA==\r\n\r\n"
        )
        reader = AwsChunkedReader(FakeSource(body))

        self.assertEqual(await reader.read(64), b"hello")
        self.assertEqual(await reader.read(64), b"")

    async def test_reads_requested_sizes(self):
        reader = AwsChunkedReader(
            FakeSource(b"5\r\nhello\r\n5\r\nworld\r\n0\r\n\r\n"),
        )

        self.assertEqual(await reader.read(3), b"hel")
        self.assertEqual(await reader.read(4), b"lowo")
        self.assertEqual(await reader.read(9), b"rld")
        self.assertEqual(await reader.read(9), b"")

    async def test_decodes_empty_body(self):
        reader = AwsChunkedReader(FakeSource(b"0\r\n\r\n"))

        self.assertEqual(await reader.read(), b"")

    async def test_rejects_malformed_frame_size(self):
        reader = AwsChunkedReader(
            FakeSource(b"zz\r\nhello\r\n0\r\n\r\n"),
            resource="/photos/cat.png",
        )

        with self.assertRaises(S3ObjektBodyIncompleteError) as cm:
            await reader.read()

        self.assertEqual(cm.exception.resource, "/photos/cat.png")

    async def test_rejects_truncated_frame(self):
        reader = AwsChunkedReader(FakeSource(b"9\r\nhello"))

        with self.assertRaises(S3ObjektBodyIncompleteError):
            await reader.read()

    async def test_rejects_unterminated_size_line(self):
        reader = AwsChunkedReader(FakeSource(b"5"))

        with self.assertRaises(S3ObjektBodyIncompleteError):
            await reader.read()


class TestBuildBodyReader(unittest.IsolatedAsyncioTestCase):
    async def test_returns_plain_reader_for_unframed_body(self):
        reader = build_body_reader(
            FakeRequest([b"hello"]),
            max_bytes=1024,
        )

        self.assertIsInstance(reader, RequestBodyReader)
        self.assertEqual(await reader.read(), b"hello")

    async def test_decodes_body_marked_by_content_encoding(self):
        request = FakeRequest(
            [b"5\r\nhello\r\n0\r\n\r\n"],
            {"content-encoding": "aws-chunked"},
        )
        reader = build_body_reader(request, max_bytes=1024)

        self.assertIsInstance(reader, AwsChunkedReader)
        self.assertEqual(await reader.read(), b"hello")

    async def test_decodes_body_marked_by_streaming_payload(self):
        request = FakeRequest(
            [b"5\r\nhello\r\n0\r\n\r\n"],
            {
                "x-amz-content-sha256": (
                    "STREAMING-UNSIGNED-PAYLOAD-TRAILER"
                ),
            },
        )
        reader = build_body_reader(request, max_bytes=1024)

        self.assertIsInstance(reader, AwsChunkedReader)
        self.assertEqual(await reader.read(), b"hello")
