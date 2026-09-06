#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 likx（理科）与 wk（文科）两张低置信度表里"已修正"的结果回写到 docs/knowledge-points。

两表字段一致：
  修正后定义 -> definition
  修正后详解 -> explanation

字节级字符串替换，不重排 JSON。

用法：
  python apply_defexp_to_library.py --dry-run
  python apply_defexp_to_library.py --apply
"""
import argparse
import collections
import glob
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TABLES = {
    "likx": "review/tables_20260906/likx.ndjson",
    "wk": "review/tables_20260906/wk.ndjson",
}
KB = "docs/knowledge-points"


def first(v):
    return v[0] if isinstance(v, list) and v else v


def replace_string_in_block(block, field, new_value):
    pattern = re.compile(r'"' + field + r'"\s*:\s*"(?:[^"\\]|\\.)*"')
    new_block, n = pattern.subn(
        lambda m: '"' + field + '": ' + json.dumps(new_value, ensure_ascii=False),
        block,
        count=1,
    )
    assert n == 1, (field, "replace failed")
    return new_block


def build_changes():
    lib = {}
    for fn in sorted(glob.glob(f"{KB}/*.json")):
        d = json.load(open(fn, encoding="utf-8"))
        for p in d.get("l2_points", []):
            lib[p["id"]] = (fn, p)

    changes = collections.defaultdict(dict)  # fn -> {id: {field: new}}
    stats = collections.Counter()
    skipped = []
    for table, path in TABLES.items():
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        fixed = [r for r in rows if first(r.get("验收结果")) == "已修正"]
        for r in fixed:
            iid = r["id"]
            if iid not in lib:
                skipped.append((table, iid, "id不在库中"))
                continue
            defn = (r.get("修正后定义") or "").strip()
            expl = (r.get("修正后详解") or "").strip()
            if not defn or not expl:
                skipped.append((table, iid, "修正字段为空"))
                continue
            fn, _ = lib[iid]
            changes[fn].setdefault(iid, {})["definition"] = defn
            changes[fn].setdefault(iid, {})["explanation"] = expl
            stats[table] += 1
    return changes, skipped, stats, lib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        ap.error("必须指定 --dry-run 或 --apply")

    changes, skipped, stats, lib = build_changes()
    op_count = sum(len(fmap) for fmap in changes.values())
    print("已修正记录(按表):", dict(stats))
    print("去重后操作数:", op_count, "| 涉及文件数:", len(changes))
    for s in skipped:
        print("SKIP:", s)

    if args.dry_run:
        print("\n-- 预览 --")
        for fn in sorted(changes):
            for iid, fmap in changes[fn].items():
                print(f"\n[{fn.split('/')[-1]}] {iid}")
                for f, new in fmap.items():
                    old = lib[iid][1].get(f)
                    print(f"  {f}: {repr(old)[:60]}")
                    print(f"     -> {repr(new)[:80]}")
        return

    to_write = {}
    for fn in sorted(changes):
        id_changes = changes[fn]
        raw = open(fn, encoding="utf-8").read()
        edits = []
        for iid, fmap in id_changes.items():
            anchor = '"id": ' + json.dumps(iid, ensure_ascii=False)
            p = raw.find(anchor)
            if p < 0:
                raise SystemExit(f"[FAIL] {fn}: 找不到 id {iid}")
            start = raw.rfind("\n    {", 0, p)
            end = raw.find("\n    }", p)
            if start < 0 or end < 0:
                raise SystemExit(f"[FAIL] {fn}: {iid} 块边界异常")
            end += len("\n    }")
            block = raw[start:end]
            for f, new in fmap.items():
                block = replace_string_in_block(block, f, new)
            edits.append((start, end, block))
        for start, end, block in sorted(edits, key=lambda x: x[0], reverse=True):
            raw = raw[:start] + block + raw[end:]
        json.loads(raw)
        to_write[fn] = raw

    for fn, raw in to_write.items():
        open(fn, "w", encoding="utf-8").write(raw)

    print(f"\n已写回 {len(to_write)} 个文件")
    print("下一步: python validate_kb.py --dir docs/knowledge-points")


if __name__ == "__main__":
    main()
