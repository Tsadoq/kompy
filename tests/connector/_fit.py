"""FIT test data, built with fit_tool (kompy never imports fit_tool at module level, but tests may)."""

from __future__ import annotations

from functools import cache

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.profile_type import FileType, Manufacturer


@cache
def fit_bytes() -> bytes:
    """
    Build a minimal valid FIT file, like the one Komoot returns for a planned tour.

    :return: The encoded FIT file.
    """
    message = FileIdMessage()
    message.type = FileType.COURSE
    message.manufacturer = Manufacturer.DEVELOPMENT.value
    message.product = 0
    message.serial_number = 1
    message.time_created = 1_700_000_000_000
    builder = FitFileBuilder(auto_define=True)
    builder.add(message)
    return bytes(builder.build().to_bytes())
