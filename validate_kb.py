#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_kb.py —— 知识点库全量结构化校验脚本

用法:
    python validate_kb.py --dir ./drafts
    python validate_kb.py --file module_xxx.json

校验项（对应《知识点库对齐规范 v1.0》§2、§6.4）:
    - JSON 可解析、顶层含 module_path / l2_points
    - ID 格式合规 + 模块内唯一
    - difficulty / frequency 范围 1-5
    - typical_errors >= 3 条 + 质量启发式
    - example 以 [仿题] 开头
    - explanation 长度 80-200 字
    - prerequisites 均为合法 ID（悬空引用检查，需全量加载后二次扫描）
    - difficulty / frequency 分布异常告警
"""

import argparse
import glob
import json
import os
import re
from collections import Counter

# ---------- ID 正则（对应 §2.1）----------
# 多版本: ^[A-Z]{2,3}_[A-Z]+_G[1-2](?:_B[1-3])?_[A-Z0-9]{2,6}_\d{3}$
# 单版本: ^[A-Z]{2,3}_G[1-2](?:_B[1-3])?_[A-Z0-9]{2,6}_\d{3}$
ID_RE = re.compile(
    r'^[A-Z]{2,3}(?:_[A-Z]+)?_G[1-2](?:_B[1-3])?_[A-Z0-9]{2,6}_\d{3}$'
)

FUZZY_ERRORS = ("概念不清", "计算错误", "审题不清", "理解不透彻", "掌握不牢")


def check_point(p, errors, all_ids):
    lp = p.get("l2_point", p)  # 兼容两种结构
    pid = lp.get("id", "")

    # ID 格式
    if not pid:
        errors.append(f"{pid or '<空ID>'}: 缺少 id 字段")
    elif not ID_RE.match(pid):
        errors.append(f"{pid}: ID 格式不符合规范")

    # difficulty / frequency
    for field in ("difficulty", "frequency"):
        val = lp.get(field)
        if not isinstance(val, int) or not (1 <= val <= 5):
            errors.append(f"{pid}: {field}={val!r} 超出 1-5 整数范围")

    # typical_errors
    te = lp.get("typical_errors", [])
    if not isinstance(te, list) or len(te) < 3:
        errors.append(f"{pid}: typical_errors 少于 3 条 (实际 {len(te) if isinstance(te, list) else '非数组'})")
    else:
        for e in te:
            if not isinstance(e, str) or len(e) < 8:
                errors.append(f"{pid}: typical_errors 条目过短/非法: {e!r}")
            if any(f in e for f in FUZZY_ERRORS):
                errors.append(f"{pid}: typical_errors 含泛泛废话: '{e}'")

    # example
    ex = lp.get("example", "")
    if not isinstance(ex, str) or not ex.startswith("[仿题]"):
        errors.append(f"{pid}: example 未以 [仿题] 开头")

    # explanation
    exp = lp.get("explanation", "")
    if not isinstance(exp, str):
        errors.append(f"{pid}: explanation 非字符串")
    else:
        n = len(exp)
        if n < 80:
            errors.append(f"{pid}: explanation 过短 (<80字, 实际 {n})")
        elif n > 200:
            errors.append(f"{pid}: explanation 过长 (>200字, 实际 {n})")

    # keywords
    kw = lp.get("keywords", [])
    if not isinstance(kw, list) or not (3 <= len(kw) <= 8):
        errors.append(f"{pid}: keywords 数量不符合 3-8 (实际 {len(kw) if isinstance(kw, list) else '非数组'})")

    # prerequisites 悬空引用（依赖全量 all_ids，首次扫描留 None）
    pre = lp.get("prerequisites", None)
    if pre is None:
        errors.append(f"{pid}: 缺少 prerequisites 字段")
    elif not isinstance(pre, list):
        errors.append(f"{pid}: prerequisites 非数组")
    elif all_ids is not None:
        for ref in pre:
            if ref and ref not in all_ids:
                errors.append(f"{pid}: prerequisites 引用悬空 ID: {ref}")

    # name 长度
    name = lp.get("name", "")
    if not (5 <= len(name) <= 15):
        errors.append(f"{pid}: name 长度不符合 5-15 字 (实际 {len(name)})")

    # definition 长度
    definition = lp.get("definition", "")
    if len(definition) > 40:
        errors.append(f"{pid}: definition 超过 40 字")

    # 合规启发式（占位词检测）
    for text, label in ((exp, "explanation"), (definition, "definition")):
        if "见教材" in text or "（略）" in text or text.endswith("略"):
            errors.append(f"{pid}: {label} 疑似引用教材原文/占位")


def _ids_in_file(path):
    """提取单个文件内已定义的 ID 集合，供悬空引用自检。"""
    try:
        points, _ = load_points(path)
    except Exception:
        return set()
    return {
        (p.get("l2_point", p)).get("id")
        for p in points
        if (p.get("l2_point", p)).get("id")
    }


def load_points(path):
    """支持单个 JSON 对象 或 JSON 数组两种文件格式"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        if "l2_points" in data:
            return data["l2_points"], data.get("module_path", "")
        # 单条对象
        return [data], ""
    if isinstance(data, list):
        return data, ""
    raise ValueError(f"{path}: 无法解析的知识点结构")


