# app/locks.py
# SPDX-License-Identifier: GPL-3.0-only

import asyncio
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import AsyncIterator


class LockType(StrEnum):
    """Lock modes supported by the lock manager."""

    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class LockResource:
    """
    Normalized directory or file resource used for lock comparisons.

    A directory resource has no filename. A file resource consists of
    its parent directory and filename.
    """

    directory: str
    filename: str | None = None


@dataclass(frozen=True)
class LockHolder:
    """Lock currently held by an asyncio task."""

    resource: LockResource
    lock_type: LockType
    owner: asyncio.Task


class LockManager:
    """
    Coordinate in-process locks for filesystem resources.

    Locks use hierarchical semantics. Directory locks cover entire
    directory subtrees, while file locks cover only the specific file.
    Overlapping resources are compatible only for READ + READ.

    +------------+------------+------------+------------+------------+
    |            | DIR READ   | DIR WRITE  | FILE READ  | FILE WRITE |
    +------------+------------+------------+------------+------------+
    | DIR READ   | YES        | -          | YES        | -          |
    | DIR WRITE  | -          | -          | -          | -          |
    | FILE READ  | YES        | -          | YES        | -          |
    | FILE WRITE | -          | -          | -          | -          |
    +------------+------------+------------+------------+------------+

    A directory overlaps with itself and any descendant directory, and
    with any file in its subtree. Two files overlap only if they refer
    to the same file.

    Locks are local to the current process, are neither reentrant nor
    fair, and compare normalized paths lexically without resolving
    symbolic links.
    """

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._holders: list[LockHolder] = []

    @asynccontextmanager
    async def lock_directory(
        self,
        dir_path: str,
        lock_type: LockType,
    ) -> AsyncIterator[None]:
        """
        Acquire a lock covering a directory and its entire subtree.

        READ: shared lock for reading the subtree. Compatible only with
        other READ locks on overlapping resources.

        WRITE: exclusive lock for the subtree. Conflicts with any
        overlapping directory or file lock.
        """
        resource = self._build_directory_resource(dir_path)
        owner = self._get_current_task()

        await self._acquire(resource, lock_type, owner)
        try:
            yield
        finally:
            await self._release(resource, lock_type, owner)

    @asynccontextmanager
    async def lock_file(
        self,
        file_path: str,
        lock_type: LockType,
    ) -> AsyncIterator[None]:
        """
        Acquire a lock for a single file.

        READ: shared lock for the file. Compatible only with other READ
        locks on overlapping resources.

        WRITE: exclusive lock for the file. Conflicts with any
        overlapping directory or file lock.
        """
        resource = self._build_file_resource(file_path)
        owner = self._get_current_task()

        await self._acquire(resource, lock_type, owner)
        try:
            yield
        finally:
            await self._release(resource, lock_type, owner)

    def _get_current_task(self) -> asyncio.Task:
        task = asyncio.current_task()

        if task is None:
            raise RuntimeError(
                "Lock operations require a running asyncio task."
            )

        return task

    def _build_directory_resource(self, dir_path: str) -> LockResource:
        directory = os.path.abspath(os.path.normpath(dir_path))
        return LockResource(directory=directory)

    def _build_file_resource(self, file_path: str) -> LockResource:
        normalized_path = os.path.abspath(os.path.normpath(file_path))
        directory = os.path.normpath(
            os.path.dirname(normalized_path) or "."
        )
        filename = os.path.basename(normalized_path)

        if not filename:
            raise ValueError("File path must include a file name.")

        return LockResource(
            directory=directory,
            filename=filename,
        )

    async def _acquire(
        self,
        resource: LockResource,
        lock_type: LockType,
        owner: asyncio.Task,
    ) -> None:
        """
        Wait until the requested lock becomes available and register it
        for the specified task.

        Raises RuntimeError if the task attempts to acquire a conflicting
        lock it already holds.
        """
        async with self._condition:
            if self._has_owner_conflict(resource, lock_type, owner):
                raise RuntimeError(
                    "Attempted to acquire a conflicting lock already "
                    "held by the same task: "
                    f"resource={resource!r}, "
                    f"lock_type={lock_type!r}, "
                    f"owner={owner!r}"
                )

            while self._has_conflict(resource, lock_type):
                await self._condition.wait()

            self._holders.append(
                LockHolder(
                    resource=resource,
                    lock_type=lock_type,
                    owner=owner,
                ),
            )

    async def _release(
        self,
        resource: LockResource,
        lock_type: LockType,
        owner: asyncio.Task,
    ) -> None:
        """
        Release a previously acquired lock owned by the specified task.
        Raises RuntimeError if the task does not own the lock.
        """
        async with self._condition:
            for index, holder in enumerate(self._holders):
                if (
                    holder.resource == resource
                    and holder.lock_type == lock_type
                    and holder.owner is owner
                ):
                    del self._holders[index]
                    self._condition.notify_all()
                    return

            raise RuntimeError(
                "Attempted to release a lock not held by its owner: "
                f"resource={resource!r}, "
                f"lock_type={lock_type!r}, "
                f"owner={owner!r}"
            )

    def _has_conflict(
        self,
        requested_resource: LockResource,
        requested_lock_type: LockType,
    ) -> bool:
        return any(
            self._conflicts(
                requested_resource=requested_resource,
                requested_lock_type=requested_lock_type,
                held_resource=holder.resource,
                held_lock_type=holder.lock_type,
            )
            for holder in self._holders
        )

    def _conflicts(
        self,
        requested_resource: LockResource,
        requested_lock_type: LockType,
        held_resource: LockResource,
        held_lock_type: LockType,
    ) -> bool:
        if not self._resources_overlap(
            requested_resource=requested_resource,
            held_resource=held_resource,
        ):
            return False

        return not (
            requested_lock_type == LockType.READ
            and held_lock_type == LockType.READ
        )

    def _has_owner_conflict(
        self,
        resource: LockResource,
        lock_type: LockType,
        owner: asyncio.Task,
    ) -> bool:
        return any(
            holder.owner is owner
            and self._conflicts(
                requested_resource=resource,
                requested_lock_type=lock_type,
                held_resource=holder.resource,
                held_lock_type=holder.lock_type,
            )
            for holder in self._holders
        )

    def _resources_overlap(
        self,
        requested_resource: LockResource,
        held_resource: LockResource,
    ) -> bool:
        requested_is_directory = requested_resource.filename is None
        held_is_directory = held_resource.filename is None

        if requested_is_directory and held_is_directory:
            return (
                self._is_same_or_descendant_directory(
                    parent=requested_resource.directory,
                    child=held_resource.directory,
                )
                or self._is_same_or_descendant_directory(
                    parent=held_resource.directory,
                    child=requested_resource.directory,
                )
            )

        if requested_is_directory:
            return self._directory_contains_file(
                directory=requested_resource.directory,
                file_resource=held_resource,
            )

        if held_is_directory:
            return self._directory_contains_file(
                directory=held_resource.directory,
                file_resource=requested_resource,
            )

        return (
            requested_resource.directory == held_resource.directory
            and requested_resource.filename == held_resource.filename
        )

    def _directory_contains_file(
        self,
        directory: str,
        file_resource: LockResource,
    ) -> bool:
        if file_resource.filename is None:
            return False

        file_path = os.path.join(
            file_resource.directory,
            file_resource.filename,
        )
        return self._is_same_or_descendant_path(
            parent=directory,
            child=file_path,
        )

    def _is_same_or_descendant_directory(
        self,
        parent: str,
        child: str,
    ) -> bool:
        return self._is_same_or_descendant_path(
            parent=parent,
            child=child,
        )

    def _is_same_or_descendant_path(
        self,
        parent: str,
        child: str,
    ) -> bool:
        try:
            return os.path.commonpath([parent, child]) == parent
        except ValueError:
            return False


locks = LockManager()
