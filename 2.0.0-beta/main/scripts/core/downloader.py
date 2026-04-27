#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下載功能模組
"""

import os
import sys
import threading
import queue
import yt_dlp

# 添加父目錄到路徑，以便導入其他模組
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # main/scripts
root_dir = os.path.dirname(parent_dir)  # main
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from scripts.utils.logger import download_console, LogLevel
from scripts.utils.file_utils import safe_path_join, resolve_relative_path, get_deno_path

class Downloader:
    """下載器類別"""
    
    def __init__(self, root_dir, progress_callback=None, complete_callback=None):
        self.root_dir = root_dir
        self.downloads_dir = safe_path_join(root_dir, 'downloads')
        self.progress_callback = progress_callback
        self.complete_callback = complete_callback
        self.active_downloads = {}
        self._lock = threading.Lock()
    
    def start_download(self, task_id, url, quality, format_type, downloads_dir=None, add_resolution_to_filename=False, original_format=None):
        """開始下載"""
        def download_task():
            try:
                final_path = self.download_once(
                    task_id,
                    url,
                    quality,
                    format_type,
                    downloads_dir=downloads_dir,
                    add_resolution_to_filename=add_resolution_to_filename,
                    original_format=original_format,
                )
                if self.complete_callback:
                    self.complete_callback(task_id, url, file_path=final_path)
                    
            except Exception as e:
                download_console(f"【任務{task_id}】下載失敗: {e}", level=LogLevel.ERROR)
                if self.complete_callback:
                    self.complete_callback(task_id, url, error=str(e))
        
        # 在單獨的執行緒中執行下載
        thread = threading.Thread(target=download_task, daemon=True)
        thread.start()
        
        # 使用鎖保護執行緒字典的更新
        with self._lock:
            self.active_downloads[task_id] = thread

    def download_once(self, task_id, url, quality, format_type, downloads_dir=None, add_resolution_to_filename=False, original_format=None):
        """同步執行一次下載（不自行開 thread；供排程器控制併發/重試）。\n\n        成功回傳最終檔案路徑（可能為 None）。失敗則 raise Exception。\n        """
        download_console(f"【任務{task_id}】開始下載: {url}", level=LogLevel.INFO)

        # 先驗證可用的格式（可選，用於調試）
        try:
            import yt_dlp
            download_console(f"驗證可用格式: 目標畫質={quality}, 目標格式={original_format}")
            # 獲取格式列表以便驗證
            test_opts = {
                'quiet': True,
                'simulate': True,
                'skip_download': True,
            }
            deno_path = get_deno_path(self.root_dir)
            if deno_path and os.path.exists(deno_path):
                test_opts['js_runtimes'] = {'deno': {'path': deno_path}}
            
            with yt_dlp.YoutubeDL(test_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get('formats', [])
                download_console(f"可用格式數量: {len(formats)}")
                
                # 提取畫質數字用於驗證
                try:
                    import re
                    qnum = int(re.search(r'(\d+)', str(quality)).group(1)) if re.search(r'(\d+)', str(quality)) else int(quality)
                except (ValueError, AttributeError):
                    qnum = 1080
                
                # 檢查是否有符合條件的格式
                matching_formats = []
                for fmt in formats:
                    fmt_height = fmt.get('height')
                    fmt_ext = fmt.get('ext', '').lower()
                    vcodec = fmt.get('vcodec', 'none')
                    
                    if vcodec == 'none' or fmt_ext == 'mhtml':
                        continue
                    
                    if fmt_height and min(360, qnum - 50) <= fmt_height <= qnum + 100:
                        if not original_format or fmt_ext == original_format.strip().lower():
                            matching_formats.append({
                                'height': fmt_height,
                                'ext': fmt_ext,
                                'format_id': fmt.get('format_id', 'N/A')
                            })
                
                if matching_formats:
                    download_console(f"找到 {len(matching_formats)} 個符合條件的格式")
                    for mf in matching_formats[:5]:  # 只顯示前5個
                        download_console(f"  符合格式: {mf['format_id']} - {mf['height']}p, {mf['ext']}")
                else:
                    download_console(f"警告：未找到完全符合條件的格式，將使用最接近的格式", level=LogLevel.WARNING)
        except Exception as e:
            download_console(f"格式驗證失敗（將繼續下載）: {e}")

        # 設定下載選項
        ydl_opts = self._build_download_options(quality, format_type, downloads_dir, add_resolution_to_filename, original_format)

        # 設定進度回調（注入 task_id，便於前端對應）
        last_filename = {'path': ''}
        def hook(d):
            try:
                d['task_id'] = task_id
                fn = d.get('filename')
                if fn:
                    last_filename['path'] = fn
            except Exception:
                pass
            self._progress_hook(d, task_id)
        ydl_opts['progress_hooks'] = [hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        download_console(f"【任務{task_id}】下載完成", level=LogLevel.INFO)
        final_path = last_filename['path'] if last_filename.get('path') else None
        return final_path
    
    def _build_download_options(self, quality, format_type, downloads_dir=None, add_resolution_to_filename=False, original_format=None):
        """建構下載選項"""
        # 設定 FFMPEG 路徑（使用相對路徑）
        ffmpeg_path = safe_path_join(self.root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
        # 檢查 ffmpeg 是否存在，如果不存在則設為 None（讓 yt-dlp 使用系統 PATH 中的 ffmpeg）
        if not os.path.exists(ffmpeg_path):
            download_console(f"ffmpeg 路徑不存在: {ffmpeg_path}，將嘗試使用系統 PATH 中的 ffmpeg", level=LogLevel.WARNING)
            ffmpeg_path = None
        
        # 解析下載目錄
        target_dir = downloads_dir or self.downloads_dir
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            download_console(f"建立下載目錄失敗: {e}", level=LogLevel.WARNING)
            # 回退到預設 downloads 目錄
            target_dir = self.downloads_dir
        
        # 正規化輸入
        fmt_type = (format_type or '').strip()
        qval = (quality or '').strip()
        download_console(f"接收到的畫質參數: quality='{quality}', format_type='{format_type}'")
        
        # 若畫質帶有 'p'，僅取數字
        try:
            import re
            m = re.search(r"(\d+)", qval)
            qnum = m.group(1) if m else qval
            download_console(f"提取的畫質數字: {qnum}")
        except Exception:
            qnum = qval or '1080'
            download_console(f"畫質提取失敗，使用預設值: {qnum}")

        # 根據設定決定檔名模板
        # 注意：不可在 outtmpl 中手動加入副檔名（如 .mp3/.mp4），否則 FFmpegExtractAudio 或 merge
        # 會再附加一次副檔名，導致檔名變成 [影片名].[mp3/mp4].[mp3/mp4]。應由 postprocessor 自動附加。
        if add_resolution_to_filename:
            if fmt_type == "音訊":
                # 音訊格式：標題_320kbps（副檔名由 FFmpegExtractAudio 自動附加）
                outtmpl = os.path.join(target_dir, f'%(title)s_{qnum}kbps')
            else:
                # 影片格式：標題_1080p（副檔名由 merge 自動附加）
                outtmpl = os.path.join(target_dir, f'%(title)s_%(height)sp')
        else:
            # 標題（副檔名由 postprocessor 自動附加）
            outtmpl = os.path.join(target_dir, '%(title)s')

        ydl_opts = {
            'outtmpl': outtmpl,
            'format': self._get_format_selector(qnum, fmt_type, original_format),
            'quiet': True,
        }
        
        # 設定 ffmpeg 路徑（如果存在）
        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path
            download_console(f"已配置 ffmpeg 路徑: {ffmpeg_path}")
        else:
            download_console("ffmpeg 未找到，無法進行格式轉換", level=LogLevel.WARNING)
        
        # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
        deno_path = get_deno_path(self.root_dir)
        if deno_path:
            # yt-dlp 使用 js_runtimes 參數，格式為 {runtime: {config}}
            ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
            download_console(f"已配置 Deno 路徑: {deno_path}")
        else:
            download_console("未找到 Deno，YouTube 下載可能受限", level=LogLevel.WARNING)
        
        # 根據格式類型設定額外選項
        if fmt_type == "音訊":
            # 使用用戶選擇的音訊格式作為 codec（如 mp3, aac, flac, wav）
            audio_codec = original_format.strip().lower() if original_format else 'mp3'
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': audio_codec,
                    # 音訊位元率使用純數字，如 '320'
                    'preferredquality': str(qnum or '320'),
                }],
            })
        else:
            # 影片格式：如果用戶指定了格式（如 mp4），確保輸出格式正確
            if original_format:
                target_format = original_format.strip().lower()
                download_console(f"用戶選擇的格式: {target_format}")
                
                # 如果用戶選擇了 mp4，設置 merge_output_format 確保合併後的格式是 mp4
                if target_format == 'mp4' and ffmpeg_path and os.path.exists(ffmpeg_path):
                    ydl_opts['merge_output_format'] = 'mp4'
                    download_console(f"已設置 merge_output_format=mp4，確保合併後的輸出為 mp4")
                    
                    # 同時添加 FFmpegVideoConvertor 作為備選，確保最終輸出為 mp4
                    postprocessors = ydl_opts.get('postprocessors', [])
                    has_video_converter = any(
                        pp.get('key') == 'FFmpegVideoConvertor' 
                        for pp in postprocessors
                    )
                    if not has_video_converter:
                        postprocessors.append({
                            'key': 'FFmpegVideoConvertor',
                            'preferedformat': 'mp4',  # 注意：yt-dlp 使用的是 'preferedformat'（拼寫錯誤但這是官方 API）
                        })
                        ydl_opts['postprocessors'] = postprocessors
                        download_console(f"已添加 FFmpegVideoConvertor postprocessor，確保最終輸出為 mp4")
                elif target_format in ['webm', 'mkv', 'flv', 'avi']:
                    # 對於其他格式，也設置 merge_output_format
                    if ffmpeg_path and os.path.exists(ffmpeg_path):
                        ydl_opts['merge_output_format'] = target_format
                        download_console(f"已設置 merge_output_format={target_format}")
        
        return ydl_opts
    
    def _get_format_selector(self, quality, format_type, original_format=None):
        """獲取格式選擇器 - 使用更嚴格的篩選機制確保畫質匹配"""
        # 影片：依高度限制，音訊：無高度限制
        if format_type == "音訊":
            return "bestaudio/best"
        
        # 將畫質字符串轉換為數字
        try:
            import re
            qnum = int(re.search(r'(\d+)', str(quality)).group(1)) if re.search(r'(\d+)', str(quality)) else int(quality)
        except (ValueError, AttributeError):
            qnum = 1080  # 預設值
        
        # 獲取用戶選擇的格式（如 mp4, webm, mkv 等）
        target_ext = None
        if original_format:
            target_ext = original_format.strip().lower()
            download_console(f"用戶選擇的格式: {target_ext}")
        
        # 定義畫質容差範圍（允許的偏差）
        # 策略：優先選擇不超過目標的畫質，如果沒有才選擇略高的畫質
        # 對於常見畫質，定義允許的範圍
        quality_ranges = {
            360: (360, 480),   # 360p: 允許 360-480p（上限）
            480: (480, 720),   # 480p: 允許 480-720p（上限）
            720: (720, 1080),  # 720p: 允許 720-1080p（上限）
            1080: (1080, 1440), # 1080p: 允許 1080-1440p（上限）
            1440: (1440, 2160), # 1440p: 允許 1440-2160p（上限）
            2160: (2160, 4320), # 2160p: 允許 2160-4320p（上限）
            4320: (4320, 9999), # 4320p: 允許 4320p 及以上
        }
        
        # 找到最接近的畫質級別並設定範圍
        min_height = max(360, qnum - 20)  # 允許 -20p 偏差（更嚴格）
        max_height = qnum + 50  # 允許 +50p 偏差（更嚴格，避免選擇過高畫質）
        
        # 根據目標畫質調整範圍
        for base_quality, (min_q, max_q) in sorted(quality_ranges.items()):
            if qnum <= base_quality:
                # 使用該級別的下限作為最小高度
                min_height = min_q
                # 最大高度不超過該級別的上限，且不超過目標+50p
                max_height = min(max_q, qnum + 50)
                break
        else:
            # 如果目標畫質超過 4320p，使用更寬鬆的範圍
            min_height = max(360, qnum - 50)
            max_height = qnum + 100
        
        download_console(f"畫質範圍: {min_height}p - {max_height}p (目標: {qnum}p)")
        
        # 構建格式選擇器，使用更嚴格的優先級
        # 注意：yt-dlp 不支持 height={qnum} 精確匹配，使用 height<= 和 height>= 組合
        if target_ext and target_ext in ['mp4', 'webm', 'mkv', 'flv', 'avi']:
            # 優先選擇指定格式，嚴格限制畫質範圍
            # 使用 height<=qnum 和 height>=qnum 組合來近似精確匹配
            format_selector = (
                # 第一優先級：在允許範圍內的最佳格式（不超過目標，最接近目標）
                f"bestvideo[ext={target_ext}][height>={min_height}][height<={qnum}]+bestaudio[ext=m4a]/"
                f"bestvideo[ext={target_ext}][height>={min_height}][height<={qnum}]+bestaudio/"
                f"best[ext={target_ext}][height>={min_height}][height<={qnum}]/"
                # 第二優先級：在允許範圍內但略高於目標（僅當沒有符合的較低畫質時，且不超過最大限制）
                f"bestvideo[ext={target_ext}][height>{qnum}][height<={max_height}]+bestaudio[ext=m4a]/"
                f"bestvideo[ext={target_ext}][height>{qnum}][height<={max_height}]+bestaudio/"
                f"best[ext={target_ext}][height>{qnum}][height<={max_height}]/"
                # 第三優先級：不限制格式，但嚴格限制畫質範圍（不超過目標）
                f"bestvideo[height>={min_height}][height<={qnum}]+bestaudio/"
                f"best[height>={min_height}][height<={qnum}]/"
                # 第四優先級：不限制格式，但略高於目標（且不超過最大限制）
                f"bestvideo[height>{qnum}][height<={max_height}]+bestaudio/"
                f"best[height>{qnum}][height<={max_height}]/"
                # 最後回退：不限制格式和畫質（僅當沒有符合條件的格式時）
                f"bestvideo[ext={target_ext}]+bestaudio/"
                f"best[ext={target_ext}]/"
                f"bestvideo+bestaudio/best"
            )
        else:
            # 如果沒有指定格式，使用通用選擇器，但嚴格限制畫質範圍
            format_selector = (
                # 第一優先級：在允許範圍內的最佳格式（不超過目標）
                f"bestvideo[height>={min_height}][height<={qnum}]+bestaudio/"
                f"best[height>={min_height}][height<={qnum}]/"
                # 第二優先級：在允許範圍內但略高於目標（僅當沒有符合的較低畫質時，且不超過最大限制）
                f"bestvideo[height>{qnum}][height<={max_height}]+bestaudio/"
                f"best[height>{qnum}][height<={max_height}]/"
                # 最後回退：不限制畫質（僅當沒有符合條件的格式時）
                f"bestvideo+bestaudio/best"
            )
        
        download_console(f"畫質選擇器: {format_selector[:200]}... (目標畫質: {qnum}p, 範圍: {min_height}p-{max_height}p, 目標格式: {target_ext or '未指定'})")
        return format_selector
    
    def _progress_hook(self, d, task_id):
        """進度回調"""
        if d['status'] == 'downloading':
            if self.progress_callback:
                self.progress_callback(task_id, d)
        elif d['status'] == 'finished':
            download_console(f"【任務{task_id}】檔案處理完成: {d['filename']}")
    
    def cancel_download(self, task_id):
        """取消下載"""
        with self._lock:
            if task_id in self.active_downloads:
                # 注意：yt-dlp 沒有直接的取消方法，這裡只是移除追蹤
                del self.active_downloads[task_id]
                download_console(f"【任務{task_id}】下載已取消")
    
    def get_download_status(self, task_id):
        """獲取下載狀態"""
        with self._lock:
            return task_id in self.active_downloads


class DownloadScheduler:
    """全域下載排程器：控制同時下載數、集中重試。\n\n    - 使用固定 worker 數量確保同時下載上限。\n+    - 每個任務最多重試 retry_count 次（總嘗試次數 = retry_count）。\n    """

    def __init__(self, downloader: Downloader, max_concurrent: int = 3, retry_count: int = 3, status_callback=None):
        self.downloader = downloader
        self.max_concurrent = max(1, int(max_concurrent or 1))
        self.retry_count = max(1, int(retry_count or 1))
        self.status_callback = status_callback  # fn(task_id, status_text)

        self._q = queue.Queue()
        self._stop = threading.Event()
        self._workers = []

        for i in range(self.max_concurrent):
            t = threading.Thread(target=self._worker_loop, args=(i,), daemon=True)
            t.start()
            self._workers.append(t)

    def submit(self, task_id, url, quality, format_type, downloads_dir=None, add_resolution_to_filename=False, original_format=None):
        self._q.put({
            'task_id': int(task_id),
            'url': url,
            'quality': quality,
            'format_type': format_type,
            'downloads_dir': downloads_dir,
            'add_resolution_to_filename': add_resolution_to_filename,
            'original_format': original_format,
        })

    def _emit_status(self, task_id, text):
        try:
            if callable(self.status_callback):
                self.status_callback(int(task_id), str(text))
        except Exception:
            pass

    def _worker_loop(self, worker_id):
        while not self._stop.is_set():
            job = None
            try:
                job = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            if job is None:
                continue

            task_id = job.get('task_id')
            url = job.get('url')
            quality = job.get('quality')
            format_type = job.get('format_type')
            downloads_dir = job.get('downloads_dir')
            add_resolution = job.get('add_resolution_to_filename', False)
            original_format = job.get('original_format')

            last_err = None
            for attempt in range(1, self.retry_count + 1):
                try:
                    if attempt > 1:
                        self._emit_status(task_id, f"下載失敗，重試中({attempt}/{self.retry_count})")
                    final_path = self.downloader.download_once(
                        task_id,
                        url,
                        quality,
                        format_type,
                        downloads_dir=downloads_dir,
                        add_resolution_to_filename=add_resolution,
                        original_format=original_format,
                    )
                    if self.downloader.complete_callback:
                        self.downloader.complete_callback(task_id, url, file_path=final_path)
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    download_console(f"【任務{task_id}】worker{worker_id} 下載失敗({attempt}/{self.retry_count}): {e}", level=LogLevel.ERROR)

            if last_err is not None:
                # 最終失敗才回報 error（由 Api 決定是否彈窗）
                if self.downloader.complete_callback:
                    try:
                        self.downloader.complete_callback(task_id, url, error=str(last_err))
                    except Exception:
                        pass

            try:
                self._q.task_done()
            except Exception:
                pass
