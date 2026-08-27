#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""feishu-op.py —— 知识点库调度助手（规避 PowerShell 中文编码陷阱）。
中文关键字均在 .py 内以 UTF-8 保存，经 json.dumps 与 urllib 传输，确保飞书写入不乱码。

用法（参数全 ASCII）:
  python feishu-op.py claim      <app_token> <table_id> <token> <record_id> <agent_name>
  python feishu-op.py verify     <app_token> <table_id> <token> <record_id> <agent_name>
  python feishu-op.py writeback  <app_token> <table_id> <token> <record_id> <count> <filename>
  python feishu-op.py fail       <app_token> <table_id> <token> <record_id> <reason>
  python feishu-op.py get        <app_token> <table_id> <token> <record_id>
"""
import sys, json, time, urllib.request

APPS = "https://open.feishu.cn/open-apis/bitable/v1/apps"


def req(url, token, body=None, method="POST"):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "Bearer " + token)
    r.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode("utf-8"))


def put(app, table, token, rid, fields):
    url = f"{APPS}/{app}/tables/{table}/records/{rid}"
    return req(url, token, {"fields": fields}, method="PUT")


def get(app, table, token, rid):
    url = f"{APPS}/{app}/tables/{table}/records/{rid}"
    return req(url, token, method="GET")


def now_ms():
    return str(int(time.time() * 1000))


def main():
    a = sys.argv[1]
    app, table, token = sys.argv[2], sys.argv[3], sys.argv[4]
    if a == "claim":
        rid, agent = sys.argv[5], sys.argv[6]
        r = put(app, table, token, rid, {
            "状态": "执行中",
            "负责Agent": agent,
            "开始时间": now_ms(),
        })
        print(json.dumps(r, ensure_ascii=False))
    elif a == "verify":
        rid, agent = sys.argv[5], sys.argv[6]
        r = get(app, table, token, rid)
        f = r.get("data", {}).get("record", {}).get("fields", {})
        cur = f.get("负责Agent")
        cur = cur[0]["text"] if isinstance(cur, list) else cur
        print(json.dumps({"responsible": cur, "match": cur == agent}, ensure_ascii=False))
    elif a == "writeback":
        rid, count, fname = sys.argv[5], int(sys.argv[6]), sys.argv[7]
        r = put(app, table, token, rid, {
            "状态": "完成",
            "结束时间": now_ms(),
            "产出条数": count,
            "校验结果": "通过",
            "负责Agent": "agent-ls-01",
            "备注": fname,
        })
        print(json.dumps(r, ensure_ascii=False))
    elif a == "fail":
        rid, reason = sys.argv[5], sys.argv[6]
        r = put(app, table, token, rid, {
            "状态": "失败",
            "结束时间": now_ms(),
            "备注": reason,
        })
        print(json.dumps(r, ensure_ascii=False))
    elif a == "get":
        rid = sys.argv[5]
        print(json.dumps(get(app, table, token, rid), ensure_ascii=False))


if __name__ == "__main__":
    main()