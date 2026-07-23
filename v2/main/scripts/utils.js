/**
 * Utility Functions Module
 * Contains helper functions used throughout the application
 */

// Global variables
let downloadQueue = [];
let nextTaskId = 0;
window.__ofDevCommandsEnabled = false;
window.__ofHideDevCommandEnableWarn = false;
window.__ofNotificationsEnabled = true;

// Audio quality options for MP3, AAC, FLAC, WAV
const AUDIO_QUALITIES = [
    {label: "320kbps", value: "320"},
    {label: "256kbps", value: "256"},
    {label: "192kbps", value: "192"},
    {label: "128kbps", value: "128"}
];

// Dev command constants
const DEV_RICK_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
const DEV_RICK_PLAYLIST_URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ';
const DEV_RICK_THUMB = 'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg';
const DEV_UI_VIDEOS_PER_PLAYLIST = 2;
const DEV_CMD_VQ = ['--360', '--480', '--720', '--1080', '--1440', '--2160', '--4k'];
const DEV_CMD_AQ = ['--96', '--128', '--192', '--256', '--320'];

/**
 * Escape HTML special characters to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

/**
 * Sort video qualities from high to low
 * Handles "4K", "1080p", "720p", "360p", "2K", etc.
 */
function sortQualities(qualities) {
    return (qualities || []).slice().sort(function(a, b) {
        function getNum(s) {
            if (typeof s.label === "string") {
                if (s.label.endsWith("K")) {
                    let num = parseInt(s.label);
                    return !isNaN(num) ? num * 1000 : 0;
                }
                if (s.label.endsWith("p")) {
                    let num = parseInt(s.label);
                    return !isNaN(num) ? num : 0;
                }
            }
            let num = parseInt(s.label);
            return !isNaN(num) ? num : 0;
        }
        return getNum(b) - getNum(a);
    });
}

/**
 * Sort formats, prioritizing "mp4" and "mp3"
 */
function sortFormats(formats) {
    const priority = {"影片+音訊": 3, "影片": 2, "音訊": 1};
    return (formats || []).slice().sort(function(a, b) {
        let pa = priority[a.desc] || 0;
        let pb = priority[b.desc] || 0;
        if (pa !== pb) return pb - pa;
        return a.value.localeCompare(b.value);
    });
}

/**
 * Check if URL is a valid YouTube URL
 */
function isYoutubeUrl(url) {
    return /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\//.test(url.trim());
}

/**
 * Get backend API (Qt WebChannel or pywebview)
 */
function __getBackendApi() {
    try {
        if (window.api) return window.api;
        if (window.pywebview && window.pywebview.api) return window.pywebview.api;
    } catch(e) {}
    return null;
}

/**
 * Normalize filename for display by converting special Unicode characters
 * e.g., ⧸ → /, ⧹ → \
 */
function normalizeFilenameForDisplay(filename) {
    if (!filename) return filename;
    const replacements = {
        '⧸': '/',   // U+2FF8
        '⧹': '\\',  // U+2FF9
        '／': '/',  // 全形斜杠
        '＼': '\\', // 全形反斜杠
        '：': ':',  // 全形冒號
        '？': '?',  // 全形問號
        '＊': '*',  // 全形星號
        '＂': '"',  // 全形雙引號
        '＜': '<',  // 全形小於
        '＞': '>',  // 全形大於
        '｜': '|',  // 全形豎線
    };
    return filename.replace(/[⧸⧹／＼：？＊＂＜＞｜]/g, (char) => replacements[char] || char);
}

/**
 * Console redirection to Python backend
 */
