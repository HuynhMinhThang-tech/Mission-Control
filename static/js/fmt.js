/* Quy tắc hiển thị số DUY NHẤT của giao diện (cùng quy tắc với app/utils.py và export/assets/live.js; sửa ở đâu thì sửa cả ba):
     số nguyên          1.234.567        (không có phần thập phân)
     số thập phân       1.234,50         (luôn đúng 2 chữ số sau dấu phẩy; trọng lượng, điểm, trung bình... giữ nguyên phần lẻ)
     tỷ lệ / phần trăm  54,20%           (luôn đúng 2 chữ số sau dấu phẩy)
     tiền               1.234.567 đ      (ghi ĐỦ số kèm đơn vị của dữ liệu; không viết tắt nghìn/triệu/tỷ; KHÔNG có phần thập phân:
                                          3.724.488.031,25 đ hiện là 3.724.488.031 đ)
   Chỉ TIỀN bị bỏ phần thập phân. Muốn biết một số có phải tiền không thì phải truyền đơn vị (`u`): numU, val, colFmt, colUnit. */
const FMT = (() => {
  const nf = d => new Intl.NumberFormat('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: true });
  const f0 = nf(0), f2 = nf(2);
  const ok = v => v !== null && v !== undefined && v !== '' && typeof v !== 'boolean' && isFinite(+v);
  const isInt = x => Math.abs(x - Math.round(x)) < 1e-9;
  const raw = v => v === null || v === undefined ? '' : String(v);
  const isMoney = u => /^(đ|đồng|vnd|vnđ|₫)$/i.test(String(u ?? '').trim());
  const whole = v => f0.format(+v);                                                                 // Intl làm tròn nửa ra xa số 0, giống app/utils.py: _round_half_away
  const num = v => ok(v) ? (isInt(+v) ? f0.format(Math.round(+v)) : f2.format(+v)) : raw(v);       // nguyên -> không thập phân, lẻ -> 2 chữ số
  const numU = (v, u) => ok(v) ? (isMoney(u) ? whole(v) : num(v)) : raw(v);                        // như num nhưng theo đơn vị: tiền thì nguyên đồng
  const dec = v => ok(v) ? f2.format(+v) : raw(v);                                                  // luôn 2 chữ số (cột có số lẻ)
  const pct = p => ok(p) ? f2.format(+p) + '%' : raw(p);                                            // p theo đơn vị % (54.2 -> 54,20%)
  const ratio = r => ok(r) ? pct(+r * 100) : raw(r);                                                // r là tỷ lệ 0..1
  const val = (v, u) => !ok(v) ? '—' : u === '%' ? pct(v) : isMoney(u) ? whole(v) + ' đ' : u ? num(v) + ' ' + u : num(v);   // giá trị kèm đơn vị của dữ liệu
  const colFmt = (vals, u) => isMoney(u) ? (v => ok(v) ? whole(v) : raw(v))
    : (vals || []).some(v => ok(v) && !isInt(+v)) ? dec : (v => ok(v) ? f0.format(Math.round(+v)) : raw(v));
  /* Đơn vị suy từ TÊN cột: chỉ dùng cho bản lưu cũ chưa có `units` do máy chủ tính (app/labels.py: unit là nguồn chính). */
  const unitOf = name => { const n = String(name ?? '').toLowerCase();
    if (/\((đ|vnđ|vnd)\)/.test(n)) return 'đ';
    if (/\(%\)|tỷ lệ|tỷ trọng/.test(n)) return '%';
    if (/số lượng|trọng lượng|số đơn|điểm|đánh giá|giá trị/.test(n)) return '';
    return /doanh thu|doanh số|lợi nhuận|chi phí|tổng tiền|thành tiền|tiền|giá|lương|thu nhập|ngân sách|vốn|thuế|phí/.test(n) ? 'đ' : '' };
  const colUnit = (t, j) => t && t.units && t.units[j] !== undefined ? t.units[j] : unitOf(t && t.cols && t.cols[j]);
  /* Chuỗi tiền đã định dạng từ bản lưu cũ ('3.724.488.031,25 đ') -> bỏ phần thập phân. Chuỗi khác giữ nguyên. */
  const money = s => { const m = /^\s*([-−]?)(\d{1,3}(?:\.\d{3})*|\d+),(\d+)\s*(đ|đồng|VN[ĐD])\s*$/i.exec(String(s ?? ''));
    return m ? (m[1] ? '−' : '') + whole(m[2].replace(/\./g, '') + '.' + m[3]) + ' đ' : s };
  return { num, numU, dec, pct, ratio, val, colFmt, isMoney, unitOf, colUnit, money };
})();
