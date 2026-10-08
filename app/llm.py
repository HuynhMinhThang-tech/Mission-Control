# -*- coding: utf-8 -*-
"""Lớp gọi LLM theo KHÓA CỦA TỪNG NGƯỜI DÙNG (endpoint tương thích OpenAI) + đọc JSON chịu lỗi.
Mọi lỗi liên quan khóa/model/địa chỉ được dịch sang thông báo tiếng Việt (UserError) để hiện trong panel."""
import ipaddress
import json
import re
import socket
from urllib.parse import urlparse

from . import config, db, state
from .errors import UserError

NO_KEY = 'Bạn chưa nhập API key. Hãy mở tab "API & Model" ở thanh bên trái, nhập key và chọn model.'
NO_MODEL = 'Bạn chưa chọn model. Hãy mở tab "API & Model" ở thanh bên trái và nhập tên model.'
BROKEN = 'Không đọc được API key đã lưu (khóa mã hóa của máy chủ đã thay đổi). Hãy nhập lại API key trong tab "API & Model".'


class Truncated(RuntimeError):
    """Câu trả lời bị cắt giữa chừng vì hết max_tokens."""


# ------------------------------------------------------------ Base URL an toàn --
def check_base_url(url):
    """Chống SSRF: người dùng được nhập Base URL tự do, nhưng máy chủ không được bị lợi dụng gọi vào mạng nội bộ / dịch vụ metadata."""
    url = (url or "").strip() or config.DEFAULT_BASE_URL
    if len(url) > 300:
        raise UserError("Base URL quá dài (tối đa 300 ký tự).")
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise UserError("Base URL không hợp lệ. Cần dạng https://tên-miền/đường-dẫn (không chứa tài khoản/mật khẩu).")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UserError(f"Không phân giải được tên miền '{p.hostname}'. Hãy kiểm tra lại Base URL.")
    dev_local = not config.IS_PROD            # máy cá nhân: cho phép trỏ tới model chạy cục bộ (Ollama, LM Studio...)
    for ip in {ipaddress.ip_address(i[4][0]) for i in infos}:
        if dev_local and ip.is_loopback:
            continue
        if not ip.is_global or ip.is_multicast:
            raise UserError("Base URL trỏ tới địa chỉ nội bộ nên bị chặn vì lý do bảo mật.")
    if p.scheme == "http" and not (dev_local and all(ipaddress.ip_address(i[4][0]).is_loopback for i in infos)):
        raise UserError("Base URL phải dùng https:// để khóa API không bị lộ khi truyền đi.")
    return url


def make_client(cfg):
    import httpx
    from openai import OpenAI
    return OpenAI(api_key=cfg["api_key"], base_url=check_base_url(cfg.get("base_url")), max_retries=2,
                  http_client=httpx.Client(follow_redirects=False, timeout=httpx.Timeout(180, connect=15)))   # không theo chuyển hướng -> không bị đẩy sang địa chỉ nội bộ


# ------------------------------------------------------------ Dịch lỗi API -> tiếng Việt --
def _detail(e):
    d = getattr(e, "message", None) or str(e)
    return re.sub(r"\s+", " ", str(d))[:220]


