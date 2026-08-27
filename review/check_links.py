# -*- coding: utf-8 -*-
"""
prerequisites 断链检查：
1. 收集 docs/knowledge-points 全部 l2_points 的 id 到集合；
2. 遍历每个 l2_points 的 prerequisites，检查引用的 id 是否存在于集合；
3. 输出断链明细（格式：知识点id -> 引用不存在: 前置id），最后打印断链总数。

只读源目录；报告（断链检查报告.txt）写入本脚本所在目录（review/）。
"""

import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent   # review/
REPO_ROOT = SCRIPT_DIR.parent
SOURCE_DIR = REPO_ROOT / "docs" / "knowledge-points"
REPORT_FILE = SCRIPT_DIR / "断链检查报告.txt"


def iter_l2_points() -> list[tuple[Path, dict]]:
    """读取全部 JSON，返回 [(文件路径, l2_point), ...]。"""
    points: list[tuple[Path, dict]] = []
    for f in sorted(SOURCE_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[警告] 无法解析 {f.name}: {e}")
            continue
        raw = data.get("l2_points")
        if not isinstance(raw, list):
            print(f"[警告] {f.name} 缺少 l2_points 列表")
            continue
        for p in raw:
            if isinstance(p, dict):
                points.append((f, p))
    return points


def main() -> None:
    points = iter_l2_points()

    all_ids: set[str] = set()
    missing_id_files: set[str] = set()
    duplicate_ids: set[str] = set()

    for f, p in points:
        pid = p.get("id")
        if not pid:
            missing_id_files.add(f.name)
            continue
        if pid in all_ids:
            duplicate_ids.add(pid)
        all_ids.add(pid)

    broken: list[tuple[str, str]] = []  # (知识点id, 缺失前置id)
    for f, p in points:
        pid = p.get("id")
        for prereq in p.get("prerequisites", []) or []:
            if prereq not in all_ids:
                broken.append((pid, prereq))

    lines = [f"{pid} -> 引用不存在: {missing}" for pid, missing in broken]
    lines.append(f"\n断链总数: {len(broken)}")
    if duplicate_ids:
        dup = sorted(duplicate_ids)
        lines.append(f"提示: 发现 {len(dup)} 个重复 id（已去重后检查），前 10 个: {dup[:10]}")
    if missing_id_files:
        lines.append(f"提示: {sorted(missing_id_files)} 中存在缺少 id 的知识点")

    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        print(line)

    print(f"\n报告已写入: {REPORT_FILE}")
    n_files = sum(1 for _ in SOURCE_DIR.glob("*.json"))
    print(f"检查范围: {len(points)} 条知识点, {len(all_ids)} 个唯一 id, {n_files} 个文件")


if __name__ == "__main__":
    main()
