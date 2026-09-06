#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 likx/wk 回写后超长的 2 条 definition 收短到 40 字内。"""
import glob
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FIXES = {
    "WL_G1_B4_JXZD_006": "简谐运动中，远离平衡位置速度减小、加速度增大；靠近时速度增大、加速度减小。",
    "YY_WY_G1_B3_U5_006": "compared with、given that等固定化过去分词短语作独立成分。",
}
KB = "docs/knowledge-points"


def main():
    lib = {}
    for fn in sorted(glob.glob(f"{KB}/*.json")):
        d = json.load(open(fn, encoding="utf-8"))
        for p in d.get("l2_points", []):
            lib[p["id"]] = fn

    for iid, new in FIXES.items():
        assert len(new) <= 40, (iid, len(new))
        fn = lib[iid]
        raw = open(fn, encoding="utf-8").read()
        anchor = '"id": ' + json.dumps(iid, ensure_ascii=False)
        p = raw.find(anchor)
        assert p >= 0, iid
        start = raw.rfind("\n    {", 0, p)
        end = raw.find("\n    }", p) + len("\n    }")
        block = raw[start:end]
        pat = re.compile(r'"definition"\s*:\s*"(?:[^"\\]|\\.)*"')
        block2, n = pat.subn(
            lambda m: '"definition": ' + json.dumps(new, ensure_ascii=False),
            block,
            count=1,
        )
        assert n == 1, iid
        raw = raw[:start] + block2 + raw[end:]
        json.loads(raw)
        open(fn, "w", encoding="utf-8").write(raw)
        print(f"{iid}: {len(new)} 字 -> {new}")


if __name__ == "__main__":
    main()
