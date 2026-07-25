/**
 * Queue Manager Module
 * Handles download queue rendering and management
 */

// Queue render debounce timer
let queueRenderTimer = null;
// Collapse state for playlist cards
const collapsedState = {};

/**
 * Schedule a debounced queue render
 */
function scheduleRenderQueue() {
    if (queueRenderTimer) {
        clearTimeout(queueRenderTimer);
    }
    queueRenderTimer = setTimeout(() => {
        queueRenderTimer = null;
        renderQueue();
    }, 300);
}

/**
 * Render the download queue
 */
function renderQueue() {
    const queueList = document.getElementById('queue-list');
    if (!queueList) return;

    // Save scroll position to reduce visual jump
    const savedScrollTop = queueList.scrollTop;
    queueList.innerHTML = '';

    if (downloadQueue.length === 0) {
        queueList.innerHTML = '<div style="text-align:center;padding:40px;color:var(--of-text-muted);">佇列中沒有任務</div>';
        return;
    }

    // Group tasks by playlist
    const groups = [];
    const processedIds = new Set();

    downloadQueue.forEach(task => {
        if (processedIds.has(task.id)) return;
        
        if (task.playlistGroupId) {
            // Find all tasks in this playlist
            const playlistTasks = downloadQueue.filter(t => t.playlistGroupId === task.playlistGroupId);
            playlistTasks.forEach(t => processedIds.add(t.id));
            
            if (playlistTasks.length > 0) {
                groups.push({
                    id: task.playlistGroupId,
                    url: task.playlistUrl,
                    uploader: task.playlistUploader,
                    thumbnail: task.playlistThumbnail,
                    title: task.playlistTitle || '播放清單',
                    tasks: playlistTasks
                });
            }
        } else {
            // Single task
            processedIds.add(task.id);
            groups.push({ single: task });
        }
    });

    const esc = escapeHtml;

    function renderThumbnailContent(thumbnail) {
        if (thumbnail && thumbnail.startsWith('http')) {
            return `<img src="${esc(thumbnail)}" alt="縮圖" onerror="this.parentElement.innerHTML='<div class=\\'queue-item-thumbnail-text\\'>找不到縮圖</div>'">`;
        }
        return `<div class="queue-item-thumbnail-text">找不到縮圖</div>`;
    }

    function renderOneTask(task, isNested) {
        const displayUrl = task.url.length > 50 ? task.url.substring(0, 47) + '...' : task.url;
        const thumbnailContent = renderThumbnailContent(task.thumbnail);
        const isCompleted = task.status === '已完成';
        const progressContent = isCompleted
            ? `<div class="progress-bar-container"><div class="progress-bar" style="width: 100%;"></div></div><div class="progress-text"><span class="completed-badge">下載完成</span> (${task.progress.toFixed(1)}%)</div>`
            : `<div class="progress-bar-container"><div class="progress-bar" style="width: ${task.progress}%;"></div></div><div class="progress-text">${esc(task.status)} (${task.progress.toFixed(1)}%)</div>`;
        const itemClass = isNested ? 'queue-playlist-video-item' : 'queue-item';
        const thumbClass = isNested ? 'queue-playlist-video-thumb' : 'queue-item-thumbnail';
        return `
            <div class="${thumbClass}">${thumbnailContent}</div>
            <div class="queue-item-info">
                <div class="queue-item-title">${esc(task.title)}</div>
                <div class="queue-item-meta">${esc(task.uploader)} · ${esc(task.duration)} · ${esc(task.quality)} · ${esc(task.format).toUpperCase()}</div>
                <div class="queue-item-url">
                    <a href="${esc(task.url)}" class="queue-item-link" data-url="${esc(task.url)}" title="${esc(task.url)}">${esc(displayUrl)}</a>
                </div>
                ${progressContent}
            </div>
            <div class="queue-item-actions">
                <button class="queue-item-action-btn" onclick="openFileLocation(${task.id})" ${isCompleted ? '' : 'disabled'}>
                    <img src="assets/folder.png" alt="開啟檔案位置">
                </button>
            </div>
        `;
    }

    function attachLinkHandler(container) {
        const linkElement = container.querySelector('.queue-item-link');
        if (linkElement) {
            linkElement.addEventListener('click', function(ev) {
                ev.preventDefault();
                ev.stopPropagation();
                const url = this.getAttribute('data-url') || this.getAttribute('href');
                if (url) {
                    try {
                        if (window.api && window.api.open_external_link) {
                            window.api.open_external_link(url);
                        } else {
                            window.open(url, '_blank');
                        }
                    } catch(e) {
                        try { window.open(url, '_blank'); } catch(_) {}
                    }
                }
            });
        }
    }

    groups.forEach((group, groupIndex) => {
        if (group.single) {
            const task = group.single;
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('queue-item');
            itemDiv.setAttribute('data-task-id', task.id);
            const isCompleted = task.status === '已完成';
            if (isCompleted) itemDiv.classList.add('completed');
            itemDiv.innerHTML = renderOneTask(task, false);
            queueList.appendChild(itemDiv);
            attachLinkHandler(itemDiv);
        } else {
            const cardId = 'playlist-card-' + group.id;
            const cardDiv = document.createElement('div');
            cardDiv.className = 'queue-playlist-card';
            cardDiv.setAttribute('data-playlist-id', group.id);
            const allDone = group.tasks.every(t => t.status === '已完成');
            const hasCompletedTask = group.tasks.some(t => t.status === '已完成');
            if (allDone) cardDiv.classList.add('completed');
            const totalProgress = group.tasks.length ? (group.tasks.reduce((s, t) => s + (t.progress || 0), 0) / group.tasks.length) : 0;
            const playlistUrl = group.url || group.tasks[0]?.playlistUrl || '';
            const playlistUploader = group.uploader || group.tasks[0]?.playlistUploader || '未知作者';
            const playlistThumb = group.thumbnail || group.tasks[0]?.playlistThumbnail || group.tasks[0]?.thumbnail || '';
            const playlistDisplayUrl = playlistUrl.length > 50 ? playlistUrl.substring(0, 47) + '...' : playlistUrl;
            const playlistThumbContent = renderThumbnailContent(playlistThumb);
            cardDiv.innerHTML = `
                <div class="queue-playlist-card-header" onclick="togglePlaylistCard('${cardId}')" role="button" tabindex="0" aria-expanded="true">
                    <div class="queue-playlist-card-header-main">
                        <div class="queue-item-thumbnail">${playlistThumbContent}</div>
                        <div class="queue-item-info">
                            <div class="queue-item-title">${esc(group.title)}</div>
                            <div class="queue-item-meta">${esc(playlistUploader)} · ${group.tasks.length} 部影片</div>
                            ${playlistUrl ? `<div class="queue-item-url"><a href="${esc(playlistUrl)}" class="queue-item-link" data-url="${esc(playlistUrl)}" title="${esc(playlistUrl)}">${esc(playlistDisplayUrl)}</a></div>` : ''}
                        </div>
                        <div class="queue-item-actions">
                            <button class="queue-item-action-btn" onclick="event.stopPropagation(); openPlaylistFileLocation('${group.id}')" ${hasCompletedTask ? '' : 'disabled'}>
                                <img src="assets/folder.png" alt="開啟檔案位置">
                            </button>
                        </div>
                        <span class="queue-playlist-card-chevron" id="${cardId}-chevron" style="transform: rotate(0deg);">▲</span>
                    </div>
                    <div class="queue-playlist-card-total-progress" id="${cardId}-total">
                        <span class="queue-playlist-badge">播放清單</span>
                        <div class="queue-playlist-total-bar-wrap">
                            <div class="progress-bar-container">
                                <div class="progress-bar" style="width: ${totalProgress}%;"></div>
                            </div>
                        </div>
                        <span class="queue-playlist-total-pct">${totalProgress.toFixed(1)}%</span>
                    </div>
                </div>
                <div class="queue-playlist-card-body" id="${cardId}-body">
                    ${group.tasks.map(t => {
                        const isCompleted = t.status === '已完成';
                        return `<div class="queue-playlist-video-item ${isCompleted ? 'completed' : ''}" data-task-id="${t.id}">${renderOneTask(t, true)}</div>`;
                    }).join('')}
                </div>
            `;
            queueList.appendChild(cardDiv);
            const headerMainEl = cardDiv.querySelector('.queue-playlist-card-header-main');
            if (headerMainEl) attachLinkHandler(headerMainEl);
            const bodyEl = cardDiv.querySelector('.queue-playlist-card-body');
            const chevronEl = cardDiv.querySelector('.queue-playlist-card-chevron');
            if (bodyEl) {
                bodyEl.querySelectorAll('.queue-playlist-video-item').forEach((row) => {
                    attachLinkHandler(row);
                });
            }
            // Restore collapse state
            if (collapsedState[group.id]) {
                bodyEl.classList.add('queue-playlist-card-body-collapsed');
                if (chevronEl) chevronEl.textContent = '▶';
            }
        }

        if (groupIndex < groups.length - 1) {
            const separatorDiv = document.createElement('div');
            separatorDiv.classList.add('queue-separator');
            queueList.appendChild(separatorDiv);
        }
    });

    // Restore scroll position to reduce visual jump
    if (savedScrollTop > 0) {
        requestAnimationFrame(() => { queueList.scrollTop = savedScrollTop; });
    }
}

