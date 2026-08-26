# -*- coding: utf-8 -*-
"""上游功能哨兵：检测上游仓库的新功能提交并开 issue 提醒。

设计要点：
- 噪音过滤：每日自动数据提交（[Auto] / data: 前缀等）不算功能，直接忽略
- 去重以 issue 为准：正文内嵌 <!-- upstream-sha: xxxxx --> 隐藏标记，
  已提及（含已关闭）的 sha 不再重复开 issue。cherry-pick 后 sha 会变，
  因此不能用 git 历史/patch-id 去重
- --dry-run：只打印将执行的动作，不创建 issue（本地测试用）
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import urllib.request
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.notify import send_email

NOISE_PATTERNS = [
    r"^\[Auto\]",
    r"^data:",
    r"^\[Force\]",
    r"^\[CI\]",
    r"^chore: (bump|update) (data|deps)",
]


def sh(*args, cwd=None):
    result = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd
    )
    if result.returncode != 0:
        raise RuntimeError(f"命令失败 {' '.join(args)}:\n{result.stderr}")
    return result.stdout.strip()


def is_noise(message: str) -> bool:
    first_line = message.splitlines()[0].strip() if message else ""
    return any(re.search(p, first_line, re.IGNORECASE) for p in NOISE_PATTERNS)


def upstream_new_commits() -> list:
    """上游有、origin/main 没有的提交，按时间正序。"""
    out = sh("git", "log", "--no-merges", "--date=short",
             "--format=%H%x1f%an%x1f%ad%x1f%B%x1e",
             "origin/main..upstream/main")
    commits = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        sha, author, date, body = (record.strip().split("\x1f", 3) + [""] * 4)[:4]
        commits.append({"sha": sha, "author": author, "date": date, "message": body.strip()})
    return commits


def list_known_shas(repo: str, token: str) -> set:
    """从全部（含已关闭）upstream-feature issue 的隐藏标记提取已提醒的短 sha。"""
    url = f"https://api.github.com/repos/{repo}/issues?labels=upstream-feature&state=all&per_page=100"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req) as resp:
        issues = json.loads(resp.read().decode("utf-8"))
    known = set()
    for issue in issues:
        for m in re.finditer(r"<!-- upstream-sha: ([0-9a-f]{7,40}) -->", issue.get("body") or ""):
            known.add(m.group(1)[:7])
    return known


def ensure_label(repo: str, token: str):
    url = f"https://api.github.com/repos/{repo}/labels"
    data = json.dumps({"name": "upstream-feature", "color": "5319e7",
                       "description": "上游仓库待评估/已处理的功能提交"}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }, method="POST")
    try:
        urllib.request.urlopen(req)
        print("  已创建标签 upstream-feature")
    except urllib.error.HTTPError as e:
        if e.code == 422:  # 已存在
            pass
        else:
            raise


def create_issue(repo: str, token: str, commit: dict, upstream_repo: str) -> int:
    short = commit["sha"][:7]
    url = f"https://github.com/{upstream_repo}/commit/{commit['sha']}"
    compare = f"https://github.com/{upstream_repo}/compare/{short}"
    try:
        stat = sh("git", "show", "--stat", "--format=", commit["sha"]).splitlines()[:15]
        stat_text = "\n".join(stat) if stat else "（无文件改动信息）"
    except RuntimeError:
        stat_text = "（无法获取改动统计）"

    title = commit["message"].splitlines()[0][:60] or "上游新提交"
    body = f"""<!-- upstream-sha: {short} -->

## 上游新功能提交待评估

| | |
|---|---|
| 提交 | [{short}]({url}) |
| 作者 | {commit['author']} |
| 日期 | {commit['date']} |

**提交说明**
```
{commit['message'][:800]}
```

**改动概览**
```
{stat_text}
```

## 处理方式

**想要这个功能** —— 在本地执行后推送：
```bash
git fetch upstream
git cherry-pick {short}
# 冲突高发文件：index.html / css/style.css / book.html
```

**不想要** —— 直接关闭本 issue。

处理完成后关闭即可（已关闭的 issue 不会重复提醒）。
"""
    api = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps({"title": f"[上游] {title}", "body": body,
                       "labels": ["upstream-feature"]}).encode()
    req = urllib.request.Request(api, data=data, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }, method="POST")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["number"]


def main():
    parser = argparse.ArgumentParser(description="上游功能哨兵")
    parser.add_argument("--dry-run", action="store_true", help="只打印动作，不创建 issue")
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "scoful/FanqieRankTracker")
    upstream_repo = os.environ.get("UPSTREAM_REPO", "wen1701/FanqieRankTracker")
    token = os.environ.get("GH_TOKEN", "")

    # 保证 origin/main 是最新的；dry-run 跳过（本地测试不应有副作用）
    if args.dry_run:
        print("（dry-run：跳过 fetch，使用现有引用）")
    else:
        try:
            sh("git", "fetch", "origin", "main", "--no-tags")
        except RuntimeError as e:
            print(f"⚠️  fetch origin 失败，使用现有 origin/main 引用: {e.splitlines()[-1]}")

    commits = upstream_new_commits()
    features = [c for c in commits if not is_noise(c["message"])]
    noise_count = len(commits) - len(features)
    print(f"上游新提交 {len(commits)} 个，其中功能提交 {len(features)} 个、数据噪音 {noise_count} 个")

    if not features:
        print("✅ 没有新的功能提交，无需提醒")
        return

    if args.dry_run or not token:
        for c in features:
            print(f"  [dry-run] 将开 issue: {c['sha'][:7]} {c['message'].splitlines()[0][:50]}")
        return

    ensure_label(repo, token)
    known = list_known_shas(repo, token)
    print(f"历史已提醒: {len(known)} 个")

    created = 0
    created_issues = []
    for c in features:
        short = c["sha"][:7]
        if short in known:
            print(f"  ⏭️  已提醒过: {short}")
            continue
        number = create_issue(repo, token, c, upstream_repo)
        title = c["message"].splitlines()[0][:50]
        print(f"  ✅ 新 issue #{number}: {short} {title}")
        created_issues.append((number, short, title))
        created += 1

    print(f"完成：新开 {created} 个提醒 issue")

    if created_issues and not args.dry_run:
        lines = [f"上游仓库 {upstream_repo} 有 {len(created_issues)} 个新功能提交待评估：", ""]
        for number, short, title in created_issues:
            lines.append(f"- #{number} {title}")
            lines.append(f"  https://github.com/{repo}/issues/{number}")
        lines += [
            "",
            "处理方式：想要 → cherry-pick 后关闭 issue；不想要 → 直接关闭。",
            "详情见 issue 正文（含改动统计与摘取命令）。",
        ]
        send_email(
            f"[番茄风向标] 上游有 {len(created_issues)} 个新功能提交待评估",
            "\n".join(lines),
        )


if __name__ == "__main__":
    main()
