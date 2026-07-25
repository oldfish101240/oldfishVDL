/**
 * Main Application Logic
 * Handles page navigation, settings, and core application functionality
 */

// Page cache for dynamic content loading
const pageCache = {};
let activePageName = null;
let pageTransitionId = 0;

/**
 * Load page content from external HTML file
 */
async function loadPageContent(pageName) {
    const pageContent = document.getElementById('page-content');
    
    // Return cached content if available
    if (pageCache[pageName]) {
        return pageCache[pageName];
    }
    
    // Load page content from file
    try {
        const response = await fetch(`pages/${pageName}.html`);
        if (!response.ok) throw new Error(`Failed to load ${pageName}`);
        const html = await response.text();
        pageCache[pageName] = html;
        return html;
    } catch (error) {
        console.error('Error loading page:', error);
        return `<div style="padding: 40px; text-align: center; color: var(--of-text-muted);">載入失敗</div>`;
    }
}

/**
 * Show a specific page with animation
 */
async function showPage(pageName) {
    const pageContent = document.getElementById('page-content');
    if (!pageContent || (activePageName === pageName && pageContent.children.length)) return;
    activePageName = pageName;
    const transitionId = ++pageTransitionId;
    // Update navigation selection state
    document.getElementById('nav-home').classList.remove('selected');
    document.getElementById('nav-queue').classList.remove('selected');
    document.getElementById('nav-settings').classList.remove('selected');
    const navAbout = document.getElementById('nav-about');
    if (navAbout) navAbout.classList.remove('selected');

    // Set current page navigation as selected
    if (pageName === 'home') {
        document.getElementById('nav-home').classList.add('selected');
    } else if (pageName === 'queue') {
        document.getElementById('nav-queue').classList.add('selected');
    } else if (pageName === 'settings') {
        document.getElementById('nav-settings').classList.add('selected');
    } else if (pageName === 'about') {
        const navA = document.getElementById('nav-about');
        if (navA) navA.classList.add('selected');
    }

    const mainEl = document.querySelector('.main');

    // Set scroll behavior
    if (mainEl) {
        if (pageName === 'home') {
            mainEl.style.overflowY = 'auto';
        } else if (pageName === 'settings') {
            mainEl.style.overflowY = 'auto';
        } else {
            mainEl.style.overflowY = 'hidden';
        }
    }

    // Fade out current content
    pageContent.classList.add('fade-out');
    
    // Wait for fade-out animation
    await new Promise(resolve => setTimeout(resolve, 120));
    if (transitionId !== pageTransitionId) return;
    
    // Load new page content
    const html = await loadPageContent(pageName);
    if (transitionId !== pageTransitionId) return;
    pageContent.innerHTML = html;
    
    // Fade in new content
    pageContent.classList.remove('fade-out');
    pageContent.classList.add('fade-in');
    
    // Remove fade-in class after animation
    setTimeout(() => {
        pageContent.classList.remove('fade-in');
    }, 120);

    // Page-specific initialization
    if (pageName === 'queue') {
        if (typeof renderQueue === 'function') renderQueue();
        // Show queue page bottom bar animation
        setTimeout(() => {
            const queueBottom = document.querySelector('.queue-bottom');
            if (queueBottom) queueBottom.classList.add('visible');
        }, 400);
    } else if (pageName === 'settings') {
        if (typeof loadSettings === 'function') loadSettings();
        // Show settings page bottom bar animation
        setTimeout(() => {
            const settingsBottom = document.querySelector('.settings-fixed-bottom');
            if (settingsBottom) settingsBottom.classList.add('visible');
        }, 100);
    } else if (pageName === 'about') {
        // Inject version number and GitHub link
        try { document.getElementById('about-version').textContent = (window.__APP_VERSION || '未知'); } catch(e) {}
        try {
            var link = document.getElementById('about-github');
            if (link) {
                link.addEventListener('click', function(ev){
                    ev.preventDefault();
                    // Open with system default browser
                    try {
                        window.api.open_external_link('https://github.com/oldfish101240/oldfish-Video-Downloader');
                    } catch(e) {
                        console.error('無法開啟外部連結:', e);
                        // Fallback
                        try { window.open('https://github.com/oldfish101240/oldfish-Video-Downloader', '_blank'); } catch(_) {}
                    }
                });
            }
        } catch(e) {}
    }

    // Hide bottom bars that do not belong to the active page.  Previously this
    // also hid the queue/settings bar immediately after scheduling it to show.
    const queueBottom = document.querySelector('.queue-bottom');
    const settingsBottom = document.querySelector('.settings-fixed-bottom');
    if (pageName !== 'queue' && queueBottom) queueBottom.classList.remove('visible');
    if (pageName !== 'settings' && settingsBottom) settingsBottom.classList.remove('visible');

    // Bind page-specific events
    if (typeof bindPageEvents === 'function') bindPageEvents(pageName);

    // Reinitialize dev command hints (since page content is dynamically loaded)
    requestAnimationFrame(() => {
        try { 
            if (typeof initDevCommandInputHints === 'function') initDevCommandInputHints(); 
        } catch (eDevReinit) { 
            console.warn('重新初始化 dev command hints 失敗:', eDevReinit); 
        }
    });
}

