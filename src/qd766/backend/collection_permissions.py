from sqlalchemy import select
from .models import AccountCollectionPermission


def can_collect(db, account_id) -> bool:
    # Query a scalar each time so revoking permission is not hidden by the ORM identity cache.
    return db.scalar(select(AccountCollectionPermission.enabled).where(
        AccountCollectionPermission.account_id == account_id)) is True
