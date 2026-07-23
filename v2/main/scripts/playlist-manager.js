/**
 * Playlist Manager Module
 * Handles playlist selection, video quality/format options, and playlist downloads
 */

// Playlist-related variables
let currentPlaylistData = null;
let playlistVideosData = [];
let playlistUseHighestQuality = false;
let playlistGlobalFormatMode = ''; // '' | 'mp4' | 'mp3' | 'individual'
let playlistPendingQualities = 0;   // Number of videos with pending quality extraction

/**
 * Show playlist selection modal
 */
function showPlaylistModal(url, playlistInfo = null) {
    console.log('[前端] showPlaylistModal called', {url, hasInfo: !!playlistInfo});
    const modal = document.getElementById('playlist-modal-bg');
    if (!modal) {
        console.error('[前端] Playlist modal element not found');
        if (typeof showModal === 'function') showModal('錯誤', '找不到播放清單視窗元素');
        return;
    }
    
    if (typeof openPopupOverlay === 'function') openPopupOverlay(modal);
    
    const content = document.getElementById('playlist-modal-content');
    if (content) {
        content.innerHTML = '<div style="text-align:center;padding:40px;color:var(--of-text-muted);">載入中...</div>';
    }
    
    if (playlistInfo) {
        console.log('[前端] Has playlist info, rendering directly', playlistInfo);
        try {
            renderPlaylist(playlistInfo);
        } catch (e) {
            console.error('[前端] Error rendering playlist:', e);
            if (typeof showModal === 'function') showModal('錯誤', '渲染播放清單時發生錯誤: ' + e.message);
            closePlaylistModal();
        }
    } else {
        console.log('[前端] No playlist info, fetching from API');
        // Fetch playlist info from API
        if (window.api) {
            // Immediately set callback to ensure correct handling when API returns
            console.log('[前端] Immediately setting playlist-specific callback function');
            
            // Save current URL for verification
            const currentPlaylistUrl = url;
            
            // Use callback manager to set dedicated callback
            window.__videoInfoCallback = function(info) {
                console.log('[前端] Received playlist info callback', info);
                console.log('[前端] info type:', typeof info);
                console.log('[前端] info.is_playlist:', info ? info.is_playlist : 'N/A');
                console.log('[前端] Current request URL:', currentPlaylistUrl);
                
                try {
                    if (info && info.is_playlist) {
                        console.log('[前端] Confirmed playlist, starting render');
                        console.log('[前端] Playlist title:', info.playlist_title);
                        console.log('[前端] Playlist video count:', info.video_count);
                        console.log('[前端] Playlist video list:', info.videos ? info.videos.length : 0);
                        renderPlaylist(info);
                    } else {
                        console.error('[前端] Not playlist info:', info);
                        if (typeof showModal === 'function') showModal('錯誤', '無法獲取播放清單資訊');
                        closePlaylistModal();
                        if (typeof hideLoading === 'function') hideLoading();
                    }
                } catch (e) {
                    console.error('[前端] Error handling playlist info:', e);
                    console.error('[前端] Error stack:', e.stack);
                    if (typeof showModal === 'function') showModal('錯誤', '處理播放清單資訊時發生錯誤: ' + e.message);
                    closePlaylistModal();
                    if (typeof hideLoading === 'function') hideLoading();
                }
            };
            
            window.__videoInfoErrorCallback = function(error) {
                console.error('[前端] Failed to get playlist info:', error);
                if (typeof showModal === 'function') showModal('錯誤', '無法獲取播放清單資訊: ' + (error || '未知錯誤'));
                closePlaylistModal();
                if (typeof hideLoading === 'function') hideLoading();
            };
            
            console.log('[前端] Callback setup complete');
            console.log('[前端] window.__videoInfoCallback exists:', typeof window.__videoInfoCallback === 'function');
            console.log('[前端] window.__onVideoInfo exists:', typeof window.__onVideoInfo === 'function');
            
            // Immediately call API, don't use setTimeout
            console.log('[前端] Immediately calling API to get playlist info');
            try {
                window.api.start_get_video_info(url);
                console.log('[前端] API call complete (executing asynchronously)');
            } catch (e) {
                console.error('[前端] Error calling API:', e);
                if (typeof showModal === 'function') showModal('錯誤', '調用 API 失敗: ' + e.message);
                closePlaylistModal();
            }
        } else {
            console.error('[前端] API not initialized');
            if (typeof showModal === 'function') showModal('錯誤', 'API 未初始化');
            closePlaylistModal();
            if (typeof hideLoading === 'function') hideLoading();
        }
    }
}

