"""Editorial notices; no connection to collection, billing or source alerts."""
import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func, inspect
from sqlalchemy.exc import IntegrityError
from .models import SystemNotice as Notice, SystemNoticeDismissal as Dismissal
from .admin import administrator, audit
from .auth import current_session, SESSION_COOKIE, csrf_matches

router = APIRouter(prefix='/api/v1', tags=['system notices'])


def ready(db):
    inspector = inspect(db.connection())
    return inspector.has_table('system_notices') and inspector.has_table('system_notice_dismissals')


def require_schema(db):
    if not ready(db):
        raise HTTPException(503, 'Thông báo hệ thống đang được cập nhật. Vui lòng thử lại sau.')


def reader(request, db, write=False):
    login, account = current_session(db, request.cookies.get(SESSION_COOKIE))
    if account is None:
        raise HTTPException(401, 'Vui lòng đăng nhập để xem thông báo.')
    if not account.trial_admitted:
        raise HTTPException(403, 'Tài khoản chưa được duyệt.')
    if write and not csrf_matches(request.headers.get('X-QD766-CSRF', ''), login.csrf_token):
        raise HTTPException(403, 'Xác nhận phiên không hợp lệ.')
    return account


def payload(row, full=True):
    return {'id': str(row.id), 'title': row.title, 'summary': row.summary, 'kind': row.kind,
        'state': row.state, 'revision': row.revision, 'publication': row.publication,
        'updatedAt': row.updated_at.isoformat(),
        'publishedAt': row.published_at.isoformat() if row.published_at else None,
        **({'body': row.body} if full else {})}


class NoticeEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: uuid.UUID
    expectedRevision: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default='', max_length=300)
    body: str = Field(min_length=1, max_length=16000)
    kind: Literal['info','important','maintenance'] = 'info'

    @field_validator('title', 'body')
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError('Vui lòng nhập nội dung thông báo.')
        return value.strip()


class NoticeAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expectedRevision: int = Field(ge=1)
    action: Literal['publish','archive']


class Dismiss(BaseModel):
    model_config = ConfigDict(extra='forbid')
    publication: int = Field(ge=1)


