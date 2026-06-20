#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主要 API 類別模組
"""

import os
import sys
import json
import threading
import subprocess
import yt_dlp
import base64
import urllib.request

# 添加父目錄到路徑，以便導入其他模組
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # main/scripts
root_dir = os.path.dirname(parent_dir)  # main
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PySide6.QtCore import QObject, Slot, Signal, QTimer, QEventLoop
from PySide6.QtWidgets import QFileDialog
from PySide6.QtGui import QGuiApplication
from PySide6.QtGui import QImage
from scripts.utils.logger import api_console, download_console, video_info_console, debug_console, LogLevel
from scripts.utils.file_utils import safe_path_join, get_download_path, resolve_relative_path, get_deno_path
import re


def _sanitize_folder_name(name):
    """將播放清單標題轉為可用的資料夾名稱，移除非法字元"""
    if not name or not str(name).strip():
        return '播放清單'
    s = str(name).strip()
    s = re.sub(r'[<>:"/\\|?*]', '', s)  # 移除 Windows 非法字元
    s = re.sub(r'\s+', ' ', s).strip()   # 多餘空白壓成單一空格
    return s[:100] if s else '播放清單'   # 限制長度


def _ellipsis(text, max_len=40):
    """將文字過長時加上刪節號"""
    if text is None:
        return ''
    s = str(text)
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + '…'
from scripts.utils.version_utils import compare_versions
from scripts.config.settings import SettingsManager
from .video_info import extract_video_info, is_playlist_url, extract_playlist_info, get_video_qualities_and_formats
from .downloader import Downloader, DownloadScheduler


def _open_in_explorer_win(path):
    """
    在 Windows 用檔案總管開啟路徑；若為檔案則開啟所在資料夾並選取該檔案。
    使用 list 形式 + DETACHED_PROCESS，不經 shell，避免阻塞主程式。
    """
    api_console("[DBG] _open_in_explorer_win 進入", level=LogLevel.DEBUG)
    path = os.path.normpath(os.path.abspath(path))
    if not os.path.exists(path):
        folder = os.path.dirname(path)
        if os.path.exists(folder):
            path = folder
        else:
            api_console("[DBG] _open_in_explorer_win 路徑不存在，return", level=LogLevel.DEBUG)
            return
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        if os.path.isdir(path):
            api_console("[DBG] _open_in_explorer_win 即將 Popen(explorer 資料夾)", level=LogLevel.DEBUG)
            subprocess.Popen(["explorer", path], creationflags=creationflags)
        else:
            api_console("[DBG] _open_in_explorer_win 即將 Popen(explorer /select)", level=LogLevel.DEBUG)
            subprocess.Popen(["explorer", "/select,", path], creationflags=creationflags)
        api_console("[DBG] _open_in_explorer_win Popen 已呼叫，結束", level=LogLevel.DEBUG)
    except Exception as e:
        api_console(f"開啟檔案總管失敗: {e}，嘗試僅開啟資料夾", level=LogLevel.ERROR)
        try:
            subprocess.Popen(["explorer", os.path.dirname(path)], creationflags=creationflags)
        except Exception as e2:
            api_console(f"開啟資料夾也失敗: {e2}", level=LogLevel.ERROR)


class Api(QObject):
    """主要 API 類別"""
    
    # 信號定義
    eval_js_requested = Signal(str)
    infoReady = Signal('QVariant')
    infoError = Signal(str)
    notificationRequested = Signal(str, str)
    updateDialogRequested = Signal('QVariant')  # 更新對話框請求信號
    
    @Slot(str, str, result=str)
    def log_from_js(self, level, message):
        """接收來自 JavaScript 的日誌訊息並輸出到 Python console"""
        try:
            from scripts.utils.logger import debug_console, info_console, warning_console, error_console, LogLevel
            
            # 將 JavaScript 的日誌級別映射到 Python 的日誌級別
            level_lower = level.lower()
            if level_lower == 'error':
                error_console(f"[JS] {message}", tag="前端")
            elif level_lower == 'warn' or level_lower == 'warning':
                warning_console(f"[JS] {message}", tag="前端")
            elif level_lower == 'info':
                info_console(f"[JS] {message}", tag="前端")
            elif level_lower == 'debug':
                debug_console(f"[JS] {message}", tag="前端")
            else:
                # 預設使用 info 級別
                info_console(f"[JS] {message}", tag="前端")
            
            return "OK"
        except Exception as e:
            # 如果日誌系統出錯，至少用 print 輸出
            print(f"[JS日誌接收器錯誤] {e}: {message}")
            return "ERROR"
    
    def __init__(self, page, root_dir):
        super().__init__()
        self.page = page
        self.root_dir = root_dir
        self.download_threads = {}
        self.completed_tasks = set()
        self.settings_process = None
        # 保護 task_download_paths / task_formats / downloading_urls / pending_tasks_by_url 等。
        # 持鎖時僅做 dict/set 讀寫，不得呼叫 _safe_eval_js、_process_pending_tasks_for_url 或 thread.join，避免卡死主線程或死鎖。
        self._lock = threading.Lock()
        self.task_has_postprocessing = {}
        self.task_in_postprocessing = {}
        self.task_download_paths = {}  # 追蹤每個任務的下載路徑
        self.task_formats = {}  # 追蹤每個任務的格式（用於避免同名文件不同格式時抓錯狀態）
        self.task_urls = {}  # 追蹤每個任務的 URL（用於檢查同名影片）
        self.task_playlist_groups = {}  # 追蹤每個任務的播放清單群組ID（task_id -> playlistGroupId）
        self.playlist_titles = {}  # 播放清單群組ID -> 播放清單名稱
        self.playlist_notified = set()  # 追蹤已發送完成通知的播放清單群組ID
        self.downloading_urls = set()  # 正在下載的 URL 集合
        self.pending_tasks_by_url = {}  # 按 URL 分組的等待任務列表
        self.notification_handler = None
        self._last_progress_percent = {}
        self._ytdlp_update_in_progress = False
        
        # 初始化組件
        self.settings_manager = SettingsManager(root_dir)
        self.downloader = Downloader(
            root_dir,
            progress_callback=self._download_progress_hook,
            complete_callback=self._notify_download_complete_safely
        )

        # 全域下載排程器：同時下載上限/重試次數（先用設定或預設值）
        try:
            settings = self.settings_manager.load_settings()
            max_c = int(settings.get('maxConcurrentDownloads', 3) or 3)
        except Exception:
            max_c = 3
        self.scheduler = DownloadScheduler(
            self.downloader,
            max_concurrent=max_c,
            retry_count=3,
            status_callback=self._scheduler_status_update,
        )
        
        # 連接信號
        self.eval_js_requested.connect(self._on_eval_js_requested)
        self.notificationRequested.connect(self._on_notification_requested)
        self.updateDialogRequested.connect(self._on_update_dialog_requested)
    def set_notification_handler(self, handler):
        """設定通知處理器，由主視窗提供"""
        self.notification_handler = handler

    @Slot(str, result=str)
    def set_clipboard_text(self, text):
        """寫入系統剪貼簿文字（供前端右鍵選單使用）"""
        try:
            cb = QGuiApplication.clipboard()
            cb.setText(str(text or ''))
            return "OK"
        except Exception as e:
            api_console(f"寫入剪貼簿失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"

    @Slot(result=str)
    def get_clipboard_text(self):
        """讀取系統剪貼簿文字（供前端右鍵選單使用）"""
        try:
            cb = QGuiApplication.clipboard()
            return cb.text() or ""
        except Exception as e:
            api_console(f"讀取剪貼簿失敗: {e}", level=LogLevel.ERROR)
            return ""

    @Slot(str, result=str)
    def set_clipboard_image(self, image_source):
        """
        寫入系統剪貼簿圖片。
        支援:
        - http(s) URL
        - 本機路徑（絕對/相對）
        - file:// URL
        - data URL: data:image/png;base64,...
        """
        try:
            src = str(image_source or "").strip()
            if not src:
                return "圖片來源不可用"

            img = QImage()

            # data URL
            if src.startswith("data:image/") and "base64," in src:
                b64 = src.split("base64,", 1)[1].strip()
                image_bytes = base64.b64decode(b64)
                img = QImage.fromData(image_bytes)
            # file:// URL
            elif src.lower().startswith("file://"):
                # Windows 可能是 file:///C:/...
                local_path = src[7:]
                if local_path.startswith("/"):
                    local_path = local_path[1:]
                local_path = local_path.replace("/", os.sep)
                img.load(local_path)
            # http(s) URL
            elif src.lower().startswith("http://") or src.lower().startswith("https://"):
                req = urllib.request.Request(
                    src,
                    headers={
                        "User-Agent": "oldfish-Video-Downloader",
                        "Accept": "image/*,*/*;q=0.8",
                    },
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    image_bytes = resp.read()
                img = QImage.fromData(image_bytes)
            # 本機路徑（相對/絕對）
            else:
                try:
                    # 先把相對路徑解析到 root_dir 下
                    local_path = resolve_relative_path(src, self.root_dir)
                except Exception:
                    local_path = src
                if not os.path.isabs(local_path):
                    local_path = os.path.abspath(os.path.join(self.root_dir, local_path))
                img.load(local_path)

            if img.isNull():
                return "圖片解析失敗"

            cb = QGuiApplication.clipboard()
            cb.setImage(img)
            return "OK"
        except Exception as e:
            api_console(f"寫入剪貼簿圖片失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"
    
    def _format_eta(self, eta_seconds):
        """格式化 ETA（預估剩餘時間）"""
        try:
            if eta_seconds is None or eta_seconds < 0:
                return ''
            
            eta_seconds = int(eta_seconds)
            
            if eta_seconds < 60:
                return f"{eta_seconds}秒"
            elif eta_seconds < 3600:
                minutes = eta_seconds // 60
                seconds = eta_seconds % 60
                if seconds > 0:
                    return f"{minutes}分{seconds}秒"
                else:
                    return f"{minutes}分鐘"
            else:
                hours = eta_seconds // 3600
                minutes = (eta_seconds % 3600) // 60
                if minutes > 0:
                    return f"{hours}小時{minutes}分鐘"
                else:
                    return f"{hours}小時"
        except Exception:
            return ''

    
    @Slot(str, result=str)
    def start_get_video_info(self, url):
        """開始獲取影片資訊（自動檢測播放清單）"""
        def task():
            try:
                api_console(f"start_get_video_info 被調用，URL: {url}")
                # 檢測是否為播放清單
                if is_playlist_url(url):
                    api_console("檢測到播放清單URL", level=LogLevel.INFO)
                    api_console(f"確認為播放清單URL，開始提取...")
                    playlist_info = extract_playlist_info(url, self.root_dir)
                    api_console(f"播放清單資訊提取完成，結果: {playlist_info is not None}")
                    if playlist_info:
                        api_console(f"播放清單資訊結構: is_playlist={playlist_info.get('is_playlist')}, video_count={playlist_info.get('video_count')}")
                        api_console(f"準備發送 infoReady 信號...")
                        self.infoReady.emit(playlist_info)
                        api_console(f"infoReady 信號已發送")
                    else:
                        api_console(f"播放清單資訊為 None，發送錯誤信號")
                        self.infoError.emit("無法獲取播放清單資訊")
                else:
                    api_console(f"不是播放清單URL，按單個影片處理")
                    info = extract_video_info(url, self.root_dir)
                    if info:
                        api_console(f"影片資訊提取完成，發送 infoReady 信號")
                        self.infoReady.emit(info)
                    else:
                        api_console(f"影片資訊為 None，發送錯誤信號")
                        self.infoError.emit("無法獲取影片資訊")
            except Exception as e:
                api_console(f"start_get_video_info 發生異常: {e}", level=LogLevel.ERROR)
                api_console(f"異常詳情: {type(e).__name__}: {str(e)}")
                import traceback
                api_console(f"完整堆疊:\n{traceback.format_exc()}")
                self.infoError.emit(str(e))
        
        api_console(f"啟動背景執行緒處理 URL: {url}")
        threading.Thread(target=task, daemon=True).start()
        return 'started'
    
    @Slot(str, result='QVariant')
    def get_playlist_info(self, url):
        """獲取播放清單資訊"""
        try:
            api_console(f"獲取播放清單資訊: {url}", level=LogLevel.INFO)
            playlist_info = extract_playlist_info(url, self.root_dir)
            return playlist_info
        except Exception as e:
            api_console(f"獲取播放清單資訊失敗: {e}", level=LogLevel.ERROR)
            return None
    
    @Slot(str, result='QVariant')
    def get_video_qualities_formats(self, url):
        """獲取單個影片的畫質和格式選項（用於播放清單）"""
        try:
            return get_video_qualities_and_formats(url, self.root_dir)
        except Exception as e:
            api_console(f"獲取影片畫質和格式失敗: {e}", level=LogLevel.ERROR)
            return {
                'qualities': [{'label': '1080p', 'ratio': ''}, {'label': '720p', 'ratio': ''}, {'label': '480p', 'ratio': ''}],
                'formats': [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}, {'value': 'mp3', 'label': 'mp3', 'desc': '音訊'}]
            }

    @Slot(str, result=str)
    def start_playlist_qualities_fetch(self, videos_json):
        """播放清單：背景逐支提取每部影片可用畫質（eager）。

        videos_json: JSON字串，格式：
          [
            {"index": 0, "url": "https://..."},
            ...
          ]

        會逐支回推前端：
          window.__onPlaylistVideoQualities(index, qualitiesArray)
        """
        try:
            items = json.loads(videos_json or '[]')
            if not isinstance(items, list):
                return "FAILED: invalid payload"

            # 受控併發，避免同時開太多 yt-dlp extract_info
            max_concurrent = 4
            sem = threading.Semaphore(max_concurrent)

            def worker(idx, url):
                if url is None:
                    return
                u = str(url).strip()
                if not u:
                    return
                sem.acquire()
                try:
                    result = get_video_qualities_and_formats(u, self.root_dir) or {}
                    qualities = result.get('qualities') or []
                    # 用 JS 物件回推（_safe_eval_js 會把 list 轉成字串，不適合）
                    payload = json.dumps(qualities, ensure_ascii=False)
                    js = f"(function(){{ try{{ if (window.__onPlaylistVideoQualities){{ window.__onPlaylistVideoQualities({int(idx)}, {payload}); }} }}catch(e){{ console.error(e); }} }})();"
                    self._eval_js(js)
                except Exception as e:
                    # 失敗時回推空陣列（前端可維持預設）
                    try:
                        js = f"(function(){{ try{{ if (window.__onPlaylistVideoQualities){{ window.__onPlaylistVideoQualities({int(idx)}, []); }} }}catch(e){{}} }})();"
                        self._eval_js(js)
                    except Exception:
                        pass
                    video_info_console(f"提取畫質失敗 idx={idx}: {e}", level=LogLevel.ERROR)
                finally:
                    try:
                        sem.release()
                    except Exception:
                        pass

            started = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                idx = it.get('index')
                url = it.get('url')
                if idx is None or url is None:
                    continue
                t = threading.Thread(target=worker, args=(idx, url), daemon=True)
                t.start()
                started += 1

            return f"OK:{started}"
        except Exception as e:
            api_console(f"start_playlist_qualities_fetch 失敗: {e}", level=LogLevel.ERROR)
            return f"FAILED:{e}"
    
    @Slot(str, result='QVariant')
    def get_video_info(self, url):
        """獲取影片資訊"""
        api_console(f"取得影片資訊: {url}", level=LogLevel.INFO)
        try:
            # 直接使用 yt-dlp 獲取資訊，與原始版本一致
            import yt_dlp
            
            # 設定 FFMPEG 路徑（使用相對路徑）
            ffmpeg_path = safe_path_join(self.root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
            api_console(f"ffmpeg 路徑: {ffmpeg_path}")
            api_console(f"ffmpeg 存在: {os.path.exists(ffmpeg_path)}")
            
            # 設定 yt-dlp 選項（不限制格式，以獲取所有可用格式）
            ydl_opts = {
                'quiet': False,  # 改為 False 以查看警告信息
                'simulate': True,
                'skip_download': True,
                'no_playlist': True,  # 確保只提取單個視頻
                # 不設定 format，以獲取所有可用格式
            }
            
            # 設定 ffmpeg 路徑（如果存在）
            if os.path.exists(ffmpeg_path):
                ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
            deno_path = get_deno_path(self.root_dir)
            api_console(f"Deno 路徑查找結果: {deno_path}")
            if deno_path and os.path.exists(deno_path):
                ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
                api_console(f"已配置 Deno 路徑: {deno_path}")
                api_console(f"js_runtimes 配置: {ydl_opts.get('js_runtimes')}")
            else:
                api_console(f"Deno 未找到或不存在: {deno_path}")
                if deno_path:
                    api_console(f"Deno 路徑存在性檢查: {os.path.exists(deno_path)}")
            
            api_console(f"yt-dlp 選項: simulate=True")
            api_console("即將呼叫 yt-dlp.extract_info(download=False)")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
            api_console("yt-dlp.extract_info 完成")
            
            # 詳細調試信息
            api_console(f"info_dict 類型: {type(info_dict)}")
            api_console(f"info_dict 鍵: {list(info_dict.keys())[:10] if isinstance(info_dict, dict) else 'N/A'}")
            
            # 檢查是否成功獲取格式列表
            formats_list = info_dict.get('formats', [])
            formats_count = len(formats_list)
            api_console(f"獲取到 {formats_count} 個格式")
            
            if formats_count == 0:
                api_console("警告：未獲取到任何格式，可能是 JavaScript runtime 配置問題", level=LogLevel.WARNING)
                # 打印 info_dict 的部分內容以便調試
                api_console(f"info_dict 部分內容: title={info_dict.get('title', 'N/A')}, id={info_dict.get('id', 'N/A')}")
            else:
                # 打印前幾個格式的詳細信息
                api_console(f"前 5 個格式的詳細信息:")
                for i, fmt in enumerate(formats_list[:5]):
                    fmt_id = fmt.get('format_id', 'N/A')
                    height = fmt.get('height', 'N/A')
                    width = fmt.get('width', 'N/A')
                    ext = fmt.get('ext', 'N/A')
                    vcodec = fmt.get('vcodec', 'N/A')
                    acodec = fmt.get('acodec', 'N/A')
                    api_console(f"  格式 {i+1}: id={fmt_id}, height={height}, width={width}, ext={ext}, vcodec={vcodec}, acodec={acodec}")
            
            title = info_dict.get('title', '無標題影片')
            duration_seconds = info_dict.get('duration')
            duration = ""
            if duration_seconds:
                minutes, seconds = divmod(duration_seconds, 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    duration = f"{minutes:02d}:{seconds:02d}"
            
            uploader = info_dict.get('uploader', '未知上傳者')
            # 縮圖：優先使用 'thumbnail'，否則從 'thumbnails' 陣列中取解析度最高的一張
            thumbnail = info_dict.get('thumbnail') or ''
            if not thumbnail:
                thumbs = info_dict.get('thumbnails') or []
                if isinstance(thumbs, list) and thumbs:
                    try:
                        # 依寬或高度排序取最大
                        best = sorted(thumbs, key=lambda t: max(t.get('width', 0) or 0, t.get('height', 0) or 0))[-1]
                        thumbnail = best.get('url') or ''
                    except Exception:
                        try:
                            thumbnail = thumbs[-1].get('url') or ''
                        except Exception:
                            thumbnail = ''
            api_console(f"取得縮圖 URL: {bool(thumbnail)}")
            
            # 處理畫質和格式（使用與 extract_video_info 相同的邏輯）
            seen_heights = set()
            qualities = []
            
            def _quality_label_from_height(h):
                """高度轉為大眾常見畫質"""
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
            
            # 從 formats 中提取畫質
            api_console(f"開始提取畫質，formats_list 長度: {len(formats_list)}")
            
            # 打印所有格式的詳細信息
            api_console(f"所有格式的詳細信息:")
            for i, fmt in enumerate(formats_list):
                fmt_id = fmt.get('format_id', 'N/A')
                height = fmt.get('height', 'N/A')
                width = fmt.get('width', 'N/A')
                ext = fmt.get('ext', 'N/A')
                vcodec = fmt.get('vcodec', 'N/A')
                acodec = fmt.get('acodec', 'N/A')
                api_console(f"  格式 {i+1}: id={fmt_id}, height={height}, width={width}, ext={ext}, vcodec={vcodec}, acodec={acodec}")
            
            height_count = 0
            filtered_count = 0
            mhtml_count = 0
            for fmt in formats_list:
                ext = fmt.get('ext', '').lower()
                # 過濾掉縮圖格式（mhtml）
                if ext == 'mhtml':
                    mhtml_count += 1
                    api_console(f"  跳過縮圖格式: {fmt.get('format_id', 'N/A')} (ext=mhtml)")
                    continue
                
                height = fmt.get('height')
                vcodec = fmt.get('vcodec', 'none')
                # 只處理有視頻編碼的格式（vcodec != 'none'）
                if vcodec == 'none':
                    api_console(f"  跳過無視頻編碼格式: {fmt.get('format_id', 'N/A')} (vcodec=none)")
                    continue
                
                if height is not None:
                    height_count += 1
                    api_console(f"  處理視頻格式: height={height}, vcodec={vcodec}, ext={ext}")
                    # 過濾掉低於360p的畫質選項
                    if height >= 360 and height not in seen_heights:
                        label = _quality_label_from_height(height)
                        qualities.append({'label': label, 'ratio': ''})
                        seen_heights.add(height)
                        filtered_count += 1
                        api_console(f"  添加畫質: {label} (原始高度: {height})")
                    elif height < 360:
                        api_console(f"  跳過低畫質: {height}p (低於360p)")
                    else:
                        api_console(f"  跳過重複畫質: {height}p")
                else:
                    api_console(f"  跳過無高度格式: {fmt.get('format_id', 'N/A')} (height=None)")
            
            api_console(f"畫質提取統計: 總格式數={len(formats_list)}, 縮圖格式={mhtml_count}, 有高度的視頻格式={height_count}, 過濾後畫質數={filtered_count}")
            
            # 由高到低排序
            qualities.sort(key=lambda q: int(''.join(ch for ch in q['label'] if ch.isdigit()) or '0'), reverse=True)
            api_console(f"最終提取到 {len(qualities)} 個畫質選項: {[q['label'] for q in qualities]}")
            
            # 格式：與 extract_video_info 一致
            has_any_audio = any((f.get('acodec') and f.get('acodec') != 'none') for f in formats_list)
            formats_out = [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}]
            if has_any_audio:
                formats_out.append({'value': 'mp3', 'label': 'mp3', 'desc': '音訊'})
            
            result = {
                'title': title,
                'duration': duration,
                'uploader': uploader,
                'thumb': thumbnail,  # 使用原始縮圖 URL
                'qualities': qualities,
                'formats': formats_out
            }
            
            api_console(f"返回結果: title={title}, qualities數量={len(qualities)}, formats數量={len(formats_out)}")
            api_console(f"返回的畫質列表: {[q['label'] for q in qualities]}")
            
            return result
            
        except Exception as e:
            api_console(f"獲取影片資訊失敗: {e}", level=LogLevel.ERROR)
            import traceback
            api_console(f"錯誤堆疊: {traceback.format_exc()}")
            return None
    
    def _eval_js(self, script):
        """執行 JavaScript"""
        self.eval_js_requested.emit(script)
    
    def _safe_eval_js(self, function_name, *args):
        """安全地執行JavaScript函數"""
        try:
            safe_args = []
            for arg in args:
                if isinstance(arg, str):
                    safe_args.append(json.dumps(arg))
                elif isinstance(arg, (int, float)):
                    safe_args.append(str(arg))
                elif arg is None:
                    safe_args.append('null')
                else:
                    safe_args.append(json.dumps(str(arg)))
            
            js_call = f"{function_name}({', '.join(safe_args)})"
            api_console(f"[DBG] _safe_eval_js 即將 emit → {function_name}(...) 長度={len(js_call)}", level=LogLevel.DEBUG)
            self._eval_js(js_call)
            api_console(f"[DBG] _safe_eval_js emit 已回傳", level=LogLevel.DEBUG)
        except Exception as e:
            api_console(f"安全JavaScript執行失敗: {e}", level=LogLevel.WARNING)
            try:
                safe_script = f"{function_name}()"
                self._eval_js(safe_script)
            except Exception as e2:
                api_console(f"後備JavaScript執行也失敗: {e2}", level=LogLevel.WARNING)
    
    @Slot(str)
    def _on_eval_js_requested(self, script):
        """處理 JavaScript 執行請求"""
        try:
            api_console("[DBG] _on_eval_js_requested 即將 runJavaScript（主線程）", level=LogLevel.DEBUG)
            self.page.runJavaScript(script)
            api_console("[DBG] _on_eval_js_requested runJavaScript 已回傳", level=LogLevel.DEBUG)
        except Exception as e:
            api_console(f"JavaScript執行失敗: {e}", level=LogLevel.ERROR)
    
    def _on_update_dialog_requested(self, version_info):
        """處理更新對話框請求（在主線程中執行）"""
        try:
            # 使用 QTimer 延遲執行，確保頁面加載完成
            from PySide6.QtCore import QTimer
            def show_dialog():
                self.show_update_dialog(version_info)
                current_version = version_info.get('current_version', '')
                latest_version = version_info.get('latest_version', '')
                api_console(f"已顯示 yt-dlp 更新對話框（目前版本: {current_version}, 最新版本: {latest_version}）", level=LogLevel.INFO)
            QTimer.singleShot(500, show_dialog)  # 500ms 後執行
        except Exception as e:
            api_console(f"顯示更新對話框失敗: {e}", level=LogLevel.ERROR)
    
    def _download_progress_hook(self, task_id, d):
        """下載進度回調"""
        try:
            # 將「下載」與「後處理(合併/轉檔)」合併為單一連續進度，避免前端看到第二次重跳
            download_stage_max = 92.0
            postprocess_stage_percent = 97.0
            status_key = d.get('status')
            if not status_key:
                download_console(f"【任務{task_id}】進度回調缺少 status 欄位")
                return
            
            if status_key == 'downloading':
                downloaded_bytes = d.get('downloaded_bytes', 0)
                
                # 計算進度百分比
                if d.get('total_bytes'):
                    total_bytes = d['total_bytes']
                    if total_bytes > 0:
                        raw_percent = min(100, max(0, downloaded_bytes / total_bytes * 100))
                        percent = min(download_stage_max, max(0, raw_percent * download_stage_max / 100.0))
                        status = "下載中"
                    else:
                        percent = 0
                        status = "下載中 (未知進度)"
                elif d.get('total_bytes_estimate'):
                    total_bytes_estimate = d['total_bytes_estimate']
                    if total_bytes_estimate > 0:
                        raw_percent = min(100, max(0, downloaded_bytes / total_bytes_estimate * 100))
                        percent = min(download_stage_max, max(0, raw_percent * download_stage_max / 100.0))
                        status = "下載中 (預估)"
                    else:
                        percent = 0
                        status = "下載中 (未知進度)"
                else:
                    percent = 0
                    status = "下載中 (未知進度)"
                
                # 提取並格式化 ETA（預估剩餘時間）
                eta = d.get('eta')
                if eta is not None and isinstance(eta, (int, float)) and eta >= 0:
                    eta_str = self._format_eta(eta)
                    if eta_str:
                        status = f"{status} - 剩餘 {eta_str}"
                
                download_console(f"[進度] 任務{task_id}: {percent:.1f}% - {status}", level=LogLevel.INFO)
                try:
                    with self._lock:
                        self._last_progress_percent[str(task_id)] = float(percent)
                except Exception:
                    pass
                # 傳遞當前檔案路徑（若可得）以保持與舊版一致
                file_arg = d.get('filename') or ''
                safe_file_arg = (file_arg or '').replace('\\', '/')
                # 獲取任務格式（用於避免同名文件不同格式時抓錯狀態）
                task_format = ''
                task_url = ''
                with self._lock:
                    task_format = self.task_formats.get(str(task_id), '')
                    task_url = self.task_urls.get(str(task_id), '')
                download_console(f"[進度更新] 任務{task_id}: {percent:.1f}% - {status}, 格式: {task_format}, URL: {task_url}", level=LogLevel.DEBUG)
                # 傳遞 status（已包含 ETA）和格式給前端
                self._safe_eval_js("window.updateDownloadProgress", task_id, percent, status, '', safe_file_arg, task_format)
            elif status_key == 'finished':
                try:
                    download_console(f"任務 {task_id} 下載階段完成，進入後處理", level=LogLevel.INFO)
                    file_arg = d.get('filename') or ''
                    safe_file_arg = (file_arg or '').replace('\\', '/')
                    # 獲取任務格式
                    task_format = ''
                    task_url = ''
                    with self._lock:
                        task_format = self.task_formats.get(str(task_id), '')
                        task_url = self.task_urls.get(str(task_id), '')
                        current_percent = float(self._last_progress_percent.get(str(task_id), 0.0))
                        percent = max(current_percent, postprocess_stage_percent)
                        self._last_progress_percent[str(task_id)] = percent
                    download_console(f"[後處理通知] 任務{task_id}: {percent:.1f}% - 後處理中, 格式: {task_format}, URL: {task_url}", level=LogLevel.DEBUG)
                    self._safe_eval_js("window.updateDownloadProgress", task_id, percent, "後處理中", '', safe_file_arg, task_format)
                except Exception as e:
                    download_console(f"完成進度回報失敗: {e}", level=LogLevel.ERROR)
            else:
                # 處理其他未知狀態
                download_console(f"【任務{task_id}】未知狀態: {status_key}")
        except KeyError as e:
            download_console(f"【任務{task_id}】進度回調缺少必要欄位: {e}", level=LogLevel.ERROR)
        except Exception as e:
            download_console(f"【任務{task_id}】進度回調處理失敗: {e}", level=LogLevel.ERROR)

    def _scheduler_status_update(self, task_id, status_text):
        """排程器狀態更新（例如重試中），只更新狀態文字，不重置進度條。"""
        try:
            with self._lock:
                p = self._last_progress_percent.get(str(task_id), 0.0)
                task_format = self.task_formats.get(str(task_id), '')
            self._safe_eval_js("window.updateDownloadProgress", int(task_id), float(p), str(status_text), '', '', task_format)
        except Exception:
            pass
    
    def _notify_download_complete_safely(self, task_id, url, error=None, file_path=None):
        """安全地通知下載完成"""
        try:
            download_console(f"[DBG] _notify_download_complete_safely 進入 task_id={task_id}", level=LogLevel.DEBUG)
            download_console("[DBG] _notify_download_complete_safely 即將取得 _lock(completed_tasks)", level=LogLevel.DEBUG)
            with self._lock:
                if task_id in self.completed_tasks:
                    download_console("[DBG] _notify_download_complete_safely 已完成過，return", level=LogLevel.DEBUG)
                    return
                self.completed_tasks.add(task_id)
            download_console("[DBG] _notify_download_complete_safely 已釋放 _lock(completed_tasks)", level=LogLevel.DEBUG)

            if error:
                self._safe_eval_js("window.onDownloadError", task_id, error)
                # 即使出錯，也要移除正在下載標記，並處理等待中的任務
                with self._lock:
                    if url in self.downloading_urls:
                        self.downloading_urls.discard(url)
                download_console("[DBG] _notify_download_complete_safely 即將 _process_pending_tasks_for_url (error 分支)", level=LogLevel.DEBUG)
                self._process_pending_tasks_for_url(url)
            else:
                # 記錄最終檔案路徑到任務追蹤中（確保為絕對路徑，支援播放清單子資料夾）
                if file_path:
                    # 將路徑轉換為絕對路徑，確保「開啟資料夾」按鈕能正確導向
                    if not os.path.isabs(file_path):
                        # 如果是相對路徑，使用任務記錄的下載目錄（可能包含播放清單子資料夾）
                        with self._lock:
                            task_dir = self.task_download_paths.get(str(task_id))
                        if task_dir and os.path.isabs(task_dir):
                            # 如果任務目錄是絕對路徑，用它來解析相對路徑
                            file_path = os.path.normpath(os.path.join(task_dir, file_path))
                        else:
                            # 否則使用預設下載目錄
                            base_dir = get_download_path(self.root_dir, self.settings_manager)
                            file_path = os.path.normpath(os.path.join(base_dir, file_path))
                    else:
                        file_path = os.path.normpath(file_path)
                    with self._lock:
                        self.task_download_paths[str(task_id)] = file_path
                    download_console(f"任務 {task_id} 最終檔案路徑已記錄: {file_path}")
                
                # 與舊版一致，將最終檔案路徑傳給前端以啟用「開啟資料夾」按鈕
                safe_file = (file_path or '').replace('\\', '/')
                # 獲取任務格式
                task_format = ''
                with self._lock:
                    task_format = self.task_formats.get(str(task_id), '')
                    self._last_progress_percent[str(task_id)] = 100.0
                self._safe_eval_js("window.updateDownloadProgress", task_id, 100, "已完成", '', safe_file, task_format)
                
                # 移除正在下載標記（鎖內僅做狀態更新，鎖外再處理等待任務，避免死鎖）
                with self._lock:
                    if url in self.downloading_urls:
                        self.downloading_urls.discard(url)
                        download_console(f"任務 {task_id} 下載完成，移除 URL {url} 的正在下載標記")
                download_console("[DBG] _notify_download_complete_safely 即將 _process_pending_tasks_for_url (完成分支)", level=LogLevel.DEBUG)
                self._process_pending_tasks_for_url(url)

            download_console("[DBG] _notify_download_complete_safely 即將 _safe_eval_js onDownloadComplete", level=LogLevel.DEBUG)
            self._safe_eval_js("window.onDownloadComplete", task_id)
            
            # 發送通知（根據播放清單通知設定決定時機）
            settings = self.settings_manager.load_settings()
            if settings.get('enableNotifications', True):
                should_notify = True
                playlist_notify_mode = settings.get('playlistNotificationMode', 'complete')
                
                # 檢查是否為播放清單任務
                with self._lock:
                    playlist_group_id = self.task_playlist_groups.get(str(task_id))
                
                # 準備顯示用影片標題（從檔名推斷）
                video_title_display = None
                if file_path:
                    base = os.path.basename(file_path)
                    name, _ = os.path.splitext(base)
                    video_title_display = _ellipsis(name)
                if not video_title_display:
                    video_title_display = f"任務 {task_id}"

                # 若是播放清單且模式為 complete，僅在整個播放清單完成時通知一次
                if playlist_group_id and playlist_notify_mode == 'complete':
                    with self._lock:
                        # 檢查是否已經發送過通知（避免重複）
                        if playlist_group_id in self.playlist_notified:
                            should_notify = False
                            download_console(f"播放清單 {playlist_group_id} 已完成通知已發送，跳過", level=LogLevel.DEBUG)
                        else:
                            # 找出同一個播放清單的所有任務
                            playlist_task_ids = [tid for tid, pgid in self.task_playlist_groups.items() if pgid == playlist_group_id]
                            # 檢查是否所有任務都已完成
                            all_completed = all(int(tid) in self.completed_tasks for tid in playlist_task_ids)
                            should_notify = all_completed
                            if all_completed:
                                self.playlist_notified.add(playlist_group_id)  # 標記已發送通知
                                download_console(f"播放清單 {playlist_group_id} 所有任務已完成，發送通知", level=LogLevel.INFO)
                            else:
                                completed_count = sum(1 for tid in playlist_task_ids if int(tid) in self.completed_tasks)
                                download_console(f"播放清單 {playlist_group_id} 進度: {completed_count}/{len(playlist_task_ids)}，暫不發送通知", level=LogLevel.DEBUG)
                
                if should_notify:
                    try:
                        # 播放清單完成模式且有群組ID：顯示播放清單完成
                        if playlist_group_id and playlist_notify_mode == 'complete':
                            with self._lock:
                                playlist_title = self.playlist_titles.get(str(playlist_group_id)) or '播放清單'
                            playlist_title_display = _ellipsis(playlist_title)
                            self._safe_eval_js("window.__ofShowToast", "播放清單下載完成", f"\"{playlist_title_display}\"已下載完成")
                            self._send_notification("播放清單下載完成", f"\"{playlist_title_display}\"已下載完成")
                        else:
                            # 單一影片（或播放清單但模式為 each）：每部影片完成就通知
                            self._safe_eval_js("window.__ofShowToast", "影片下載完成", f"\"{video_title_display}\"已下載完成")
                            self._send_notification("影片下載完成", f"\"{video_title_display}\"已下載完成")
                    except Exception as toast_err:
                        download_console(f"顯示 Toast 失敗: {toast_err}")
                    
        except Exception as e:
            download_console(f"通知下載完成失敗: {e}", level=LogLevel.WARNING)

    @Slot(result=str)
    def choose_folder(self):
        """開啟 Windows 檔案總管的資料夾選擇對話方塊，回傳所選路徑（空字串代表取消）"""
        try:
            # 使用 QTimer.singleShot 延遲至下一個事件循環迭代，
            # 避免從 QWebChannel（JavaScript）直接呼叫 QFileDialog 造成的死結
            result_holder = [None]

            def show_dialog():
                try:
                    directory = QFileDialog.getExistingDirectory(
                        None, '選擇資料夾', self.root_dir,
                        QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
                    )
                    result_holder[0] = directory if directory else ''
                except Exception as e:
                    api_console(f"選擇資料夾失敗: {e}", level=LogLevel.ERROR)
                    result_holder[0] = ''
                finally:
                    loop.quit()

            loop = QEventLoop()
            QTimer.singleShot(0, show_dialog)
            loop.exec()
            return result_holder[0] or ''
        except Exception as e:
            api_console(f"選擇資料夾失敗: {e}", level=LogLevel.ERROR)
            return ''
    
    @Slot(str, result=str)
    def download(self, url):
        """下載按鈕被點擊"""
        download_console(f"收到下載請求: {url}", level=LogLevel.INFO)
        return "下載功能尚未實作"
    
    def _process_pending_tasks_for_url(self, url):
        """處理等待中的同名任務（當一個任務完成時）"""
        try:
            download_console(f"[DBG] _process_pending_tasks_for_url 進入 url={url[:50]}...", level=LogLevel.DEBUG)
            download_console("[DBG] _process_pending_tasks_for_url 即將取得 _lock", level=LogLevel.DEBUG)
            with self._lock:
                if url not in self.pending_tasks_by_url:
                    download_console("[DBG] _process_pending_tasks_for_url 無等待任務，return", level=LogLevel.DEBUG)
                    return

                pending_tasks = self.pending_tasks_by_url[url]
                if not pending_tasks:
                    download_console("[DBG] _process_pending_tasks_for_url 列表空，return", level=LogLevel.DEBUG)
                    return

                pending_task = pending_tasks.pop(0)
                task_id = pending_task['task_id']

                if not pending_tasks:
                    del self.pending_tasks_by_url[url]

                self.downloading_urls.add(url)
            download_console("[DBG] _process_pending_tasks_for_url 已釋放 _lock", level=LogLevel.DEBUG)
            download_console(f"開始下載等待中的任務 {task_id}（URL: {url}）", level=LogLevel.INFO)

            task_format = ''
            download_console("[DBG] _process_pending_tasks_for_url 即將取得 _lock(task_format)", level=LogLevel.DEBUG)
            with self._lock:
                task_format = self.task_formats.get(str(task_id), '')
            download_console("[DBG] _process_pending_tasks_for_url 已釋放 _lock，即將 _safe_eval_js", level=LogLevel.DEBUG)
            self._safe_eval_js("window.updateDownloadProgress", task_id, 0, "等待中", '', '', task_format)
            
            # 將任務提交到排程器
            self.scheduler.submit(
                task_id,
                pending_task['url'],
                pending_task['quality'],
                pending_task['format'],
                downloads_dir=pending_task['downloads_dir'],
                add_resolution_to_filename=pending_task['add_resolution'],
                original_format=pending_task['original_format'],
            )
        except Exception as e:
            download_console(f"處理等待中的任務時出錯: {e}", level=LogLevel.ERROR)
    
    @Slot(str, str, str, str, result=str)
    def check_file_exists_before_download(self, url, quality, format_type, original_format=None):
        """在開始下載前檢查文件是否存在（不開始下載）"""
        try:
            # 規範化格式
            fmt = (original_format or format_type or '').strip().lower()
            if fmt in ('mp3', 'aac', 'flac', 'wav', 'audio'):
                normalized_format = '音訊'
            else:
                normalized_format = '影片'
            
            # 規範化畫質
            q = (quality or '').strip()
            if normalized_format == '影片':
                import re
                m = re.search(r"(\d+)", q)
                normalized_quality = m.group(1) if m else '1080'
            else:
                import re
                m = re.search(r"(\d+)", q)
                normalized_quality = m.group(1) if m else '320'
            
            # 獲取下載路徑
            settings = self.settings_manager.load_settings()
            add_resolution = settings.get('addResolutionToFilename', False)
            resolved_download_dir = get_download_path(self.root_dir, self.settings_manager)
            
            # 檢查文件是否存在
            existing_file = None
            try:
                import threading
                
                result = [None]
                exception = [None]
                
                def check_file():
                    try:
                        result[0] = self._check_file_exists(url, normalized_quality, normalized_format, 
                                                           resolved_download_dir, add_resolution, original_format=fmt)
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=check_file, daemon=True)
                thread.start()
                thread.join(timeout=5)  # 5秒超時
                
                if thread.is_alive():
                    download_console(f"文件存在檢查超時，跳過檢查", level=LogLevel.WARNING)
                    existing_file = None
                elif exception[0]:
                    download_console(f"文件存在檢查出錯: {exception[0]}，跳過檢查", level=LogLevel.WARNING)
                    existing_file = None
                else:
                    existing_file = result[0]
            except Exception as e:
                download_console(f"文件存在檢查失敗: {e}，跳過檢查", level=LogLevel.WARNING)
                existing_file = None
            
            if existing_file:
                return f"FILE_EXISTS:{existing_file}"
            return "FILE_NOT_EXISTS"
        except Exception as e:
            download_console(f"檢查文件是否存在時出錯: {e}", level=LogLevel.ERROR)
            return "FILE_NOT_EXISTS"  # 出錯時假設文件不存在，允許下載
    
    @Slot(str, result=str)
    def delete_existing_file(self, file_path):
        """刪除已存在的檔案（僅允許刪除下載目錄內的檔案）。成功回傳 OK，失敗回傳錯誤訊息。"""
        try:
            if not file_path or not file_path.strip():
                return "錯誤：未提供檔案路徑"
            file_path = os.path.normpath(os.path.abspath(file_path.strip()))
            settings = self.settings_manager.load_settings()
            resolved_download_dir = get_download_path(self.root_dir, self.settings_manager)
            download_dir_real = os.path.realpath(resolved_download_dir)
            file_real = os.path.realpath(file_path)
            if not file_real.startswith(download_dir_real):
                download_console(f"拒絕刪除：檔案不在下載目錄內: {file_path}", level=LogLevel.WARNING)
                return "錯誤：僅允許刪除下載目錄內的檔案"
            if not os.path.isfile(file_real):
                download_console(f"檔案不存在或非檔案，跳過刪除: {file_real}", level=LogLevel.INFO)
                return "OK"
            os.remove(file_real)
            download_console(f"已刪除舊檔案: {file_real}", level=LogLevel.INFO)
            return "OK"
        except Exception as e:
            download_console(f"刪除檔案失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"
    
    @Slot(str, result=str)
    def check_playlist_folder_exists(self, playlist_data_json):
        """檢查播放清單資料夾是否存在，並檢測重複的影片檔案（使用現有標題推算檔名，避免大量網路請求）
        
        返回 JSON 字串：
        {
            "folderExists": bool,
            "duplicates": [
                {"url": str, "title": str, "filePath": str, "quality": str, "format": str},
                ...
            ]
        }
        """
        try:
            payload = json.loads(playlist_data_json or '{}')
            playlist_title = payload.get('playlistTitle') or payload.get('playlist_title') or '播放清單'
            videos = payload.get('videos') or []

            if not isinstance(videos, list) or len(videos) == 0:
                return json.dumps({"folderExists": False, "duplicates": []}, ensure_ascii=False)

            # 獲取下載路徑與設定
            settings = self.settings_manager.load_settings()
            add_resolution = settings.get('addResolutionToFilename', False)
            base_dir = get_download_path(self.root_dir, self.settings_manager)
            subfolder = _sanitize_folder_name(playlist_title)
            playlist_folder = safe_path_join(base_dir, subfolder)

            # 檢查資料夾是否存在
            folder_exists = os.path.isdir(playlist_folder)
            duplicates = []

            if folder_exists:
                download_console(f"播放清單資料夾已存在: {playlist_folder}", level=LogLevel.INFO)
                video_exts = {'mp4', 'mkv', 'webm', 'flv', 'avi', 'mov'}
                audio_exts = {'mp3', 'aac', 'flac', 'wav', 'm4a', 'ogg', 'opus'}

                # 先建立資料夾檔案索引，避免每部影片都重複掃描
                folder_files = []
                try:
                    for name in os.listdir(playlist_folder):
                        full_path = os.path.join(playlist_folder, name)
                        if os.path.isfile(full_path):
                            stem, ext = os.path.splitext(name)
                            folder_files.append({
                                "name": name,
                                "stem": stem,
                                "ext": ext.lower().lstrip('.'),
                                "path": full_path,
                            })
                except OSError:
                    folder_files = []

                def _normalize_stem_for_match(stem_text):
                    s = str(stem_text or '')
                    # 移除常見解析度/音訊碼率後綴（例如 _1080p / _320kbps）
                    s = re.sub(r'[_\-\s]*(\d{3,4})p$', '', s, flags=re.IGNORECASE)
                    s = re.sub(r'[_\-\s]*(\d{2,4})kbps$', '', s, flags=re.IGNORECASE)
                    # 僅保留中英數，降低符號差異造成漏判
                    s = re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', '', s).lower()
                    return s

                for video in videos:
                    url = (video.get('url') or '').strip()
                    quality = video.get('quality', '1080p')
                    format_type = video.get('format', 'mp4')
                    title = video.get('title', '未知影片')

                    if not url:
                        continue

                    try:
                        # 規範化格式與副檔名
                        fmt = (format_type or '').strip().lower()
                        if fmt in ('mp3', 'aac', 'flac', 'wav', 'audio'):
                            normalized_format = '音訊'
                            # 若原始格式為常見音訊格式就直接使用，否則預設 mp3
                            ext = fmt if fmt in ('mp3', 'aac', 'flac', 'wav') else 'mp3'
                        else:
                            normalized_format = '影片'
                            # 若原始格式為影片常見格式就直接使用，否則預設 mp4
                            ext = fmt if fmt in ('mp4', 'mkv', 'webm') else 'mp4'

                        # 依畫質字串抓出數字（例如 1080p -> 1080）
                        q = (quality or '').strip()
                        import re as re_module
                        m = re_module.search(r"(\d+)", q)
                        qnum = m.group(1) if m else ('320' if normalized_format == '音訊' else '1080')

                        # 使用前端傳來的標題推算實際檔名（套用與下載時相同的非法字元過濾）
                        safe_title = re.sub(r'[<>:"/\\|?*]', '', str(title) or '')
                        if not safe_title:
                            safe_title = '無標題影片'

                        possible_files = []
                        if normalized_format == '音訊':
                            # mp3 等音訊：不論 add_resolution 設定，都檢查兩種檔名（下載時可能不同設定）
                            possible_files.append(f"{safe_title}.{ext}")
                            possible_files.append(f"{safe_title}_{qnum}kbps.{ext}")
                        elif add_resolution:
                            possible_files.append(f"{safe_title}_{qnum}p.{ext}")
                        else:
                            possible_files.append(f"{safe_title}.{ext}")

                        existing_file = None
                        for filename in possible_files:
                            file_path = os.path.join(playlist_folder, filename)
                            if os.path.exists(file_path):
                                existing_file = file_path
                                break

                        # 精確未命中時，做正規化匹配，避免副檔名/後綴差異造成漏判
                        if not existing_file and safe_title:
                            safe_title_norm = _normalize_stem_for_match(safe_title)
                            if safe_title_norm:
                                if normalized_format == '音訊':
                                    candidate_exts = audio_exts
                                else:
                                    candidate_exts = video_exts

                                for f in folder_files:
                                    if f.get('ext') not in candidate_exts:
                                        continue
                                    stem_norm = _normalize_stem_for_match(f.get('stem', ''))
                                    if not stem_norm:
                                        continue
                                    # 支援同名、加後綴、或少量前綴（例如序號）情境
                                    if (
                                        stem_norm == safe_title_norm
                                        or stem_norm.startswith(safe_title_norm)
                                        or safe_title_norm.startswith(stem_norm)
                                    ):
                                        existing_file = f.get('path')
                                        break

                        if existing_file:
                            # 根據實際檔名修正顯示用畫質資訊，讓提示內容更精確
                            display_quality = quality
                            try:
                                base_name = os.path.basename(existing_file)
                                if normalized_format == '音訊':
                                    # 嘗試從檔名解析出 xxxxkbps
                                    m2 = re_module.search(r'_(\d+)kbps', base_name, re.IGNORECASE)
                                    if m2:
                                        display_quality = f"{m2.group(1)}kbps"
                                    else:
                                        display_quality = f"{qnum}kbps"
                                else:
                                    # 影片：顯示為 xxxxp
                                    m2 = re_module.search(r'(\d+)', base_name)
                                    if m2:
                                        display_quality = f"{m2.group(1)}p"
                                    elif qnum:
                                        display_quality = f"{qnum}p"
                            except Exception:
                                # 解析失敗時維持原本的 quality 顯示
                                pass

                            duplicates.append({
                                "url": url,
                                "title": title,
                                "filePath": existing_file,
                                "quality": display_quality,
                                "format": format_type
                            })
                    except Exception as e:
                        download_console(f"檢查影片重複時出錯 (url={url}): {e}", level=LogLevel.WARNING)
                        continue

            result = {
                "folderExists": folder_exists,
                "duplicates": duplicates,
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            download_console(f"檢查播放清單資料夾時出錯: {e}", level=LogLevel.ERROR)
            return json.dumps({"folderExists": False, "duplicates": []}, ensure_ascii=False)
    
    @Slot(str, result=str)
    def delete_existing_files(self, file_paths_json):
        """批量刪除已存在的檔案（僅允許刪除下載目錄內的檔案）
        file_paths_json: JSON 字串陣列，包含要刪除的檔案路徑
        返回 JSON 字串：{"success": [str, ...], "failed": [{"path": str, "error": str}, ...]}
        """
        try:
            file_paths = json.loads(file_paths_json or '[]')
            if not isinstance(file_paths, list):
                return json.dumps({"success": [], "failed": [{"path": "", "error": "參數格式錯誤"}]})
            
            settings = self.settings_manager.load_settings()
            resolved_download_dir = get_download_path(self.root_dir, self.settings_manager)
            download_dir_real = os.path.realpath(resolved_download_dir)
            
            success = []
            failed = []
            
            for file_path in file_paths:
                if not file_path or not str(file_path).strip():
                    continue
                
                try:
                    file_path = os.path.normpath(os.path.abspath(str(file_path).strip()))
                    file_real = os.path.realpath(file_path)
                    
                    if not file_real.startswith(download_dir_real):
                        download_console(f"拒絕刪除：檔案不在下載目錄內: {file_path}", level=LogLevel.WARNING)
                        failed.append({"path": file_path, "error": "檔案不在下載目錄內"})
                        continue
                    
                    if not os.path.isfile(file_real):
                        download_console(f"檔案不存在或非檔案，跳過刪除: {file_real}", level=LogLevel.INFO)
                        success.append(file_path)  # 視為成功（檔案已不存在）
                        continue
                    
                    os.remove(file_real)
                    download_console(f"已刪除舊檔案: {file_real}", level=LogLevel.INFO)
                    success.append(file_path)
                except Exception as e:
                    download_console(f"刪除檔案失敗 ({file_path}): {e}", level=LogLevel.ERROR)
                    failed.append({"path": file_path, "error": str(e)})
            
            result = {
                "success": success,
                "failed": failed
            }
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            download_console(f"批量刪除檔案時出錯: {e}", level=LogLevel.ERROR)
            return json.dumps({"success": [], "failed": [{"path": "", "error": str(e)}]})
    
    def _check_file_exists(self, url, quality, format_type, downloads_dir, add_resolution, original_format=None):
        """檢查目標文件是否存在，返回文件路徑（如果存在）
        
        只檢查相同格式的文件，例如：
        - 如果 original_format='mp3'，只檢查 .mp3 文件
        - 如果 original_format='mp4'，只檢查 .mp4, .mkv, .webm 等影片格式
        """
        try:
            # 先獲取視頻信息以確定標題和高度
            import yt_dlp
            ffmpeg_path = safe_path_join(self.root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
            ydl_opts = {
                'quiet': True,
                'simulate': True,
                'extract_flat': False,
            }
            
            # 設定 ffmpeg 路徑（如果存在）
            if os.path.exists(ffmpeg_path):
                ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
            deno_path = get_deno_path(self.root_dir)
            if deno_path:
                ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
                api_console(f"已配置 Deno 路徑: {deno_path}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
            
            title = info_dict.get('title', '無標題影片')
            # 清理標題中的非法字符
            import re
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
            
            # 規範化格式和畫質（format_type 可能是 '音訊'/'影片' 或 'mp3'/'mp4' 等）
            fmt = (original_format or format_type or '').strip().lower()
            if fmt in ('mp3', 'aac', 'flac', 'wav', 'audio', '音訊'):
                normalized_format = '音訊'
                ext = fmt if fmt in ('mp3', 'aac', 'flac', 'wav') else 'mp3'
            else:
                normalized_format = '影片'
                ext = fmt if fmt in ('mp4', 'mkv', 'webm') else 'mp4'
            
            q = (quality or '').strip()
            import re as re_module
            m = re_module.search(r"(\d+)", q)
            qnum = m.group(1) if m else ('320' if normalized_format == '音訊' else '1080')
            
            # 構建可能的文件名列表
            possible_files = []
            
            # 獲取實際高度（用於影片）
            height = None
            if normalized_format == '影片':
                formats = info_dict.get('formats', [])
                for f in formats:
                    h = f.get('height')
                    if h and h >= int(qnum):
                        height = h
                        break
                if not height:
                    height = qnum
            
            # 根據設定構建可能的文件名
            if normalized_format == '音訊':
                # mp3 等音訊：不論 add_resolution，都檢查兩種檔名（下載時可能不同設定）
                possible_files.append(f"{safe_title}.{ext}")
                possible_files.append(f"{safe_title}_{qnum}kbps.{ext}")
            elif add_resolution:
                possible_files.append(f"{safe_title}_{height}p.{ext}")
            else:
                possible_files.append(f"{safe_title}.{ext}")
            
            # 檢查文件是否存在（只檢查相同格式）
            for filename in possible_files:
                file_path = os.path.join(downloads_dir, filename)
                if os.path.exists(file_path):
                    return file_path
            
            # 音訊：若精確檔名未命中，掃描資料夾內同副檔名且檔名以標題開頭的檔案
            if normalized_format == '音訊' and safe_title:
                try:
                    for name in os.listdir(downloads_dir):
                        if name.lower().endswith(f'.{ext}') and os.path.isfile(os.path.join(downloads_dir, name)):
                            base = os.path.splitext(name)[0]
                            if base == safe_title or base.startswith(safe_title + '_'):
                                return os.path.join(downloads_dir, name)
                except OSError:
                    pass
            
            # 只檢查用戶指定的格式，不檢查其他擴展名
            # 這樣可以允許用戶下載同一影片的不同格式（例如已有 mp4，可以再下載 mp3）
            
            return None
        except Exception as e:
            api_console(f"檢查文件是否存在時出錯: {e}")
            return None
    
    @Slot(str, result=str)
    def start_batch_download(self, video_data_json):
        """批量下載（主要給播放清單使用）
        video_data_json 支援兩種格式：
        1. 陣列：[{ "id", "url", "quality", "format" }, ...]
        2. 物件：{ "playlistTitle": "播放清單名稱", "playlistGroupId": "...", "videos": [...] }  # 下載到集中子資料夾

        - **重要**：`id` 會直接當作任務ID回報進度/完成，必須與前端佇列對齊。
        """
        try:
            payload = json.loads(video_data_json or '[]')
            playlist_subfolder = None
            playlist_group_id = None
            if isinstance(payload, dict):
                playlist_subfolder = payload.get('playlistTitle') or payload.get('playlist_title')
                playlist_group_id = payload.get('playlistGroupId') or payload.get('playlist_group_id')
                video_list = payload.get('videos') or []
            else:
                video_list = payload if isinstance(payload, list) else []

            if not isinstance(video_list, list):
                return "批量下載失敗: 參數格式錯誤"

            download_console(f"開始批量下載，共 {len(video_list)} 部影片", level=LogLevel.INFO)
            if playlist_subfolder:
                subfolder = _sanitize_folder_name(playlist_subfolder)
                download_console(f"播放清單將下載至子資料夾: {subfolder}", level=LogLevel.INFO)
            if playlist_group_id:
                download_console(f"播放清單群組ID: {playlist_group_id}", level=LogLevel.DEBUG)
                # 記錄播放清單名稱供通知顯示
                with self._lock:
                    self.playlist_titles[str(playlist_group_id)] = playlist_subfolder or '播放清單'

            def run_one(tid, u, q, f, subfolder=None, pl_group_id=None):
                try:
                    # 記錄播放清單群組ID（如果有的話）
                    if pl_group_id:
                        with self._lock:
                            self.task_playlist_groups[str(tid)] = pl_group_id
                    self._start_download_impl(int(tid), u, q, f, subfolder=subfolder)
                except Exception as e:
                    download_console(f"批量下載啟動失敗(task_id={tid}): {e}", level=LogLevel.ERROR)
                    try:
                        self._notify_download_complete_safely(int(tid), u, error=str(e))
                    except Exception:
                        pass

            subfolder = _sanitize_folder_name(playlist_subfolder) if playlist_subfolder else None
            started = 0
            for idx, item in enumerate(video_list):
                if not isinstance(item, dict):
                    continue
                url = (item.get('url') or '').strip()
                if not url:
                    continue
                raw_id = item.get('id')
                task_id = int(raw_id) if raw_id is not None else idx
                quality = item.get('quality', '1080p')
                format_type = item.get('format', 'mp4')

                t = threading.Thread(
                    target=run_one,
                    args=(task_id, url, quality, format_type, subfolder, playlist_group_id),
                    daemon=True,
                )
                t.start()
                started += 1

            return f"已開始批量下載 {started} 部影片"
        except Exception as e:
            download_console(f"批量下載失敗: {e}", level=LogLevel.ERROR)
            return f"批量下載失敗: {e}"

    @Slot(int, str, str, str, result=str)
    def start_download(self, task_id, url, quality, format_type):
        """開始下載（單一影片，使用預設路徑）"""
        return self._start_download_impl(task_id, url, quality, format_type, subfolder=None)

    def _start_download_impl(self, task_id, url, quality, format_type, subfolder=None):
        """內部實作：開始下載，可指定播放清單子資料夾"""
        try:
            download_console(f"[DBG] _start_download_impl 進入 task_id={task_id}", level=LogLevel.DEBUG)
            download_console(f"開始下載任務 {task_id}: {url}", level=LogLevel.INFO)
            fmt = (format_type or '').strip().lower()
            # 對齊下載器分支：將具體副檔名映射為語義分類
            if fmt in ('mp3', 'aac', 'flac', 'wav', 'audio'):
                normalized_format = '音訊'
            else:
                # 預設走影片路徑（包含 mp4、mkv、webm 或未指定時）
                normalized_format = '影片'

            # 將畫質轉為下載器可理解的數值或保留音訊位元率
            q = (quality or '').strip()
            if normalized_format == '影片':
                # 允許 '1080p' 或 '1080'，只取數字
                import re
                m = re.search(r"(\d+)", q)
                normalized_quality = m.group(1) if m else '1080'
            else:
                # 音訊使用位元率數字（例如 '320'）
                import re
                m = re.search(r"(\d+)", q)
                normalized_quality = m.group(1) if m else '320'

            # 讀取設定中的下載路徑和解析度檔名選項
            settings = self.settings_manager.load_settings()
            add_resolution = settings.get('addResolutionToFilename', False)

            # 決定下載目錄（播放清單使用子資料夾集中存放）
            base_dir = get_download_path(self.root_dir, self.settings_manager)
            if subfolder:
                resolved_download_dir = safe_path_join(base_dir, subfolder)
            else:
                resolved_download_dir = base_dir
            download_console(f"使用下載路徑: {resolved_download_dir}", level=LogLevel.INFO)

            try:
                os.makedirs(resolved_download_dir, exist_ok=True)
            except Exception as e:
                download_console(f"創建下載資料夾失敗，改用預設: {e}", level=LogLevel.ERROR)
                resolved_download_dir = safe_path_join(self.root_dir, 'downloads')
                if subfolder:
                    resolved_download_dir = safe_path_join(resolved_download_dir, subfolder)
                os.makedirs(resolved_download_dir, exist_ok=True)

            # 先檢查是否有同名影片正在下載（這個很快，不會阻塞）
            download_console("[DBG] start_download 即將取得 _lock（檢查同名）", level=LogLevel.DEBUG)
            with self._lock:
                if url in self.downloading_urls:
                    # 有同名影片正在下載，將任務加入等待佇列（僅在鎖內做 dict 更新，不呼叫 JS）
                    download_console(f"發現同名影片正在下載: {url}，任務 {task_id} 將等待下載完成", level=LogLevel.INFO)
                    self.task_download_paths[str(task_id)] = resolved_download_dir
                    self.task_formats[str(task_id)] = fmt
                    self.task_urls[str(task_id)] = url
                    if url not in self.pending_tasks_by_url:
                        self.pending_tasks_by_url[url] = []
                    self.pending_tasks_by_url[url].append({
                        'task_id': task_id,
                        'url': url,
                        'quality': normalized_quality,
                        'format': normalized_format,
                        'downloads_dir': resolved_download_dir,
                        'add_resolution': add_resolution,
                        'original_format': fmt,
                    })
                    need_waiting_ui = True
                else:
                    need_waiting_ui = False
            download_console("[DBG] start_download 已釋放 _lock（檢查同名）", level=LogLevel.DEBUG)
            if need_waiting_ui:
                download_console("[DBG] start_download 即將 _safe_eval_js 等待中 UI", level=LogLevel.DEBUG)
                self._safe_eval_js("window.updateDownloadProgress", task_id, 0, "等待同名影片下載完成", '', '', fmt)
                return "已加入等待佇列（等待同名影片下載完成）"

            # 檢查文件是否已存在（在背景線程執行，主線程僅短暫等待，避免 UI 卡死）
            existing_file = None
            try:
                result = [None]
                exception = [None]

                def check_file():
                    try:
                        result[0] = self._check_file_exists(
                            url, normalized_quality, normalized_format,
                            resolved_download_dir, add_resolution, original_format=fmt
                        )
                    except Exception as e:
                        exception[0] = e

                thread = threading.Thread(target=check_file, daemon=True)
                thread.start()
                download_console("[DBG] start_download 主線程即將 thread.join(1.5s)", level=LogLevel.DEBUG)
                # 主線程最多等 1.5 秒，避免長期佔用導致「開啟資料夾」等操作無回應
                thread.join(timeout=1.5)
                download_console("[DBG] start_download 主線程 thread.join 已返回", level=LogLevel.DEBUG)

                if thread.is_alive():
                    download_console("文件存在檢查超時，跳過檢查", level=LogLevel.WARNING)
                    existing_file = None
                elif exception[0]:
                    download_console(f"文件存在檢查出錯: {exception[0]}，跳過檢查", level=LogLevel.WARNING)
                    existing_file = None
                else:
                    existing_file = result[0]
            except Exception as e:
                download_console(f"文件存在檢查失敗: {e}，跳過檢查", level=LogLevel.WARNING)
                existing_file = None
            
            if existing_file:
                # 文件已存在，返回特殊狀態讓前端顯示確認對話框
                download_console(f"發現已存在的文件: {existing_file}")
                # 將信息存儲在臨時變量中，等待用戶確認
                with self._lock:
                    if not hasattr(self, '_pending_downloads'):
                        self._pending_downloads = {}
                    self._pending_downloads[str(task_id)] = {
                        'url': url,
                        'quality': normalized_quality,
                        'format': normalized_format,
                        'original_format': fmt,  # 保留原始格式（如 mp3, mp4）
                        'downloads_dir': resolved_download_dir,
                        'add_resolution': add_resolution,
                        'existing_file': existing_file
                    }
                return f"FILE_EXISTS:{existing_file}"

            # 記錄任務路徑與格式，並標記此 URL 為正在下載（單一鎖區塊，不長期佔用）
            download_console("[DBG] start_download 即將取得 _lock（記錄路徑）", level=LogLevel.DEBUG)
            with self._lock:
                self.task_download_paths[str(task_id)] = resolved_download_dir
                self.task_formats[str(task_id)] = fmt
                self.task_urls[str(task_id)] = url
                self.downloading_urls.add(url)
            download_console("[DBG] start_download 已釋放 _lock（記錄路徑）", level=LogLevel.DEBUG)

            download_console(f"任務 {task_id} 下載路徑已記錄: {resolved_download_dir}, 格式: {fmt}, URL: {url}")
            download_console(f"開始下載任務 {task_id}，URL: {url}")

            # 丟給全域排程器（控制同時下載上限 + 重試）
            self.scheduler.submit(
                task_id,
                url,
                normalized_quality,
                normalized_format,
                downloads_dir=resolved_download_dir,
                add_resolution_to_filename=add_resolution,
                original_format=fmt,
            )
            return "已加入下載佇列"
        except Exception as e:
            download_console(f"開始下載失敗: {e}", level=LogLevel.ERROR)
            return f"下載失敗: {e}"
    
    @Slot(int, bool, result=str)
    def confirm_redownload(self, task_id, should_delete):
        """確認是否重新下載（刪除舊文件）"""
        try:
            download_console(f"[confirm_redownload] 開始處理任務 {task_id}, should_delete={should_delete}", level=LogLevel.INFO)
            
            # 先獲取待處理任務信息（在鎖內）
            with self._lock:
                if not hasattr(self, '_pending_downloads'):
                    download_console(f"[confirm_redownload] 沒有 _pending_downloads 屬性", level=LogLevel.WARNING)
                    return "沒有待處理的下載任務"
                
                pending = self._pending_downloads.get(str(task_id))
                if not pending:
                    download_console(f"[confirm_redownload] 找不到任務 {task_id} 在 _pending_downloads 中", level=LogLevel.WARNING)
                    return "找不到待處理的下載任務"
                
                url = pending['url']
                normalized_quality = pending['quality']
                normalized_format = pending['format']
                original_format = pending.get('original_format', None)  # 獲取原始格式
                resolved_download_dir = pending['downloads_dir']
                add_resolution = pending['add_resolution']
                existing_file = pending['existing_file']
            
            download_console(f"[confirm_redownload] 獲取到任務信息: url={url}, existing_file={existing_file}", level=LogLevel.INFO)
            
            # 如果用戶確認刪除，刪除舊文件（在後台線程執行，不阻塞 UI）
            if should_delete:
                import threading
                
                def delete_file_thread():
                    try:
                        if os.path.exists(existing_file):
                            os.remove(existing_file)
                            download_console(f"已刪除舊文件: {existing_file}", level=LogLevel.INFO)
                        else:
                            download_console(f"文件不存在，無需刪除: {existing_file}", level=LogLevel.INFO)
                    except Exception as e:
                        download_console(f"刪除舊文件失敗（將在下載時覆蓋）: {e}", level=LogLevel.WARNING)
                        # 不返回錯誤，讓下載繼續進行（下載器會處理文件覆蓋）
                
                # 在單獨的線程中執行刪除操作，不等待完成
                delete_thread = threading.Thread(target=delete_file_thread, daemon=True)
                delete_thread.start()
                # 不等待刪除完成，直接繼續執行下載（下載器會處理文件覆蓋）
            else:
                # 用戶取消，移除待處理任務和相關數據
                with self._lock:
                    if str(task_id) in self._pending_downloads:
                        del self._pending_downloads[str(task_id)]
                    # 清理任務相關數據
                    self.task_download_paths.pop(str(task_id), None)
                    self.task_formats.pop(str(task_id), None)
                    self.task_urls.pop(str(task_id), None)
                    self.task_playlist_groups.pop(str(task_id), None)
                download_console(f"用戶取消任務 {task_id}，已清理相關數據", level=LogLevel.INFO)
                return "已取消下載"
            
            # 記錄任務的下載路徑和格式（與 start_download 保持一致）
            download_console(f"[confirm_redownload] 準備記錄任務信息", level=LogLevel.INFO)
            with self._lock:
                self.task_download_paths[str(task_id)] = resolved_download_dir
                self.task_formats[str(task_id)] = original_format or normalized_format  # 記錄格式（如 mp3, mp4）
                self.task_urls[str(task_id)] = url  # 記錄 URL
                # 標記此 URL 為正在下載
                self.downloading_urls.add(url)
            
            download_console(f"任務 {task_id} 下載路徑已記錄: {resolved_download_dir}, 格式: {original_format or normalized_format}, URL: {url}")
            download_console(f"開始下載任務 {task_id}，URL: {url}")
            
            # 開始下載，傳遞原始格式
            download_console(f"[confirm_redownload] 準備調用 scheduler.submit", level=LogLevel.INFO)
            self.scheduler.submit(
                task_id,
                url,
                normalized_quality,
                normalized_format,
                downloads_dir=resolved_download_dir,
                add_resolution_to_filename=add_resolution,
                original_format=original_format,
            )
            download_console(f"[confirm_redownload] scheduler.submit 調用完成", level=LogLevel.INFO)
            
            # 移除待處理任務
            with self._lock:
                if str(task_id) in self._pending_downloads:
                    del self._pending_downloads[str(task_id)]
                    download_console(f"[confirm_redownload] 已從 _pending_downloads 中移除任務 {task_id}", level=LogLevel.INFO)
            
            download_console(f"[confirm_redownload] 任務 {task_id} 處理完成，返回成功", level=LogLevel.INFO)
            return "已加入下載佇列"
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            download_console(f"確認重新下載失敗: {e}", level=LogLevel.ERROR)
            download_console(f"錯誤堆棧: {error_trace}", level=LogLevel.ERROR)
            return f"失敗: {e}"

    @Slot(int, result=str)
    def open_file_location_by_task(self, task_id):
        """
        根據任務ID開啟檔案所在資料夾。
        僅做同步的 dict 查詢後立即 return；實際開啟在背景線程執行，不碰主線程。
        """
        try:
            api_console(f"[DBG] open_file_location_by_task 進入 task_id={task_id}", level=LogLevel.DEBUG)
            if task_id is None:
                return "失敗: 任務ID不可用"
            task_key = str(task_id).strip()
            if not task_key:
                return "失敗: 任務ID不可用"

            api_console("[DBG] open_file_location_by_task 即將取得 _lock", level=LogLevel.DEBUG)
            with self._lock:
                file_path = self.task_download_paths.get(task_key)
            api_console("[DBG] open_file_location_by_task 已釋放 _lock", level=LogLevel.DEBUG)
            if not file_path:
                api_console(f"[DBG] open_file_location_by_task 找不到路徑 task_key={task_key}", level=LogLevel.DEBUG)
                return f"失敗: 找不到任務 {task_key} 的檔案路徑"

            download_console(f"[open_file_location] 任務 {task_id} 的檔案路徑: {file_path}")

            def _run_open():
                err_msg = None
                try:
                    api_console("[DBG] _run_open 背景線程進入", level=LogLevel.DEBUG)
                    if sys.platform.startswith("win"):
                        _open_in_explorer_win(file_path)
                    else:
                        folder = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path
                        if os.path.exists(folder):
                            subprocess.Popen(["xdg-open", folder])
                    api_console("[DBG] _run_open 背景線程完成", level=LogLevel.DEBUG)
                except Exception as e:
                    api_console(f"根據任務ID開啟檔案位置失敗: {e}", level=LogLevel.ERROR)
                    err_msg = str(e)
                if err_msg:
                    QTimer.singleShot(0, lambda msg=err_msg: self._safe_eval_js("window.showModal", "錯誤", msg))

            api_console("[DBG] open_file_location_by_task 即將 start 背景線程", level=LogLevel.DEBUG)
            threading.Thread(target=_run_open, daemon=True).start()
            api_console("[DBG] open_file_location_by_task 即將 return", level=LogLevel.DEBUG)
            return "正在開啟檔案位置..."
        except Exception as e:
            api_console(f"根據任務ID開啟檔案位置失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"

    @Slot(str, result=str)
    def open_file_location(self, file_path):
        """開啟檔案所在資料夾（支援 Windows）"""
        try:
            if not file_path or not file_path.strip():
                return "檔案路徑不可用"
            
            # 統一分隔符並清理路徑
            fp = str(file_path).strip().replace('/', os.sep)
            
            # 如果檔案路徑是相對路徑，嘗試在設定檔的下載路徑中尋找
            if not os.path.isabs(fp):
                # 獲取設定檔中的自訂下載路徑
                settings = self.settings_manager.load_settings()
                custom_path = settings.get('customDownloadPath', '')
                
                # 優先使用設定檔中的路徑
                if custom_path and os.path.exists(custom_path):
                    # 在自訂路徑中尋找檔案
                    custom_file_path = os.path.join(custom_path, fp)
                    if os.path.exists(custom_file_path):
                        fp = custom_file_path
                        download_console(f"在自訂路徑中找到檔案: {fp}")
                    else:
                        # 如果自訂路徑中找不到，嘗試預設下載路徑
                        default_file_path = os.path.join(self.root_dir, 'downloads', fp)
                        if os.path.exists(default_file_path):
                            fp = default_file_path
                            download_console(f"在預設路徑中找到檔案: {fp}")
                        else:
                            # 最後嘗試相對於根目錄的路徑
                            fp = os.path.join(self.root_dir, fp)
                else:
                    # 如果沒有自訂路徑，嘗試預設下載路徑
                    default_file_path = os.path.join(self.root_dir, 'downloads', fp)
                    if os.path.exists(default_file_path):
                        fp = default_file_path
                        download_console(f"在預設路徑中找到檔案: {fp}")
                    else:
                        # 最後嘗試相對於根目錄的路徑
                        fp = os.path.join(self.root_dir, fp)
            else:
                # 絕對路徑，檢查是否在允許範圍內
                if not fp.startswith(self.root_dir) and not fp.startswith(os.path.expanduser("~")):
                    return "檔案路徑不在允許範圍內"
            
            # 確保路徑是絕對路徑
            if not os.path.isabs(fp):
                fp = os.path.abspath(fp)
            
            # 在後台線程中執行開啟資料夾操作，與 open_file_location_by_task 同一套邏輯
            def open_folder_thread():
                try:
                    if os.path.exists(fp):
                        if sys.platform.startswith("win"):
                            _open_in_explorer_win(fp)
                        else:
                            folder = os.path.dirname(fp) if os.path.isfile(fp) else fp
                            subprocess.Popen(["xdg-open", folder])
                except Exception as e:
                    api_console(f"開啟資料夾時出錯: {e}", level=LogLevel.ERROR)

            if os.path.exists(fp):
                threading.Thread(target=open_folder_thread, daemon=True).start()
                return "正在開啟檔案位置..."
            return "檔案不存在"
        except Exception as e:
            api_console(f"開啟檔案位置失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"
    
    @Slot(str, result=str)
    def open_external_link(self, url):
        """使用系統預設瀏覽器開啟外部連結"""
        try:
            if not url or not url.strip():
                return "連結不可用"
            
            url = url.strip()
            
            # 驗證URL格式
            import re
            url_pattern = re.compile(
                r'^https?://'  # http:// 或 https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
                r'localhost|'  # localhost
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
                r'(?::\d+)?'  # 可選端口
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            # 確保 URL 格式正確
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # 驗證URL格式
            if not url_pattern.match(url):
                return "無效的URL格式"
            
            # 使用系統預設瀏覽器開啟
            if sys.platform.startswith('win'):
                subprocess.Popen(['cmd', '/c', 'start', '', url], 
                               creationflags=subprocess.CREATE_NO_WINDOW)
            elif sys.platform.startswith('darwin'):  # macOS
                subprocess.Popen(['open', url])
            else:  # Linux 和其他 Unix-like 系統
                subprocess.Popen(['xdg-open', url])
            
            api_console(f"已開啟外部連結: {url}", level=LogLevel.INFO)
            return "已開啟外部連結"
        except Exception as e:
            api_console(f"開啟外部連結失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"
    
    @Slot(str, result=str)
    def cancel_download(self, task_id):
        """取消下載"""
        try:
            self.downloader.cancel_download(task_id)
            return "下載已取消"
        except Exception as e:
            download_console(f"取消下載失敗: {e}", level=LogLevel.ERROR)
            return f"取消失敗: {e}"
    
    @Slot(result=str)
    def open_settings(self):
        """開啟設定視窗"""
        api_console("開啟設定視窗", level=LogLevel.INFO)
        try:
            # 檢查是否已經有設定視窗在運行
            if self.settings_process is not None and self.settings_process.poll() is None:
                api_console("設定視窗已經開啟，嘗試調到該視窗", level=LogLevel.INFO)
                return "設定視窗已經開啟"
            
            settings_script = safe_path_join(self.root_dir, 'settings.pyw')
            if os.path.exists(settings_script):
                self.settings_process = subprocess.Popen([sys.executable, settings_script])
                api_console("設定視窗已開啟", level=LogLevel.INFO)
                return "設定視窗已開啟"
            else:
                api_console("找不到設定腳本", level=LogLevel.ERROR)
                return "找不到設定腳本"
        except Exception as e:
            api_console(f"開啟設定視窗失敗: {e}", level=LogLevel.ERROR)
            return f"開啟失敗: {e}"
    
    @Slot()
    def close_settings(self):
        """關閉設定視窗"""
        try:
            if self.settings_process and self.settings_process.poll() is None:
                self.settings_process.terminate()
                api_console("設定視窗已關閉", level=LogLevel.INFO)
        except Exception as e:
            api_console(f"關閉設定視窗失敗: {e}")
    
    @Slot(result=dict)
    def load_settings(self):
        """載入設定"""
        return self.settings_manager.load_settings()
    
    @Slot(dict)
    def save_settings(self, settings):
        """儲存設定"""
        self.settings_manager.save_settings(settings)
    
    @Slot(result=dict)
    def reset_to_defaults(self):
        """重設為預設值"""
        return self.settings_manager.reset_to_defaults()
    
    def _send_notification(self, title, message):
        """發送通知"""
        try:
            self.notificationRequested.emit(title or '', message or '')
        except Exception as e:
            api_console(f"發送通知失敗: {e}")

    def _on_notification_requested(self, title, message):
        """在主執行緒處理通知"""
        try:
            if callable(self.notification_handler):
                self.notification_handler(title or '', message or '')
            else:
                api_console(f"通知: {title} - {message}")
        except Exception as e:
            api_console(f"通知處理失敗: {e}")
    
    @Slot(result=str)
    def check_ytdlp_version(self):
        """檢查 yt-dlp 版本，並在 debug 中顯示目前與線上最新版本"""
        try:
            import urllib.request, json, time, os
            
            current_version = yt_dlp.version.__version__
            api_console(f"目前 yt-dlp 版本: {current_version}")
            
            # 檢查快取檔案
            cache_file = safe_path_join(self.root_dir, 'main', 'ytdlp_version_cache.json')
            latest = None
            
            # 檢查快取是否有效（24小時內）
            cache_valid = False
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    cache_time = cache_data.get('timestamp', 0)
                    cache_version = cache_data.get('version', '')
                    
                    # 檢查快取是否在24小時內且版本不為空
                    if (time.time() - cache_time < 86400) and cache_version:
                        latest = cache_version
                        cache_valid = True
                        api_console(f"使用快取的版本資訊: {latest}")
                except Exception as e:
                    api_console(f"讀取版本快取失敗: {e}")
            
            # 如果快取無效，從網路獲取
            if not cache_valid:
                try:
                    # 減少超時時間到5秒
                    with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        latest = data.get('info', {}).get('version') or ''
                    
                    # 儲存到快取
                    try:
                        cache_data = {
                            'version': latest,
                            'timestamp': time.time()
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                        api_console(f"版本資訊已快取: {latest}")
                    except Exception as e:
                        api_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    api_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest = cache_data.get('version', '')
                            api_console(f"使用舊快取版本: {latest}")
                        except Exception:
                            pass
            
            if latest:
                api_console(f"偵測到的最新 yt-dlp 版本: {latest}")
            else:
                api_console("無法取得最新 yt-dlp 版本")
            
            return current_version
        except Exception as e:
            api_console(f"檢查版本失敗: {e}", level=LogLevel.ERROR)
            return "未知版本"
    
    @Slot(result=str)
    def refresh_version(self):
        """重新整理版本號顯示"""
        try:
            # 動態重新導入模組以獲取最新版本號
            import importlib
            import config.constants
            importlib.reload(config.constants)
            from config.constants import APP_VERSION, APP_VERSION_HOME
            
            # 更新版本號顯示
            version_script = f"""
            (function(){{
                try {{
                    window.__APP_VERSION = '{APP_VERSION}';
                    window.__APP_VERSION_HOME = '{APP_VERSION_HOME}';
                    
                    var versionTag = document.getElementById('version-tag');
                    if (versionTag) {{
                        versionTag.textContent = '{APP_VERSION_HOME}';
                    }}
                    
                    var aboutVersion = document.getElementById('about-version');
                    if (aboutVersion) {{
                        aboutVersion.textContent = '{APP_VERSION}';
                    }}
                }} catch(e) {{
                    console.error('更新版本號失敗:', e);
                }}
            }})();
            """
            
            self._eval_js(version_script)
            return f"版本號已更新為: {APP_VERSION_HOME}"
        except Exception as e:
            api_console(f"重新整理版本號失敗: {e}", level=LogLevel.ERROR)
            return f"更新失敗: {e}"

    @Slot(result=str)
    def restart_app(self):
        """重啟應用程式（舊版等價：優先重啟打包 exe，否則重啟腳本）"""
        try:
            api_console("應用程式重啟請求")
            # 嘗試啟動同一資料夾上一層的 exe
            exe_path = os.path.normpath(os.path.join(self.root_dir, os.pardir, 'oldfish影片下載器.exe'))
            started = False
            try:
                if os.path.exists(exe_path):
                    api_console(f"嘗試啟動 exe: {exe_path}")
                    try:
                        si = None
                        flags = 0
                        if sys.platform.startswith('win'):
                            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 0
                            flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), startupinfo=si, creationflags=flags)
                    except Exception:
                        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
                    started = True
            except Exception as e:
                api_console(f"啟動 exe 失敗: {e}")

            if not started:
                # 退而求其次：重啟目前 Python 腳本（優先使用內嵌 pythonw，若無則 python.exe，最後使用目前解譯器）
                pyw = safe_path_join(self.root_dir, 'main.pyw')
                embed_dir = safe_path_join(self.root_dir, 'lib', 'python_embed')
                pythonw = safe_path_join(embed_dir, 'pythonw.exe')
                python = safe_path_join(embed_dir, 'python.exe')
                candidates = []
                if os.path.isfile(pythonw):
                    candidates.append(pythonw)
                if os.path.isfile(python):
                    candidates.append(python)
                # 最後退回目前執行中的解譯器
                candidates.append(os.path.normpath(sys.executable))
                try:
                    for exe in candidates:
                        try:
                            exe_path = os.path.normpath(exe)
                            script_path = os.path.normpath(pyw)
                            # 額外檢查：檔案存在且大小合理，避免誤選無效檔
                            if not (os.path.isfile(exe_path) and os.path.isfile(script_path)):
                                continue
                            try:
                                size_ok = os.path.getsize(exe_path) > 1024 * 50
                            except Exception:
                                size_ok = True
                            if not size_ok:
                                api_console(f"跳過過小的可執行檔: {exe_path}")
                                continue
                            api_console(f"嘗試以解譯器啟動: {exe_path} {script_path}")
                            try:
                                si = None
                                flags = 0
                                if sys.platform.startswith('win'):
                                    si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 0
                                    flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                                subprocess.Popen([exe_path, script_path], cwd=os.path.dirname(script_path), startupinfo=si, creationflags=flags)
                            except Exception:
                                subprocess.Popen([exe_path, script_path], cwd=os.path.dirname(script_path))
                            started = True
                            break
                        except Exception as inner_e:
                            api_console(f"嘗試使用 {exe} 重啟失敗: {inner_e}")
                except Exception as e:
                    api_console(f"啟動內嵌解譯器失敗: {e}")

            # 關閉目前應用
            try:
                from PySide6.QtWidgets import QApplication
                if started:
                    QApplication.quit()
                    return "正在重啟"
                else:
                    # 未能啟動新程序，只回報訊息
                    return "未找到可重啟目標，請手動重新啟動。"
            except Exception as e:
                api_console(f"結束目前應用失敗: {e}", level=LogLevel.ERROR)
                return "重啟流程已嘗試，請確認是否已開啟新視窗。"
        except Exception as e:
            api_console(f"重啟失敗: {e}", level=LogLevel.ERROR)
            return f"重啟失敗: {e}"

    @Slot()
    def restartApp(self):
        """為相容舊版 JS 呼叫名稱，轉呼叫 restart_app"""
        try:
            self.restart_app()
        except Exception as e:
            api_console(f"restartApp 失敗: {e}", level=LogLevel.ERROR)
    
    @Slot()
    def test_update_dialog(self):
        """測試更新對話框顯示（用於調試）"""
        try:
            api_console("測試更新對話框...")
            version_info = {
                'update_available': True,
                'current_version': '2023.12.30',
                'latest_version': '2024.01.15'
            }
            self.show_update_dialog(version_info)
            return "測試對話框已觸發"
        except Exception as e:
            api_console(f"測試更新對話框失敗: {e}", level=LogLevel.ERROR)
            return f"測試失敗: {e}"
    
    def check_and_update_ytdlp(self):
        """檢查 yt-dlp 是否需要更新；若有新版本則彈出與舊版一致的更新對話框"""
        try:
            import urllib.request, json, time, os
            
            # 檢查快取檔案
            cache_file = safe_path_join(self.root_dir, 'main', 'ytdlp_version_cache.json')
            current_version = yt_dlp.version.__version__
            latest = None
            
            # 檢查快取是否有效（24小時內）
            cache_valid = False
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    cache_time = cache_data.get('timestamp', 0)
                    cache_version = cache_data.get('version', '')
                    
                    # 檢查快取是否在24小時內且版本不為空
                    if (time.time() - cache_time < 86400) and cache_version:
                        latest = cache_version
                        cache_valid = True
                        api_console(f"使用快取的版本資訊: {latest}")
                except Exception as e:
                    api_console(f"讀取版本快取失敗: {e}")
            
            # 如果快取無效，從網路獲取
            if not cache_valid:
                api_console("檢查 yt-dlp 版本...")
                try:
                    # 減少超時時間到5秒
                    with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        latest = data.get('info', {}).get('version') or ''
                    
                    # 儲存到快取
                    try:
                        cache_data = {
                            'version': latest,
                            'timestamp': time.time()
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                        api_console(f"版本資訊已快取: {latest}")
                    except Exception as e:
                        api_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    api_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest = cache_data.get('version', '')
                            api_console(f"使用舊快取版本: {latest}")
                        except Exception:
                            pass
            
            api_console(f"目前版本: {current_version}")
            if latest:
                api_console(f"偵測到的最新版本: {latest}")
                try:
                    needs_update = compare_versions(current_version, latest) < 0
                except Exception:
                    needs_update = False
                if needs_update:
                    version_info = {
                        'update_available': True,
                        'current_version': current_version,
                        'latest_version': latest
                    }
                    # 使用信號在主線程中顯示對話框（因為 check_and_update_ytdlp 在後台線程執行）
                    api_console(f"發現 yt-dlp 新版本（目前版本: {current_version}, 最新版本: {latest}），準備顯示更新對話框", level=LogLevel.INFO)
                    self.updateDialogRequested.emit(version_info)
            return current_version
        except Exception as e:
            api_console(f"版本檢查失敗: {e}")
            return None

    @Slot(result='QVariant')
    def check_ytdlp_update_detail(self):
        """回傳是否需要更新的詳細資訊（對齊舊版資料結構）"""
        try:
            import urllib.request, json, time, os
            
            # 檢查快取檔案
            cache_file = safe_path_join(self.root_dir, 'main', 'ytdlp_version_cache.json')
            current_version = yt_dlp.version.__version__
            latest_version = None
            
            # 檢查快取是否有效（24小時內）
            cache_valid = False
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    cache_time = cache_data.get('timestamp', 0)
                    cache_version = cache_data.get('version', '')
                    
                    # 檢查快取是否在24小時內且版本不為空
                    if (time.time() - cache_time < 86400) and cache_version:
                        latest_version = cache_version
                        cache_valid = True
                except Exception as e:
                    api_console(f"讀取版本快取失敗: {e}")
            
            # 如果快取無效，從網路獲取
            if not cache_valid:
                try:
                    # 減少超時時間到5秒
                    with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        latest_version = data.get('info', {}).get('version') or ''
                    
                    # 儲存到快取
                    try:
                        cache_data = {
                            'version': latest_version,
                            'timestamp': time.time()
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        api_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    api_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest_version = cache_data.get('version', '')
                        except Exception:
                            pass
            
            if latest_version:
                if compare_versions(current_version, latest_version) < 0:
                    return {
                        'update_available': True,
                        'current_version': current_version,
                        'latest_version': latest_version
                    }
                return {
                    'update_available': False,
                    'current_version': current_version,
                    'latest_version': latest_version
                }
            return None
        except Exception as e:
            api_console(f"檢查版本細節失敗: {e}")
            return None

    @Slot()
    def startYtDlpUpdate(self):
        """由前端呼叫，啟動 yt-dlp 更新（背景執行並回報進度）——對齊舊版行為"""
        def run_update():
            with self._lock:
                self._ytdlp_update_in_progress = True
            try:
                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(0, '開始更新…');")
                # 選擇 python 執行檔：優先內嵌，否則使用目前執行環境
                python_exe = safe_path_join(self.root_dir, 'lib', 'python_embed', 'python.exe')
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                cmd = [python_exe, '-m', 'pip', 'install', '--upgrade', 'yt-dlp', '--disable-pip-version-check']
                api_console(f"執行更新命令: {' '.join(cmd)}")
                # 在 Windows 隱藏 console 啟動 pip 更新
                si = None
                flags = 0
                if sys.platform.startswith('win'):
                    try:
                        si = subprocess.STARTUPINFO()
                        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        si.wShowWindow = 0
                        flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                    except Exception:
                        si = None
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    startupinfo=si,
                    creationflags=flags,
                )
                try:
                    import time
                    progress = 3
                    last_emit = 0.0
                    output_lines = []
                    for line in proc.stdout:
                        ln = (line or '').strip()
                        if not ln:
                            continue
                        output_lines.append(ln)
                        api_console(f"pip 輸出: {ln}")
                        lower = ln.lower()
                        if 'collecting' in lower or 'downloading' in lower:
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(undefined, '正在下載套件…');")
                            progress = max(progress, 10)
                        elif 'installing collected packages' in lower:
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(undefined, '正在安裝…');")
                            progress = max(progress, 60)
                        elif 'successfully installed' in lower or 'already satisfied' in lower:
                            progress = max(progress, 95)
                        now = time.time()
                        if now - last_emit > 0.2:
                            progress = min(progress + 1, 97)
                            self._eval_js(f"window.__ofUpdateProgress && window.__ofUpdateProgress({progress}, undefined);")
                            last_emit = now
                    
                    # 等待進程完成
                    ret = proc.wait()
                    output_text = '\n'.join(output_lines)
                    api_console(f"pip 更新完成，返回碼: {ret}")
                    api_console(f"pip 輸出內容: {output_text[:500]}")  # 只記錄前500字符
                    
                    if ret == 0:
                        # 驗證更新是否成功：檢查當前版本
                        try:
                            # 重新加載 yt-dlp 模組以使用新版本
                            import importlib
                            
                            # 檢查 yt-dlp 的實際安裝路徑
                            python_embed_path = safe_path_join(self.root_dir, 'lib', 'python_embed')
                            if python_embed_path not in sys.path:
                                sys.path.insert(0, python_embed_path)
                            
                            # 清除模組緩存，強制重新加載
                            modules_to_remove = [k for k in sys.modules.keys() if k.startswith('yt_dlp')]
                            for mod_name in modules_to_remove:
                                del sys.modules[mod_name]
                            
                            # 重新導入 yt_dlp 模組
                            import yt_dlp
                            # 更新全局引用
                            globals()['yt_dlp'] = yt_dlp
                            
                            # 檢查模組實際路徑
                            yt_dlp_path = yt_dlp.__file__ if hasattr(yt_dlp, '__file__') else 'unknown'
                            debug_console(f"yt-dlp 模組路徑: {yt_dlp_path}")
                            
                            new_version = yt_dlp.version.__version__
                            api_console(f"更新後 yt-dlp 版本: {new_version}", level=LogLevel.INFO)
                            
                            # 檢查是否真的安裝了新版本
                            was_updated = 'successfully installed' in output_text.lower()
                            is_latest = 'already satisfied' in output_text.lower()
                            
                            if was_updated:
                                # 真的更新了
                                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已成功更新到最新版本！\\n\\n目前版本: {new_version}');")
                            elif is_latest:
                                # 已經是最新版本
                                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '檢查完成');")
                                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已經是最新版本！\\n\\n目前版本: {new_version}');")
                            else:
                                # 其他情況
                                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已更新！\\n\\n目前版本: {new_version}');")
                        except Exception as verify_err:
                            api_console(f"驗證更新版本失敗: {verify_err}", level=LogLevel.ERROR)
                            import traceback
                            api_console(traceback.format_exc(), level=LogLevel.ERROR)
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                            self._eval_js("window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 更新完成，請重新啟動應用程式以確保新版本生效。');")
                    else:
                        api_console(f"pip 更新失敗，返回碼: {ret}", level=LogLevel.ERROR)
                        api_console(f"pip 錯誤輸出: {output_text[-500:]}", level=LogLevel.ERROR)  # 只記錄最後500字符
                        self._eval_js("window.__ofUpdateDone && window.__ofUpdateDone(false, 'yt-dlp 更新失敗，請稍後再試或手動更新。');")
                finally:
                    # 確保進程資源被釋放
                    if proc.stdout:
                        proc.stdout.close()
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait()
            except Exception as e:
                api_console(f"更新執行失敗: {e}", level=LogLevel.ERROR)
                safe_msg = str(e).replace('\\', '/')
                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(false, '更新過程發生錯誤：{safe_msg}');")
            finally:
                with self._lock:
                    self._ytdlp_update_in_progress = False
        threading.Thread(target=run_update, daemon=True).start()

    def is_ytdlp_update_in_progress(self):
        """回傳 yt-dlp 是否正在更新中"""
        with self._lock:
            return self._ytdlp_update_in_progress

    def show_update_dialog(self, version_info):
        """顯示更新對話框（完全對齊舊版樣式與互動）"""
        try:
            # 確保在頁面加載完成後執行
            # 注入舊版的進度對話與完成對話
            update_js = """
            if (typeof window.__executeUpdate === 'undefined') {
            window.__executeUpdate = function() {
                const progressOverlay = document.createElement('div');
                progressOverlay.id = 'update-progress-overlay';
                progressOverlay.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); z-index: 10001; display: flex; align-items: center; justify-content: center; font-family: 'Segoe UI', Arial, sans-serif;`;
                const progressDialog = document.createElement('div');
                progressDialog.style.cssText = `background: #23262f; border-radius: 16px; padding: 32px; max-width: 380px; width: 90%; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3); border: 1px solid #444; text-align: center;`;
                const spinner = document.createElement('div');
                spinner.style.cssText = `width:56px;height:56px;background:#2ecc71;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px auto;animation:spin 1s linear infinite;box-shadow:0 0 6px #27ae60;`;
                spinner.innerHTML = '<img src="assets/update.png" alt="updating" style="width:28px;height:28px;object-fit:contain;filter:brightness(10);">';
                const titleEl = document.createElement('h3');
                titleEl.style.cssText = 'margin:0 0 10px 0;color:#e5e7eb;font-size:20px;font-weight:bold;';
                titleEl.textContent = '正在更新 yt-dlp';
                const tipEl = document.createElement('p');
                tipEl.style.cssText = 'color:#aaa;margin:0 0 12px 0;font-size:14px;';
                tipEl.id = 'of-update-tip';
                tipEl.textContent = '正在準備…';
                const barWrap = document.createElement('div');
                barWrap.style.cssText = 'height:8px;background:#181a20;border:1px solid #444;border-radius:6px;overflow:hidden;';
                const bar = document.createElement('div');
                bar.id = 'of-update-bar';
                bar.style.cssText = 'height:100%;width:0%;background:#27ae60;transition:width .2s ease;';
                barWrap.appendChild(bar);
                progressDialog.appendChild(spinner);
                progressDialog.appendChild(titleEl);
                progressDialog.appendChild(tipEl);
                progressDialog.appendChild(barWrap);
                progressOverlay.appendChild(progressDialog);
                document.body.appendChild(progressOverlay);
                window.__ofUpdateProgress = function(percent, tipText){
                    try { if (typeof percent === 'number') { const el = document.getElementById('of-update-bar'); if (el) el.style.width = Math.max(0, Math.min(100, percent)) + '%'; } if (typeof tipText === 'string') { const t = document.getElementById('of-update-tip'); if (t) t.textContent = tipText; } } catch(_){ }
                };
                window.__ofUpdateDone = function(success, message){
                    try { document.getElementById('update-progress-overlay')?.remove(); } catch(_){ }
                    const overlay = document.createElement('div');
                    overlay.id = 'update-success-overlay';
                    overlay.style.cssText = `position:fixed; inset:0; background:rgba(0,0,0,.7); z-index:10002; display:flex; align-items:center; justify-content:center; font-family:'Segoe UI',Arial,sans-serif;`;
                    const dialog = document.createElement('div');
                    dialog.style.cssText = `background:#23262f; border-radius:16px; padding:32px; max-width:420px; width:90%; box-shadow:0 4px 24px rgba(0,0,0,.3); border:1px solid #444; text-align:center;`;
                    const badge = document.createElement('div');
                    badge.style.cssText = `width:68px; height:68px; border-radius:50%; margin:0 auto 16px auto; display:flex; align-items:center; justify-content:center; box-shadow:0 0 8px ${success?"#27ae60":"#c0392b"}; background:${success?"#2ecc71":"#e74c3c"}; color:#fff; font-size:28px;`;
                    const img = document.createElement('img');
                    img.alt = success ? 'updated' : 'failed';
                    img.src = success ? 'assets/updated.png' : 'assets/update.png';
                    img.style.cssText = 'width:36px;height:36px;object-fit:contain;filter:brightness(10);';
                    badge.appendChild(img);
                    const title = document.createElement('h3');
                    title.style.cssText = 'margin:0 0 10px 0; color:#e5e7eb; font-size:20px; font-weight:bold;';
                    title.textContent = success ? '更新完成' : '更新失敗';
                    const text = document.createElement('p');
                    text.style.cssText = 'color:#aaa; margin:0 0 16px 0; font-size:14px;';
                    text.textContent = message || (success ? 'yt-dlp 已更新至最新版本。' : '請稍後再試或手動更新。');
                    const hint = document.createElement('p');
                    hint.style.cssText = 'color:#888; margin:0 0 20px 0; font-size:12px; font-style:italic;';
                    hint.textContent = success ? '更新已完成，為確保生效，建議重新啟動應用程式。' : '';
                    const btnRow = document.createElement('div');
                    btnRow.style.cssText = 'display:flex; justify-content:flex-end; gap:12px;';
                    const laterBtn = document.createElement('button');
                    laterBtn.textContent = success ? '稍後' : '關閉';
                    laterBtn.style.cssText = 'background:#23262f; color:#e5e7eb; border:1px solid #444; padding:10px 20px; border-radius:8px; cursor:pointer; font-size:14px;';
                    laterBtn.onclick = ()=> overlay.remove();
                    btnRow.appendChild(laterBtn);
                    if (success) { const restartBtn = document.createElement('button'); restartBtn.textContent = '立即重啟'; restartBtn.style.cssText = 'background:#27ae60; color:#fff; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-size:14px; font-weight:bold;'; restartBtn.onclick = ()=> { try { window.api.restartApp(); } catch(_){} }; btnRow.appendChild(restartBtn); }
                    dialog.appendChild(badge); dialog.appendChild(title); dialog.appendChild(text); if (success) dialog.appendChild(hint); dialog.appendChild(btnRow);
                    overlay.appendChild(dialog); document.body.appendChild(overlay);
                };
                try { window.api.startYtDlpUpdate(); } catch (e) { console.error(e); }
            };
            }
            """
            self._eval_js(update_js)

            # 再注入舊版對話框，帶入具體版本號
            current_version = version_info.get('current_version', '')
            latest_version = version_info.get('latest_version', '')
            # 使用 setTimeout 確保在頁面加載完成後執行
            dialog_html = """
            setTimeout(function() {
            (function() {
                const overlay = document.createElement('div');
                overlay.id = 'update-dialog-overlay';
                overlay.style.cssText = `position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0, 0, 0, 0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; font-family: 'Segoe UI', Arial, sans-serif;`;
                const dialog = document.createElement('div');
                dialog.id = 'update-dialog';
                dialog.style.cssText = `background: #23262f; border-radius: 16px; padding: 32px; max-width: 420px; width: 90%; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3); border: 1px solid #444;`;
                const titleDiv = document.createElement('div');
                titleDiv.style.cssText = `display: flex; align-items: center; margin-bottom: 16px;`;
                const iconDiv = document.createElement('div');
                iconDiv.style.cssText = `width: 48px; height: 48px; background: #2ecc71; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 16px; box-shadow: 0 0 6px #27ae60;`;
                iconDiv.innerHTML = '<img src="assets/update.png" alt="update" style="width:24px;height:24px;object-fit:contain;filter:brightness(1);">';
                const title = document.createElement('h3');
                title.style.cssText = `margin: 0; color: #e5e7eb; font-size: 20px; font-weight: bold;`;
                title.textContent = '發現 yt-dlp 新版本';
                titleDiv.appendChild(iconDiv); titleDiv.appendChild(title);
                const versionDiv = document.createElement('div');
                versionDiv.style.cssText = `background: #181a20; border-radius: 12px; padding: 18px; margin-bottom: 24px; border: 1px solid #444;`;
                const currentVersionDiv = document.createElement('div');
                currentVersionDiv.style.cssText = 'margin-bottom: 12px;';
                currentVersionDiv.innerHTML = `<span style=\"color: #aaa; font-size: 15px;\">目前版本:</span> <span style=\"color: #e5e7eb; font-weight: 500; margin-left: 12px;\">__CURR__</span>`;
                const latestVersionDiv = document.createElement('div');
                latestVersionDiv.innerHTML = `<span style=\"color: #aaa; font-size: 15px;\">最新版本:</span> <span style=\"color: #2ecc71; font-weight: 500; margin-left: 12px;\">__LATEST__</span>`;
                versionDiv.appendChild(currentVersionDiv); versionDiv.appendChild(latestVersionDiv);
                const question = document.createElement('p');
                question.style.cssText = `color: #e5e7eb; margin: 16px 0 8px 0; font-size: 15px; font-weight: 600;`;
                question.textContent = '是否要更新到最新版本？';
                const actionsRow = document.createElement('div');
                actionsRow.style.cssText = `display: flex; align-items: center; justify-content: flex-start; gap: 16px; margin: 0 0 8px 0;`;
                const note = document.createElement('p');
                note.style.cssText = `color: #888; margin: 0; font-size: 12px; line-height: 1.4; font-style: italic; flex: 1;`;
                note.textContent = '※yt-dlp為下載器的重要核心元件，建議更新以避免錯誤及獲得更好的使用體驗';
                const buttonDiv = document.createElement('div');
                buttonDiv.style.cssText = `display: flex; gap: 16px; justify-content: flex-end; margin: 0 0 24px 0;`;
                const skipBtn = document.createElement('button');
                skipBtn.id = 'skip-update-btn';
                skipBtn.style.cssText = `background: #23262f; color: #e5e7eb; border: 1px solid #444; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: 500; transition: all 0.2s ease;`;
                skipBtn.textContent = '稍後提醒';
                skipBtn.onmouseover = function(){ this.style.background = '#2b2e37'; this.style.borderColor = '#2ecc71'; };
                skipBtn.onmouseout = function(){ this.style.background = '#23262f'; this.style.borderColor = '#444'; };
                const updateBtn = document.createElement('button');
                updateBtn.id = 'update-now-btn';
                updateBtn.style.cssText = `background: #27ae60; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: bold; transition: all 0.2s ease; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);`;
                updateBtn.textContent = '立即更新';
                updateBtn.onmouseover = function(){ this.style.background = '#219150'; this.style.transform = 'scale(1.03)'; this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)'; };
                updateBtn.onmouseout = function(){ this.style.background = '#27ae60'; this.style.transform = 'scale(1)'; this.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)'; };
                buttonDiv.appendChild(skipBtn); buttonDiv.appendChild(updateBtn);
                actionsRow.appendChild(note);
                dialog.appendChild(titleDiv); dialog.appendChild(versionDiv); dialog.appendChild(question); dialog.appendChild(actionsRow); dialog.appendChild(buttonDiv);
                overlay.appendChild(dialog); document.body.appendChild(overlay);
                updateBtn.addEventListener('click', function(){ overlay.remove(); window.__executeUpdate(); });
                skipBtn.addEventListener('click', function(){ overlay.remove(); });
                overlay.addEventListener('click', function(e){ if (e.target === this) { this.remove(); if (window.__onUpdateDialogResult) { window.__onUpdateDialogResult('skip'); } } });
            })();
            }, 100);
            """
            dialog_html = dialog_html.replace("__CURR__", str(current_version).replace('\\', '/')).replace("__LATEST__", str(latest_version).replace('\\', '/'))
            # 使用 runJavaScript 直接執行，確保立即顯示
            try:
                self.page.runJavaScript(dialog_html)
            except Exception as js_err:
                api_console(f"直接執行 JavaScript 失敗，使用信號: {js_err}")
                self._eval_js(dialog_html)
            return "update"
        except Exception as e:
            api_console(f"注入更新對話框失敗: {e}")
