"""Operator-only local gate for new user collection, not a source circuit.

No public endpoint can create/remove this marker. Existing data and settlement,
system collection and AI requests are intentionally unaffected.
"""
from pathlib import Path

PAUSE_FILE = Path(__file__).resolve().parents[3] / '.tmp-user-collection-maintenance' / 'paused.json'
PAUSE_MESSAGE = 'Tra cứu dữ liệu mới đang tạm dừng để cập nhật dữ liệu. Bạn vẫn có thể xem lại dữ liệu đã khai thác.'


def user_collection_paused() -> bool:
    # Presence is sufficient: a malformed marker must not accidentally reopen.
    return PAUSE_FILE.exists()