/**
 * Load settings from backend
 */
function loadSettings() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.load_settings()
            .then(settings => {
                console.log('設定已載入:', settings);
                window.__ofNotificationsEnabled = settings.enableNotifications !== false;
                
                // Update UI
                const notificationCheckbox = document.getElementById('enable-notifications');
                if (notificationCheckbox) {
                    notificationCheckbox.checked = settings.enableNotifications !== false;
                }
                
                const resolutionCheckbox = document.getElementById('add-resolution-to-filename');
                if (resolutionCheckbox) {
                    resolutionCheckbox.checked = settings.addResolutionToFilename === true;
                }

                const maxConcInput = document.getElementById('max-concurrent-downloads');
                if (maxConcInput) {
                    let v = Number(settings.maxConcurrentDownloads || 3);
                    if (!isFinite(v)) v = 3;
                    v = Math.max(1, Math.min(10, Math.round(v)));
                    maxConcInput.value = String(v);
                }
                
                const downloadPathInput = document.getElementById('custom-download-path');
                if (downloadPathInput) {
                    downloadPathInput.value = settings.customDownloadPath || '';
                }

                // Load playlist notification mode settings
                const playlistNotifyMode = settings.playlistNotificationMode || 'complete';
                const notifyCompleteRadio = document.getElementById('playlist-notify-complete');
                const notifyEachRadio = document.getElementById('playlist-notify-each');
                if (notifyCompleteRadio) notifyCompleteRadio.checked = (playlistNotifyMode === 'complete');
                if (notifyEachRadio) notifyEachRadio.checked = (playlistNotifyMode === 'each');

                // Enable/disable playlist notification options based on notification setting
                const enabled = settings.enableNotifications !== false;
                if (notifyCompleteRadio) notifyCompleteRadio.disabled = !enabled;
                if (notifyEachRadio) notifyEachRadio.disabled = !enabled;

                if (typeof ThemeManager !== 'undefined') {
                    ThemeManager.loadThemeFromSettings(settings);
                    ThemeManager.initThemePickerEvents();
                }

                window.__ofDevCommandsEnabled = settings.enableDevCommands === true;
                window.__ofHideDevCommandEnableWarn = settings.hideDevCommandEnableWarning === true;
                const devCmdCheckbox = document.getElementById('enable-dev-commands');
                if (devCmdCheckbox) {
                    devCmdCheckbox.checked = settings.enableDevCommands === true;
                }
                
                // Add auto-save event listeners for settings
                setupAutoSaveListeners();
            })
            .catch(error => {
                console.error('載入設定失敗:', error);
            });
    }
}

/**
 * Setup auto-save event listeners for settings
 */