def validate_file(path, all_ids):
    errors = []
    try:
        points, module_path = load_points(path)
    except Exception as e:
        return [f"{path}: 文件解析失败 - {e}"]

    seen = set()
    for p in points:
        lp = p.get("l2_point", p)
        pid = lp.get("id", "")
        if pid in seen:
            errors.append(f"{pid}: 模块内 ID 重复")
        seen.add(pid)
        check_point(p, errors, all_ids)

    return errors


def distribution(points, field):
    counter = Counter()
    for p in points:
        lp = p.get("l2_point", p)
        val = lp.get(field)
        if isinstance(val, int):
            counter[str(val)] += 1
    return dict(sorted(counter.items()))


def main():
    parser = argparse.ArgumentParser(description="高中知识点库结构化校验")
    parser.add_argument("--dir", help="待校验目录（批量扫描 *.json）")
    parser.add_argument("--file", help="单个 JSON 文件")
    args = parser.parse_args()

    if not (args.dir or args.file):
        parser.error("必须指定 --dir 或 --file")

    # ---- 第一次扫描：收集全部 ID（供悬空引用检查）----
    files = []
    if args.dir:
        files = sorted(glob.glob(os.path.join(args.dir, "**", "*.json"), recursive=True))
    if args.file:
        files.append(args.file)

    all_ids = set()
    all_points = []
    for fp in files:
        try:
            points, _ = load_points(fp)
            all_points.extend(points)
            for p in points:
                pid = (p.get("l2_point", p)).get("id")
                if pid:
                    all_ids.add(pid)
        except Exception:
            pass  # 解析失败在第二次扫描报错

    print(f"📦 全量加载: {len(files)} 个文件, {len(all_ids)} 个唯一 ID\n")

    # ---- 第二次扫描：完整校验（此时 all_ids 已齐，可做悬空检查）----
    total_errors = []
    file_reports = []
    for fp in files:
        errs = validate_file(fp, all_ids)
        total_errors.extend(errs)
        file_reports.append((fp, errs))

    # ---- 打印每个文件结果 + 分布 ----
    for fp, errs in file_reports:
        if errs:
            print(f"❌ {fp} —— {len(errs)} 个问题")
            for e in errs[:10]:
                print(f"    · {e}")
            if len(errs) > 10:
                print(f"    · ... 另有 {len(errs)-10} 条")
        else:
            print(f"✅ {fp}")
    print()

    # ---- 全量分布统计 ----
    if all_points:
        print("📊 全库难度分布:", distribution(all_points, "difficulty"))
        print("📊 全库考频分布:", distribution(all_points, "frequency"))
        for field in ("difficulty", "frequency"):
            counter = Counter()
            for p in all_points:
                lp = p.get("l2_point", p)
                v = lp.get(field)
                if isinstance(v, int):
                    counter[v] += 1
            total = sum(counter.values())
            if total:
                for k in sorted(counter):
                    ratio = counter[k] / total
                    if ratio > 0.6:
                        print(f"⚠️  {field}={k} 占比 {ratio:.0%} > 60%，疑似标注失衡")
                    elif counter[k] == 0:
                        print(f"⚠️  {field}={k} 数量为 0，疑似标注失衡")

    print()
    if total_errors:
        print(f"🔴 校验未通过: 共 {len(total_errors)} 个问题")
        raise SystemExit(1)
    else:
        print("🟢 全部通过，可以移入 kb_v1/ 并灌库")


if __name__ == "__main__":
    main()
