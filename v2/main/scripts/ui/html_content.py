#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML 內容模組 - 完整版本
"""

import os
import sys

# 添加父目錄到路徑，以便導入其他模組
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # main/scripts
root_dir = os.path.dirname(parent_dir)  # main
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

def get_html_content():
    """獲取完整的 HTML 內容"""
    import os
    from scripts.utils.file_utils import safe_path_join
    
    # 優先載入 main.html 檔案（使用相對路徑）
    html_file = safe_path_join(os.path.dirname(__file__), '..', '..', 'main.html')
    if os.path.exists(html_file):
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    from scripts.utils.logger import info_console
                    info_console(f"成功載入 main.html，長度: {len(content)}")
                    return content
                else:
                    from scripts.utils.logger import warning_console
                    warning_console("main.html 檔案為空，使用預設內容")
        except UnicodeDecodeError as e:
            from scripts.utils.logger import error_console
            error_console(f"main.html 編碼錯誤: {e}")
        except PermissionError as e:
            from scripts.utils.logger import error_console
            error_console(f"main.html 權限不足: {e}")
        except Exception as e:
            from scripts.utils.logger import error_console
            error_console(f"讀取 main.html 失敗: {e}")
    else:
        from scripts.utils.logger import warning_console
        warning_console(f"main.html 檔案不存在: {html_file}")
    
    # 如果檔案不存在或讀取失敗，返回簡化版本
    from scripts.utils.logger import info_console
    info_console("使用內建HTML內容")
    return '''<!DOCTYPE html>
<html lang="zh-tw">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>oldfish影片下載器</title>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        // 初始化 Qt WebChannel 並建立與後端的橋接，提供 window.pywebview.api 相容層
        (function(){
            function initChannel(){
                if (typeof QWebChannel === 'undefined' || !window.qt || !qt.webChannelTransport){
                    // 若尚未就緒，稍後重試
                    return setTimeout(initChannel, 50);
                }
                new QWebChannel(qt.webChannelTransport, function(channel){
                    window.api = channel.objects.api;
                    window.pywebview = { api: window.api };
                });
            }
            initChannel();
        })();
    </script>
    <style>
        :root {
            --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
            --ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);
            --ease-smooth: cubic-bezier(0.25, 0.46, 0.45, 0.94);
            --ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275);
            transition: all 0.25s var(--ease-default);
        }
        
        /* 基本動畫關鍵幀 */
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        body {
            margin: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #181a20;
            color: #e5e7eb;
            transition: background 0.3s ease, color 0.3s ease;
        }
        /* 全域卷軸樣式（Chromium/QtWebEngine） */
        html, body, .main, .queue-list {
            scrollbar-width: thin; /* Firefox 後備 */
            scrollbar-color: #4a4f59 #121418; /* 拇指/軌道：現代灰 */
        }
        ::-webkit-scrollbar {
            width: 8px;  /* 更纖細 */
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #121418; /* 深色軌道 */
        }
        ::-webkit-scrollbar-thumb {
            background: #3a3f4a; /* 中性深灰 */
            border-radius: 6px;
            border: 2px solid #121418; /* 與軌道留縫，視覺更輕 */
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #4a4f59; /* 略亮的灰色，避免過亮 */
            border-color: #121418;
        }
        ::-webkit-scrollbar-corner {
            background: #121418;
        }
        .container {
            display: flex;
            height: 100vh;
        }
        .sidebar {
            width: 160px;
            background: #23262f;
            box-shadow: 2px 0 8px #111;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            padding-top: 20px;
            transition: width 0.3s var(--ease-smooth);
            overflow: hidden;
        }
        .sidebar.collapsed {
            width: 60px;
        }
        .sidebar .menu-btn {
            margin-bottom: 30px;
            cursor: pointer;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: 6px;
            transition: transform 0.3s ease;
        }
        .sidebar.collapsed .menu-btn img {
            transform: rotate(180deg);
        }
        .sidebar .nav-item {
            width: 100%;
            height: 48px;
            margin-bottom: 6px; /* 標籤間距縮短 */
            display: flex;
            align-items: center;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s var(--ease-smooth);
            padding-left: 12px;
            position: relative;
            overflow: hidden;
        }
        
        .sidebar .nav-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
            transition: left 0.5s;
        }
        
        .sidebar .nav-item:hover::before {
            left: 100%;
        }
        
        .sidebar .nav-item:hover {
            transform: translateX(4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .sidebar .nav-item.selected {
            background: #2ecc71;
            box-shadow: 0 0 6px #27ae60;
        }
        .sidebar .nav-item img {
            width: 28px;
            height: 28px;
            filter: brightness(0.85);
        }
        .sidebar .nav-text {
            margin-left: 16px;
            font-size: 17px;
            font-weight: 500;
            transition: opacity 0.2s ease-in-out 0.05s;
            opacity: 1;
            color: #e5e7eb;
            white-space: nowrap;
        }
        .sidebar.collapsed .nav-text {
            opacity: 0;
            transition: opacity 0.1s ease-in-out
        }
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            position: relative;
            overflow-y: auto; /* 讓主內容可滾動，配合 sticky 底部區 */
        }
        .title-img {
            margin-top: 60px;
            margin-bottom: 30px;
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 540px;
            filter: drop-shadow(0 0 8px #222);
        }
        .search-row {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 40px;
        }
        .search-input {
            width: 340px;
            height: 38px;
            border-radius: 8px;
            border: 1px solid #444;
            background: #23262f;
            color: #e5e7eb;
            padding: 0 14px;
            font-size: 16px;
            outline: none;
            transition: all 0.3s var(--ease-smooth);
            position: relative;
        }
        
        .search-input::placeholder {
            transition: opacity 0.3s ease;
        }
        
        .search-input:focus::placeholder {
            opacity: 0.5;
        }
        
        .search-input:focus {
            border-color: #2ecc71;
            box-shadow: 0 0 0 2px rgba(46, 204, 113, 0.2);
            transform: translateY(-1px);
        }
        
        .search-btn {
            width: 100px;
            height: 40px;
            border-radius: 8px;
            border: none;
            background: #2ecc71;
            color: white;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            margin-left: 12px;
            transition: all 0.3s var(--ease-smooth);
            position: relative;
            overflow: hidden;
        }
        
        .search-btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .search-btn:hover::before {
            left: 100%;
        }
        
        .search-btn:hover {
            background: #27ae60;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(46, 204, 113, 0.3);
        }
        
        .search-btn:active {
            transform: translateY(0);
        }
        
        .search-btn:disabled {
            background: #666;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .search-btn:disabled::before {
            display: none;
        }
        
        .video-info {
            background: #23262f;
            border-radius: 16px;
            padding: 30px;
            margin: 0 20px 30px 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            border: 1px solid #333;
            max-width: 800px;
            width: 100%;
            display: none;
            animation: slideIn 0.5s var(--ease-spring);
        }
        
        .video-info.show {
            display: block;
        }
        
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .video-thumbnail {
            width: 100%;
            max-width: 400px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        }
        
        .video-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 12px;
            color: #e5e7eb;
            line-height: 1.3;
        }
        
        .video-meta {
            color: #aaa;
            margin-bottom: 20px;
            font-size: 16px;
        }
        
        .quality-select, .format-select {
            margin-bottom: 20px;
        }
        
        .select-label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #e5e7eb;
            font-size: 16px;
        }
        
        .select {
            width: 100%;
            padding: 12px;
            border: 1px solid #444;
            border-radius: 8px;
            background: #1a1d23;
            color: #e5e7eb;
            font-size: 16px;
            outline: none;
            transition: all 0.3s var(--ease-smooth);
        }
        
        .select:focus {
            border-color: #2ecc71;
            box-shadow: 0 0 0 2px rgba(46, 204, 113, 0.2);
        }
        
        .download-btn {
            width: 100%;
            padding: 16px;
            font-size: 18px;
            font-weight: 600;
            background: #2ecc71;
            color: white;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s var(--ease-smooth);
            position: relative;
            overflow: hidden;
        }
        
        .download-btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }
        
        .download-btn:hover::before {
            left: 100%;
        }
        
        .download-btn:hover {
            background: #27ae60;
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(46, 204, 113, 0.4);
        }
        
        .download-btn:disabled {
            background: #666;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .download-btn:disabled::before {
            display: none;
        }
        
        .queue-list {
            background: #23262f;
            border-radius: 16px;
            padding: 30px;
            margin: 0 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            border: 1px solid #333;
            max-width: 1000px;
            width: 100%;
        }
        
        .queue-item {
            display: flex;
            gap: 20px;
            padding: 20px;
            border: 1px solid #444;
            border-radius: 12px;
            margin-bottom: 15px;
            background: #1a1d23;
            transition: all 0.3s var(--ease-smooth);
        }
        
        .queue-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
            border-color: #555;
        }
        
        .queue-item-thumbnail {
            width: 120px;
            height: 90px;
            border-radius: 8px;
            overflow: hidden;
            flex-shrink: 0;
        }
        
        .queue-item-thumbnail img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        
        .queue-item-info {
            flex: 1;
        }
        
        .queue-item-title {
            font-weight: bold;
            margin-bottom: 8px;
            font-size: 18px;
            color: #e5e7eb;
            line-height: 1.3;
        }
        
        .queue-item-meta {
            color: #aaa;
            font-size: 14px;
            margin-bottom: 8px;
        }
        
        .queue-item-url {
            color: #2ecc71;
            font-size: 12px;
            word-break: break-all;
            margin-bottom: 10px;
        }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #444;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 8px;
        }
        
        .progress-fill {
            height: 100%;
            background: #2ecc71;
            transition: width 0.3s ease;
            border-radius: 4px;
        }
        
        .status {
            font-size: 14px;
            color: #aaa;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.show {
            display: flex;
        }
        
        .modal-content {
            background: #23262f;
            padding: 40px;
            border-radius: 16px;
            text-align: center;
            max-width: 500px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            border: 1px solid #333;
        }
        
        .modal h3 {
            margin: 0 0 20px 0;
            color: #2ecc71;
            font-size: 24px;
        }
        
        .modal p {
            margin: 0 0 30px 0;
            font-size: 16px;
            line-height: 1.5;
        }
        
        .modal .btn {
            padding: 12px 24px;
            font-size: 16px;
            background: #2ecc71;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s var(--ease-smooth);
        }
        
        .modal .btn:hover {
            background: #27ae60;
            transform: translateY(-2px);
        }
        
        .version-tag {
            position: absolute;
            left: 12px;
            bottom: 8px;
            font-size: 12px;
            color: #888;
            user-select: none;
            pointer-events: none;
        }
        
        body.light-theme .version-tag {
            color: #666;
        }
        
        /* 響應式設計 */
        @media (max-width: 768px) {
            .sidebar {
                width: 60px;
            }
            .sidebar .nav-text {
                opacity: 0;
            }
            .title-img {
                width: 300px;
            }
            .search-input {
                width: 250px;
            }
            .video-info, .queue-list {
                margin: 0 10px;
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="menu-btn" onclick="toggleSidebar()">
                <img src="assets/menu.png" alt="選單">
            </div>
            <div class="nav-item selected" id="nav-home" onclick="showPage('home')">
                <img src="assets/home.png" alt="首頁">
                <span class="nav-text">首頁</span>
            </div>
            <div class="nav-item" id="nav-queue" onclick="showPage('queue')">
                <img src="assets/quene.png" alt="佇列">
                <span class="nav-text">下載佇列</span>
            </div>
            <div class="nav-item" onclick="openSettings()">
                <img src="assets/settings.png" alt="設定">
                <span class="nav-text">設定</span>
            </div>
        </div>
        
        <div class="main">
            <img id="title-img" class="title-img" src="assets/icon_text.png" alt="OldFish 影片下載器">
            
            <div id="search-row" class="search-row">
                <input type="text" id="url-input" class="search-input" placeholder="請輸入影片網址...">
                <button class="search-btn" onclick="getVideoInfo()">獲取資訊</button>
            </div>
            
            <div id="video-info" class="video-info">
                <img id="video-thumbnail" class="video-thumbnail" src="" alt="縮圖">
                <div id="video-title" class="video-title"></div>
                <div id="video-meta" class="video-meta"></div>
                
                <div class="quality-select">
                    <label class="select-label">畫質選擇</label>
                    <select id="quality-select" class="select">
                        <option value="">請選擇畫質</option>
                    </select>
                </div>
                
                <div class="format-select">
                    <label class="select-label">格式選擇</label>
                    <select id="format-select" class="select">
                        <option value="">請選擇格式</option>
                    </select>
                </div>
                
                <button id="download-btn" class="download-btn" onclick="startDownload()" disabled>
                    開始下載
                </button>
            </div>
            
            <div id="queue-page" style="display: none;">
                <div class="queue-list">
                    <h2 style="margin: 0 0 20px 0; color: #e5e7eb;">下載佇列</h2>
                    <div id="queue-list">
                        <p style="text-align: center; color: #888; font-size: 18px; margin-top: 50px;">目前沒有下載任務。</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- 模態視窗 -->
    <div id="modal-bg" class="modal">
        <div class="modal-content">
            <h3 id="modal-title">標題</h3>
            <p id="modal-message">訊息</p>
            <button class="btn" onclick="closeModal()">確定</button>
        </div>
    </div>
    
    <script>
        let currentVideoInfo = null;
        let downloadQueue = [];
        let taskIdCounter = 1;
        let lastVideoInfo = null;
        
        // 音訊品質選項
        const AUDIO_QUALITIES = [
            {"label": "320kbps", "value": "320"},
            {"label": "256kbps", "value": "256"},
            {"label": "192kbps", "value": "192"},
            {"label": "128kbps", "value": "128"},
            {"label": "96kbps", "value": "96"},
        ];
        
        function toggleSidebar() {
            const sidebar = document.querySelector('.sidebar');
            sidebar.classList.toggle('collapsed');
        }
        
        function showPage(pageName) {
            // 更新選單狀態
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('selected'));
            if (pageName === 'home') {
                document.getElementById('nav-home').classList.add('selected');
                document.getElementById('title-img').style.display = 'block';
                document.getElementById('search-row').style.display = 'flex';
                document.getElementById('video-info').style.display = 'none';
                document.getElementById('queue-page').style.display = 'none';
            } else if (pageName === 'queue') {
                document.getElementById('nav-queue').classList.add('selected');
                document.getElementById('title-img').style.display = 'none';
                document.getElementById('search-row').style.display = 'none';
                document.getElementById('video-info').style.display = 'none';
                document.getElementById('queue-page').style.display = 'block';
                updateQueueDisplay();
            }
        }
        
        function getVideoInfo() {
            const url = document.getElementById('url-input').value.trim();
            if (!url) {
                showModal('錯誤', '請輸入影片網址');
                return;
            }
            
            if (window.api) {
                window.api.start_get_video_info(url);
            } else {
                showModal('錯誤', 'API 未初始化');
            }
        }
        
        function startDownload() {
            if (!currentVideoInfo) {
                showModal('錯誤', '請先獲取影片資訊');
                return;
            }
            
            const quality = document.getElementById('quality-select').value;
            const format = document.getElementById('format-select').value;
            
            if (!quality || !format) {
                showModal('錯誤', '請選擇畫質和格式');
                return;
            }
            
            const taskId = 'task_' + taskIdCounter++;
            const task = {
                id: taskId,
                title: currentVideoInfo.title,
                uploader: currentVideoInfo.uploader,
                duration: currentVideoInfo.duration,
                url: document.getElementById('url-input').value.trim(),
                quality: quality,
                format: format,
                status: '準備中',
                progress: 0
            };
            
            downloadQueue.push(task);
            updateQueueDisplay();
            
            if (window.api) {
                window.api.start_download(taskId, task.url, quality, format);
            }
            
            showModal('成功', '下載已開始');
        }
        
        function updateQueueDisplay() {
            const queueList = document.getElementById('queue-list');
            if (downloadQueue.length === 0) {
                queueList.innerHTML = '<p style="text-align: center; color: #888; font-size: 18px; margin-top: 50px;">目前沒有下載任務。</p>';
                return;
            }
            
            queueList.innerHTML = downloadQueue.map(task => `
                <div class="queue-item">
                    <div class="queue-item-thumbnail">
                        <img src="${currentVideoInfo?.thumb || 'assets/folder.png'}" alt="縮圖">
                    </div>
                    <div class="queue-item-info">
                        <div class="queue-item-title">${task.title}</div>
                        <div class="queue-item-meta">${task.uploader} · ${task.duration}</div>
                        <div class="queue-item-url">${task.url}</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${task.progress}%"></div>
                        </div>
                        <div class="status">${task.status}</div>
                    </div>
                </div>
            `).join('');
        }
        
        function openSettings() {
            if (window.api) {
                window.api.open_settings();
            }
        }
        
        function showModal(title, message) {
            document.getElementById('modal-title').textContent = title;
            document.getElementById('modal-message').textContent = message;
            document.getElementById('modal-bg').classList.add('show');
        }
        
        function closeModal() {
            document.getElementById('modal-bg').classList.remove('show');
        }
        
        // API 回調函數
        window.__onVideoInfoReady = function(info) {
            currentVideoInfo = info;
            lastVideoInfo = info;
            
            document.getElementById('video-thumbnail').src = info.thumb || 'assets/folder.png';
            document.getElementById('video-title').textContent = info.title;
            document.getElementById('video-meta').textContent = `${info.uploader} · ${info.duration}`;
            
            // 更新畫質選項
            const qualitySelect = document.getElementById('quality-select');
            qualitySelect.innerHTML = '<option value="">請選擇畫質</option>';
            
            if (info.formats && info.formats.some(f => f.desc === '音訊')) {
                // 音訊格式
                AUDIO_QUALITIES.forEach(quality => {
                    const option = document.createElement('option');
                    option.value = quality.value;
                    option.textContent = quality.label;
                    qualitySelect.appendChild(option);
                });
            } else {
                // 影片格式
                info.qualities.forEach(quality => {
                    const option = document.createElement('option');
                    option.value = quality.label;
                    option.textContent = quality.label + (quality.ratio ? ' ' + quality.ratio : '');
                    qualitySelect.appendChild(option);
                });
            }
            
            // 更新格式選項
            const formatSelect = document.getElementById('format-select');
            formatSelect.innerHTML = '<option value="">請選擇格式</option>';
            info.formats.forEach(format => {
                const option = document.createElement('option');
                option.value = format.value;
                option.textContent = format.desc;
                formatSelect.appendChild(option);
            });
            
            document.getElementById('video-info').classList.add('show');
            document.getElementById('download-btn').disabled = false;
        };
        
        window.__onVideoInfoError = function(error) {
            showModal('錯誤', '獲取影片資訊失敗：' + error);
        };
        
        window.updateDownloadProgress = function(taskId, progress, status) {
            const task = downloadQueue.find(t => t.id === taskId);
            if (task) {
                task.progress = progress;
                task.status = status;
                updateQueueDisplay();
            }
        };
        
        window.onDownloadComplete = function(taskId) {
            const task = downloadQueue.find(t => t.id === taskId);
            if (task) {
                task.status = '完成';
                task.progress = 100;
                updateQueueDisplay();
            }
        };
        
        window.onDownloadError = function(taskId, error) {
            const task = downloadQueue.find(t => t.id === taskId);
            if (task) {
                task.status = '錯誤：' + error;
                updateQueueDisplay();
            }
        };
        
        // 鍵盤快捷鍵
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && document.getElementById('url-input') === document.activeElement) {
                getVideoInfo();
            }
        });
    </script>
</body>
</html>'''