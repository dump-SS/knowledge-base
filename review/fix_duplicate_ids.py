# -*- coding: utf-8 -*-
"""
修正 l2_points.id 与文件名的册号/模块段不一致问题，并同步更新 prerequisites 引用。

规则：id 的 册段(G#B#) 与 模块段 对齐文件名（仅修正与文件名不一致的条目）。
覆盖（92 处）：
  SW_G1B2_JYBZ.json        9 条  模块段 JYBD -> JYBZ（内容不同，两文件都保留）
  WL_G1B2_PTYD.json       22 条  册号   G1B1 -> G1B2
  YY_WY_G1B1_U2..U6.json  60 条  册号   B2..B6 -> B1
  YY_WY_G1B3_U3.json       1 条  模块段 U4 -> U3（恰好补上缺失的 U3_004 空号）

关键设计：
  - 映射按文件作用域：同一旧 id 可能同时存在于两个文件（如 YY_WY_G1_B2_U2_001
    在 G1B1_U2 与 G1B2_U2），只改"与自身文件名不一致"的那个文件，另一个不动。
  - prerequisites 的旧 id 引用随所在文件一并替换（34 个不同 id、65 处引用），避免制造新断链。
  - 应用阶段做字节级替换：只替换旧 id 字符串，文件其余字节原样保留，
    保证 diff 里只有 id 与 prerequisites 引用行的变化。
"""

import json
import re
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent.parent / "docs" / "knowledge-points"

G_RE = re.compile(r"G\d+")
B_RE = re.compile(r"B\d+")


def file_id_map(d: dict, file_book: str, file_mod: str) -> dict[str, str]:
    """返回该文件内 id 与文件名不一致的 {旧id: 新id}。"""
    m: dict[str, str] = {}
    for p in d.get("l2_points", []):
        pid = p.get("id", "")
        seg = pid.split("_")
        gi = next((i for i, s in enumerate(seg) if G_RE.fullmatch(s)), None)
        bi = next((i for i, s in enumerate(seg) if B_RE.fullmatch(s)), None)
        if gi is None or bi is None or bi + 1 >= len(seg):
            continue
        if seg[gi] + seg[bi] != file_book or seg[bi + 1] != file_mod:
            new = seg[:]
            new[gi], new[bi], new[bi + 1] = file_book[:2], file_book[2:], file_mod
            m[pid] = "_".join(new)
    return m


def main() -> None:
    files = sorted(SOURCE_DIR.glob("*.json"))

    # 1) 先扫描，汇总各文件的修正映射并核对总数
    plans: dict[str, dict[str, str]] = {}
    for f in files:
        stem = f.name[:-5]
        fm = re.search(r"(G\d+B\d+)", stem)
        if not fm:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        m = file_id_map(d, fm.group(1), stem.split("_")[-1])
        if m:
            plans[f.name] = m
    total = sum(len(m) for m in plans.values())
    print(f"待修正: {total} 个 id, 分布: {', '.join(f'{k}:{len(v)}' for k, v in sorted(plans.items()))}")
    assert total == 92, f"预期 92 处不一致，实际 {total}"

    # 2) 应用修改：字节级替换（只换旧 id 串，其余内容与格式原样保留），
    #    避免 json round-trip 重排数组等无关格式导致 diff 噪音
    n_files = n_id = n_ref = 0
    for f in files:
        m = plans.get(f.name)
        if not m:
            continue
        raw = f.read_bytes()
        changed_bytes = raw
        for old, new in m.items():
            b_old, b_new = old.encode("utf-8"), new.encode("utf-8")
            assert changed_bytes.count(b_old) > 0, f"{f.name}: 未找到 {old}"
            changed_bytes = changed_bytes.replace(b_old, b_new)
        # 防御性校验：改后文件内 id 不得重复
        d = json.loads(changed_bytes.decode("utf-8"))
        ids = [p["id"] for p in d.get("l2_points", [])]
        dup = {x for x in ids if ids.count(x) > 1}
        assert not dup, f"{f.name} 修改后出现重复 id: {dup}"
        f.write_bytes(changed_bytes)
        n_files += 1
        n_id += len(m)
        # 统计该文件 prerequisites 引用替换数
        d_old = json.loads(raw.decode("utf-8"))
        for p in d_old.get("l2_points", []):
            for x in p.get("prerequisites") or []:
                if x in m:
                    n_ref += 1
        print(f"  {f.name}: id {len(m)} 条, prerequisites 引用 {n_ref} 处")

    print(f"\n共改写 {n_files} 个文件, {n_id} 个 id, {n_ref} 处 prerequisites 引用")


if __name__ == "__main__":
    main()
