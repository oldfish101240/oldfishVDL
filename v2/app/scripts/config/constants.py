#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常數定義模組
"""

# 應用程式資訊
APP_NAME = "oldfish影片下載器"
APP_VERSION = "2.1.0-Release"
APP_VERSION_HOME = "2.2.0-Release - 2026.05.10"

# Console 日誌預設等級（建議正式使用 WARNING：只顯示必要警告/錯誤）
# 可選："DEBUG" / "INFO" / "WARNING" / "ERROR"
# 注意：constants.py 盡量保持「不 import 專案內模組」，避免被單獨執行或被工具掃描時因路徑問題噴錯
DEFAULT_LOG_LEVEL = "DEBUG"

# 音訊品質選項
AUDIO_QUALITIES = [
    {"label": "320kbps", "value": "320"},
    {"label": "256kbps", "value": "256"},
    {"label": "192kbps", "value": "192"},
    {"label": "128kbps", "value": "128"},
    {"label": "96kbps", "value": "96"},
]

# 預設設定
DEFAULT_SETTINGS = {
    'enableNotifications': True,
    'addResolutionToFilename': False,
    'customDownloadPath': '',
    'maxConcurrentDownloads': 3,
    'playlistNotificationMode': 'complete',  # 'complete': 整個播放清單完成才通知, 'each': 每部影片完成就通知
    'enableDevCommands': False,
    'hideDevCommandEnableWarning': False,
    'themeColor': '#3498db',  # 主題主色調（十六進位色碼）
    'themeMode': 'dark',
    'themeAccent': 'blue',
    'lightMode': False,  # 淺色模式
}

# 視窗設定
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640
WINDOW_MIN_WIDTH = 800
WINDOW_MIN_HEIGHT = 520
SETTINGS_WINDOW_WIDTH = 500
SETTINGS_WINDOW_HEIGHT = 350
