#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影片資訊處理模組
"""

import os
import sys
import math
import hashlib
import urllib.request
import yt_dlp

# 添加父目錄到路徑，以便導入其他模組
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # main/scripts
root_dir = os.path.dirname(parent_dir)  # main
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from scripts.utils.logger import video_info_console, LogLevel
from scripts.utils.file_utils import safe_path_join, resolve_relative_path, get_deno_path

def extract_video_info(url, root_dir):
    """提取影片資訊"""
    try:
        video_info_console(f"開始提取影片資訊: {url}", level=LogLevel.INFO)
        
        # 設定 FFMPEG 路徑（使用相對路徑）
        ffmpeg_path = safe_path_join(root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
        video_info_console(f"ffmpeg 路徑: {ffmpeg_path}")
        video_info_console(f"ffmpeg 存在: {os.path.exists(ffmpeg_path)}")
        
        # 設定 yt-dlp 選項
        ydl_opts = {
            'quiet': False,  # 改為 False 以查看警告信息
            'simulate': True,
            'extract_flat': False,
            'skip_download': True,
            'no_playlist': True,  # 確保只提取單個視頻
        }
        
        # 設定 ffmpeg 路徑（如果存在）
        if os.path.exists(ffmpeg_path):
            ydl_opts['ffmpeg_location'] = ffmpeg_path
        
        # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
        deno_path = get_deno_path(root_dir)
        if deno_path and os.path.exists(deno_path):
            # 嘗試不同的配置格式
            ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
            video_info_console(f"已配置 Deno 路徑: {deno_path}")
            video_info_console(f"Deno 文件存在: {os.path.exists(deno_path)}")
        else:
            video_info_console(f"Deno 未找到或不存在: {deno_path}", level=LogLevel.WARNING)
        
        video_info_console("yt-dlp 選項: quiet=True, no_warnings=True, simulate=True, extract_flat=False, ffmpeg_location=<ffmpeg.exe>")
        video_info_console("呼叫 yt-dlp.extract_info(download=False) 開始")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
        video_info_console("影片資訊取得完成", level=LogLevel.INFO)
        
        # 詳細調試信息
        video_info_console(f"info_dict 類型: {type(info_dict)}")
        formats_list = info_dict.get('formats', [])
        formats_count = len(formats_list)
        video_info_console(f"獲取到 {formats_count} 個格式")
        
        if formats_count == 0:
            video_info_console("警告：未獲取到任何格式", level=LogLevel.WARNING)
            video_info_console(f"info_dict 鍵: {list(info_dict.keys())[:10] if isinstance(info_dict, dict) else 'N/A'}")
        else:
            # 打印前幾個格式的詳細信息
            video_info_console(f"前 5 個格式的詳細信息:")
            for i, fmt in enumerate(formats_list[:5]):
                fmt_id = fmt.get('format_id', 'N/A')
                height = fmt.get('height', 'N/A')
                width = fmt.get('width', 'N/A')
                ext = fmt.get('ext', 'N/A')
                vcodec = fmt.get('vcodec', 'N/A')
                acodec = fmt.get('acodec', 'N/A')
                video_info_console(f"  格式 {i+1}: id={fmt_id}, height={height}, width={width}, ext={ext}, vcodec={vcodec}, acodec={acodec}")

        title = info_dict.get('title', '無標題影片')
        uploader = info_dict.get('uploader', '未知上傳者')
        duration_seconds = info_dict.get('duration', 0)
        duration_str = format_duration(duration_seconds)
        
        # 縮圖：先取 thumbnail，否則從 thumbnails 取解析度最大者，並嘗試快取到本地
        thumbnail = info_dict.get('thumbnail') or ''
        if not thumbnail:
            thumbs = info_dict.get('thumbnails') or []
            if isinstance(thumbs, list) and thumbs:
                try:
                    best = sorted(thumbs, key=lambda t: max(t.get('width', 0) or 0, t.get('height', 0) or 0))[-1]
                    thumbnail = best.get('url') or ''
                except Exception:
                    try:
                        thumbnail = thumbs[-1].get('url') or ''
                    except Exception:
                        thumbnail = ''
        cached_thumb = cache_thumbnail(thumbnail, root_dir) if thumbnail else ''
        
        # 畫質：依 formats 的 height 建立唯一的 label；非常規畫質一律歸類成大眾常見畫質
        seen_heights = set()
        qualities = []
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a

        def _quality_label_from_height(h):
            """高度轉為大眾常見畫質（不顯示比例）。\n\n            規則：以來源 height 歸類到「不低於來源」的常見級距，含預留 8K。\n            """
            try:
                h_int = int(h)
            except Exception:
                return f"{h}p"
            if h_int >= 4320:
                return "4320p(8K)"
            if h_int >= 2160:
                return "2160p(4K)"
            if h_int >= 1440:
                return "1440p(2K)"
            if h_int >= 1080:
                return "1080p"
            if h_int >= 720:
                return "720p"
            if h_int >= 480:
                return "480p"
            return "360p"
        
        # 詳細調試畫質提取過程
        formats_for_quality = info_dict.get('formats', []) or []
        video_info_console(f"開始提取畫質，格式列表長度: {len(formats_for_quality)}")
        
        # 打印所有格式的詳細信息（不只是前5個）
        video_info_console(f"所有格式的詳細信息:")
        for i, fmt in enumerate(formats_for_quality):
            fmt_id = fmt.get('format_id', 'N/A')
            height = fmt.get('height', 'N/A')
            width = fmt.get('width', 'N/A')
            ext = fmt.get('ext', 'N/A')
            vcodec = fmt.get('vcodec', 'N/A')
            acodec = fmt.get('acodec', 'N/A')
            video_info_console(f"  格式 {i+1}: id={fmt_id}, height={height}, width={width}, ext={ext}, vcodec={vcodec}, acodec={acodec}")
        
        height_count = 0
        filtered_count = 0
        mhtml_count = 0
        for f in formats_for_quality:
            ext = f.get('ext', '').lower()
            # 過濾掉縮圖格式（mhtml）
            if ext == 'mhtml':
                mhtml_count += 1
                video_info_console(f"  跳過縮圖格式: {f.get('format_id', 'N/A')} (ext=mhtml)")
                continue
            
            h = f.get('height')
            vcodec = f.get('vcodec', 'none')
            # 只處理有視頻編碼的格式（vcodec != 'none'）
            if vcodec == 'none':
                video_info_console(f"  跳過無視頻編碼格式: {f.get('format_id', 'N/A')} (vcodec=none)")
                continue
            
            if h is not None:
                height_count += 1
                video_info_console(f"  處理視頻格式: height={h}, vcodec={vcodec}, ext={ext}")
                # 過濾掉低於360p的畫質選項
                if h >= 360 and h not in seen_heights:
                    label = _quality_label_from_height(h)
                    qualities.append({'label': label, 'ratio': ''})
                    seen_heights.add(h)
                    filtered_count += 1
                    video_info_console(f"  添加畫質: {label} (原始高度: {h})")
                elif h < 360:
                    video_info_console(f"  跳過低畫質: {h}p (低於360p)")
                else:
                    video_info_console(f"  跳過重複畫質: {h}p")
            else:
                video_info_console(f"  跳過無高度格式: {f.get('format_id', 'N/A')} (height=None)")
        
        video_info_console(f"畫質提取統計: 總格式數={len(formats_for_quality)}, 縮圖格式={mhtml_count}, 有高度的視頻格式={height_count}, 過濾後畫質數={filtered_count}")
        
        # 由高到低排序
        qualities.sort(key=lambda q: int(''.join(ch for ch in q['label'] if ch.isdigit()) or '0'), reverse=True)
        video_info_console(f"最終提取到 {len(qualities)} 個畫質選項: {[q['label'] for q in qualities]}")
        
        # 格式：與舊版一致，預設提供 mp4（影片）；若偵測到任何音訊流，額外提供 mp3（音訊）
        has_any_audio = any((f.get('acodec') and f.get('acodec') != 'none') for f in (info_dict.get('formats') or []))
        formats_out = [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}]
        if has_any_audio:
            formats_out.append({'value': 'mp3', 'label': 'mp3', 'desc': '音訊'})
        
        return {
            'title': title,
            'uploader': uploader,
            'duration': duration_str,
            'thumb': cached_thumb or thumbnail or '',
            'qualities': qualities,
            'formats': formats_out,
            'url': url
        }
        
    except Exception as e:
        video_info_console(f"提取影片資訊失敗: {e}", level=LogLevel.ERROR)
        try:
            import traceback
            video_info_console(traceback.format_exc(), level=LogLevel.ERROR)
        except Exception:
            pass
        return None

def format_duration(seconds):
    """格式化時長"""
    if not seconds:
        return "未知時長"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def cache_thumbnail(thumb_url, root_dir):
    """快取縮圖"""
    if not thumb_url:
        return ""
    
    try:
        # 生成快取檔名
        thumb_hash = hashlib.md5(thumb_url.encode()).hexdigest()
        cache_dir = safe_path_join(root_dir, 'thumb_cache')
        cache_file = safe_path_join(cache_dir, f"{thumb_hash}.jpg")
        
        # 如果已存在，直接返回
        if os.path.exists(cache_file):
            return f"thumb_cache/{thumb_hash}.jpg"
        
        # 檢查快取目錄大小，如果超過限制則清理舊檔案
        _cleanup_thumbnail_cache(cache_dir, max_size_mb=50)
        
        # 下載縮圖
        urllib.request.urlretrieve(thumb_url, cache_file)
        return f"thumb_cache/{thumb_hash}.jpg"
        
    except Exception as e:
        video_info_console(f"快取縮圖失敗: {e}")
        return thumb_url

def _cleanup_thumbnail_cache(cache_dir, max_size_mb=50):
    """清理縮圖快取，保持目錄大小在限制內"""
    try:
        if not os.path.exists(cache_dir):
            return
        
        # 計算目錄總大小
        total_size = 0
        files_info = []
        
        for filename in os.listdir(cache_dir):
            filepath = os.path.join(cache_dir, filename)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                total_size += size
                files_info.append((filepath, os.path.getmtime(filepath), size))
        
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # 如果超過限制，按修改時間排序並刪除最舊的檔案
        if total_size > max_size_bytes:
            files_info.sort(key=lambda x: x[1])  # 按修改時間排序
            
            for filepath, _, size in files_info:
                if total_size <= max_size_bytes:
                    break
                
                try:
                    os.remove(filepath)
                    total_size -= size
                    video_info_console(f"已清理舊縮圖快取: {os.path.basename(filepath)}")
                except Exception as e:
                    video_info_console(f"清理縮圖快取失敗: {e}", level=LogLevel.WARNING)
                    
    except Exception as e:
        video_info_console(f"縮圖快取清理失敗: {e}", level=LogLevel.WARNING)

def process_formats(formats):
    """處理格式和畫質"""
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a
    
    def format_sort_key(f):
        # 優先級：影片+音訊 > 影片 > 音訊
        priority = {"影片+音訊": 3, "影片": 2, "音訊": 1}
        return (priority.get(f.get('desc', ''), 0), f.get('height', 0) or 0)
    
    # 收集所有畫質
    qualities = set()
    format_types = []
    
    for fmt in formats:
        height = fmt.get('height')
        if height:
            # 計算寬高比
            width = fmt.get('width', 0)
            if width and height:
                ratio_gcd = gcd(width, height)
                ratio = f"{width//ratio_gcd}:{height//ratio_gcd}"
            else:
                ratio = None
            
            quality_label = f"{height}p"
            qualities.add((quality_label, ratio))
        
        # 收集格式類型
        desc = fmt.get('desc', '')
        if desc and desc not in [f['desc'] for f in format_types]:
            format_types.append({
                'desc': desc,
                'value': fmt.get('format_id', ''),
                'ext': fmt.get('ext', '')
            })
    
    # 轉換為列表並排序
    qualities_list = [{'label': q[0], 'ratio': q[1]} for q in sorted(qualities, key=lambda x: int(x[0][:-1]), reverse=True)]
    format_types.sort(key=format_sort_key, reverse=True)
    
    return qualities_list, format_types

def is_playlist_url(url):
    """檢查 URL 是否為播放清單"""
    try:
        if not url:
            return False
        url_str = str(url).strip()
        # 檢查是否包含播放清單標識
        return 'list=' in url_str or '/playlist' in url_str
    except Exception:
        return False

def extract_playlist_info(url, root_dir):
    """提取播放清單資訊"""
    try:
        video_info_console(f"開始提取播放清單資訊: {url}", level=LogLevel.INFO)
        video_info_console(f"開始處理 URL: {url}")
        
        # 設定 FFMPEG 路徑
        ffmpeg_path = safe_path_join(root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
        video_info_console(f"FFMPEG 路徑: {ffmpeg_path}")
        
        # 設定 yt-dlp 選項，使用 extract_flat 來快速獲取播放清單資訊
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'simulate': True,
            'extract_flat': True,  # 只提取基本資訊，不提取每個影片的詳細資訊
        }
        
        # 設定 ffmpeg 路徑（如果存在）
        if os.path.exists(ffmpeg_path):
            ydl_opts['ffmpeg_location'] = ffmpeg_path
        
        # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
        deno_path = get_deno_path(root_dir)
        if deno_path:
            ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
            video_info_console(f"已配置 Deno 路徑: {deno_path}")
        
        video_info_console(f"yt-dlp 選項設定完成，開始提取資訊...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
        
        video_info_console(f"yt-dlp 提取完成，檢查結果...")
        video_info_console(f"info_dict 類型: {type(info_dict)}")
        video_info_console(f"_type 欄位: {info_dict.get('_type', 'N/A')}")
        
        # 檢查是否為播放清單
        if not info_dict.get('_type') == 'playlist':
            video_info_console(f"警告：不是播放清單類型，_type={info_dict.get('_type')}", level=LogLevel.WARNING)
            # 如果不是播放清單，返回 None
            return None
        
        playlist_title = info_dict.get('title', '無標題播放清單')
        playlist_uploader = info_dict.get('uploader', '未知上傳者')
        entries = info_dict.get('entries', [])
        
        video_info_console(f"標題: {playlist_title}")
        video_info_console(f"上傳者: {playlist_uploader}")
        video_info_console(f"找到 {len(entries)} 個條目")
        video_info_console(f"播放清單包含 {len(entries)} 部影片", level=LogLevel.INFO)
        
        # 提取每部影片的基本資訊
        videos = []
        for idx, entry in enumerate(entries):
            if not entry:
                video_info_console(f"條目 {idx + 1} 為空，跳過")
                continue
            
            video_info_console(f"處理第 {idx + 1} 部影片...")
            video_id = entry.get('id', '')
            video_url = entry.get('url') or f"https://www.youtube.com/watch?v={video_id}"
            video_title = entry.get('title', f'影片 {idx + 1}')
            video_duration = entry.get('duration', 0)
            video_duration_str = format_duration(video_duration) if video_duration else "未知時長"
            
            video_info_console(f"影片 {idx + 1}: {video_title[:50]}...")
            
            # 獲取縮圖
            thumbnail = entry.get('thumbnail') or ''
            if not thumbnail:
                thumbs = entry.get('thumbnails') or []
                if isinstance(thumbs, list) and thumbs:
                    try:
                        best = sorted(thumbs, key=lambda t: max(t.get('width', 0) or 0, t.get('height', 0) or 0))[-1]
                        thumbnail = best.get('url') or ''
                    except Exception:
                        try:
                            thumbnail = thumbs[-1].get('url') or ''
                        except Exception:
                            thumbnail = ''
            
            # 暫時跳過縮圖快取，避免阻塞
            cached_thumb = thumbnail or ''
            
            # 獲取上傳者資訊，優先使用影片的上傳者，否則使用播放清單的上傳者
            video_uploader = entry.get('uploader') or entry.get('channel') or playlist_uploader
            
            videos.append({
                'id': video_id,
                'url': video_url,
                'title': video_title,
                'duration': video_duration_str,
                'duration_seconds': video_duration,
                'thumb': cached_thumb,
                'uploader': video_uploader,
                'index': idx + 1
            })
            video_info_console(f"影片 {idx + 1} 處理完成")
        
        result = {
            'is_playlist': True,
            'playlist_title': playlist_title,
            'playlist_uploader': playlist_uploader,
            'video_count': len(videos),
            'videos': videos,
            'url': url
        }
        
        video_info_console(f"提取完成，共 {len(videos)} 部影片")
        video_info_console(f"返回結果結構: is_playlist={result.get('is_playlist')}, video_count={result.get('video_count')}")
        video_info_console(f"播放清單資訊提取完成: {playlist_title} ({len(videos)} 部影片)", level=LogLevel.INFO)
        
        return result
        
    except Exception as e:
        video_info_console(f"提取播放清單資訊失敗: {e}", level=LogLevel.ERROR)
        video_info_console(f"錯誤詳情: {type(e).__name__}: {str(e)}")
        try:
            import traceback
            video_info_console(traceback.format_exc(), level=LogLevel.ERROR)
            video_info_console(f"完整錯誤堆疊:\n{traceback.format_exc()}")
        except Exception:
            pass
        return None

def get_video_qualities_and_formats(url, root_dir):
    """獲取影片的畫質和格式選項（用於播放清單中的單個影片）"""
    try:
        video_info_console(f"開始獲取畫質和格式: {url}")
        
        # 設定 FFMPEG 路徑
        ffmpeg_path = safe_path_join(root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'simulate': True,
            'extract_flat': False,
        }
        
        # 設定 ffmpeg 路徑（如果存在）
        if os.path.exists(ffmpeg_path):
            ydl_opts['ffmpeg_location'] = ffmpeg_path
        
        # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
        deno_path = get_deno_path(root_dir)
        if deno_path:
            ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
            video_info_console(f"已配置 Deno 路徑: {deno_path}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
        
        # 提取畫質（邏輯與 extract_video_info 中一致；非常規畫質歸類成常見畫質）
        seen_heights = set()
        qualities = []
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a

        def _quality_label_from_height(h):
            try:
                h_int = int(h)
            except Exception:
                return f"{h}p"
            if h_int >= 4320:
                return "4320p(8K)"
            if h_int >= 2160:
                return "2160p(4K)"
            if h_int >= 1440:
                return "1440p(2K)"
            if h_int >= 1080:
                return "1080p"
            if h_int >= 720:
                return "720p"
            if h_int >= 480:
                return "480p"
            return "360p"
        for f in info_dict.get('formats', []) or []:
            h = f.get('height')
            if h and h >= 360 and h not in seen_heights:
                label = _quality_label_from_height(h)
                qualities.append({'label': label, 'ratio': ''})
                seen_heights.add(h)
        qualities.sort(key=lambda q: int(''.join(ch for ch in q['label'] if ch.isdigit()) or '0'), reverse=True)
        
        # 提取格式
        has_any_audio = any((f.get('acodec') and f.get('acodec') != 'none') for f in (info_dict.get('formats') or []))
        formats_out = [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}]
        if has_any_audio:
            formats_out.append({'value': 'mp3', 'label': 'mp3', 'desc': '音訊'})
        
        video_info_console(f"畫質和格式提取完成")
        return {
            'qualities': qualities,
            'formats': formats_out
        }
        
    except Exception as e:
        video_info_console(f"獲取影片畫質和格式失敗: {e}", level=LogLevel.ERROR)
        return {
            'qualities': [],
            'formats': [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}]
        }
