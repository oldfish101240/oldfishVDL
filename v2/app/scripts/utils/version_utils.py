#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本處理工具模組
"""

import re

def compare_versions(version1, version2):
    """比較兩個版本號，返回 -1, 0, 1 分別表示 version1 <, =, > version2"""
    def version_tuple(v):
        # 處理空字串或None
        if not v or not str(v).strip():
            return (0,)
        
        v_str = str(v).strip()
        parts = []
        
        for part in v_str.split('.'):
            # 移除非數字字符，只保留數字部分
            numeric_part = re.sub(r'[^\d]', '', part)
            if numeric_part:
                try:
                    parts.append(int(numeric_part))
                except ValueError:
                    parts.append(0)
            else:
                # 如果整個部分都是非數字，檢查是否為特殊標識符
                if part.lower() in ['alpha', 'beta', 'rc', 'dev']:
                    # 為特殊標識符分配較小的數值
                    special_values = {'alpha': -3, 'beta': -2, 'rc': -1, 'dev': -4}
                    parts.append(special_values.get(part.lower(), 0))
                else:
                    parts.append(0)
        
        # 確保至少有一個部分
        if not parts:
            parts = [0]
            
        return tuple(parts)
    
    try:
        v1_tuple = version_tuple(version1)
        v2_tuple = version_tuple(version2)
        
        if v1_tuple < v2_tuple:
            return -1
        elif v1_tuple > v2_tuple:
            return 1
        else:
            return 0
    except Exception:
        # 如果比較失敗，視為相等
        return 0
