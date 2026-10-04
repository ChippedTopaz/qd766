from sqlalchemy import select
from .models import AccountCollectionPermission, UserAccount


def can_collect(db, account_id) -> bool:
    if db.info.get("default_collection_access"):
        # No separate permission grant. Account admission/scope remain mandatory.
        return db.scalar(select(UserAccount.id).where(UserAccount.id==account_id,
            UserAccount.active.is_(True),UserAccount.trial_admitted.is_(True),
            UserAccount.root_department_id.is_not(None))) is not None
    # Query a scalar each time so revoking permission is not hidden by the ORM identity cache.
    return db.scalar(select(AccountCollectionPermission.enabled).where(
        AccountCollectionPermission.account_id == account_id)) is True
