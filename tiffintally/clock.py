"""Kitchen clock.

Render's free instance runs in UTC. A cook in India who opens the sheet
between midnight and 05:30 IST would otherwise have "today" and "tomorrow"
land on the previous day. The zone defaults to Asia/Kolkata and can be
overridden with TIFFINTALLY_TZ. The returned value is naive on purpose:
the rest of the app compares naive message timestamps.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo


def now() -> datetime:
    zone = os.getenv("TIFFINTALLY_TZ", "Asia/Kolkata")
    return datetime.now(ZoneInfo(zone)).replace(tzinfo=None)