/**
 * Render playlist
 */
function renderPlaylist(playlistInfo) {
    console.log('[前端] renderPlaylist start', playlistInfo);
    try {
        if (!playlistInfo) {
            console.error('[前端] Playlist info is empty');
            if (typeof showModal === 'function') showModal('錯誤', '播放清單資訊為空');
            closePlaylistModal();
            if (typeof hideLoading === 'function') hideLoading();
            return;
        }
        
        currentPlaylistData = playlistInfo;
        const videos = playlistInfo.videos || [];
        console.log('[前端] Playlist contains', videos.length, 'videos');
        
        // Default select all for download: selected=true
        playlistVideosData = videos.map((video, idx) => {
            console.log(`[前端] Processing video ${idx + 1}:`, video.title || 'No title');
            return {
                ...video,
                selected: true,
                quality: '1080p',
                format: 'mp4',
                qualities: null,
                formats: null
            };
        });

        // Update title
        const titleEl = document.getElementById('playlist-modal-title');
        const subtitleEl = document.getElementById('playlist-modal-subtitle');
        if (titleEl) {
            titleEl.textContent = playlistInfo.playlist_title || '播放清單';
        }
        if (subtitleEl) {
            subtitleEl.textContent = `共 ${playlistInfo.video_count || playlistVideosData.length || 0} 部影片`;
        }

        // Render video list
        const content = document.getElementById('playlist-modal-content');
        if (!content) {
            console.error('[前端] Playlist content container not found');
            if (typeof showModal === 'function') showModal('錯誤', '找不到播放清單內容容器');
            return;
        }
        
        console.log('[前端] Clearing content container, starting render', playlistVideosData.length, 'items');
        content.innerHTML = '';

        if (playlistVideosData.length === 0) {
            content.innerHTML = '<div style="text-align:center;padding:40px;color:var(--of-text-muted);">播放清單中沒有影片</div>';
            console.log('[前端] Playlist is empty');
            updatePlaylistSelectedCount();
            if (typeof hideLoading === 'function') hideLoading();
            return;
        }

        // Initialize quality loading count
        playlistPendingQualities = playlistVideosData.length;

        playlistVideosData.forEach((video, index) => {
            try {
                const item = document.createElement('div');
                item.className = 'playlist-video-item';
                item.dataset.index = index;
                
                const safeTitle = escapeHtml(video.title || '無標題');
                const safeDuration = escapeHtml(video.duration || '未知時長');
                const safeThumb = escapeHtml(video.thumb || 'assets/icon.png');
                const safeUploader = escapeHtml(video.uploader || playlistInfo.playlist_uploader || '未知上傳者');
                
                item.innerHTML = `
                    <input type="checkbox" class="playlist-video-checkbox" onchange="togglePlaylistVideo(${index})" ${video.selected ? 'checked' : ''}>
                    <img class="playlist-video-thumb" src="${safeThumb}" alt="縮圖" onerror="this.src='assets/icon.png'">
                    <div class="playlist-video-info">
                        <div class="playlist-video-title">${safeTitle}</div>
                        <div class="playlist-video-meta">${safeUploader} · ${safeDuration}</div>
                    </div>
                    <div class="playlist-video-controls">
                        <div class="playlist-video-select">
                            <label style="display:block;font-size:11px;color:var(--of-text-muted);margin-bottom:3px;" id="playlist-quality-label-${index}">${(video.format === 'mp3') ? '位元率' : '畫質'}</label>
                            <div class="custom-select ${playlistUseHighestQuality ? 'disabled' : ''}" id="playlist-quality-${index}">
                                <div class="custom-select-header" onclick="togglePlaylistSelect('playlist-quality-${index}', ${index}, 'quality')">
                                    <span class="custom-select-text">${(video.format === 'mp3') ? (video.quality ? (AUDIO_QUALITIES.find(q => q.value === video.quality)?.label || '192kbps') : '192kbps') : (video.quality || '1080p')}</span>
                                    <div class="custom-select-arrow"></div>
                                </div>
                                <div class="custom-select-options">
                                    <div class="custom-select-option ${video.quality === '1080p' ? 'selected' : ''}" onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '1080p')">1080p</div>
                                    <div class="custom-select-option ${video.quality === '720p' ? 'selected' : ''}" onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '720p')">720p</div>
                                    <div class="custom-select-option ${video.quality === '480p' ? 'selected' : ''}" onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '480p')">480p</div>
                                    <div class="custom-select-option ${video.quality === '360p' ? 'selected' : ''}" onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '360p')">360p</div>
                                </div>
                            </div>
                        </div>
                        <div class="playlist-video-select">
                            <label style="display:block;font-size:11px;color:var(--of-text-muted);margin-bottom:3px;">格式</label>
                            <div class="custom-select ${playlistGlobalFormatMode && playlistGlobalFormatMode !== 'individual' ? 'disabled' : ''}" id="playlist-format-${index}">
                                <div class="custom-select-header" onclick="togglePlaylistSelect('playlist-format-${index}', ${index}, 'format')">
                                    <span class="custom-select-text">${(video.format === 'mp3') ? '音訊(mp3)' : '影片(mp4)'}</span>
                                    <div class="custom-select-arrow"></div>
                                </div>
                                <div class="custom-select-options">
                                    <div class="custom-select-option ${video.format === 'mp4' ? 'selected' : ''}" onclick="selectPlaylistOption('playlist-format-${index}', ${index}, 'format', 'mp4')">影片(mp4)</div>
                                    <div class="custom-select-option ${video.format === 'mp3' ? 'selected' : ''}" onclick="selectPlaylistOption('playlist-format-${index}', ${index}, 'format', 'mp3')">音訊(mp3)</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                content.appendChild(item);
                console.log(`[前端] Video ${index + 1} render complete`);
            } catch (e) {
                console.error(`[前端] Error rendering video ${index + 1}:`, e);
            }
        });

        console.log('[前端] All videos rendered, updating selected count');
        updatePlaylistSelectedCount();
        syncPlaylistToolbarState();
        updatePlaylistControlsLockState();
        console.log('[前端] renderPlaylist complete, starting eager quality extraction');

        // Eager: background fetch quality options for each video (consistent with single download logic)
        // Note: don't close loading mask until all qualities are loaded
        try {
            const backend = __getBackendApi();
            if (backend && backend.start_playlist_qualities_fetch) {
                const payload = playlistVideosData.map((v, idx) => ({ index: idx, url: v.url }));
                backend.start_playlist_qualities_fetch(JSON.stringify(payload))
                    .then((res) => { console.log('[播放清單] start_playlist_qualities_fetch:', res); })
                    .catch((e) => { console.error('[播放清單] start_playlist_qualities_fetch error:', e); });
            } else {
                // Backend doesn't support, close loading mask directly
                playlistPendingQualities = 0;
                if (typeof hideLoading === 'function') hideLoading();
            }
        } catch (e) {
            console.error('[播放清單] Eager quality extraction startup failed:', e);
            playlistPendingQualities = 0;
            if (typeof hideLoading === 'function') hideLoading();
        }
    } catch (e) {
        console.error('[前端] renderPlaylist error:', e);
        if (typeof showModal === 'function') showModal('錯誤', '渲染播放清單時發生錯誤: ' + e.message);
        closePlaylistModal();
        if (typeof hideLoading === 'function') hideLoading();
    }
}

/**
 * Backend pushes quality options for individual playlist video
 */
window.__onPlaylistVideoQualities = function(index, qualities) {
    try {
        const idx = Number(index);
        if (!Number.isFinite(idx) || !playlistVideosData[idx]) return;
        if (!Array.isArray(qualities)) qualities = [];
        const video = playlistVideosData[idx];
        video.qualities = qualities;

        // Check current format, if audio format use updatePlaylistVideoQualityOptions to update
        const audioTypes = ["mp3", "aac", "flac", "wav"];
        if (audioTypes.includes(video.format)) {
            updatePlaylistVideoQualityOptions(idx, video.format);
            if (!video._qualitiesLoaded) {
                video._qualitiesLoaded = true;
                if (playlistPendingQualities > 0) {
                    playlistPendingQualities--;
                    if (playlistPendingQualities <= 0) {
                        playlistPendingQualities = 0;
                        if (typeof hideLoading === 'function') hideLoading();
                    }
                }
            }
            return;
        }

        // Update corresponding dropdown options (video format)
        const qSel = document.getElementById(`playlist-quality-${idx}`);
        const options = qSel ? qSel.querySelector('.custom-select-options') : null;
        if (!options) return;

        const sorted = sortQualities(qualities);
        // If no available qualities, keep default items but mark as loaded
        if (!sorted.length) {
            if (playlistPendingQualities > 0) {
                playlistPendingQualities--;
                if (playlistPendingQualities <= 0) {
                    playlistPendingQualities = 0;
                    if (typeof hideLoading === 'function') hideLoading();
                }
            }
            return;
        }

        // If apply highest quality checked, immediately apply highest and lock display
        if (playlistUseHighestQuality) {
            const best = sorted[0]?.label;
            if (best) playlistVideosData[idx].quality = best;
        } else {
            // If current selection not in list, fallback to highest quality
            const cur = playlistVideosData[idx].quality || '';
            const exists = sorted.some(q => (q && q.label) === cur);
            if (!exists && sorted[0]?.label) playlistVideosData[idx].quality = sorted[0].label;
        }

        // Rebuild options
        options.innerHTML = '';
        sorted.forEach(q => {
            const label = q.label + (q.ratio ? (' ' + q.ratio) : '');
            const div = document.createElement('div');
            div.className = 'custom-select-option';
            div.textContent = q.label;
            if (q.label === playlistVideosData[idx].quality) div.classList.add('selected');
            div.onclick = () => selectPlaylistOption(`playlist-quality-${idx}`, idx, 'quality', q.label);
            options.appendChild(div);
        });

        // Update header display
        const textSpan = qSel.querySelector('.custom-select-text');
        if (textSpan) textSpan.textContent = playlistVideosData[idx].quality;

        // If apply highest quality on, update lock state (ensure disabled class)
        updatePlaylistControlsLockState();

        // Mark this video quality as loaded and update global count
        if (!video._qualitiesLoaded) {
            video._qualitiesLoaded = true;
            if (playlistPendingQualities > 0) {
                playlistPendingQualities--;
                if (playlistPendingQualities <= 0) {
                    playlistPendingQualities = 0;
                    console.log('[播放清單] All video qualities loaded, closing loading mask');
                    if (typeof hideLoading === 'function') hideLoading();
                }
            }
        }
    } catch(e) {
        console.error('[播放清單] __onPlaylistVideoQualities failed:', e);
    }
};

/**
 * Toggle playlist dropdown
 */
function togglePlaylistSelect(selectId, index, type) {
    // Apply highest quality: lock single video quality
    if (type === 'quality' && playlistUseHighestQuality) return;
    // All video formats not individual: lock single video format
    if (type === 'format' && playlistGlobalFormatMode && playlistGlobalFormatMode !== 'individual') return;
    // Check if disabled
    const select = document.getElementById(selectId);
    if (!select || select.classList.contains('disabled')) return;
    
    const options = select.querySelector('.custom-select-options');
    const header = select.querySelector('.custom-select-header');
    
    if (!options || !header) return;
    
    // Close other playlist dropdowns
    const allSelects = document.querySelectorAll('.playlist-video-controls .custom-select');
    allSelects.forEach(s => {
        if (s.id !== selectId) {
            const opt = s.querySelector('.custom-select-options');
            const hdr = s.querySelector('.custom-select-header');
            if (opt && hdr) {
                opt.classList.remove('show');
                hdr.classList.remove('active');
            }
        }
    });
    
    // Toggle current dropdown
    const isOpen = options.classList.contains('show');
    if (isOpen) {
        options.classList.remove('show');
        header.classList.remove('active');
        if (typeof clearSelectOptionsPosition === 'function') clearSelectOptionsPosition(select);
    } else {
        options.classList.add('show');
        header.classList.add('active');
        if (typeof positionSelectOptions === 'function') positionSelectOptions(select);
    }
}

/**
 * Select playlist option
 */
function selectPlaylistOption(selectId, index, type, value) {
    const select = document.getElementById(selectId);
    if (!select || select.classList.contains('disabled')) return;
    
    const header = select.querySelector('.custom-select-header');
    const textSpan = header ? header.querySelector('.custom-select-text') : null;
    const options = select.querySelector('.custom-select-options');
    
    // Update display text
    if (textSpan) {
        if (type === 'quality') {
            const audioTypes = ["mp3", "aac", "flac", "wav"];
            const video = playlistVideosData[index];
            if (video && audioTypes.includes(video.format)) {
                const audioQuality = AUDIO_QUALITIES.find(q => q.value === value);
                textSpan.textContent = audioQuality ? audioQuality.label : value;
            } else {
                textSpan.textContent = value;
            }
        } else if (type === 'format') {
            textSpan.textContent = value === 'mp3' ? '音訊(mp3)' : '影片(mp4)';
        }
    }
    
    // Update data
    if (type === 'quality') {
        playlistVideosData[index].quality = value;
    } else if (type === 'format') {
        playlistVideosData[index].format = value;
        if (typeof updatePlaylistVideoQualityOptions === 'function') {
            updatePlaylistVideoQualityOptions(index, value);
        }
    }
    
    // Close dropdown
    options.classList.remove('show');
    header.classList.remove('active');
    if (typeof clearSelectOptionsPosition === 'function') clearSelectOptionsPosition(select);
}

/**
 * Toggle playlist video selection
 */
function togglePlaylistVideo(index) {
    playlistVideosData[index].selected = !playlistVideosData[index].selected;
    updatePlaylistSelectedCount();
}

/**
 * Update playlist selected count
 */
function updatePlaylistSelectedCount() {
    const countEl = document.getElementById('playlist-selected-count');
    const downloadBtn = document.getElementById('playlist-download-btn');
    const selectedCount = playlistVideosData.filter(v => v.selected).length;
    
    if (countEl) {
        countEl.textContent = `已選擇 ${selectedCount} 部影片`;
    }
    
    if (downloadBtn) {
        downloadBtn.disabled = selectedCount === 0;
    }
}

/**
 * Playlist select all changed
 */
function onPlaylistSelectAllChanged(checked) {
    playlistVideosData.forEach(video => {
        video.selected = checked;
    });
    updatePlaylistSelectedCount();
    
    // Update checkbox UI
    const checkboxes = document.querySelectorAll('.playlist-video-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checked;
    });
}

/**
 * Playlist apply highest quality changed
 */
function onPlaylistApplyHighestQualityChanged(checked) {
    playlistUseHighestQuality = checked;
    updatePlaylistControlsLockState();
    
    if (checked) {
        // Apply highest quality to all videos
        playlistVideosData.forEach((video, idx) => {
            if (video.qualities && video.qualities.length > 0) {
                const sorted = sortQualities(video.qualities);
                if (sorted.length > 0) {
                    video.quality = sorted[0].label;
                    // Update UI
                    const qSel = document.getElementById(`playlist-quality-${idx}`);
                    if (qSel) {
                        const textSpan = qSel.querySelector('.custom-select-text');
                        if (textSpan) textSpan.textContent = video.quality;
                    }
                }
            }
        });
    }
}

/**
 * Toggle playlist global format select
 */
function togglePlaylistGlobalFormatSelect() {
    const select = document.getElementById('playlist-global-format-select');
    if (!select) return;
    
    const options = select.querySelector('.custom-select-options');
    const header = select.querySelector('.custom-select-header');
    
    if (!options || !header) return;
    
    const isOpen = options.classList.contains('show');
    if (isOpen) {
        options.classList.remove('show');
        header.classList.remove('active');
    } else {
        options.classList.add('show');
        header.classList.add('active');
    }
}

/**
 * Select playlist global format option
 */
function selectPlaylistGlobalFormatOption(value) {
    const select = document.getElementById('playlist-global-format-select');
    if (!select) return;
    
    const header = select.querySelector('.custom-select-header');
    const textSpan = header ? header.querySelector('.custom-select-text') : null;
    const options = select.querySelector('.custom-select-options');
    
    if (textSpan) {
        if (value === '') {
            textSpan.textContent = '-請選擇影片格式-';
        } else if (value === 'mp4') {
            textSpan.textContent = '影片(mp4)';
        } else if (value === 'mp3') {
            textSpan.textContent = '音訊(mp3)';
        } else if (value === 'individual') {
            textSpan.textContent = '個別選擇格式';
        }
    }
    
    playlistGlobalFormatMode = value;
    
    // Apply format to all videos
    if (value === 'mp4' || value === 'mp3') {
        playlistVideosData.forEach((video, idx) => {
            video.format = value;
            if (typeof updatePlaylistVideoQualityOptions === 'function') {
                updatePlaylistVideoQualityOptions(idx, value);
            }
            // Update UI
            const fSel = document.getElementById(`playlist-format-${idx}`);
            if (fSel) {
                const textSpan = fSel.querySelector('.custom-select-text');
                if (textSpan) textSpan.textContent = value === 'mp3' ? '音訊(mp3)' : '影片(mp4)';
            }
        });
    }
    
    updatePlaylistControlsLockState();
    
    // Close dropdown
    options.classList.remove('show');
    header.classList.remove('active');
}

/**
 * Update playlist video quality options based on format
 */
function updatePlaylistVideoQualityOptions(index, format) {
    const audioTypes = ["mp3", "aac", "flac", "wav"];
    const isAudio = audioTypes.includes(format);
    
    const qSel = document.getElementById(`playlist-quality-${index}`);
    if (!qSel) return;
    
    const options = qSel.querySelector('.custom-select-options');
    const header = qSel.querySelector('.custom-select-header');
    const textSpan = header ? header.querySelector('.custom-select-text') : null;
    const labelEl = document.getElementById(`playlist-quality-label-${index}`);
    
    if (labelEl) {
        labelEl.textContent = isAudio ? '位元率' : '畫質';
    }
    
    if (isAudio) {
        // Audio format: show audio quality options
        options.innerHTML = AUDIO_QUALITIES.map(q => 
            `<div class="custom-select-option ${q.value === playlistVideosData[index].quality ? 'selected' : ''}" 
                  onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '${q.value}')">${q.label}</div>`
        ).join('');
        
        const currentQuality = playlistVideosData[index].quality || '192';
        const audioQuality = AUDIO_QUALITIES.find(q => q.value === currentQuality);
        if (textSpan) textSpan.textContent = audioQuality ? audioQuality.label : currentQuality;
        
        // If current quality not in audio qualities, default to 192kbps
        if (!audioQuality) {
            playlistVideosData[index].quality = '192';
            if (textSpan) textSpan.textContent = '192kbps';
        }
    } else {
        // Video format: show video quality options
        const video = playlistVideosData[index];
        if (video.qualities && video.qualities.length > 0) {
            const sorted = sortQualities(video.qualities);
            options.innerHTML = sorted.map(q => 
                `<div class="custom-select-option ${q.label === playlistVideosData[index].quality ? 'selected' : ''}" 
                      onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '${q.label}')">${q.label}</div>`
            ).join('');
            
            if (textSpan) textSpan.textContent = playlistVideosData[index].quality;
        } else {
            // Default video qualities
            options.innerHTML = `
                <div class="custom-select-option ${playlistVideosData[index].quality === '1080p' ? 'selected' : ''}" 
                      onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '1080p')">1080p</div>
                <div class="custom-select-option ${playlistVideosData[index].quality === '720p' ? 'selected' : ''}" 
                      onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '720p')">720p</div>
                <div class="custom-select-option ${playlistVideosData[index].quality === '480p' ? 'selected' : ''}" 
                      onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '480p')">480p</div>
                <div class="custom-select-option ${playlistVideosData[index].quality === '360p' ? 'selected' : ''}" 
                      onclick="selectPlaylistOption('playlist-quality-${index}', ${index}, 'quality', '360p')">360p</div>
            `;
            if (textSpan) textSpan.textContent = playlistVideosData[index].quality || '1080p';
        }
    }
}

/**
 * Update playlist controls lock state
 */
function updatePlaylistControlsLockState() {
    playlistVideosData.forEach((video, idx) => {
        const qSel = document.getElementById(`playlist-quality-${idx}`);
        const fSel = document.getElementById(`playlist-format-${idx}`);
        
        if (qSel) {
            if (playlistUseHighestQuality) {
                qSel.classList.add('disabled');
            } else {
                qSel.classList.remove('disabled');
            }
        }
        
        if (fSel) {
            if (playlistGlobalFormatMode && playlistGlobalFormatMode !== 'individual') {
                fSel.classList.add('disabled');
            } else {
                fSel.classList.remove('disabled');
            }
        }
    });
}

/**
 * Sync playlist toolbar state
 */
function syncPlaylistToolbarState() {
    const selectAllCheckbox = document.getElementById('playlist-select-all');
    const applyHighestCheckbox = document.getElementById('playlist-apply-highest-quality');
    const globalFormatSelect = document.getElementById('playlist-global-format-select');
    
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = playlistVideosData.every(v => v.selected);
    }
    
    if (applyHighestCheckbox) {
        applyHighestCheckbox.checked = playlistUseHighestQuality;
    }
    
    if (globalFormatSelect) {
        const textSpan = globalFormatSelect.querySelector('.custom-select-text');
        if (textSpan) {
            if (playlistGlobalFormatMode === '') {
                textSpan.textContent = '-請選擇影片格式-';
            } else if (playlistGlobalFormatMode === 'mp4') {
                textSpan.textContent = '影片(mp4)';
            } else if (playlistGlobalFormatMode === 'mp3') {
                textSpan.textContent = '音訊(mp3)';
            } else if (playlistGlobalFormatMode === 'individual') {
                textSpan.textContent = '個別選擇格式';
            }
        }
    }
}

