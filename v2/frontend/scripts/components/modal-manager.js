/**
 * Modal Manager Module
 * Handles all modal/popup overlay interactions
 */

// 重用既有 overlay；取消尚未完成的關閉計時，避免快速開關時閃爍或錯誤隱藏。
const popupCloseTimers = new WeakMap();

/** Open a popup overlay with animation. */
function openPopupOverlay(overlay) {
    if (!overlay) return;
    const closeTimer = popupCloseTimers.get(overlay);
    if (closeTimer) clearTimeout(closeTimer);
    overlay.style.display = 'flex';
    requestAnimationFrame(() => {
        overlay.classList.add('show');
    });
}

/**
 * Close a popup overlay with animation
 */
function closePopupOverlay(overlay) {
    if (!overlay) return;
    overlay.classList.remove('show');
    const closeTimer = setTimeout(() => {
        if (!overlay.classList.contains('show')) overlay.style.display = 'none';
        popupCloseTimers.delete(overlay);
    }, 180);
    popupCloseTimers.set(overlay, closeTimer);
}

/**
 * Show a simple modal with title and message
 */
function showModal(title, message, onConfirm = null) {
    const modalBg = document.getElementById('modal-bg');
    if (!modalBg) return;
    
    const modalTitle = document.getElementById('modal-title');
    const modalMsg = document.getElementById('modal-msg');
    const modalBtn = document.getElementById('modal-btn');
    
    if (modalTitle) modalTitle.textContent = title;
    if (modalMsg) modalMsg.textContent = message;
    
    if (modalBtn) {
        modalBtn.onclick = function() {
            closePopupOverlay(modalBg);
            if (onConfirm) onConfirm();
        };
    }
    
    openPopupOverlay(modalBg);
}

/**
 * Show a confirmation modal with yes/no buttons
 */
function showConfirmModal(title, message, onConfirm, onCancel = null) {
    const modalBg = document.getElementById('modal-bg');
    if (!modalBg) return;
    
    const modalTitle = document.getElementById('modal-title');
    const modalMsg = document.getElementById('modal-msg');
    const modalButtons = document.getElementById('modal-buttons');
    const modalBtnPrimary = document.getElementById('modal-btn-primary');
    const modalBtnSecondary = document.getElementById('modal-btn-secondary');
    const modalBtn = document.getElementById('modal-btn');
    
    if (modalTitle) modalTitle.textContent = title;
    if (modalMsg) modalMsg.textContent = message;
    
    // Hide single button, show buttons container
    if (modalBtn) modalBtn.style.display = 'none';
    if (modalButtons) modalButtons.style.display = 'flex';
    
    if (modalBtnPrimary) {
        modalBtnPrimary.onclick = function() {
            closePopupOverlay(modalBg);
            if (onConfirm) onConfirm();
        };
    }
    
    if (modalBtnSecondary) {
        modalBtnSecondary.onclick = function() {
            closePopupOverlay(modalBg);
            if (onCancel) onCancel();
        };
    }
    
    openPopupOverlay(modalBg);
}

/**
 * Close the modal
 */
function closeModal() {
    const modalBg = document.getElementById('modal-bg');
    if (modalBg) closePopupOverlay(modalBg);
}

/**
 * Close the video modal
 */
function closeVideoModal() {
    const videoModalBg = document.getElementById('video-modal-bg');
    if (videoModalBg) closePopupOverlay(videoModalBg);
}

/**
 * Close the playlist modal
 */
function closePlaylistModal() {
    const playlistModalBg = document.getElementById('playlist-modal-bg');
    if (playlistModalBg) closePopupOverlay(playlistModalBg);
}

/**
 * Close the playlist duplicate modal
 */
function closePlaylistDuplicateModal() {
    const playlistDuplicateOverlay = document.getElementById('playlist-duplicate-overlay');
    if (playlistDuplicateOverlay) closePopupOverlay(playlistDuplicateOverlay);
}

/**
 * Initialize modal close buttons
 */
function initModalCloseButtons() {
    // Video modal close button
    const videoModalClose = document.getElementById('video-modal-close');
    if (videoModalClose) {
        videoModalClose.onclick = closeVideoModal;
    }
    
    // Playlist modal close button
    const playlistModalClose = document.getElementById('playlist-modal-close');
    if (playlistModalClose) {
        playlistModalClose.onclick = closePlaylistModal;
    }
    
    // Modal close button
    const modalClose = document.getElementById('modal-close');
    if (modalClose) {
        modalClose.onclick = closeModal;
    }
    
    // Close modals on overlay click
    document.querySelectorAll('.app-modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                closePopupOverlay(overlay);
            }
        });
    });
    
    // Close modals on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            document.querySelectorAll('.app-modal-overlay.show').forEach(overlay => {
                closePopupOverlay(overlay);
            });
        }
    });
}

// Initialize modal close buttons when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModalCloseButtons);
} else {
    initModalCloseButtons();
}