function setupAutoSaveListeners() {
    // Prevent duplicate event listeners
    if (window._listenersSetup) {
        return;
    }
    window._listenersSetup = true;
    
    // Add change listener for notification setting
    const notificationCheckbox = document.getElementById('enable-notifications');
    if (notificationCheckbox && !notificationCheckbox.hasAttribute('data-listener-added')) {
        notificationCheckbox.addEventListener('change', function() {
            console.log('通知設定已變更，自動儲存中...');
            window.__ofNotificationsEnabled = !!this.checked;
            // Enable/disable playlist notification options
            const notifyCompleteRadio = document.getElementById('playlist-notify-complete');
            const notifyEachRadio = document.getElementById('playlist-notify-each');
            const enabled = !!this.checked;
            if (notifyCompleteRadio) notifyCompleteRadio.disabled = !enabled;
            if (notifyEachRadio) notifyEachRadio.disabled = !enabled;
            if (typeof saveSettings === 'function') saveSettings(true); // Silent save
        });
        notificationCheckbox.setAttribute('data-listener-added', 'true');
    }

    // Add change listener for resolution setting
    const resolutionCheckbox = document.getElementById('add-resolution-to-filename');
    if (resolutionCheckbox && !resolutionCheckbox.hasAttribute('data-listener-added')) {
        resolutionCheckbox.addEventListener('change', function() {
            console.log('解析度設定已變更，自動儲存中...');
            if (typeof saveSettings === 'function') saveSettings(true);
        });
        resolutionCheckbox.setAttribute('data-listener-added', 'true');
    }

    // Add change listener for max concurrent downloads
    const maxConcInput = document.getElementById('max-concurrent-downloads');
    if (maxConcInput && !maxConcInput.hasAttribute('data-listener-added')) {
        maxConcInput.addEventListener('change', function() {
            let v = Number(this.value);
            if (!isFinite(v)) v = 3;
            v = Math.max(1, Math.min(10, Math.round(v)));
            this.value = String(v);
            console.log('最大並發下載數已變更，自動儲存中...');
            if (typeof saveSettings === 'function') saveSettings(true);
        });
        maxConcInput.setAttribute('data-listener-added', 'true');
    }

    // Add change listener for custom download path
    const downloadPathInput = document.getElementById('custom-download-path');
    if (downloadPathInput && !downloadPathInput.hasAttribute('data-listener-added')) {
        downloadPathInput.addEventListener('change', function() {
            console.log('自訂下載路徑已變更，自動儲存中...');
            if (typeof saveSettings === 'function') saveSettings(true);
        });
        downloadPathInput.setAttribute('data-listener-added', 'true');
    }

    // Add change listener for playlist notification mode
    const notifyCompleteRadio = document.getElementById('playlist-notify-complete');
    const notifyEachRadio = document.getElementById('playlist-notify-each');
    
    if (notifyCompleteRadio && !notifyCompleteRadio.hasAttribute('data-listener-added')) {
        notifyCompleteRadio.addEventListener('change', function() {
            if (this.checked) {
                console.log('播放清單通知模式已變更為「完成時通知」，自動儲存中...');
                if (typeof saveSettings === 'function') saveSettings(true);
            }
        });
        notifyCompleteRadio.setAttribute('data-listener-added', 'true');
    }
    
    if (notifyEachRadio && !notifyEachRadio.hasAttribute('data-listener-added')) {
        notifyEachRadio.addEventListener('change', function() {
            if (this.checked) {
                console.log('播放清單通知模式已變更為「每部影片通知」，自動儲存中...');
                if (typeof saveSettings === 'function') saveSettings(true);
            }
        });
        notifyEachRadio.setAttribute('data-listener-added', 'true');
    }

    // Add change listener for dev commands
    const devCmdCheckbox = document.getElementById('enable-dev-commands');
    if (devCmdCheckbox && !devCmdCheckbox.hasAttribute('data-listener-added')) {
        devCmdCheckbox.addEventListener('change', function() {
            if (this.checked && !window.__ofHideDevCommandEnableWarn) {
                if (typeof openDevCommandEnableWarningModal === 'function') {
                    openDevCommandEnableWarningModal();
                } else {
                    this.checked = false;
                }
            } else if (this.checked) {
                window.__ofDevCommandsEnabled = true;
                console.log('Dev Commands 已啟用，自動儲存中...');
                if (typeof saveSettings === 'function') saveSettings(true);
                try { 
                    if (typeof refreshAllDevCommandHints === 'function') refreshAllDevCommandHints(); 
                } catch (eDw) {}
            } else {
                window.__ofDevCommandsEnabled = false;
                console.log('Dev Commands 已停用，自動儲存中...');
                if (typeof saveSettings === 'function') saveSettings(true);
                try { 
                    if (typeof refreshAllDevCommandHints === 'function') refreshAllDevCommandHints(); 
                } catch (eDw) {}
            }
        });
        devCmdCheckbox.setAttribute('data-listener-added', 'true');
    }
}

