# -*- coding: utf-8 -*-
"""Cơ sở dữ liệu: tài khoản, lịch sử phân tích và tệp xuất (thay cho history.json + thư mục workspace/)."""
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, defer, relationship, sessionmaker
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, crypto

Base = declarative_base()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    display_name = Column(String(80), nullable=False)
    email = Column(String(254), nullable=False, unique=True, index=True)       # luôn lưu chữ thường
    password_hash = Column(String(255), nullable=False)                         # băm một chiều: không ai đọc lại được
    role = Column(String(10), nullable=False, default="user")                   # user | admin
    status = Column(String(10), nullable=False, default="pending")              # pending | approved | rejected | disabled
    created_at = Column(DateTime, nullable=False, default=_now)
    decided_at = Column(DateTime)
    reset_hash = Column(String(255))                                            # mật khẩu MỚI (đã băm) đang chờ admin duyệt; mật khẩu cũ vẫn dùng được cho tới lúc duyệt
    reset_requested_at = Column(DateTime)
    auth_ver = Column(Integer, nullable=False, default=0, server_default="0")   # tăng mỗi khi đổi mật khẩu -> mọi phiên đăng nhập cũ bị đăng xuất
    analyses = relationship("Analysis", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", cascade="all, delete-orphan", uselist=False)


class UserSettings(Base):
    """Cấu hình LLM riêng của từng người dùng. api_key_enc là bản MÃ HÓA (xem crypto.py), không bao giờ là bản rõ."""
    __tablename__ = "user_settings"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    api_key_enc = Column(Text)
    base_url = Column(String(300))
    model = Column(String(200))
    updated_at = Column(DateTime, nullable=False, default=_now)
    user = relationship("User", back_populates="settings")


class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(String(16), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    question = Column(Text, default="")
    ctx = Column(Text, default="")
    title = Column(Text, default="")
    report_title = Column(Text, default="")
    started = Column(String(32))
    finished = Column(String(32))
    sources = Column(JSON, default=list)
    files = Column(JSON, default=list)
    has_snap = Column(Boolean, default=False)
    snapshot = Column(JSON)
    created_at = Column(DateTime, nullable=False, default=_now, index=True)
    user = relationship("User", back_populates="analyses")
    blobs = relationship("AnalysisFile", back_populates="analysis", cascade="all, delete-orphan")


class AnalysisFile(Base):
    __tablename__ = "analysis_files"
    __table_args__ = (UniqueConstraint("analysis_id", "name"),)
    id = Column(Integer, primary_key=True)
    analysis_id = Column(String(16), ForeignKey("analyses.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    mimetype = Column(String(100), nullable=False)
    data = Column(LargeBinary, nullable=False)
    analysis = relationship("Analysis", back_populates="blobs")


_kw = {"pool_pre_ping": True}
if config.DATABASE_URL.startswith("sqlite"):
    _kw["connect_args"] = {"check_same_thread": False}
engine = create_engine(config.DATABASE_URL, **_kw)
Session = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def scope():
    s = Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _add_missing_columns():
    """Nâng cấp nhẹ: thêm cột mới vào bảng đã có (database tạo từ phiên bản trước). Bảng/cột mới hoàn toàn thì create_all lo."""
    insp = inspect(engine)
    with engine.begin() as c:
        for t in Base.metadata.sorted_tables:
            have = {col["name"] for col in insp.get_columns(t.name)}
            for col in t.columns:
                if col.name in have or col.primary_key:
                    continue
                ddl = f"ALTER TABLE {t.name} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}"
                if col.server_default is not None:
                    ddl += f" DEFAULT {col.server_default.arg}" + ("" if col.nullable else " NOT NULL")
                c.execute(text(ddl))


def init_db():
    Base.metadata.create_all(engine)       # bỏ qua bảng đã tồn tại (vd. đã tạo bằng sql/schema.sql)
    _add_missing_columns()
    ensure_admin()


# ------------------------------------------------------------------ Tài khoản --
def user_dict(u):
    """Chỉ những trường an toàn để hiển thị; KHÔNG bao giờ có password_hash."""
    return {"id": u.id, "display_name": u.display_name, "email": u.email, "role": u.role, "status": u.status, "auth_ver": u.auth_ver or 0,
            "reset_pending": bool(u.reset_hash), "reset_requested_at": u.reset_requested_at.isoformat(timespec="seconds") if u.reset_requested_at else None,
            "created_at": u.created_at.isoformat(timespec="seconds") if u.created_at else None}


def create_user(name, email, password, role="user", status="pending"):
    u = User(display_name=name, email=email, password_hash=generate_password_hash(password), role=role, status=status)
    if status == "approved":
        u.decided_at = _now()
    try:
        with scope() as s:
            s.add(u)
    except IntegrityError:
        raise ValueError("Email này đã được đăng ký.")
    return user_dict(u)


def find_by_email(email):
    with scope() as s:
        return s.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user(uid):
    with scope() as s:
        u = s.get(User, uid)
        return user_dict(u) if u else None


def check_login(email, password):
    """Trả về (user_dict | None). Luôn tốn thời gian băm tương đương để không lộ email nào tồn tại."""
    u = find_by_email(email)
    ok = check_password_hash(u.password_hash if u else _DUMMY_HASH, password)
    return user_dict(u) if (u and ok) else None


_DUMMY_HASH = generate_password_hash("không-tồn-tại")


def list_users():
    with scope() as s:
        rows = s.execute(select(User).order_by(User.created_at.desc())).scalars().all()
        return [user_dict(u) for u in rows]


def count_pending():
    """Số việc đang chờ admin: tài khoản mới + yêu cầu đặt lại mật khẩu."""
    with scope() as s:
        n = s.execute(select(func.count()).select_from(User).where(User.status == "pending")).scalar_one()
        return n + s.execute(select(func.count()).select_from(User).where(User.reset_hash.isnot(None), User.status == "approved")).scalar_one()


def request_reset(email, new_password):
    """Ghi mật khẩu mới (đã băm) vào hàng chờ duyệt. Trả False nếu email không có tài khoản user đang hoạt động (người gọi KHÔNG tiết lộ điều này)."""
    with scope() as s:
        u = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not u or u.role != "user" or u.status != "approved":
            return False
        u.reset_hash, u.reset_requested_at = generate_password_hash(new_password), _now()
        return True


def decide_reset(uid, approve):
    with scope() as s:
        u = s.get(User, uid)
        if not u or u.role != "user" or not u.reset_hash:
            return False, "Không có yêu cầu đặt lại mật khẩu nào của người này."
        if approve:
            u.password_hash, u.auth_ver = u.reset_hash, (u.auth_ver or 0) + 1     # đổi mật khẩu + đăng xuất mọi phiên cũ
        u.reset_hash, u.reset_requested_at = None, None
        return True, "Đã đổi mật khẩu theo yêu cầu." if approve else "Đã từ chối yêu cầu đặt lại mật khẩu."


def set_password(email, new_password):
    """Dùng cho manage.py (kể cả admin quên mật khẩu): đặt mật khẩu trực tiếp trên máy chủ."""
    with scope() as s:
        u = s.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not u:
            return False
        u.password_hash, u.auth_ver, u.reset_hash, u.reset_requested_at = generate_password_hash(new_password), (u.auth_ver or 0) + 1, None, None
        return True


TRANSITIONS = {            # hành động -> (trạng thái được phép đi từ, trạng thái mới)
    "approve": ({"pending", "rejected"}, "approved"),
    "reject": ({"pending"}, "rejected"),
    "disable": ({"approved"}, "disabled"),
    "enable": ({"disabled"}, "approved"),
}


def change_status(uid, action):
    """Trả về (ok, thông báo). Chỉ áp dụng cho tài khoản role=user; admin quản lý qua biến môi trường."""
    with scope() as s:
        u = s.get(User, uid)
        if not u or u.role != "user":
            return False, "Không tìm thấy tài khoản."
        if action == "delete":
            s.delete(u)
            invalidate_history(uid)
            return True, "Đã xóa tài khoản và toàn bộ dữ liệu của người này."
        frm, to = TRANSITIONS[action]
        if u.status not in frm:
            return False, "Thao tác không phù hợp với trạng thái hiện tại."
        u.status, u.decided_at = to, _now()
        return True, "Đã cập nhật."


def ensure_admin():
    """Tạo admin đầu tiên từ ADMIN_EMAIL / ADMIN_PASSWORD nếu chưa có. Không ghi đè mật khẩu đã đổi."""
    if not config.ADMIN_EMAIL or not config.ADMIN_PASSWORD:
        return
    if find_by_email(config.ADMIN_EMAIL):
        return
    create_user(config.ADMIN_NAME, config.ADMIN_EMAIL, config.ADMIN_PASSWORD, role="admin", status="approved")


# ------------------------------------------------------------------ Lịch sử --
_HC = {}
_HC_LOCK = threading.Lock()


def invalidate_history(uid):
    with _HC_LOCK:
        _HC.pop(uid, None)


def _hist_row(a):
    return {"id": a.id, "question": a.question or "", "title": a.title or "", "ctx": a.ctx or "", "started": a.started, "finished": a.finished,
            "files": a.files or [], "report_title": a.report_title or "", "sources": a.sources or [], "snap": bool(a.has_snap)}


def list_history(uid):
    """Danh sách lịch sử của ĐÚNG người dùng này (giao diện gọi mỗi giây nên có cache, xóa khi lưu/xóa)."""
    with _HC_LOCK:
        if uid in _HC:
            return _HC[uid]
    with scope() as s:
        rows = s.execute(select(Analysis).options(defer(Analysis.snapshot)).where(Analysis.user_id == uid).order_by(Analysis.created_at.desc())).scalars().all()
        out = [_hist_row(a) for a in rows]
    with _HC_LOCK:
        _HC[uid] = out
    return out


def save_analysis(uid, entry, snapshot, files):
    """files: {tên: (bytes, mimetype)}. Lưu một luồng đã duyệt cùng toàn bộ tệp xuất trong một giao dịch."""
    with scope() as s:
        a = Analysis(id=entry["id"], user_id=uid, question=entry.get("question", ""), ctx=entry.get("ctx", ""), title=entry.get("title", ""),
                     report_title=entry.get("report_title", ""), started=entry.get("started"), finished=entry.get("finished"),
                     sources=entry.get("sources", []), files=entry.get("files", []), has_snap=snapshot is not None, snapshot=snapshot)
        for name, (data, mt) in files.items():
            a.blobs.append(AnalysisFile(name=name, mimetype=mt, data=data))
        s.add(a)
    invalidate_history(uid)


def get_snapshot(uid, aid):
    with scope() as s:
        return s.execute(select(Analysis.snapshot).where(Analysis.id == aid, Analysis.user_id == uid)).scalar_one_or_none()


def get_file(uid, aid, name):
    with scope() as s:
        row = s.execute(select(AnalysisFile.data, AnalysisFile.mimetype).join(Analysis).where(
            Analysis.id == aid, Analysis.user_id == uid, AnalysisFile.name == name)).first()
        return (bytes(row[0]), row[1]) if row else None


def delete_analysis(uid, aid):
    with scope() as s:
        a = s.execute(select(Analysis).where(Analysis.id == aid, Analysis.user_id == uid)).scalar_one_or_none()
        if not a:
            return False
        s.delete(a)
    invalidate_history(uid)
    return True


# ------------------------------------------------------------------ Cấu hình LLM theo người dùng --
def load_llm_cfg(uid):
    """Dùng nội bộ để gọi API: có giải mã key. broken=True nếu có key nhưng không giải mã được (đổi MASTER_KEY)."""
    with scope() as s:
        r = s.get(UserSettings, uid)
        if not r:
            return {"api_key": "", "base_url": "", "model": "", "broken": False}
        key = crypto.decrypt(uid, r.api_key_enc) if r.api_key_enc else ""
        return {"api_key": key or "", "base_url": r.base_url or "", "model": r.model or "", "broken": bool(r.api_key_enc and key is None)}


def llm_public(uid):
    """Dùng cho giao diện: KHÔNG bao giờ trả key, chỉ 4 ký tự cuối để người dùng nhận ra key nào đang lưu."""
    c = load_llm_cfg(uid)
    return {"has_key": bool(c["api_key"]), "broken": c["broken"], "key_hint": c["api_key"][-4:] if len(c["api_key"]) >= 8 else "",
            "base_url": c["base_url"] or config.DEFAULT_BASE_URL, "model": c["model"], "configured": bool(c["base_url"] or c["model"])}


def save_llm(uid, api_key, base_url, model):
    """api_key rỗng/None = giữ key cũ."""
    with scope() as s:
        r = s.get(UserSettings, uid)
        if not r:
            r = UserSettings(user_id=uid)
            s.add(r)
        if api_key:
            r.api_key_enc = crypto.encrypt(uid, api_key)
        r.base_url, r.model, r.updated_at = base_url, model, _now()


def clear_llm_key(uid):
    with scope() as s:
        r = s.get(UserSettings, uid)
        if r:
            r.api_key_enc, r.updated_at = None, _now()
