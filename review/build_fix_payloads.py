# -*- coding: utf-8 -*-
"""
校验审校结果并生成飞书批量回写负载。

- 校验：结果与输入条数/顺序/record_id 一致；verdict 合法；fixed 行修正字段非空、其余为空；
- 合并：各表人工结果 + 自动通过行（like/wk）；
- 输出：review/fixwork/payload_{tbl}_{n}.json，形如 {"update_records": {rid: {字段ID: CellValue}}}，
  select 值为数组；单文件不超过 100 条。
"""
import json
import sys

OUT = "review/fixwork"
BATCHES = {
    "like": ["like_b01", "like_b02"],
    "wk": ["wk_b01", "wk_b02", "wk_b03", "wk_b04"],
    "ffr": ["ffr_b01", "ffr_b02", "ffr_b03", "ffr_b04"],
}
FIELDS = {
    "like": {"定义": "fld300iPcM", "详解": "fldCd1v3uZ", "状态": "fld1HXYZB6"},
    "wk": {"定义": "fld2DeuVmp", "详解": "fldHK1yHsm", "状态": "fld1IBoy6n"},
    "ffr": {"修正": "fld7xzTrjB", "状态": "fld1GM4UQD"},
}
VERDICT = {
    "like": {"fixed": "已修正", "pass": "无需修正直接通过", "rewrite": "难以修正需重写"},
    "wk": {"fixed": "已修正", "pass": "无需修正直接通过", "rewrite": "难以修正需重写"},
    "ffr": {"fixed": "已修正", "pass": "无需修正", "rewrite": " 无法修改/问题不明"},
}
CORR_KEY = {"like": ("修正后定义", "修正后详解"), "wk": ("修正后定义", "修正后详解"), "ffr": ("修正内容",)}


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def main():
    stats = {}
    payloads = {}
    for tbl, batches in BATCHES.items():
        results = []
        for b in batches:
            src = load(f"{OUT}/{b}.json")
            res = load(f"{OUT}/{b}_result.json")
            if len(src) != len(res):
                sys.exit(f"[FAIL] {b}: 条数不一致 {len(src)} vs {len(res)}")
            for s, r in zip(src, res):
                if s["record_id"] != r.get("record_id"):
                    sys.exit(f"[FAIL] {b}: record_id 不一致 {s['record_id']} vs {r.get('record_id')}")
                v = r.get("verdict")
                if v not in VERDICT[tbl]:
                    sys.exit(f"[FAIL] {b} {s['id']}: verdict 非法 {v}")
                filled = [k for k in CORR_KEY[tbl] if (r.get(k) or "").strip()]
                if v == "fixed" and len(filled) != len(CORR_KEY[tbl]):
                    sys.exit(f"[FAIL] {b} {s['id']}: fixed 但修正字段不全 {filled}")
                if v != "fixed" and filled:
                    sys.exit(f"[FAIL] {b} {s['id']}: 非 fixed 却有修正 {filled}")
                if not (r.get("reason") or "").strip():
                    sys.exit(f"[FAIL] {b} {s['id']}: 缺 reason")
            results.extend(res)
        # like/wk 自动通过行
        autopass = load(f"{OUT}/{tbl}_autopass.json") if tbl in ("like", "wk") else []
        upd = {}
        for r in results:
            cell = {FIELDS[tbl]["状态"]: [VERDICT[tbl][r["verdict"]]]}
            if r["verdict"] == "fixed":
                if tbl == "ffr":
                    cell[FIELDS[tbl]["修正"]] = r["修正内容"]
                else:
                    cell[FIELDS[tbl]["定义"]] = r["修正后定义"]
                    cell[FIELDS[tbl]["详解"]] = r["修正后详解"]
            if r["record_id"] in upd:
                sys.exit(f"[FAIL] {tbl}: record_id 重复 {r['record_id']}")
            upd[r["record_id"]] = cell
        for a in autopass:
            if a["record_id"] in upd:
                sys.exit(f"[FAIL] {tbl}: autopass 与人工重复 {a['record_id']}")
            upd[a["record_id"]] = {FIELDS[tbl]["状态"]: [VERDICT[tbl]["pass"]]}
        vc = {}
        for r in results:
            vc[r["verdict"]] = vc.get(r["verdict"], 0) + 1
        stats[tbl] = (len(results), vc, len(autopass), len(upd))
        # 分块写负载
        keys = list(upd.keys())
        n = 0
        for i in range(0, len(keys), 100):
            n += 1
            chunk = {k: upd[k] for k in keys[i:i + 100]}
            with open(f"{OUT}/payload_{tbl}_{n}.json", "w", encoding="utf-8") as f:
                json.dump({"update_records": chunk}, f, ensure_ascii=False)
        payloads[tbl] = n

    for tbl, (cnt, vc, ap, total) in stats.items():
        print(f"{tbl}: 人工 {cnt} {vc} + 自动通过 {ap} = {total} 条，负载文件 {payloads[tbl]} 个")
    print("校验全部通过")


if __name__ == "__main__":
    main()