/**
 * Save settings to backend
 */
function saveSettings(silent = false) {
    const settings = {
        enableNotifications: window.__ofNotificationsEnabled,
        addResolutionToFilename: document.getElementById('add-resolution-to-filename')?.checked || false,
        maxConcurrentDownloads: Number(document.getElementById('max-concurrent-downloads')?.value) || 3,
        customDownloadPath: document.getElementById('custom-download-path')?.value || '',
        playlistNotificationMode: document.getElementById('playlist-notify-each')?.checked ? 'each' : 'complete',
        enableDevCommands: window.__ofDevCommandsEnabled,
        hideDevCommandEnableWarning: window.__ofHideDevCommandEnableWarn
    };

    if (typeof ThemeManager !== 'undefined') {
        const themeSettings = ThemeManager.getThemeSettings();
        settings.themeMode = themeSettings.themeMode;
        settings.themeAccent = themeSettings.themeAccent;
    }

    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.save_settings(settings)
            .then(() => {
                if (!silent) {
                    console.log('設定已儲存');
                }
            })
            .catch(error => {
                console.error('儲存設定失敗:', error);
                if (!silent) {
                    if (typeof showModal === 'function') {
                        showModal('錯誤', '儲存設定失敗');
                    }
                }
            });
    }
}

/**
 * Bind page-specific events
 */
function bindPageEvents(pageName) {
    if (pageName === 'home') {
        const urlInput = document.getElementById('video-url');
        if (urlInput) {
            urlInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    if (typeof downloadVideo === 'function') downloadVideo();
                }
            });
        }
    } else if (pageName === 'queue') {
        const urlInput = document.getElementById('queue-video-url');
        if (urlInput) {
            urlInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    if (typeof downloadVideoFromQueue === 'function') downloadVideoFromQueue();
                }
            });
        }
    }
}

/**
 * Handle queue input Enter key press
 */
function handleQueueInputKeyPress(event) {
    if (event.key === 'Enter') {
        if (typeof downloadVideoFromQueue === 'function') downloadVideoFromQueue();
    }
}

/**
 * Check critical functions on startup
 */
function checkCriticalFunctions() {
    const functions = ['showPage', 'renderQueue', 'showModal', 'showConfirmModal', 'closeConfirmModal'];
    const missing = [];
    functions.forEach(func => {
        if (typeof window[func] !== 'function') {
            missing.push(func);
            console.error('[函數檢查] 函數未定義:', func);
        } else {
            console.log('[函數檢查] 函數已定義:', func);
        }
    });
    if (missing.length > 0) {
        console.error('[函數檢查] 缺少以下函數:', missing.join(', '));
    }
}

// Run critical function check when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkCriticalFunctions);
} else {
    checkCriticalFunctions();
}

// The page-content container starts empty.  Render the selected home page once
// the static shell has been parsed, instead of waiting for the user to switch
// away and back.
function initializeInitialPage() {
    showPage('home').catch(error => {
        console.error('初始主頁載入失敗:', error);
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeInitialPage, { once: true });
} else {
    initializeInitialPage();
}
