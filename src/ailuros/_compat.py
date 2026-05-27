import datetime

try:
    from enum import StrEnum as StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]  # noqa: UP042
        pass

try:
    from datetime import UTC as UTC
except ImportError:
    UTC = datetime.timezone.utc  # noqa: UP017
    datetime.UTC = UTC
