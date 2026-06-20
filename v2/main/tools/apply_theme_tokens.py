#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""將 main.html 硬編碼色碼替換為 OFTheme CSS 變數（一次性工具）"""

from pathlib import Path

HTML = Path(__file__).resolve().parent.parent / "main.html"

# 順序：先長／先具體，避免部分替換
REPLACEMENTS = [
    # accent 衍生（動態）
    ("#9af0bf", "var(--of-accent-light)"),
    ("#6ee7a8", "var(--of-accent-lighter)"),
    ("#257a52", "var(--of-accent-active)"),
    ("#1d3227", "var(--of-accent-muted-bg)"),
    ("#2f5a42", "var(--of-accent-muted-border)"),
    ("#244232", "var(--of-accent-muted-bg-hover)"),
    ("#3f7556", "var(--of-accent-muted-border-hover)"),
    ("#d8f3e3", "var(--of-accent-muted-text)"),
    ("#ecfdf5", "var(--of-accent-on-muted)"),
    ("#d1fae5", "var(--of-accent-on-muted-2)"),
    ("#1e2a24", "var(--of-accent-surface-tint)"),
    ("#1a2520", "var(--of-accent-surface-tint-2)"),
    ("#e8f5e9", "var(--of-accent-completed-bg)"),
    ("#f0fdf4", "var(--of-accent-completed-bg-2)"),
    ("#b7ebc9", "var(--of-accent-completed-border-2)"),
    ("#e7f8ee", "var(--of-accent-completed-bg-2)"),
    ("#6acb91", "var(--of-accent-lighter)"),
    ("#15803d", "var(--of-accent-completed-text)"),
    # 結構色
    ("#1f242b", "var(--of-surface-popup)"),
    ("#1c1f26", "var(--of-surface-2)"),
    ("#1a1d23", "var(--of-bg-elevated)"),
    ("#16181d", "var(--of-bg)"),
    ("#181a20", "var(--of-bg)"),
    ("#23262f", "var(--of-surface)"),
    ("#2b2e37", "var(--of-bg-card)"),
    ("#121418", "var(--of-scrollbar-track)"),
    ("#4a4f59", "var(--of-scrollbar-thumb-hover)"),
    ("#3a3f4a", "var(--of-scrollbar-thumb)"),
    ("#3d4450", "var(--of-border-panel)"),
    ("#e5e7eb", "var(--of-text)"),
    ("#f3f4f6", "var(--of-text-inverse)"),
    ("#b0b0b0", "var(--of-text-secondary)"),
    ("#9ca3af", "var(--of-text-muted-2)"),
    ("#888", "var(--of-text-dim)"),
    ("#aaa", "var(--of-text-muted)"),
    ("#444", "var(--of-border)"),
    ("#333", "var(--of-border-subtle)"),
    ("#666", "var(--of-disabled)"),
    # 面板／dev-cmd（需與 theme.js 衍生 token 對應；執行腳本後由 JS 覆寫）
    ("#3a4150", "var(--of-hover-neutral)"),
    ("#171b24", "var(--of-panel-bg)"),
    ("#1a2130", "var(--of-panel-bg-top)"),
    ("#171f2d", "var(--of-panel-bg-tools)"),
    ("#151922", "var(--of-panel-bg-body)"),
    ("#1b2230", "var(--of-panel-bg-row)"),
    ("#212b3b", "var(--of-panel-bg-row-hover)"),
    ("#2b3341", "var(--of-panel-border)"),
    ("#2c3645", "var(--of-panel-border-sub)"),
    ("#283244", "var(--of-panel-border-mid)"),
    ("#303a49", "var(--of-panel-border-row)"),
    ("#4a5c78", "var(--of-panel-border-row-hover)"),
    ("#f8fafc", "var(--of-panel-text-title)"),
    ("#a9b6cb", "var(--of-panel-text-desc)"),
    ("#dbe6f7", "var(--of-panel-text-master)"),
    ("#eef2ff", "var(--of-panel-text-file)"),
    ("#94a3b8", "var(--of-panel-text-path)"),
    ("#4d5564", "var(--of-dev-cmd-match)"),
    ("#93c5fd", "var(--of-dev-cmd-rest)"),
    ("#2a2f38", "var(--of-dev-cmd-border)"),
    ("color: #fff", "color: var(--of-on-accent)"),
    ("color:#fff", "color:var(--of-on-accent)"),
]

SKIP_REGIONS = []  # 若需跳過可擴充


def main():
    text = HTML.read_text(encoding="utf-8")
    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if text == original:
        print("No changes made.")
        return
    HTML.write_text(text, encoding="utf-8")
    print(f"Updated {HTML} ({len(REPLACEMENTS)} rules)")


if __name__ == "__main__":
    main()
