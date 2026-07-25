/** Reusable yt-dlp update dialog. The Python API only supplies version data. */
window.OldfishUpdateDialog = (function () {
    let overlay;
    let promptView;
    let progressView;
    let doneView;
    let currentVersionEl;
    let latestVersionEl;
    let progressTip;
    let progressBar;
    let doneBadge;
    let doneTitle;
    let doneMsg;
    let doneHint;
    let doneActions;

    function ensureDialog() {
        if (overlay) return;
        overlay = document.createElement('div');
        overlay.id = 'update-dialog-overlay';
        overlay.className = 'modal-bg app-modal-overlay';
        overlay.innerHTML = [
            '<div class="modal update-dialog app-modal-surface" role="dialog" aria-modal="true">',
            '  <div class="update-dialog-prompt-view" id="update-dialog-prompt-view">',
            '    <div class="update-dialog-head">',
            '      <div class="update-dialog-icon"><img src="assets/update.png" alt="update"></div>',
            '      <h3 class="update-dialog-title">發現 yt-dlp 新版本</h3>',
            '    </div>',
            '    <div class="update-dialog-versions">',
            '      <div class="update-dialog-version-row"><span class="update-dialog-version-label">目前版本:</span><span class="update-dialog-version-value" id="update-dialog-current-version"></span></div>',
            '      <div class="update-dialog-version-row"><span class="update-dialog-version-label">最新版本:</span><span class="update-dialog-version-value update-dialog-version-value--latest" id="update-dialog-latest-version"></span></div>',
            '    </div>',
            '    <p class="update-dialog-question">是否要更新到最新版本？</p>',
            '    <p class="update-dialog-note">※yt-dlp為下載器的重要核心元件，建議更新以避免錯誤及獲得更好的使用體驗</p>',
            '    <div class="update-dialog-actions">',
            '      <button type="button" class="update-dialog-btn-secondary" id="update-dialog-later">稍後提醒</button>',
            '      <button type="button" class="update-dialog-btn-primary" id="update-dialog-action">立即更新</button>',
            '    </div>',
            '  </div>',
            '  <div class="update-dialog-progress-view" id="update-dialog-progress-view" hidden>',
            '    <div class="update-dialog-spinner"><img src="assets/update.png" alt="updating"></div>',
            '    <h3 class="update-dialog-progress-title">正在更新 yt-dlp</h3>',
            '    <p class="update-dialog-progress-tip" id="update-dialog-progress-tip">正在準備…</p>',
            '    <div class="update-dialog-progress-bar-wrap"><div class="progress-bar" id="update-dialog-progress"></div></div>',
            '  </div>',
            '  <div class="update-dialog-done-view" id="update-dialog-done-view" hidden>',
            '    <div class="update-dialog-done-badge" id="update-dialog-done-badge"><img src="assets/updated.png" alt="done"></div>',
            '    <h3 class="update-dialog-done-title" id="update-dialog-done-title"></h3>',
            '    <p class="update-dialog-done-msg" id="update-dialog-done-msg"></p>',
            '    <p class="update-dialog-done-hint" id="update-dialog-done-hint" hidden></p>',
            '    <div class="update-dialog-actions" id="update-dialog-done-actions"></div>',
            '  </div>',
            '</div>'
        ].join('');
        document.body.appendChild(overlay);

        promptView = overlay.querySelector('#update-dialog-prompt-view');
        progressView = overlay.querySelector('#update-dialog-progress-view');
        doneView = overlay.querySelector('#update-dialog-done-view');
        currentVersionEl = overlay.querySelector('#update-dialog-current-version');
        latestVersionEl = overlay.querySelector('#update-dialog-latest-version');
        progressTip = overlay.querySelector('#update-dialog-progress-tip');
        progressBar = overlay.querySelector('#update-dialog-progress');
        doneBadge = overlay.querySelector('#update-dialog-done-badge');
        doneTitle = overlay.querySelector('#update-dialog-done-title');
        doneMsg = overlay.querySelector('#update-dialog-done-msg');
        doneHint = overlay.querySelector('#update-dialog-done-hint');
        doneActions = overlay.querySelector('#update-dialog-done-actions');

        overlay.querySelector('#update-dialog-later').addEventListener('click', close);
        overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
    }

    function showView(view) {
        promptView.hidden = view !== 'prompt';
        progressView.hidden = view !== 'progress';
        doneView.hidden = view !== 'done';
    }

    function open() {
        ensureDialog();
        if (typeof openPopupOverlay === 'function') openPopupOverlay(overlay);
        else overlay.style.display = 'flex';
    }

    function close() {
        if (!overlay) return;
        if (typeof closePopupOverlay === 'function') closePopupOverlay(overlay);
        else overlay.style.display = 'none';
    }

    function show(versionInfo) {
        ensureDialog();
        currentVersionEl.textContent = versionInfo.current_version || '未知';
        latestVersionEl.textContent = versionInfo.latest_version || '未知';
        progressBar.style.width = '0%';
        progressTip.textContent = '正在準備…';
        showView('prompt');

        const actionBtn = overlay.querySelector('#update-dialog-action');
        actionBtn.onclick = () => {
            showView('progress');
            try { window.api.startYtDlpUpdate(); } catch (error) { done(false, `無法開始更新：${error}`); }
        };
        open();
    }

    function updateProgress(percent, tip) {
        ensureDialog();
        showView('progress');
        if (typeof percent === 'number') progressBar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
        if (typeof tip === 'string') progressTip.textContent = tip;
    }

    function renderDoneActions(success) {
        doneActions.innerHTML = '';
        const laterBtn = document.createElement('button');
        laterBtn.type = 'button';
        laterBtn.className = 'update-dialog-btn-secondary';
        laterBtn.textContent = success ? '稍後' : '關閉';
        laterBtn.onclick = close;
        doneActions.appendChild(laterBtn);

        if (success) {
            const restartBtn = document.createElement('button');
            restartBtn.type = 'button';
            restartBtn.className = 'update-dialog-btn-primary';
            restartBtn.textContent = '立即重啟';
            restartBtn.onclick = () => {
                close();
                try { window.api.restartApp(); } catch (error) { console.error(error); }
            };
            doneActions.appendChild(restartBtn);
        }
    }

    function done(success, text) {
        ensureDialog();
        doneBadge.classList.toggle('is-error', !success);
        doneBadge.querySelector('img').src = success ? 'assets/updated.png' : 'assets/update.png';
        doneTitle.textContent = success ? '更新完成' : '更新失敗';
        doneMsg.textContent = text || (success ? 'yt-dlp 已更新至最新版本。' : '請稍後再試或手動更新。');
        if (success) {
            doneHint.hidden = false;
            doneHint.textContent = '更新已完成，為確保生效，建議重新啟動應用程式。';
        } else {
            doneHint.hidden = true;
            doneHint.textContent = '';
        }
        renderDoneActions(success);
        showView('done');
        open();
    }

    window.__ofUpdateProgress = updateProgress;
    window.__ofUpdateDone = done;
    return { show, updateProgress, done };
})();
