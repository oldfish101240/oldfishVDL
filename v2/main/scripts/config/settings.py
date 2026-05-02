#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定管理模組
"""

import os
import sys
import json

# 添加父目錄到路徑，以便導入其他模組
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # main/scripts
root_dir = os.path.dirname(parent_dir)  # main
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from scripts.config.constants import DEFAULT_SETTINGS
from scripts.utils.logger import debug_console, error_console, warning_console

class SettingsManager:
    """設定管理器"""
    
    def __init__(self, root_dir):
        self.root_dir = root_dir
        # 與設定視窗保持一致，統一使用 main/settings.json
        self.settings_file = os.path.join(root_dir, 'main', 'settings.json')
    
    def load_settings(self):
        """載入設定"""
        try:
            debug_console("載入設定中...")
            
            if os.path.exists(self.settings_file):
                try:
                    with open(self.settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                    
                    # 確保所有預設設定都存在
                    for key, value in DEFAULT_SETTINGS.items():
                        if key not in settings:
                            settings[key] = value
                    
                    debug_console(f"設定載入成功: {settings}")
                    return settings
                    
                except json.JSONDecodeError as e:
                    warning_console(f"設定檔案JSON格式錯誤: {e}")
                    warning_console("將使用預設設定並重新建立設定檔案")
                    # 備份損壞的設定檔案
                    backup_file = self.settings_file + '.backup'
                    try:
                        import shutil
                        shutil.copy2(self.settings_file, backup_file)
                        debug_console(f"已備份損壞的設定檔案到: {backup_file}")
                    except Exception as backup_e:
                        debug_console(f"備份設定檔案失敗: {backup_e}")
                    
                    # 重新建立設定檔案
                    self.save_settings(DEFAULT_SETTINGS)
                    return DEFAULT_SETTINGS.copy()
                    
                except UnicodeDecodeError as e:
                    warning_console(f"設定檔案編碼錯誤: {e}")
                    warning_console("將使用預設設定")
                    return DEFAULT_SETTINGS.copy()
            else:
                debug_console("設定檔案不存在，使用預設設定")
                return DEFAULT_SETTINGS.copy()
                
        except Exception as e:
            error_console(f"載入設定失敗: {e}")
            return DEFAULT_SETTINGS.copy()
    
    def save_settings(self, settings):
        """儲存設定"""
        try:
            debug_console(f"儲存設定: {settings}")
            
            # 確保目錄存在
            settings_dir = os.path.dirname(self.settings_file)
            os.makedirs(settings_dir, exist_ok=True)
            
            # 寫入檔案
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            debug_console("設定儲存成功")
            
        except Exception as e:
            error_console(f"儲存設定失敗: {e}")
            raise
    
    def reset_to_defaults(self):
        """重設為預設值"""
        try:
            debug_console("重設為預設值")
            return DEFAULT_SETTINGS.copy()
        except Exception as e:
            error_console(f"重設為預設值失敗: {e}")
            return DEFAULT_SETTINGS.copy()

    def get(self, key, default=None):
        """取得單一設定鍵值，若不存在回傳預設值"""
        try:
            settings = self.load_settings()
            return settings.get(key, default)
        except Exception as e:
            error_console(f"讀取設定鍵值失敗: {e}")
            return default