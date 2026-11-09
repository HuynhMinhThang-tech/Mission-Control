/* Quy tắc hiển thị số DUY NHẤT của giao diện (cùng quy tắc với app/utils.py và export/assets/live.js; sửa ở đâu thì sửa cả ba):
     số nguyên          1.234.567        (không có phần thập phân)
     số thập phân       1.234,50         (luôn đúng 2 chữ số sau dấu phẩy)
     tỷ lệ / phần trăm  54,20%           (luôn đúng 2 chữ số sau dấu phẩy)
     tiền               1.234.567 đ      (ghi ĐỦ số kèm đơn vị của dữ liệu; không viết tắt nghìn/triệu/tỷ)            */
const FMT = (() => {
  const nf = d => new Intl.NumberFormat('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: true });
  const f0 = nf(0), f2 = nf(2);
  const ok = v => v !== null && v !== undefined && v !== '' && typeof v !== 'boolean' && isFinite(+v);
  const isInt = x => Math.abs(x - Math.round(x)) < 1e-9;
  const raw = v => v === null || v === undefined ? '' : String(v);
  const num = v => ok(v) ? (isInt(+v) ? f0.format(Math.round(+v)) : f2.format(+v)) : raw(v);       // nguyên -> không thập phân, lẻ -> 2 chữ số
  const dec = v => ok(v) ? f2.format(+v) : raw(v);                                                  // luôn 2 chữ số (cột có số lẻ)
  const pct = p => ok(p) ? f2.format(+p) + '%' : raw(p);                                            // p theo đơn vị % (54.2 -> 54,20%)
  const ratio = r => ok(r) ? pct(+r * 100) : raw(r);                                                // r là tỷ lệ 0..1
  const val = (v, u) => !ok(v) ? '—' : u === '%' ? pct(v) : u ? num(v) + ' ' + u : num(v);          // giá trị kèm đơn vị của dữ liệu
  const colFmt = vals => (vals || []).some(v => ok(v) && !isInt(+v)) ? dec : (v => ok(v) ? f0.format(Math.round(+v)) : raw(v));
  return { num, dec, pct, ratio, val, colFmt };
})();
