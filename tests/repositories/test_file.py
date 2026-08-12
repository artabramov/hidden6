# tests/repositories/test_file.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.constants import FILE_CHUNK_SIZE_BYTES
from app.repositories import file as rf


class TestFileRepository(unittest.IsolatedAsyncioTestCase):

    # --- _parent_dir ---

    def test_parent_dir_empty_returns_dot(self):
        self.assertEqual(rf._parent_dir("file.txt"), ".")

    def test_parent_dir_nested(self):
        self.assertEqual(rf._parent_dir("/a/b/c"), "/a/b")

    # --- _build_temp_path ---

    @patch("app.repositories.file.uuid.uuid4")
    def test_build_temp_path(self, mock_uuid: MagicMock) -> None:
        mock_uuid.return_value = MagicMock(hex="deadbeef")
        p = rf._build_temp_path("/data/out.bin")
        self.assertTrue(p.endswith(".out.bin.deadbeef.tmp"))
        self.assertIn(os.path.join("data", ".out.bin.deadbeef.tmp"), p)

    # --- get_mimetype ---

    async def test_get_mimetype_returns_none_when_open_raises(self):
        with patch(
            "app.repositories.file.aiofiles.open",
            side_effect=FileNotFoundError,
        ):
            self.assertIsNone(await rf.get_mimetype("/nope"))

    async def test_get_mimetype_empty_head_uses_extension(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(return_value=b"")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)
        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.mimetypes.guess_type",
            return_value=("text/plain", None),
        ):
            mt = await rf.get_mimetype("/x.txt")
        self.assertEqual(mt, "text/plain")

    async def test_get_mimetype_magic_branch(self):
        mock_f = MagicMock()
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        mock_f.read = AsyncMock(return_value=png)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is rf._detect_mime_with_magic:
                return "image/png"
            msg = f"unexpected fn {fn!r}"
            raise AssertionError(msg)

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ):
            mt = await rf.get_mimetype("/p.png")
        self.assertEqual(mt, "image/png")

    async def test_get_mimetype_filetype_when_magic_returns_none(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(return_value=b"hello")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)
        ft_kind = MagicMock()
        ft_kind.mime = "application/pdf"

        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is rf._detect_mime_with_magic:
                return None
            msg = f"unexpected fn {fn!r}"
            raise AssertionError(msg)

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch(
            "app.repositories.file.filetype.guess",
            return_value=ft_kind,
        ):
            mt = await rf.get_mimetype("/d.pdf")
        self.assertEqual(mt, "application/pdf")

    async def test_get_mimetype_extension_fallback_after_filetype_fails(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(return_value=b"zzz")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is rf._detect_mime_with_magic:
                return None
            msg = f"unexpected fn {fn!r}"
            raise AssertionError(msg)

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch(
            "app.repositories.file.filetype.guess",
            side_effect=TypeError("no"),
        ), patch(
            "app.repositories.file.mimetypes.guess_type",
            return_value=("text/plain", None),
        ):
            mt = await rf.get_mimetype("/z.txt")
        self.assertEqual(mt, "text/plain")

    async def test_get_mimetype_returns_none_when_open_raises_permission(self):
        with patch(
            "app.repositories.file.aiofiles.open",
            side_effect=PermissionError,
        ):
            self.assertIsNone(await rf.get_mimetype("/forbidden"))

    async def test_get_mimetype_returns_none_when_open_raises_isadir(self):
        with patch(
            "app.repositories.file.aiofiles.open",
            side_effect=IsADirectoryError,
        ):
            self.assertIsNone(await rf.get_mimetype("/dir"))

    async def test_get_mimetype_empty_head_and_unknown_extension(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(return_value=b"")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.mimetypes.guess_type",
            return_value=(None, None),
        ):
            mt = await rf.get_mimetype("/x.unknown")

        self.assertIsNone(mt)

    async def test_get_mimetype_empty_head_normalizes_extension_value(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(return_value=b"")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.mimetypes.guess_type",
            return_value=(" Text/Plain ", None),
        ):
            mt = await rf.get_mimetype("/x.txt")

        self.assertEqual(mt, "text/plain")

    async def test_get_mimetype_filetype_value_error_falls_to_extension(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(return_value=b"data")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is rf._detect_mime_with_magic:
                return None
            raise AssertionError(fn)

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch(
            "app.repositories.file.filetype.guess",
            side_effect=ValueError("bad"),
        ), patch(
            "app.repositories.file.mimetypes.guess_type",
            return_value=(" Application/JSON ", None),
        ):
            mt = await rf.get_mimetype("/x.json")

        self.assertEqual(mt, "application/json")

    async def test_get_mimetype_filetype_without_mime_falls_to_extension(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(return_value=b"data")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)
        ft_kind = MagicMock()
        ft_kind.mime = None

        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is rf._detect_mime_with_magic:
                return None
            raise AssertionError(fn)

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch(
            "app.repositories.file.filetype.guess",
            return_value=ft_kind,
        ), patch(
            "app.repositories.file.mimetypes.guess_type",
            return_value=("image/jpeg", None),
        ):
            mt = await rf.get_mimetype("/x.jpg")

        self.assertEqual(mt, "image/jpeg")

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_normalizes_value(
        self,
        mock_cls: MagicMock,
    ) -> None:
        detector = MagicMock()
        detector.from_buffer.return_value = "Text/Plain; charset=utf-8"
        mock_cls.return_value = detector

        value = rf._detect_mime_with_magic(b"abc")

        self.assertEqual(value, "text/plain")

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_octet_stream_returns_none(
        self,
        mock_cls: MagicMock,
    ) -> None:
        detector = MagicMock()
        detector.from_buffer.return_value = "application/octet-stream"
        mock_cls.return_value = detector

        value = rf._detect_mime_with_magic(b"abc")

        self.assertIsNone(value)

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_returns_none_on_magic_exception(
        self,
        mock_cls: MagicMock,
    ) -> None:
        mock_detector = MagicMock()
        mock_detector.from_buffer.side_effect = rf.magic.MagicException("bad")
        mock_cls.return_value = mock_detector

        self.assertIsNone(rf._detect_mime_with_magic(b"data"))

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_returns_none_when_from_buffer_empty_string(
        self,
        mock_cls: MagicMock,
    ) -> None:
        detector = MagicMock()
        detector.from_buffer.return_value = ""
        mock_cls.return_value = detector

        self.assertIsNone(rf._detect_mime_with_magic(b"data"))

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_returns_none_when_from_buffer_none(
        self,
        mock_cls: MagicMock,
    ) -> None:
        detector = MagicMock()
        detector.from_buffer.return_value = None
        mock_cls.return_value = detector

        self.assertIsNone(rf._detect_mime_with_magic(b"data"))

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_returns_none_when_normalized_mime_empty(
        self,
        mock_cls: MagicMock,
    ) -> None:
        detector = MagicMock()
        detector.from_buffer.return_value = "   \t; charset=utf-8"
        mock_cls.return_value = detector

        self.assertIsNone(rf._detect_mime_with_magic(b"data"))

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_octet_stream_with_params_returns_none(
        self,
        mock_cls: MagicMock,
    ) -> None:
        detector = MagicMock()
        detector.from_buffer.return_value = (
            "application/octet-stream; charset=binary"
        )
        mock_cls.return_value = detector

        self.assertIsNone(rf._detect_mime_with_magic(b"data"))

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_returns_none_on_oserror_from_from_buffer(
        self,
        mock_cls: MagicMock,
    ) -> None:
        mock_detector = MagicMock()
        mock_detector.from_buffer.side_effect = OSError("read failed")
        mock_cls.return_value = mock_detector

        self.assertIsNone(rf._detect_mime_with_magic(b"data"))

    # --- get_filesize, isfile, isdir, ismount ---

    async def test_get_filesize(self):
        st = MagicMock()
        st.st_size = 12345
        with patch(
            "app.repositories.file.aiofiles.os.stat",
            new_callable=AsyncMock,
            return_value=st,
        ):
            n = await rf.get_filesize("/f")
        self.assertEqual(n, 12345)

    async def test_isfile(self):
        with patch(
            "app.repositories.file.aiofiles.ospath.isfile",
            new_callable=AsyncMock,
            return_value=True,
        ):
            self.assertTrue(await rf.isfile("/a"))

    async def test_isdir(self):
        with patch(
            "app.repositories.file.aiofiles.ospath.isdir",
            new_callable=AsyncMock,
            return_value=False,
        ):
            self.assertFalse(await rf.isdir("/b"))

    async def test_listdir(self):
        with patch(
            "app.repositories.file.aiofiles.os.listdir",
            new_callable=AsyncMock,
            return_value=["a", "b"],
        ):
            self.assertEqual(await rf.listdir("/data"), ["a", "b"])

    async def test_ismount(self):
        with patch(
            "app.repositories.file.aiofiles.ospath.ismount",
            new_callable=AsyncMock,
            return_value=True,
        ):
            self.assertTrue(await rf.ismount("/mnt"))

    # --- get_file_hash, read ---

    async def test_get_file_hash(self):
        async def fake_iter(
            _path: str,
            chunk_size: int = FILE_CHUNK_SIZE_BYTES,
        ):
            yield b"ab"
            yield b"cd"

        with patch.object(rf, "_iter_read", side_effect=fake_iter):
            hx = await rf.get_file_hash("/f")
        self.assertEqual(hx, hashlib.md5(b"abcd").hexdigest())

    async def test_read(self):
        async def fake_iter(
            _path: str,
            chunk_size: int = FILE_CHUNK_SIZE_BYTES,
        ):
            yield b"one"
            yield b"two"

        with patch.object(rf, "_iter_read", side_effect=fake_iter):
            data = await rf.read("/f")
        self.assertEqual(data, b"onetwo")

    # --- concat ---

    async def test_concat_writes_sources_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = os.path.join(tmp, "first")
            second = os.path.join(tmp, "second")
            destination = os.path.join(tmp, "joined")
            with open(first, "wb") as f:
                f.write(b"hello ")
            with open(second, "wb") as f:
                f.write(b"hidden")

            hashes = await rf.concat([first, second], destination)

            with open(destination, "rb") as f:
                self.assertEqual(f.read(), b"hello hidden")

        self.assertEqual(
            hashes,
            [
                hashlib.md5(b"hello ").hexdigest(),
                hashlib.md5(b"hidden").hexdigest(),
            ],
        )

    async def test_concat_leaves_no_file_when_source_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = os.path.join(tmp, "first")
            destination = os.path.join(tmp, "joined")
            with open(first, "wb") as f:
                f.write(b"hello")

            with self.assertRaises(FileNotFoundError):
                await rf.concat(
                    [first, os.path.join(tmp, "missing")],
                    destination,
                )

            self.assertFalse(os.path.exists(destination))

    # --- mkdir, rmdir, touch ---

    async def test_mkdir_fsyncs_every_created_level(self):
        calls = []

        async def fake_to_thread(fn, /, *args, **kwargs):
            calls.append((fn, args))
            return ["/data/sub/deep", "/data/sub"]

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.mkdir("/data/sub/deep")
        self.assertEqual(calls[0][0], rf._makedirs_sync)
        self.assertEqual(calls[0][1], ("/data/sub/deep",))
        self.assertEqual(
            [call.args[0] for call in fsync.await_args_list],
            ["/data", "/data/sub"],
        )

    async def test_mkdir_existing_directory_is_left_as_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            await rf.mkdir(tmp)
            self.assertTrue(os.path.isdir(tmp))

    async def test_mkdir_creates_missing_parents(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b", "c")
            await rf.mkdir(path)
            self.assertTrue(os.path.isdir(path))

    def test_makedirs_sync_returns_created_levels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b")
            created = rf._makedirs_sync(path)
        self.assertEqual(
            created,
            [path, os.path.join(tmp, "a")],
        )

    async def test_rmdir(self):
        with patch(
            "app.repositories.file.aiofiles.os.rmdir",
            new_callable=AsyncMock,
        ) as rmd, patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.rmdir("/data/empty")
        rmd.assert_awaited_once_with("/data/empty")
        fsync.assert_awaited_once_with("/data")

    async def test_rmtree_removes_files_and_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "upload")
            os.makedirs(path)
            for name in ("1.part", "2.part"):
                with open(os.path.join(path, name), "wb") as f:
                    f.write(b"x")

            await rf.rmtree(path)

            self.assertFalse(os.path.exists(path))

    async def test_rmtree_missing_directory_is_skipped(self):
        with patch(
            "app.repositories.file.aiofiles.os.rmdir",
            new_callable=AsyncMock,
        ) as rmd:
            await rf.rmtree("/data/missing")
        rmd.assert_not_awaited()

    async def test_touch(self):
        calls = []

        async def fake_to_thread(fn, /, *args, **kwargs):
            calls.append((fn, args))
            return None

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ):
            await rf.touch("/data/x.flag")
        self.assertEqual(calls[0][0], rf._touch_sync)
        self.assertEqual(calls[0][1], ("/data/x.flag",))

    @patch("app.repositories.file.os.utime")
    @patch("builtins.open")
    def test_touch_sync(self, mock_open: MagicMock, mock_utime: MagicMock):
        rf._touch_sync("/tmp/file.txt")
        mock_open.assert_called_once_with("/tmp/file.txt", "a")
        mock_utime.assert_called_once_with("/tmp/file.txt", None)

    async def test_fsync_directory(self):
        calls = []

        async def fake_to_thread(fn, /, *args, **kwargs):
            calls.append((fn, args))
            if fn is os.open:
                return 11
            return None

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ):
            await rf._fsync_directory("/data")

        self.assertEqual(calls[0], (os.open, ("/data", os.O_RDONLY)))
        self.assertEqual(calls[1], (os.fsync, (11,)))
        self.assertEqual(calls[2], (os.close, (11,)))

    async def test_fsync_directory_closes_fd_when_fsync_fails(self):
        calls = []

        async def fake_to_thread(fn, /, *args, **kwargs):
            calls.append((fn, args))
            if fn is os.open:
                return 17
            if fn is os.fsync:
                raise OSError("fsync failed")
            if fn is os.close:
                return None
            raise AssertionError(fn)

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ):
            with self.assertRaises(OSError):
                await rf._fsync_directory("/data")

        self.assertEqual(calls[0], (os.open, ("/data", os.O_RDONLY)))
        self.assertEqual(calls[1], (os.fsync, (17,)))
        self.assertEqual(calls[2], (os.close, (17,)))

    # --- delete ---

    async def test_delete_unlink_and_fsync(self):
        calls = []

        async def fake_to_thread(fn, /, *args, **kwargs):
            calls.append((fn, args))
            return None

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.delete("/data/f.txt")
        self.assertEqual(calls[0][0], os.unlink)
        self.assertEqual(calls[0][1], ("/data/f.txt",))
        fsync.assert_awaited_once_with("/data")

    async def test_delete_missing_no_fsync(self):
        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is os.unlink:
                raise FileNotFoundError
            raise AssertionError(fn)

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.delete("/missing")
        fsync.assert_not_called()

    # --- write, upload ---

    async def test_write(self):
        mock_f = MagicMock()
        mock_f.write = AsyncMock()
        mock_f.flush = AsyncMock()
        mock_f.fileno = MagicMock(return_value=9)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)
        to_thread_calls = []

        async def fake_to_thread(fn, /, *args, **kwargs):
            to_thread_calls.append((fn, args))
            return None

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ), patch(
            "app.repositories.file.uuid.uuid4",
            return_value=MagicMock(hex="abc"),
        ):
            await rf.write("/dir/out.bin", b"hello")

        self.assertTrue(mock_f.write.await_count >= 1)
        self.assertTrue(any(fn is os.fsync for fn, _ in to_thread_calls))
        self.assertTrue(any(fn is os.replace for fn, _ in to_thread_calls))

    async def test_upload(self):
        class Src:
            def __init__(self) -> None:
                self._n = 0

            async def read(self, size: int = -1) -> bytes:
                self._n += 1
                if self._n == 1:
                    return b"x" * FILE_CHUNK_SIZE_BYTES
                return b""

        mock_f = MagicMock()
        mock_f.write = AsyncMock()
        mock_f.flush = AsyncMock()
        mock_f.fileno = MagicMock(return_value=3)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def fake_to_thread(fn, /, *args, **kwargs):
            return None

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ), patch(
            "app.repositories.file.uuid.uuid4",
            return_value=MagicMock(hex="u1"),
        ):
            await rf.upload(Src(), "/dst/a.dat")

        self.assertTrue(mock_f.write.await_count >= 1)

    # --- copy, rename ---

    async def test_copy(self):
        chunks = [b"a", b"b"]

        async def fake_iter_read(
            path: str,
            chunk_size: int = FILE_CHUNK_SIZE_BYTES,
        ):
            for c in chunks:
                yield c

        mock_f = MagicMock()
        mock_f.write = AsyncMock()
        mock_f.flush = AsyncMock()
        mock_f.fileno = MagicMock(return_value=5)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def fake_to_thread(fn, /, *args, **kwargs):
            return None

        with patch.object(
            rf,
            "_iter_read",
            side_effect=fake_iter_read,
        ), patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ), patch(
            "app.repositories.file.uuid.uuid4",
            return_value=MagicMock(hex="cp"),
        ):
            await rf.copy("/src/x", "/dst/y")

        mock_f.write.assert_awaited()

    async def test_rename_same_parent_one_fsync(self):
        with patch(
            "app.repositories.file.asyncio.to_thread",
            new_callable=AsyncMock,
        ) as tt, patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.rename("/d/a.txt", "/d/b.txt")
        tt.assert_awaited()
        self.assertEqual(fsync.await_count, 1)

    async def test_rename_different_parents_two_fsync(self):
        with patch(
            "app.repositories.file.asyncio.to_thread",
            new_callable=AsyncMock,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.rename("/a/x", "/b/y")
        self.assertEqual(fsync.await_count, 2)

    async def test_rename_same_parent_fsyncs_expected_directory(self):
        async def fake_to_thread(fn, /, *args, **kwargs):
            return None

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.rename("/d/a.txt", "/d/b.txt")

        fsync.assert_awaited_once_with("/d")

    async def test_rename_different_parents_fsyncs_both_directories(self):
        async def fake_to_thread(fn, /, *args, **kwargs):
            return None

        with patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ) as fsync:
            await rf.rename("/a/x", "/b/y")

        self.assertEqual(
            fsync.await_args_list,
            [unittest.mock.call("/a"), unittest.mock.call("/b")],
        )

    # --- _atomic_write_stream error path (via write) ---

    async def test_write_unlinks_temp_on_replace_failure(self):
        mock_f = MagicMock()
        mock_f.write = AsyncMock()
        mock_f.flush = AsyncMock()
        mock_f.fileno = MagicMock(return_value=2)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)
        unlinks = []

        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is os.replace:
                raise OSError("boom")
            if fn is os.unlink:
                unlinks.append(args)
                return None
            if fn is os.fsync:
                return None
            return None

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ), patch(
            "app.repositories.file.uuid.uuid4",
            return_value=MagicMock(hex="bad"),
        ):
            with self.assertRaises(OSError):
                await rf.write("/z/out", b"data")

        tmp_in_unlink = any("tmp" in str(u[0]) for u in unlinks)
        self.assertTrue(tmp_in_unlink)

    async def test_write_replace_failure_and_missing_temp_unlink_raises(self):
        mock_f = MagicMock()
        mock_f.write = AsyncMock()
        mock_f.flush = AsyncMock()
        mock_f.fileno = MagicMock(return_value=22)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)

        async def fake_to_thread(fn, /, *args, **kwargs):
            if fn is os.fsync:
                return None
            if fn is os.replace:
                raise OSError("replace failed")
            if fn is os.unlink:
                raise FileNotFoundError
            return None

        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ), patch(
            "app.repositories.file.asyncio.to_thread",
            side_effect=fake_to_thread,
        ), patch.object(
            rf,
            "_fsync_directory",
            new_callable=AsyncMock,
        ), patch(
            "app.repositories.file.uuid.uuid4",
            return_value=MagicMock(hex="gone"),
        ):
            with self.assertRaises(OSError):
                await rf.write("/tmp/out.bin", b"abc")

    # --- _iter_read ---

    async def test_iter_read(self):
        mock_f = MagicMock()
        mock_f.read = AsyncMock(side_effect=[b"aa", b"bb", b""])
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=mock_f)
        cm.__aexit__ = AsyncMock(return_value=None)
        out = []
        with patch(
            "app.repositories.file.aiofiles.open",
            return_value=cm,
        ):
            async for ch in rf._iter_read("/p", chunk_size=2):
                out.append(ch)
        self.assertEqual(out, [b"aa", b"bb"])
        self.assertEqual(mock_f.read.await_args_list[0][0][0], 2)

    # --- _detect_mime_with_magic ---

    @patch("app.repositories.file.magic.Magic")
    def test_detect_mime_with_magic_returns_none_on_exception(
        self,
        mock_cls: MagicMock,
    ) -> None:
        mock_cls.side_effect = OSError("no lib")
        self.assertIsNone(rf._detect_mime_with_magic(b"data"))
