# -*- coding: utf-8 -*-
"""
三个低置信度审校表的批处理准备脚本。

逻辑：
- pending = 验收结果为空 或 含"待"；
- 理科表(likx)/文科表(wk)：问题描述仅涉及 definition/explanation 之外字段的行，
  其修正由 field_fix_review 表对应行承载（表内无相应修正列），自动判"无需修正直接通过"，
  仅当该 id 在 FFR 表无对应行时才转人工批次；
- 其余行 + FFR 全部 pending 行 → 按学科分组、约22条一批输出到 review/fixwork/；
- 自动通过行输出 {tbl}_autopass.json。

输出批次文件字段：LIKE/WK: record_id,id,学科,知识点,置信度,问题描述,定义原文,详解原文
                FFR: record_id,id,学科,知识点,置信度,问题字段,字段原文,问题描述
"""
import json
import os

BATCH_SIZE = 22
OUT = "review/fixwork"
TABLES = {
    "like": ("review/likx.ndjson", ["record_id", "id", "学科", "知识点", "置信度", "问题描述", "定义原文", "详解原文"]),
    "wk": ("review/wk.ndjson", ["record_id", "id", "学科", "知识点", "置信度", "问题描述", "定义原文", "详解原文"]),
    "ffr": ("review/ffr.ndjson", ["record_id", "id", "学科", "知识点", "置信度", "问题字段", "字段原文", "问题描述"]),
}


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def pending(rec):
    st = "".join(rec.get("验收结果") or [])
    return (not st) or ("待" in st)


def proj(rec, keys):
    return {k: rec.get(k) for k in keys}


def main():
    os.makedirs(OUT, exist_ok=True)
    data = {t: load(p) for t, (p, _) in TABLES.items()}
    ffr_ids = {r["id"] for r in data["ffr"]}

    plan = {}
    for tbl in ("like", "wk"):
        recs = [r for r in data[tbl] if pending(r)]
        agent_rows, autopass, uncovered = [], [], []
        for r in recs:
            d = r.get("问题描述") or ""
            has_defexp = any(t in d for t in ("definition", "explanation", "定义", "详解"))
            if not has_defexp:
                if r["id"] in ffr_ids:
                    autopass.append({"record_id": r["record_id"], "id": r["id"],
                                     "问题描述": d})
                else:
                    uncovered.append(r)
            else:
                agent_rows.append(r)
        # FFR 无对应行的非定义/详解问题行，转人工判断
        agent_rows.extend(uncovered)
        keys = TABLES[tbl][1]
        plan[tbl] = (agent_rows, autopass, uncovered)
        with open(f"{OUT}/{tbl}_autopass.json", "w", encoding="utf-8") as f:
            json.dump(autopass, f, ensure_ascii=False, indent=1)

    plan["ffr"] = ([r for r in data["ffr"] if pending(r)], [], [])

    total_batches = 0
    for tbl, (rows, autopass, uncovered) in plan.items():
        keys = TABLES[tbl][1]
        rows = sorted(rows, key=lambda r: ("".join(r.get("学科") or []), r["id"]))
        n = 0
        for i in range(0, len(rows), BATCH_SIZE):
            n += 1
            chunk = [proj(r, keys) for r in rows[i:i + BATCH_SIZE]]
            with open(f"{OUT}/{tbl}_b{n:02d}.json", "w", encoding="utf-8") as f:
                json.dump(chunk, f, ensure_ascii=False, indent=1)
        total_batches += n
        unc = f"，FFR无对应行转人工 {len(uncovered)} 条({[r['id'] for r in uncovered]})" if uncovered else ""
        print(f"{tbl}: pending相关 {len(rows)+len(autopass)} = 人工 {len(rows)} (分{n}批) + 自动通过 {len(autopass)}{unc}")

    print(f"共 {total_batches} 个批次文件，输出目录 {OUT}/")


if __name__ == "__main__":
    main()
