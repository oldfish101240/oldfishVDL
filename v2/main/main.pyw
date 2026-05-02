 #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程式入口點
"""

import os
import sys
import argparse

# 添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 確保使用內嵌的 Python 環境
python_embed_dir = os.path.join(current_dir, 'lib', 'python_embed')
if python_embed_dir not in sys.path:
    sys.path.insert(0, python_embed_dir)

from scripts.ui.main_window import create_app
from scripts.utils.logger import debug_console, info_console, error_console, warning_console, set_log_level, LogLevel
from scripts.utils.file_utils import ensure_directories
from scripts.config.constants import DEFAULT_LOG_LEVEL

def parse_launcher_args():
    """解析由 launcher 傳入的啟動旗標。"""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--safe", action="store_true")
    parser.add_argument("--no-gpu", action="store_true")
    parser.add_argument("--require-admin", action="store_true")
    parser.add_argument("--launcher-elevated", action="store_true")
    args, _ = parser.parse_known_args()
    return args

def apply_runtime_flags(args):
    """套用會影響 Qt/WebEngine 啟動的旗標。"""
    chromium_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    merged_flags = []
    if chromium_flags:
        merged_flags.append(chromium_flags)
    if args.no_gpu:
        merged_flags.extend(["--disable-gpu", "--disable-gpu-compositing"])
    if args.safe:
        # safe 模式偏向穩定性，關閉沙盒並禁用 GPU
        merged_flags.extend(["--no-sandbox", "--disable-gpu", "--disable-gpu-compositing"])

    if merged_flags:
        # 去重後寫回環境變數，避免重複旗標
        unique_flags = []
        for flag in " ".join(merged_flags).split():
            if flag not in unique_flags:
                unique_flags.append(flag)
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(unique_flags)

def main():
    """主函數"""
    try:
        launcher_args = parse_launcher_args()
        apply_runtime_flags(launcher_args)

        # 設定日誌等級：允許由環境變數覆寫，方便開發工具快速切換
        log_level_str = os.environ.get("OLDFISH_LOG_LEVEL", str(DEFAULT_LOG_LEVEL))
        level = getattr(LogLevel, log_level_str.upper(), LogLevel.INFO)
        set_log_level(level)
        
        # 獲取根目錄
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(ROOT_DIR):
            ROOT_DIR = os.path.abspath(ROOT_DIR)
        
        info_console("啟動 oldfish影片下載器...")
        debug_console(f"根目錄: {ROOT_DIR}")
        debug_console(
            f"啟動旗標: safe={launcher_args.safe}, no_gpu={launcher_args.no_gpu}, "
            f"require_admin={launcher_args.require_admin}, launcher_elevated={launcher_args.launcher_elevated}"
        )
        
        # 確保必要的目錄存在
        ensure_directories(ROOT_DIR)
        
        # 創建應用程式
        app, window = create_app(ROOT_DIR)
        
        # 運行應用程式
        sys.exit(app.exec())
        
    except Exception as e:
        error_console(f"啟動應用程式失敗: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