def explain(e, cfg):
    """Trả về UserError nếu nhận ra đây là lỗi khóa/model/địa chỉ/hạn mức/mạng; None nếu chưa rõ (có thể chỉ là tham số phụ bị từ chối)."""
    import openai
    low, model = str(e).lower(), (cfg.get("model") or "?")
    host = urlparse(cfg.get("base_url") or config.DEFAULT_BASE_URL).hostname or "máy chủ API"
    more = f" (Chi tiết: {_detail(e)})"
    if isinstance(e, UserError):
        return e
    if any(t in low for t in ("api key not valid", "api_key_invalid", "invalid api key", "incorrect api key", "invalid_api_key", "api key is invalid")):
        return UserError("API key không đúng (có thể sai ký tự, thiếu ký tự hoặc đã bị thu hồi). Hãy mở tab \"API & Model\" và nhập lại key." + more)
    if isinstance(e, openai.AuthenticationError):
        return UserError("API key bị từ chối (401): key sai, đã hết hạn hoặc bị thu hồi. Hãy nhập lại trong tab \"API & Model\"." + more)
    if isinstance(e, openai.PermissionDeniedError):
        return UserError(f"API key không có quyền dùng model '{model}' hoặc dịch vụ này (403). Kiểm tra quyền của key / vùng được hỗ trợ." + more)
    if isinstance(e, openai.NotFoundError) or (isinstance(e, openai.BadRequestError) and "model" in low and ("not found" in low or "not supported" in low or "does not exist" in low)):
        return UserError(f"Không tìm thấy model '{model}' hoặc Base URL sai (404). Hãy kiểm tra tên model và Base URL trong tab \"API & Model\"." + more)
    if isinstance(e, openai.RateLimitError):
        if any(t in low for t in ("quota", "billing", "insufficient", "exceeded your current")):
            return UserError("Tài khoản API đã hết hạn mức (quota) hoặc chưa bật thanh toán (429). Hãy kiểm tra gói của key." + more)
        return UserError("Gọi API quá nhanh hoặc vượt giới hạn tạm thời (429). Hãy chờ vài phút rồi bấm Thử lại." + more)
    if isinstance(e, openai.APITimeoutError):
        return UserError(f"Hết thời gian chờ phản hồi từ {host}. Hãy thử lại, hoặc kiểm tra Base URL.")
    if isinstance(e, openai.APIConnectionError):
        return UserError(f"Không kết nối được tới {host}. Hãy kiểm tra Base URL và kết nối mạng của máy chủ." + more)
    if isinstance(e, openai.InternalServerError):
        return UserError(f"Nhà cung cấp API đang gặp sự cố ({getattr(e, 'status_code', '5xx')}). Hãy thử lại sau ít phút." + more)
    return None


