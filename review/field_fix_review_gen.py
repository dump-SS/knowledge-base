# -*- coding: utf-8 -*-
"""
从已有 review 数据生成"其他字段补充表"，不重跑 review。

规则：
- 遍历 science/arts 两份 total_review.json 的所有 issue；
- issue 前缀为 definition/explanation 的跳过（原表已覆盖）；
- 其余按字段分类：example / typical_errors / prerequisites / keywords / 乱码 / 其他；
- 含"乱码/错字/语句不通/读不懂/占位/残留"等文本破损指示词的归入"乱码"桶（清理类工作，与内容错误区分）；
- 用 id 回查原始 JSON 取对应字段原文快照。

输出：review/field_fix_review.csv（UTF-8 BOM，一行 = 一个字段问题，按置信度升序）
"""

import json
import glob
import csv
import re

SUBJECT_CN = {"SX": "数学", "HX": "化学", "WL": "物理", "SW": "生物",
              "YW": "语文", "YY": "英语", "LS": "历史", "DL": "地理", "ZZ": "政治"}

# 文本破损/残留指示词 -> 归入"乱码"桶
GARB = ["乱码", "错字", "错词", "错别字", "语句不通", "语句破碎", "表意不通",
        "语义不通", "读不懂", "生造", "占位", "残留", "未替换", "混入"]

SKIP = {"definition", "explanation"}
FIELD_MAP = {"example": "example", "typical_errors": "typical_errors",
             "prerequisites": "prerequisites", "keywords": "keywords"}

FIELDNAMES = ["id", "学科", "知识点", "置信度", "问题字段", "字段原文",
              "问题描述", "修正内容", "验收结果"]


def lead(s: str) -> str:
    return re.split(r"[ ：:（(]", s.strip(), 1)[0]


def snapshot(kp: dict, f: str) -> str:
    if f == "name":
        return kp.get("name", "")
    if f == "name/definition":
        return f"{kp.get('name', '')} | {kp.get('definition', '')}"
    v = kp.get(f, "")
    if isinstance(v, list):
        return "；".join(str(x) for x in v)
    return v if isinstance(v, str) else str(v)


def main() -> None:
    index = {}
    for f in glob.glob("docs/knowledge-points/*.json"):
        for kp in json.load(open(f, encoding="utf-8")).get("l2_points", []):
            index[kp["id"]] = kp

    rows = []
    for f in sorted(glob.glob("review/reviews/*/total_review.json")):
        for r in json.load(open(f, encoding="utf-8")):
            kp = index.get(r["id"], {})
            for iss in r.get("issues", []):
                F = lead(iss)
                if F in SKIP:
                    continue
                if any(g in iss for g in GARB):
                    pf = "乱码"
                elif F in FIELD_MAP:
                    pf = FIELD_MAP[F]
                else:
                    pf = "其他"
                rows.append({
                    "id": r["id"],
                    "学科": SUBJECT_CN.get(r["id"].split("_")[0], "?"),
                    "知识点": r.get("name") or kp.get("name", ""),
                    "置信度": r["confidence"],
                    "问题字段": pf,
                    "字段原文": snapshot(kp, F),
                    "问题描述": iss,
                    "修正内容": "",
                    "验收结果": "",
                })

    rows.sort(key=lambda x: x["置信度"])

    with open("review/field_fix_review.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(rows)

    print(f"共 {len(rows)} 行，已写 review/field_fix_review.csv")


if __name__ == "__main__":
    main()