/**
 * Start playlist download
 */
function startPlaylistDownload() {
    const selectedVideos = playlistVideosData.filter(v => v.selected);
    
    if (selectedVideos.length === 0) {
        if (typeof showModal === 'function') showModal('錯誤', '請選擇至少一部影片');
        return;
    }
    
    closePlaylistModal();
    
    // Add each selected video to download queue
    selectedVideos.forEach(video => {
        const taskId = nextTaskId++;
        const task = {
            id: taskId,
            url: video.url,
            title: video.title,
            uploader: video.uploader,
            duration: video.duration,
            quality: video.quality,
            format: video.format,
            thumbnail: video.thumb,
            status: '等待中',
            progress: 0,
            playlistGroupId: currentPlaylistData?.playlist_id,
            playlistUrl: currentPlaylistData?.playlist_url,
            playlistTitle: currentPlaylistData?.playlist_title,
            playlistUploader: currentPlaylistData?.playlist_uploader,
            playlistThumbnail: currentPlaylistData?.playlist_thumbnail
        };
        
        downloadQueue.push(task);
        
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
    });
    
    // Render queue
    if (typeof renderQueue === 'function') renderQueue();
    
    // Show success message
    if (typeof __ofShowToast === 'function') {
        __ofShowToast('下載開始', `已將 ${selectedVideos.length} 部影片加入下載佇列`);
    }
}

/**
 * Close playlist modal
 */
function closePlaylistModal() {
    const playlistModalBg = document.getElementById('playlist-modal-bg');
    if (playlistModalBg && typeof closePopupOverlay === 'function') {
        closePopupOverlay(playlistModalBg);
    }
}
