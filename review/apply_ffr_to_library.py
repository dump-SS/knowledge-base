#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 ffr 表（review/tables_20260906/ffr.ndjson）里"已修正"的结果回写到 docs/knowledge-points 原始库。

采用字节级字段替换（不重排 JSON），保持原文件格式与未改动字段不变。

规则：
- 只处理 验收结果 == '已修正'
- 字段映射：example/typical_errors/keywords/prerequisites 直接；
  '乱码' 按 问题描述 前缀 -> example/typical_errors/name
- 值还原：
  example/name            -> 字符串整段覆盖
  typical_errors/keywords -> 按 '；' 拆成数组
  prerequisites           -> '无' 置空 []；否则把等于"字段原文"的元素替换为"修正内容"
- 同 (id, field) 去重（修正内容不一致则报错）
- typical_errors 修正后允许 <3 条（YY_WY_G1_B1_U1_006、YY_WY_G1_B1_U6_009 单独放行）

用法：
  python apply_ffr_to_library.py --dry-run
  python apply_ffr_to_library.py --apply
"""
import argparse
import collections
import glob
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE = "review/tables_20260906/ffr.ndjson"
KB = "docs/knowledge-points"


def first(v):
    return v[0] if isinstance(v, list) and v else v


def resolve_field(rec):
    pf = first(rec.get("问题字段"))
    if pf in ("example", "typical_errors", "keywords", "prerequisites"):
        return pf
    if pf == "乱码":
        lead = re.split(r"[ ：:（(]", (rec.get("问题描述") or "").strip(), 1)[0]
        return {"example": "example", "typical_errors": "typical_errors", "name": "name"}.get(lead)
    return None


def reconstruct(rec, field, point):
    c = (rec.get("修正内容") or "").strip()
    if field == "prerequisites":
        if c in ("无", "", "None"):
            return []
        old = (rec.get("字段原文") or "").strip()
        cur = list(point.get("prerequisites") or [])
        if old in cur:
            return [c if x == old else x for x in cur]
        return cur + [c]
    if field in ("typical_errors", "keywords"):
        return [x.strip() for x in c.split("；") if x.strip()]
    return c


def replace_field_in_block(block, field, new_value):
    if field in ("example", "name"):
        pattern = re.compile(r'"' + field + r'"\s*:\s*"(?:[^"\\]|\\.)*"')
        new_block, n = pattern.subn(
            lambda m: '"' + field + '": ' + json.dumps(new_value, ensure_ascii=False),
            block,
            count=1,
        )
        assert n == 1, (field, "string replace failed")
        return new_block
    if field in ("keywords", "prerequisites"):
        pattern = re.compile(r'"' + field + r'"\s*:\s*\[[^\]]*\]')
        new_block, n = pattern.subn(
            lambda m: '"' + field + '": ' + json.dumps(new_value, ensure_ascii=False),
            block,
            count=1,
        )
        assert n == 1, (field, "inline array replace failed")
        return new_block
    if field == "typical_errors":
        pattern = re.compile(r'"typical_errors"\s*:\s*\[[\s\S]*?\]')
        items = [json.dumps(x, ensure_ascii=False) for x in new_value]
        inner = ",\n        ".join(items)
        repl = '"typical_errors": [\n        ' + inner + '\n      ]'
        new_block, n = pattern.subn(lambda m: repl, block, count=1)
        assert n == 1, (field, "multiline array replace failed")
        return new_block
    raise ValueError(field)


def build_changes():
    rows = [json.loads(l) for l in open(SOURCE, encoding="utf-8")]
    fixed = [r for r in rows if first(r.get("验收结果")) == "已修正"]

    lib = {}
    for fn in sorted(glob.glob(f"{KB}/*.json")):
        d = json.load(open(fn, encoding="utf-8"))
        for p in d.get("l2_points", []):
            lib[p["id"]] = (fn, p)

    ops = collections.defaultdict(dict)  # id -> field -> rec
    skipped = []
    for r in fixed:
        iid = r["id"]
        f = resolve_field(r)
        if f is None:
            skipped.append((iid, first(r.get("问题字段")), "无法解析字段"))
            continue
        if iid not in lib:
            skipped.append((iid, f, "id不在库中"))
            continue
        prev = ops[iid].get(f)
        if prev is not None and (prev.get("修正内容") or "") != (r.get("修正内容") or ""):
            skipped.append((iid, f, "同字段修正内容不一致"))
            continue
        ops[iid][f] = r

    changes = collections.defaultdict(dict)  # filepath -> {id: {field: new}}
    field_stats = collections.Counter()
    for iid, fmap in ops.items():
        fn, point = lib[iid]
        for f, rec in fmap.items():
            new = reconstruct(rec, f, point)
            changes[fn].setdefault(iid, {})[f] = new
            field_stats[f] += 1

    return changes, skipped, field_stats, lib, len(fixed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        ap.error("必须指定 --dry-run 或 --apply")

    changes, skipped, field_stats, lib, fixed_count = build_changes()
    op_count = sum(len(fmap) for fmap in changes.values())
    print(f"已修正记录: {fixed_count}")
    print(f"去重后操作数: {op_count} | 涉及文件数: {len(changes)}")
    print("字段分布:", dict(field_stats))
    for s in skipped:
        print("SKIP:", s)

    if args.dry_run:
        print("\n-- 预览 --")
        for fn in sorted(changes):
            for iid, fmap in changes[fn].items():
                print(f"\n[{fn.split('/')[-1]}] {iid}")
                for f, new in fmap.items():
                    old = lib[iid][1].get(f)
                    print(f"  {f}: {repr(old)[:70]}")
                    print(f"     -> {repr(new)[:100]}")
        return

    # 先在内存里全部生成并校验，再统一写入，避免中途失败造成部分写入
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
                block = replace_field_in_block(block, f, new)
            edits.append((start, end, block))
        for start, end, block in sorted(edits, key=lambda x: x[0], reverse=True):
            raw = raw[:start] + block + raw[end:]
        json.loads(raw)  # 校验可解析
        to_write[fn] = raw

    for fn, raw in to_write.items():
        open(fn, "w", encoding="utf-8").write(raw)

    print(f"\n已写回 {len(to_write)} 个文件")
    print("下一步: python validate_kb.py --dir docs/knowledge-points")


if __name__ == "__main__":
    main()