/**
 * Toggle playlist card collapse state
 */
function togglePlaylistCard(cardId) {
    const body = document.getElementById(cardId + '-body');
    const chevron = document.getElementById(cardId + '-chevron');
    if (!body || !chevron) return;
    
    // Extract playlist ID from cardId
    const playlistId = cardId.replace('playlist-card-', '');
    const isCollapsed = body.classList.toggle('queue-playlist-card-body-collapsed');
    collapsedState[playlistId] = isCollapsed;
    
    // Expand: arrow up; Collapse: arrow down with rotation animation
    chevron.textContent = '▲';
    chevron.style.transform = isCollapsed ? 'rotate(180deg)' : 'rotate(0deg)';
}

/**
 * Update download progress for a specific task
 * Called by Python backend via pywebview.api.update_progress
 */
window.updateDownloadProgress = function(taskId, progress, status = '下載中', message = '', filePath = '', format = '') {
    // Backend may pass number or string, normalize to number for queue page data-task-id matching
    const tid = Number(taskId);
    if (!Number.isFinite(tid)) return;
    let taskIndex = downloadQueue.findIndex(task => task.id === tid || task.id === taskId);
    
    // If task found, verify format matches (if format provided)
    if (taskIndex !== -1 && format) {
        const task = downloadQueue[taskIndex];
        // If format doesn't match, might have wrong task, don't update
        if (task.format.toLowerCase() !== format.toLowerCase()) {
            console.warn(`Task ${taskId} format mismatch: task format is ${task.format}, but backend passed format ${format}, skipping update to avoid wrong task update`);
            console.warn(`Task details: ID=${task.id}, URL=${task.url}, format=${task.format}, status=${task.status}`);
            // Try to find correct task by URL + format
            const correctTask = downloadQueue.find(t => 
                t.url === task.url && 
                t.format.toLowerCase() === format.toLowerCase() &&
                t.id !== taskId
            );
            if (correctTask) {
                console.log(`Found correct task: ID=${correctTask.id}, format=${correctTask.format}`);
                taskIndex = downloadQueue.indexOf(correctTask);
            } else {
                return; // Don't update to avoid wrong task update
            }
        }
    }
    
    // If task not found, log warning but don't update
    if (taskIndex === -1) {
        console.warn(`Task ID ${taskId} not found, skipping progress update`);
        return;
    }
    
    if (taskIndex !== -1) {
        const task = downloadQueue[taskIndex];
        const oldStatus = task.status;
        
        // If task already completed, shouldn't update again (avoid completed task being reset)
        if (oldStatus === '已完成' && status !== '已完成') {
            console.warn(`Task ${taskId} (format: ${task.format}) already completed, shouldn't update to ${status}, skipping update to avoid wrong update`);
            return;
        }
        
        // Progress bar uses monotonic increase, avoid estimation fluctuation or post-processing causing rollback
        const incomingProgress = Number(progress);
        const safeIncomingProgress = Number.isFinite(incomingProgress) ? incomingProgress : 0;
        const currentProgress = Number.isFinite(Number(task.progress)) ? Number(task.progress) : 0;
        const mergedProgress = (status === '已完成')
            ? 100
            : Math.max(currentProgress, safeIncomingProgress);

        // Update task status
        task.progress = mergedProgress;
        task.status = status;
        // Save ETA info (if message contains it)
        if (message) {
            task.eta = message;
        }
        if (filePath) {
            task.filePath = filePath; // Update file path
        }
        
        // If status changed (especially from downloading to completed), update task display in-place first, then debounce re-render
        if (oldStatus !== status) {
            console.log(`Task ${taskId} (format: ${task.format}) status changed from "${oldStatus}" to "${status}"`);
            const itemDiv = document.querySelector(`[data-task-id="${task.id}"]`);
            if (itemDiv && status === '已完成') {
                itemDiv.classList.add('completed');
                const progressContainer = itemDiv.querySelector('.progress-bar-container');
                const progressText = itemDiv.querySelector('.progress-text');
                const infoDiv = itemDiv.querySelector('.queue-item-info');
                const openFolderBtn = itemDiv.querySelector('.queue-item-action-btn');
                if (progressContainer && progressText) {
                    const progressBar = progressContainer.querySelector('.progress-bar');
                    if (progressBar) progressBar.style.width = '100%';
                    progressText.innerHTML = '<span class="completed-badge">下載完成</span> (100.0%)';
                }
                if (infoDiv && !infoDiv.querySelector('.completed-badge')) {
                    const badge = document.createElement('div');
                    badge.classList.add('completed-badge');
                    badge.textContent = '下載完成';
                    infoDiv.appendChild(badge);
                }
                if (openFolderBtn) {
                    openFolderBtn.disabled = false;
                    openFolderBtn.style.opacity = '1';
                    openFolderBtn.style.cursor = 'pointer';
                }
                if (task.playlistGroupId) {
                    const playlistTasks = downloadQueue.filter(t => t.playlistGroupId === task.playlistGroupId);
                    const totalProgress = playlistTasks.length ? (playlistTasks.reduce((s, t) => s + (Number(t.progress) || 0), 0) / playlistTasks.length) : 0;
                    const cardId = 'playlist-card-' + task.playlistGroupId;
                    const totalWrap = document.getElementById(cardId + '-total');
                    if (totalWrap) {
                        const bar = totalWrap.querySelector('.progress-bar');
                        const pctEl = totalWrap.querySelector('.queue-playlist-total-pct');
                        if (bar) bar.style.width = totalProgress + '%';
                        if (pctEl) pctEl.textContent = totalProgress.toFixed(1) + '%';
                    }
                }
            }
            // 任務列仍在 DOM 中時只更新該列；整體重繪會讓長播放清單在下載時卡頓。
            if (!itemDiv) scheduleRenderQueue();
            return;
        }
        
        // If status unchanged, only update progress display (use task.id to match queue item data-task-id; could be single task or playlist video)
        const itemDiv = document.querySelector(`[data-task-id="${task.id}"]`);
        if (itemDiv) {
            const isCompleted = status === '已完成';
            const progressContainer = itemDiv.querySelector('.progress-bar-container');
            const progressBar = itemDiv.querySelector('.progress-bar');
            const progressText = itemDiv.querySelector('.progress-text');
            const completedBadge = itemDiv.querySelector('.completed-badge');
            const openFolderBtn = itemDiv.querySelector('.queue-item-action-btn');
            
            if (isCompleted) {
                // If status becomes completed, add completed class, keep progress bar but update to completion state
                itemDiv.classList.add('completed');
                if (progressContainer && progressText) {
                    if (progressBar) progressBar.style.width = '100%';
                    progressText.innerHTML = '<span class="completed-badge">下載完成</span> (100.0%)';
                }
                const infoDiv = itemDiv.querySelector('.queue-item-info');
                if (infoDiv && !completedBadge) {
                    const badge = document.createElement('div');
                    badge.classList.add('completed-badge');
                    badge.textContent = '下載完成';
                    infoDiv.appendChild(badge);
                }
            } else {
                // Remove completed class
                itemDiv.classList.remove('completed');
                // Update progress bar
                if (progressBar) {
                    progressBar.style.width = `${mergedProgress}%`;
                }
                if (progressText) {
                    progressText.innerText = `${status} (${mergedProgress.toFixed(1)}%)`;
                }
                // Remove completion badge (if exists)
                if (completedBadge) {
                    completedBadge.remove();
                }
            }
            
            // Update button state: only enable when status is "已完成"
            if (openFolderBtn) {
                if (status === '已完成') {
                    openFolderBtn.disabled = false;
                    openFolderBtn.style.opacity = '1';
                    openFolderBtn.style.cursor = 'pointer';
                } else {
                    openFolderBtn.disabled = true;
                    openFolderBtn.style.opacity = '0.5';
                    openFolderBtn.style.cursor = 'not-allowed';
                }
            }

            // If playlist video, sync update total progress bar
            if (task.playlistGroupId) {
                const playlistTasks = downloadQueue.filter(t => t.playlistGroupId === task.playlistGroupId);
                const totalProgress = playlistTasks.length ? (playlistTasks.reduce((s, t) => s + (Number(t.progress) || 0), 0) / playlistTasks.length) : 0;
                const cardId = 'playlist-card-' + task.playlistGroupId;
                const totalWrap = document.getElementById(cardId + '-total');
                if (totalWrap) {
                    const bar = totalWrap.querySelector('.progress-bar');
                    const pctEl = totalWrap.querySelector('.queue-playlist-total-pct');
                    if (bar) bar.style.width = totalProgress + '%';
                    if (pctEl) pctEl.textContent = totalProgress.toFixed(1) + '%';
                }
            }
        }
    }
};

