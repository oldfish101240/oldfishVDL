/**
 * Custom Select Dropdown Module
 * Handles custom select dropdown interactions
 */

/**
 * Toggle custom select dropdown
 */
function toggleSelect(selectId) {
    const select = document.getElementById(selectId);
    if (!select || select.classList.contains('disabled')) return;
    
    const options = select.querySelector('.custom-select-options');
    const header = select.querySelector('.custom-select-header');
    
    if (!options || !header) return;
    
    // Close other custom selects
    document.querySelectorAll('.custom-select').forEach(s => {
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
        clearSelectOptionsPosition(select);
    } else {
        options.classList.add('show');
        header.classList.add('active');
        positionSelectOptions(select);
    }
}

/**
 * Select option from custom select
 */
function selectOption(selectId, value, displayText) {
    const select = document.getElementById(selectId);
    if (!select) return;
    
    const header = select.querySelector('.custom-select-header');
    const textSpan = header ? header.querySelector('.custom-select-text') : null;
    const options = select.querySelector('.custom-select-options');
    
    // Update display text
    if (textSpan) {
        textSpan.textContent = displayText;
    }
    
    // Update selected state
    const optionItems = options.querySelectorAll('.custom-select-option');
    optionItems.forEach(item => {
        item.classList.remove('selected');
        if (item.textContent === displayText) {
            item.classList.add('selected');
        }
    });
    
    // Update current values based on select type
    if (selectId === 'quality-select') {
        currentQuality = value;
    } else if (selectId === 'format-select') {
        currentFormat = value;
        // Update quality options based on format
        updateQualityOptionsForFormat(value);
    }
    
    // Close dropdown
    options.classList.remove('show');
    header.classList.remove('active');
    clearSelectOptionsPosition(select);
}

/**
 * Update quality options based on selected format
 */
function updateQualityOptionsForFormat(format) {
    const qualityOptions = document.getElementById('quality-options');
    const qualityLabel = document.getElementById('video-modal-quality-label');
    
    if (!qualityOptions) return;
    
    const audioTypes = ['mp3', 'aac', 'flac', 'wav'];
    const isAudio = audioTypes.includes(format);
    
    if (qualityLabel) {
        qualityLabel.textContent = isAudio ? '位元率' : '畫質';
    }
    
    if (isAudio) {
        // Audio format: show audio quality options
        qualityOptions.innerHTML = AUDIO_QUALITIES.map(q => 
            `<div class="custom-select-option" onclick="selectOption('quality-select', '${q.value}', '${q.label}')">${q.label}</div>`
        ).join('');
        
        // Set default to 192kbps
        currentQuality = '192';
        const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
        if (qualitySelectText) qualitySelectText.textContent = '192kbps';
    } else {
        // Video format: show video quality options from lastVideoInfo
        if (lastVideoInfo && lastVideoInfo.qualities) {
            const qualities = lastVideoInfo.qualities.filter(q => {
                function getValue(q) {
                    if (q.label.endsWith('K')) return parseInt(q.label) * 1000;
                    var m = q.label.match(/(\d+)p/);
                    return m ? parseInt(m[1]) : 0;
                }
                return getValue(q) >= 360;
            });
            
            qualities.sort(function(a, b) {
                function getValue(q) {
                    if (q.label.endsWith('K')) return parseInt(q.label) * 1000;
                    var m = q.label.match(/(\d+)p/);
                    return m ? parseInt(m[1]) : 0;
                }
                return getValue(b) - getValue(a);
            });
            
            qualityOptions.innerHTML = qualities.map(q => 
                `<div class="custom-select-option" onclick="selectOption('quality-select', '${q.label}', '${q.label + (q.ratio ? ' ' + q.ratio : '')}')">${q.label + (q.ratio ? ' ' + q.ratio : '')}</div>`
            ).join('');
            
            // Set default to 1080p or first available
            currentQuality = qualities.length > 0 ? qualities[0].label : '1080p';
            const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
            if (qualitySelectText) {
                qualitySelectText.textContent = currentQuality + (qualities[0]?.ratio ? ' ' + qualities[0].ratio : '');
            }
        } else {
            // Fallback to default video qualities
            qualityOptions.innerHTML = `
                <div class="custom-select-option" onclick="selectOption('quality-select', '1080p', '1080p')">1080p</div>
                <div class="custom-select-option" onclick="selectOption('quality-select', '720p', '720p')">720p</div>
                <div class="custom-select-option" onclick="selectOption('quality-select', '480p', '480p')">480p</div>
                <div class="custom-select-option" onclick="selectOption('quality-select', '360p', '360p')">360p</div>
            `;
            currentQuality = '1080p';
            const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
            if (qualitySelectText) qualitySelectText.textContent = '1080p';
        }
    }
}

/**
 * Position select options to avoid viewport overflow
 */
function positionSelectOptions(select) {
    const options = select.querySelector('.custom-select-options');
    if (!options) return;
    
    const selectRect = select.getBoundingClientRect();
    const optionsHeight = options.scrollHeight;
    const viewportHeight = window.innerHeight;
    const spaceBelow = viewportHeight - selectRect.bottom;
    const spaceAbove = selectRect.top;
    
    // Reset position
    options.style.position = 'absolute';
    options.style.top = '100%';
    options.style.bottom = 'auto';
    options.style.maxHeight = '200px';
    
    // If not enough space below, show above
    if (spaceBelow < optionsHeight && spaceAbove > spaceBelow) {
        options.style.position = 'absolute';
        options.style.top = 'auto';
        options.style.bottom = '100%';
    }
}

/**
 * Clear select options positioning
 */
function clearSelectOptionsPosition(select) {
    const options = select.querySelector('.custom-select-options');
    if (!options) return;
    
    options.style.position = '';
    options.style.top = '';
    options.style.bottom = '';
}

/**
 * Close custom select
 */
function closeCustomSelect(select) {
    if (!select) return;
    
    const options = select.querySelector('.custom-select-options');
    const header = select.querySelector('.custom-select-header');
    
    if (options) options.classList.remove('show');
    if (header) header.classList.remove('active');
    clearSelectOptionsPosition(select);
}

/**
 * Close all custom selects
 */
function closeAllCustomSelects() {
    document.querySelectorAll('.custom-select').forEach(select => {
        closeCustomSelect(select);
    });
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(event) {
    const qualitySelect = document.getElementById('quality-select');
    const formatSelect = document.getElementById('format-select');
    
    // Only handle quality and format select when video modal is shown
    const videoModal = document.getElementById('video-modal-bg');
    if (videoModal && videoModal.classList.contains('show')) {
        if (qualitySelect && !qualitySelect.contains(event.target)) {
            closeCustomSelect(qualitySelect);
        }
        if (formatSelect && !formatSelect.contains(event.target)) {
            closeCustomSelect(formatSelect);
        }
    }
    
    // Close playlist dropdowns
    const playlistModal = document.getElementById('playlist-modal-bg');
    if (playlistModal && playlistModal.style.display !== 'none') {
        const allPlaylistSelects = document.querySelectorAll('.playlist-video-controls .custom-select');
        allPlaylistSelects.forEach(select => {
            if (!select.contains(event.target)) {
                closeCustomSelect(select);
            }
        });
    }
});
