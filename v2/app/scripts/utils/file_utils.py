#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檔案和路徑處理工具模組
"""

import os
from .logger import debug_console, error_console

def ensure_directories(root_dir):
    """確保必要的目錄存在"""
    try:
        downloads_dir = os.path.join(root_dir, 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        thumb_cache_dir = os.path.join(root_dir, 'thumb_cache')
        os.makedirs(thumb_cache_dir, exist_ok=True)
        
        debug_console("必要目錄已確保存在")
    except OSError as e:
        error_console(f"創建必要目錄失敗: {e}")

def safe_path_join(*paths):
    """安全地連接路徑，處理相對路徑和絕對路徑"""
    if not paths:
        return ""
    
    # 過濾掉空路徑
    valid_paths = [str(p) for p in paths if p]
    if not valid_paths:
        return ""
    
    # 使用 os.path.join 連接路徑
    result = os.path.join(*valid_paths)
    
    # 正規化路徑（處理 .. 和 . 等）
    result = os.path.normpath(result)
    
    return result

def resolve_relative_path(path, root_dir):
    """解析相對路徑為絕對路徑，相對於根目錄"""
    if not path:
        return ""
    
    # 如果是絕對路徑，直接返回
    if os.path.isabs(path):
        return path
    
    # 相對路徑，相對於根目錄
    return os.path.join(root_dir, path)

def get_download_path(root_dir, settings_manager):
    """獲取下載路徑，優先使用設定檔中的路徑"""
    try:
        settings = settings_manager.load_settings()
        custom_path = (settings.get('customDownloadPath', '') or '').strip()
        
        # 有自訂路徑時嘗試建立資料夾（若已存在則不影響），成功即使用
        if custom_path:
            try:
                os.makedirs(custom_path, exist_ok=True)
                return custom_path
            except Exception:
                # 建立失敗則回退至預設路徑
                pass
        
        # 否則使用預設路徑
        return safe_path_join(root_dir, 'downloads')
    except Exception as e:
        # 發生錯誤時回退到預設路徑
        return safe_path_join(root_dir, 'downloads')

def get_assets_path(root_dir):
    """獲取資源檔案路徑"""
    return safe_path_join(root_dir, 'assets')

def get_deno_path(root_dir):
    """獲取 Deno 可執行文件路徑（用於 yt-dlp 的 JavaScript 執行時）"""
    try:
        import sys
        # Deno 位於 lib/deno 目錄中
        deno_dir = safe_path_join(root_dir, 'lib', 'deno')
        
        # 根據平台選擇可執行文件名
        if sys.platform.startswith('win'):
            deno_exe = 'deno.exe'
        else:
            deno_exe = 'deno'
        
        deno_path = safe_path_join(deno_dir, deno_exe)
        
        # 檢查文件是否存在
        if os.path.exists(deno_path):
            return deno_path
        
        # 如果標準位置不存在，嘗試其他可能的位置
        # 例如直接在 deno_dir 中查找
        for possible_name in [deno_exe, 'deno']:
            possible_path = safe_path_join(deno_dir, possible_name)
            if os.path.exists(possible_path):
                return possible_path
        
        # 如果都找不到，返回 None（表示 Deno 不可用）
        return None
    except Exception as e:
        error_console(f"獲取 Deno 路徑失敗: {e}")
        return None