@router.get('/admin/system-notices')
def admin_list(request: Request, page: int = Query(1, ge=1, le=100000),
               state: Literal['draft','published','archived'] | None = None):
    with request.app.state.session_factory() as db:
        administrator(request, db)
        require_schema(db)
        stmt = select(Notice)
        if state:
            stmt = stmt.where(Notice.state == state)
        count = db.scalar(select(func.count()).select_from(stmt.subquery()))
        page = min(page, max(1, (count + 9) // 10))
        rows = db.scalars(stmt.order_by(Notice.updated_at.desc(), Notice.id.desc()).offset((page-1)*10).limit(10))
        return {'items': [payload(r) for r in rows], 'total': count, 'page': page, 'pageSize': 10}


@router.post('/admin/system-notices')
def save(edit: NoticeEdit, request: Request):
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        require_schema(db)
        row = db.scalar(select(Notice).where(Notice.id == edit.id).with_for_update())
        now = datetime.now(timezone.utc)
        if row:
            if row.revision != edit.expectedRevision:
                raise HTTPException(409, 'Thông báo đã thay đổi ở phiên khác. Hãy tải lại danh sách.')
            if row.state == 'published':
                raise HTTPException(409, 'Hãy ngừng hiện tự động trước khi chỉnh sửa thông báo đã xuất bản.')
            # An archived publication remains immutable in user history. Reuse
            # its content to create a NEW draft instead of editing history.
            if row.state == 'archived':
                raise HTTPException(409, 'Hãy tạo thông báo mới để giữ nguyên lịch sử đã xuất bản.')
            row.revision += 1
        else:
            if edit.expectedRevision != 0:
                raise HTTPException(404, 'Không tìm thấy thông báo.')
            row = Notice(id=edit.id, created_by=actor.id, created_at=now, revision=1, publication=0, state='draft')
            db.add(row)
        row.title, row.summary, row.body, row.kind = edit.title, edit.summary.strip(), edit.body, edit.kind
        row.updated_at = now
        audit(db, actor, 'system-notice.saved', noticeId=str(row.id), revision=row.revision)
        try:
            db.flush()
        except IntegrityError:
            raise HTTPException(409, 'Thông báo đã được lưu. Hãy tải lại danh sách.')
        return payload(row)


@router.post('/admin/system-notices/{identifier}/action')
def action(identifier: uuid.UUID, value: NoticeAction, request: Request):
    with request.app.state.session_factory.begin() as db:
        actor = administrator(request, db, write=True)
        require_schema(db)
        row = db.scalar(select(Notice).where(Notice.id == identifier).with_for_update())
        if not row:
            raise HTTPException(404, 'Không tìm thấy thông báo.')
        if row.revision != value.expectedRevision:
            raise HTTPException(409, 'Thông báo đã thay đổi ở phiên khác. Hãy tải lại danh sách.')
        if value.action == 'publish':
            if row.state != 'draft':
                raise HTTPException(409, 'Chỉ bản nháp mới được xuất bản.')
            row.state, row.publication, row.published_at = 'published', row.publication+1, datetime.now(timezone.utc)
        else:
            if row.state != 'published':
                raise HTTPException(409, 'Thông báo không ở trạng thái xuất bản.')
            row.state = 'archived'
        row.revision += 1
        row.updated_at = datetime.now(timezone.utc)
        audit(db, actor, 'system-notice.'+value.action, noticeId=str(row.id), publication=row.publication)
        db.flush()
        return payload(row)


@router.get('/me/system-notices')
def user_list(request: Request, page: int = Query(1, ge=1, le=100000)):
    with request.app.state.session_factory() as db:
        account = reader(request, db)
        if not ready(db):
            return {'items': [], 'total': 0, 'page': 1, 'pageSize': 10, 'latest': None}
        visible = select(Notice).where(Notice.state.in_(['published','archived']), Notice.published_at.is_not(None))
        total = db.scalar(select(func.count()).select_from(visible.subquery()))
        page = min(page, max(1, (total+9)//10))
        rows = db.scalars(visible.order_by(Notice.published_at.desc(), Notice.id.desc()).offset((page-1)*10).limit(10))
        # Only the newest active announcement can open automatically; never
        # barrage users with older popups after dismissing the newest one.
        latest = db.scalar(select(Notice).where(Notice.state == 'published').order_by(Notice.published_at.desc(), Notice.id.desc()).limit(1))
        if latest and db.get(Dismissal, (account.id, latest.id, latest.publication)):
            latest = None
        return {'items': [payload(row, False) for row in rows], 'total': total, 'page': page,
            'pageSize': 10, 'latest': payload(latest) if latest else None}


@router.get('/me/system-notices/{identifier}')
def user_detail(identifier: uuid.UUID, request: Request):
    with request.app.state.session_factory() as db:
        reader(request, db)
        require_schema(db)
        row = db.get(Notice, identifier)
        if not row or row.state not in {'published','archived'} or row.published_at is None:
            raise HTTPException(404, 'Không tìm thấy thông báo.')
        return payload(row)


@router.post('/me/system-notices/{identifier}/dismiss')
def dismiss(identifier: uuid.UUID, value: Dismiss, request: Request):
    with request.app.state.session_factory.begin() as db:
        account = reader(request, db, write=True)
        require_schema(db)
        row = db.get(Notice, identifier)
        if not row or row.state not in {'published','archived'} or row.publication != value.publication:
            raise HTTPException(409, 'Thông báo đã thay đổi. Hãy mở lại danh sách.')
        from sqlalchemy.dialects.postgresql import insert as postgres_insert
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        insert = postgres_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
        db.execute(insert(Dismissal).values(account_id=account.id, notice_id=row.id, publication=row.publication,
            dismissed_at=datetime.now(timezone.utc)).on_conflict_do_nothing())
        return {'dismissed': True}
