/**
 * Video Modal Module
 * Handles video download modal, quality/format selection, and download confirmation
 */

// Custom select dropdown variables
let currentQuality = '';
let currentFormat = '';
let isQualitySelectOpen = false;
let isFormatSelectOpen = false;

/**
 * Show video detail modal
 */
function showVideoModal(url) {
    // Record current URL for download confirmation
    try { currentUrl = (url || '').trim(); } catch(e) { currentUrl = ''; }
    
    // Check if playlist URL
    if (url && (url.includes('list=') || url.includes('/playlist'))) {
        console.log('[前端] Detected playlist URL, showing playlist modal directly');
        if (typeof showPlaylistModal === 'function') showPlaylistModal(url);
        return;
    }
    
    const videoModalBg = document.getElementById('video-modal-bg');
    if (typeof openPopupOverlay === 'function') openPopupOverlay(videoModalBg);
    
    document.getElementById('video-modal-loading').style.display = '';
    document.getElementById('video-modal-content').style.display = 'none';
    
    // Use requestAnimationFrame to ensure style update before showing, avoiding sync blocking repaint
    requestAnimationFrame(() => {
        if (typeof showLoading === 'function') showLoading();
    });
    
    // Background fetch video info, frontend receives via callback to avoid blocking
    setTimeout(function(){
        window.__videoInfoCallback = function(info) {
            console.log('[前端] showVideoModal received info callback', info);
            // Check if playlist info
            if (info && info.is_playlist) {
                console.log('[前端] Detected playlist info, switching to playlist modal');
                if (typeof closeVideoModal === 'function') closeVideoModal();
                if (typeof showPlaylistModal === 'function') showPlaylistModal(url, info);
                return;
            }
            try { lastVideoInfo = info; } catch(e) {}

            // Quality options (sorted high to low)
            var qualityOptions = document.getElementById('quality-options');
            qualityOptions.innerHTML = '';
            var qualities = (info.qualities || []).slice();
            // Filter qualities below 360p
            qualities = qualities.filter(function(q) {
                function getValue(q) {
                    if (q.label.endsWith('K')) return parseInt(q.label) * 1000;
                    var m = q.label.match(/(\d+)p/);
                    return m ? parseInt(m[1]) : 0;
                }
                return getValue(q) >= 360;
            });
            qualities.sort(function(a, b) {
                // Parse number in label (e.g., 4K, 1080p, 720p, 480p, 360p)
                function getValue(q) {
                    if (q.label.endsWith('K')) return parseInt(q.label) * 1000;
                    var m = q.label.match(/(\d+)p/);
                    return m ? parseInt(m[1]) : 0;
                }
                return getValue(b) - getValue(a);
            });
            qualities.forEach(function(q) {
                var optionDiv = document.createElement('div');
                optionDiv.className = 'custom-select-option';
                optionDiv.textContent = q.label + (q.ratio ? ' ' + q.ratio : '');
                optionDiv.onclick = () => selectOption('quality-select', q.label, q.label + (q.ratio ? ' ' + q.ratio : ''));
                if (q.label === '1080p') {
                    optionDiv.classList.add('selected');
                    const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
                    if (qualitySelectText) {
                        qualitySelectText.textContent = q.label + (q.ratio ? ' ' + q.ratio : '');
                    }
                    currentQuality = q.label;
                }
                qualityOptions.appendChild(optionDiv);
            });

            // Format options (mp4 and mp3 priority)
            var formatOptions = document.getElementById('format-options');
            formatOptions.innerHTML = '';
            var formats = (info.formats || []).slice();
            formats.sort(function(a, b) {
                var priority = {"影片+音訊": 3, "影片": 2, "音訊": 1};
                var pa = priority[a.desc] || 0;
                var pb = priority[b.desc] || 0;
                if (pa !== pb) return pb - pa;
                return a.value.localeCompare(b.value);
            });
            formats.forEach(function(f) {
                var optionDiv = document.createElement('div');
                optionDiv.className = 'custom-select-option';
                optionDiv.textContent = f.label + (f.desc ? ' (' + f.desc + ')' : '');
                optionDiv.onclick = () => selectOption('format-select', f.value, f.label + (f.desc ? ' (' + f.desc + ')' : ''));
                if (f.value === 'mp4') {
                    optionDiv.classList.add('selected');
                    const formatSelectText = document.querySelector('#format-select .custom-select-text');
                    if (formatSelectText) {
                        formatSelectText.textContent = f.label + (f.desc ? ' (' + f.desc + ')' : '');
                    }
                    currentFormat = f.value;
                }
                formatOptions.appendChild(optionDiv);
            });

            // Set defaults
            if (!currentQuality && qualities.length > 0) {
                currentQuality = qualities[0].label;
                const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
                if (qualitySelectText) {
                    qualitySelectText.textContent = qualities[0].label + (qualities[0].ratio ? ' ' + qualities[0].ratio : '');
                }
            }
            if (!currentFormat && formats.length > 0) {
                currentFormat = formats[0].value;
                const formatSelectText = document.querySelector('#format-select .custom-select-text');
                if (formatSelectText) {
                    formatSelectText.textContent = formats[0].label + (formats[0].desc ? ' (' + formats[0].desc + ')' : '');
                }
            }

            // Thumbnail handling: if info.thumb doesn't exist or load fails, show text
            const thumbElement = document.getElementById('video-modal-thumb');
            if (info.thumb) {
                thumbElement.src = info.thumb;
                thumbElement.style.display = '';
                thumbElement.alt = "影片縮圖";
                const existingNoThumbText = thumbElement.parentNode.querySelector('.video-modal-thumb-text');
                if (existingNoThumbText) { existingNoThumbText.remove(); }
            } else {
                thumbElement.src = '';
                thumbElement.style.display = 'none';
                let noThumbText = thumbElement.parentNode.querySelector('.video-modal-thumb-text');
                if (!noThumbText) {
                    noThumbText = document.createElement('div');
                    noThumbText.classList.add('video-modal-thumb-text');
                    noThumbText.innerText = "找不到縮圖";
                    noThumbText.style.width = '100%';
                    noThumbText.style.height = '100%';
                    noThumbText.style.display = 'flex';
                    noThumbText.style.alignItems = 'center';
                    noThumbText.style.justifyContent = 'center';
                    noThumbText.style.backgroundColor = 'var(--of-bg-elevated)';
                    noThumbText.style.borderRadius = '8px';
                    noThumbText.style.color = 'var(--of-text-muted)';
                    noThumbText.style.fontSize = '12px';
                    noThumbText.style.textAlign = 'center';
                    noThumbText.style.lineHeight = '1.2';
                    noThumbText.style.padding = '5px';
                    thumbElement.parentNode.insertBefore(noThumbText, thumbElement.nextSibling);
                }
            }

            document.getElementById('video-modal-title').innerText = info.title || '';
            const uploader = info.uploader || '未知上傳者';
            const duration = info.duration || '未知時長';
            document.getElementById('video-modal-meta').innerText = `${uploader} · ${duration}`;
            document.getElementById('video-modal-loading').style.display = 'none';
            document.getElementById('video-modal-content').style.display = '';
            if (typeof hideLoading === 'function') hideLoading();
        };
        
        window.__videoInfoErrorCallback = function(error) {
            console.error('獲取影片資訊時出錯:', error);
            if (typeof showModal === 'function') showModal('錯誤', '找不到影片，請確認網址是否輸入正確');
            if (typeof closeVideoModal === 'function') closeVideoModal();
            if (typeof hideLoading === 'function') hideLoading();
        };
        
        if (window.pywebview && window.pywebview.api) {
            window.pywebview.api.start_get_video_info(url);
        }
    }, 0);
}

