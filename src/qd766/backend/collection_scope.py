"""Resolve a selected province without treating a nationwide default as a boundary."""
from fastapi import HTTPException


def nationwide(account):
    return (account.role == 'admin' and account.trial_admitted) or account.access_tier == 'national'


def selected_root(account, root_id=None):
    root_id = root_id or account.root_department_id
    if root_id is None:
        raise HTTPException(403, 'Tài khoản chưa được gán tỉnh.')
    if not nationwide(account) and root_id != account.root_department_id:
        raise HTTPException(403, 'Tài khoản không được truy cập chi tiết tỉnh khác.')
    return root_id