/**
 * Open downloaded file location
 * Backend returns immediately, actual opening runs in background to avoid blocking UI
 */
function openFileLocation(taskId) {
    console.log("[DBG-Frontend] Open folder button clicked taskId=" + taskId);
    if (window.api && window.api.log_from_js) {
        try { window.api.log_from_js("info", "[DBG-Frontend] Open folder button clicked taskId=" + taskId); } catch (e) {}
    }
    const task = downloadQueue.find(t => t.id === taskId);
    if (!task) {
        if (typeof showModal === 'function') showModal("錯誤", "找不到指定的下載任務。");
        return;
    }
    const btn = document.querySelector(`[data-task-id="${taskId}"] .queue-item-action-btn`);
    if (btn) {
        btn.disabled = true;
        btn.style.opacity = '0.5';
        setTimeout(function() {
            btn.disabled = false;
            btn.style.opacity = '1';
        }, 1500);
    }
    if (!window.api) {
        if (typeof showModal === 'function') showModal("錯誤", "API 未初始化");
        return;
    }
    window.api.open_file_location_by_task(taskId)
        .then(function(result) {
            if (result && (result.includes("失敗") || result.includes("錯誤"))) {
                if (typeof showModal === 'function') showModal("錯誤", result);
            }
        })
        .catch(function(error) {
            console.error("Error opening file location:", error);
            if (typeof showModal === 'function') showModal("錯誤", "無法開啟檔案位置。");
        });
}

/**
 * Open playlist file location
 */
function openPlaylistFileLocation(playlistGroupId) {
    const targetTask = downloadQueue.find(t => String(t.playlistGroupId) === String(playlistGroupId) && t.status === '已完成');
    if (!targetTask) {
        if (typeof showModal === 'function') showModal("錯誤", "此播放清單尚未有可開啟資料夾的已完成影片。");
        return;
    }
    openFileLocation(targetTask.id);
}