/**
 * Confirm download
 */
function confirmDownload() {
    if (!currentUrl) {
        if (typeof showModal === 'function') showModal('錯誤', '沒有影片網址');
        return;
    }
    
    if (!currentQuality) {
        if (typeof showModal === 'function') showModal('錯誤', '請選擇畫質');
        return;
    }
    
    if (!currentFormat) {
        if (typeof showModal === 'function') showModal('錯誤', '請選擇格式');
        return;
    }
    
    const taskId = nextTaskId++;
    const task = {
        id: taskId,
        url: currentUrl,
        title: lastVideoInfo ? lastVideoInfo.title : '未知影片',
        uploader: lastVideoInfo ? lastVideoInfo.uploader : '未知上傳者',
        duration: lastVideoInfo ? lastVideoInfo.duration : '未知時長',
        quality: currentQuality,
        format: currentFormat,
        thumbnail: lastVideoInfo ? lastVideoInfo.thumb : '',
        status: '等待中',
        progress: 0
    };
    
    downloadQueue.push(task);
    
    if (typeof renderQueue === 'function') renderQueue();
    
    if (typeof closeVideoModal === 'function') closeVideoModal();
    
    // Call backend to start download
    if (window.api && window.api.add_to_queue) {
        window.api.add_to_queue(JSON.stringify(task))
            .then(() => {
                console.log(`Task ${taskId} added to queue`);
            })
            .catch(error => {
                console.error(`Failed to add task ${taskId} to queue:`, error);
            });
    }
}

/**
 * Download video from queue page
 */
function downloadVideoFromQueue() {
    const urlInput = document.getElementById('queue-video-url');
    const url = urlInput.value.trim();
    
    if (!url) {
        if (typeof showModal === 'function') showModal('錯誤', '請輸入影片網址');
        return;
    }

    if (typeof tryHandleDevCommand === 'function' && tryHandleDevCommand(url, urlInput)) {
        return;
    }

    // Consistent with home page: show loading overlay first, then open video/playlist info modal
    requestAnimationFrame(() => {
        if (typeof showLoading === 'function') showLoading();
    });
    
    try { currentUrl = (url || '').trim(); } catch(e) { currentUrl = ''; }
    showVideoModal(url);
    
    // Clear input
    urlInput.value = '';
}

/**
 * Download video from home page
 */
function downloadVideo() {
    var url = document.getElementById('video-url').value;
    if (!url.trim()) {
        if (typeof showModal === 'function') showModal("提醒", "請輸入影片網址！");
        return;
    }
    
    const homeInput = document.getElementById('video-url');
    if (typeof tryHandleDevCommand === 'function' && tryHandleDevCommand(url.trim(), homeInput)) {
        return;
    }
    
    if (!isYoutubeUrl(url)) {
        if (typeof showModal === 'function') showModal("網址格式錯誤", "</div><div style='text-align:left;'><br>正確格式範例：<br>https://www.youtube.com/watch?v=xxxx<br>https://youtu.be/xxxx</div>");
        return;
    }
    
    // Immediately show loading to avoid previous layer blocking render
    requestAnimationFrame(() => {
        if (typeof showLoading === 'function') showLoading();
    });
    
    try { currentUrl = (url || '').trim(); } catch(e) { currentUrl = ''; }
    showVideoModal(url);
}