(function() {
    const CONSOLE_MIN_LEVEL = 'warn';
    const levelPriority = { debug: 10, info: 20, log: 20, warn: 30, error: 40 };
    const minPriority = levelPriority[CONSOLE_MIN_LEVEL] || levelPriority.warn;

    const originalConsole = {
        log: console.log.bind(console),
        error: console.error.bind(console),
        warn: console.warn.bind(console),
        info: console.info.bind(console),
        debug: console.debug.bind(console)
    };
    
    function sendLogToPython(level, args) {
        try {
            const message = Array.from(args).map(arg => {
                if (typeof arg === 'object') {
                    try {
                        return JSON.stringify(arg);
                    } catch (e) {
                        return String(arg);
                    }
                }
                return String(arg);
            }).join(' ');
            
            if (window.api && typeof window.api.log_from_js === 'function') {
                window.api.log_from_js(level, message).catch(err => {
                    originalConsole.error('[日誌發送失敗]', err);
                });
            }
        } catch (e) {
            originalConsole.error('[日誌重定向錯誤]', e);
        }
    }
    
    function shouldOutput(level) {
        return (levelPriority[level] || 0) >= minPriority;
    }

    console.log = function(...args) {
        if (!shouldOutput('log')) return;
        originalConsole.log(...args);
        sendLogToPython('log', args);
    };
    
    console.error = function(...args) {
        originalConsole.error(...args);
        sendLogToPython('error', args);
    };
    
    console.warn = function(...args) {
        if (!shouldOutput('warn')) return;
        originalConsole.warn(...args);
        sendLogToPython('warn', args);
    };
    
    console.info = function(...args) {
        if (!shouldOutput('info')) return;
        originalConsole.info(...args);
        sendLogToPython('info', args);
    };
    
    console.debug = function(...args) {
        if (!shouldOutput('debug')) return;
        originalConsole.debug(...args);
        sendLogToPython('debug', args);
    };
    
    if (shouldOutput('info')) {
        originalConsole.info('[前端] Console 輸出已重定向到 Python 端');
    }
})();

/**
 * Global error handler
 */
window.addEventListener('error', function(e) {
    console.error('[全局錯誤]', e.message, 'at', e.filename, ':', e.lineno, ':', e.colno);
    console.error('[錯誤堆棧]', e.error ? e.error.stack : '無堆棧信息');
});

/**
 * Show loading overlay
 */
function showLoading() {
    var lb = document.getElementById('loading-bg');
    if (lb) { lb.style.display = 'flex'; }
}

/**
 * Hide loading overlay
 */
function hideLoading() {
    var lb = document.getElementById('loading-bg');
    if (lb) { lb.style.display = 'none'; }
}

/**
 * Toggle sidebar collapse state
 */
function toggleSidebar() {
    var sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed');
}

/**
 * Toast notification function
 */
window.__ofShowToast = function(title, message, variant = 'success') {
    try {
        if (!window.__ofNotificationsEnabled) {
            return;
        }
        const container = document.getElementById('toast-container');
        if (!container) {
            console.warn('toast container missing');
            return;
        }

        const toast = document.createElement('div');
        toast.className = `toast-item ${variant || 'success'}`.trim();

        const titleEl = document.createElement('div');
        titleEl.className = 'toast-title';
        const iconWrap = document.createElement('span');
        iconWrap.className = 'toast-icon-badge';
        iconWrap.textContent = '✓';
        const titleText = document.createElement('span');
        titleText.textContent = title || '通知';
        titleEl.appendChild(iconWrap);
        titleEl.appendChild(titleText);

        const msgEl = document.createElement('div');
        msgEl.className = 'toast-message';
        msgEl.textContent = message || '';

        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.setAttribute('aria-label', '關閉通知');
        closeBtn.innerHTML = '&times;';

        const progressBar = document.createElement('div');
        progressBar.className = 'toast-progress';
        const progress = document.createElement('span');
        progressBar.appendChild(progress);

        toast.appendChild(titleEl);
        toast.appendChild(msgEl);
        toast.appendChild(closeBtn);
        toast.appendChild(progressBar);

        container.appendChild(toast);

        const hideToast = () => {
            toast.style.animation = 'toastFadeOut 0.35s forwards';
            setTimeout(() => {
                toast.remove();
            }, 320);
        };

        const autoTimer = setTimeout(hideToast, 4500);

        closeBtn.addEventListener('click', () => {
            clearTimeout(autoTimer);
            hideToast();
        });

    } catch (err) {
        console.error('顯示 Toast 失敗', err);
    }
};

/**
 * Clipboard functions
 */
function setClipboardText(text) {
    const textValue = String(text ?? '');
    if (window.api && window.api.set_clipboard_text) {
        try { window.api.set_clipboard_text(textValue); } catch (_) {}
        return true;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textValue).catch(() => {});
        return true;
    }
    return false;
}

function getClipboardText() {
    if (window.api && window.api.get_clipboard_text) {
        try { return window.api.get_clipboard_text(); } catch (_) {}
    }
    if (navigator.clipboard && navigator.clipboard.readText) {
        return navigator.clipboard.readText();
    }
    return Promise.resolve('');
}

function tryCopyText(text) {
    if (text == null || text === '') return;
    const textValue = String(text);
    if (setClipboardText(textValue)) return;
    const temp = document.createElement('textarea');
    temp.value = textValue;
    document.body.appendChild(temp);
    temp.select();
    try { document.execCommand('copy'); } catch (_) {}
    document.body.removeChild(temp);
}
