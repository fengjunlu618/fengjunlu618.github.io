#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 GitHub 账号下所有启用 Pages 的仓库，生成 pages.json（动态索引页的数据源）

- 本地运行：GHPAGES_INDEX_TOKEN / GH_TOKEN / GITHUB_TOKEN 任选其一注入即可
- Actions 运行：仓库 secret GHPAGES_INDEX_TOKEN（需含 repo 权限，否则只能扫到当前仓库）
- 输出 pages.json：前端 index.html 运行时 fetch 渲染
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

LOGIN = os.environ.get("GHPAGES_LOGIN", "fengjunlu618")
TOKEN = (
    os.environ.get("GHPAGES_INDEX_TOKEN")
    or os.environ.get("GH_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or ""
)
HDR = {
    "Authorization": "token %s" % TOKEN,
    "Accept": "application/vnd.github+json",
    "User-Agent": "pages-index-bot",
}
API = "https://api.github.com"


def get(url):
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception:
        return 0, {}


def list_repos():
    """优先 /user/repos（含私有，需 token）；token 无效时回退公开仓库列表"""
    repos, page = [], 1
    while True:
        st, data = get("%s/user/repos?per_page=100&page=%d" % (API, page))
        if st == 200 and data:
            repos += [r["name"] for r in data]
            if len(data) < 100:
                break
            page += 1
        else:
            break
    if repos:
        return repos
    page = 1
    while True:
        st, data = get("%s/users/%s/repos?per_page=100&page=%d" % (API, LOGIN, page))
        if st == 200 and data:
            repos += [r["name"] for r in data]
            if len(data) < 100:
                break
            page += 1
        else:
            break
    return repos


def main():
    repos = list_repos()
    sites = []
    for name in repos:
        st, d = get("%s/repos/%s/%s/pages" % (API, LOGIN, name))
        if st != 200:
            continue
        base = d.get("html_url") or ("https://%s.github.io/%s/" % (LOGIN, name))
        st2, r = get("%s/repos/%s/%s" % (API, LOGIN, name))
        branch = (r.get("default_branch") or "main") if st2 == 200 else "main"
        st3, t = get("%s/repos/%s/%s/git/trees/%s?recursive=1" % (API, LOGIN, name, branch))
        htmls = []
        if st3 == 200:
            for item in t.get("tree", []):
                p = item.get("path", "")
                if p.lower().endswith(".html"):
                    htmls.append(p)
        htmls.sort()
        sites.append(
            {
                "repo": name,
                "branch": branch,
                "base": base,
                "pages": [{"path": p, "url": base + p} for p in htmls],
            }
        )
        time.sleep(0.05)

    total_pages = sum(len(s["pages"]) for s in sites)
    data = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "total_sites": len(sites),
        "total_pages": total_pages,
        "total_repos": len(repos),
        "sites": sites,
    }
    with open("pages.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("sites:", len(sites), "| pages:", total_pages, "| written: pages.json")


if __name__ == "__main__":
    main()