# ------------------------------------------------------------ Gọi model --
def chat(client, cfg, system, user, max_tokens=8000, json_mode=False):
    import openai
    base = dict(model=cfg["model"], max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    # thử lần lượt: ép JSON + giảm "suy nghĩ" (đỡ tốn token) -> chỉ ép JSON -> không tham số phụ (model/endpoint không hỗ trợ thì bỏ)
    variants = ([dict(response_format={"type": "json_object"}, reasoning_effort="low"), dict(response_format={"type": "json_object"})] if json_mode else []) + [{}]
    for extra in variants:
        try:
            r = client.chat.completions.create(**base, **extra)
        except Exception as e:                       # noqa: BLE001
            ue = explain(e, cfg)
            if ue:
                raise ue from e
            if extra and isinstance(e, openai.BadRequestError):       # tham số phụ bị từ chối -> thử cấu hình đơn giản hơn
                continue
            raise UserError(f"API từ chối yêu cầu: {_detail(e)}") from e
        ch = r.choices[0]
        if ch.finish_reason == "length":
            raise Truncated(ch.message.content or "")
        return ch.message.content or ""
    raise UserError("API từ chối mọi cấu hình yêu cầu. Hãy kiểm tra lại model và Base URL.")


def _session_client():
    s = state.current()
    if s.llm_cfg is None:
        s.llm_cfg, s.llm_client = db.load_llm_cfg(s.user_id), None
    cfg = s.llm_cfg
    if cfg["broken"]:
        raise UserError(BROKEN)
    if not cfg["api_key"]:
        raise UserError(NO_KEY)
    if not cfg["model"]:
        raise UserError(NO_MODEL)
    if s.llm_client is None:
        s.llm_client = make_client(cfg)
    return s.llm_client, cfg


def ensure_ready():
    """Báo lỗi sớm (trước khi chạy tác vụ) nếu người dùng chưa cấu hình key/model."""
    _session_client()


def llm(system, user, max_tokens=8000, json_mode=False):
    client, cfg = _session_client()
    return chat(client, cfg, system, user, max_tokens, json_mode)


def test_connection(cfg):
    """Gọi thử một câu rất ngắn để biết key + model + Base URL có dùng được không. Ném UserError nếu không."""
    client = make_client(cfg)
    try:
        client.chat.completions.create(model=cfg["model"], max_tokens=16, messages=[{"role": "user", "content": "Trả lời đúng một chữ: OK"}])
    except Exception as e:                           # noqa: BLE001
        raise (explain(e, cfg) or UserError(f"API từ chối yêu cầu: {_detail(e)}")) from e


def list_models(cfg):
    client = make_client(cfg)
    try:
        ids = sorted({(m.id or "").removeprefix("models/") for m in client.models.list()})
    except Exception as e:                           # noqa: BLE001
        raise (explain(e, cfg) or UserError(f"Không lấy được danh sách model: {_detail(e)}")) from e
    return [i for i in ids if i][:300]


def _balance(s):
    """JSON bị cắt cụt: đóng chuỗi/ngoặc còn thiếu để cứu phần đã có."""
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    return s + ('"' if in_str else "") + "".join(reversed(stack))


def parse_json(t):
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S) or re.search(r"```(?:json)?\s*(.*)$", t, re.S)
    t = (m.group(1) if m else t).strip()
    a = t.find("{")
    if a < 0:
        raise ValueError("Không thấy JSON trong câu trả lời")
    b = t.rfind("}")
    body = t[a: b + 1] if b > a else t[a:]
    body = body.replace("\u201c", '"').replace("\u201d", '"')
    cands = [body, re.sub(r",\s*([}\]])", r"\1", body), _balance(re.sub(r",\s*([}\]])", r"\1", t[a:]))]
    err = None
    for c in cands:
        try:
            return json.loads(c, strict=False)         # strict=False: cho phép xuống dòng thật bên trong chuỗi (code Python)
        except Exception as e:                         # noqa: BLE001
            err = e
    # bị cắt cụt giữa phần tử: lùi về dấu phẩy gần nhất (phần tử hoàn chỉnh cuối cùng) rồi đóng ngoặc
    tail = re.sub(r",\s*([}\]])", r"\1", t[a:])
    for pos in [m.start() for m in re.finditer(",", tail)][::-1][:60]:
        try:
            return json.loads(_balance(tail[:pos]), strict=False)
        except Exception:                              # noqa: BLE001
            continue
    raise ValueError(f"JSON không hợp lệ: {err}")


def llm_json(system, user, max_tokens=8000):
    """Tối đa 3 lần: (1) bình thường; (2) báo rõ lỗi để model sửa; (3) tăng giới hạn token nếu bị cắt."""
    note, tokens, err = "", max_tokens, None
    for attempt in range(3):
        try:
            return parse_json(llm(system, user + note, tokens, json_mode=True))
        except Truncated:
            tokens = min(tokens * 2, 32000)
            note = "\n\nCÂU TRẢ LỜI TRƯỚC BỊ CẮT DO QUÁ DÀI. Hãy viết NGẮN GỌN hơn, bỏ giải thích thừa, vẫn đủ các trường bắt buộc."
            err = "câu trả lời bị cắt do quá dài"
        except ValueError as e:
            err = str(e)
            note = f"\n\nLẦN TRƯỚC JSON KHÔNG HỢP LỆ ({err[:120]}). Chỉ trả về đúng 1 đối tượng JSON hợp lệ: đóng đủ ngoặc, dấu ngoặc kép trong chuỗi phải thoát bằng \\\", xuống dòng trong code dùng \\n. Không giải thích."
    raise RuntimeError(f"AI trả về dữ liệu không đọc được sau 3 lần thử ({err}). Hãy bấm Thử lại, hoặc rút gọn góp ý.")


def strip_code(t):
    m = re.search(r"```(?:python)?\s*(.*?)```", t, re.S)
    return (m.group(1) if m else t).strip()
