/**
 * OFTheme — 集中管理主題色調與衍生色 token
 * 所有 accent 相關 CSS 變數由此模組寫入 :root
 */
(function (global) {
    'use strict';

    const DEFAULT = '#3498db';
    const PRESETS = [
        { id: 'green', label: '綠色', color: '#2ecc71' },
        { id: 'blue', label: '藍色', color: '#3498db' },
        { id: 'purple', label: '紫色', color: '#9b59b6' },
        { id: 'orange', label: '橙色', color: '#e67e22' },
        { id: 'pink', label: '粉色', color: '#e91e63' },
        { id: 'cyan', label: '青色', color: '#1abc9c' },
        { id: 'red', label: '紅色', color: '#e74c3c' },
    ];

    const MIX_BASE_DARK = '#0f1419';
    const MIX_BASE_UI = '#16181d';

    function clamp(n) {
        return Math.max(0, Math.min(255, Math.round(n)));
    }

    function normalizeHex(hex) {
        if (!hex || typeof hex !== 'string') return DEFAULT;
        let h = hex.trim().toLowerCase();
        if (!h.startsWith('#')) h = '#' + h;
        if (/^#[0-9a-f]{3}$/.test(h)) {
            h = '#' + h[1] + h[1] + h[2] + h[2] + h[3] + h[3];
        }
        return /^#[0-9a-f]{6}$/.test(h) ? h : DEFAULT;
    }

    function hexToRgb(hex) {
        const h = normalizeHex(hex).slice(1);
        return {
            r: parseInt(h.slice(0, 2), 16),
            g: parseInt(h.slice(2, 4), 16),
            b: parseInt(h.slice(4, 6), 16),
        };
    }

    function rgbToHex(r, g, b) {
        return (
            '#' +
            [clamp(r), clamp(g), clamp(b)]
                .map((x) => x.toString(16).padStart(2, '0'))
                .join('')
        );
    }

    function mixHex(c1, c2, t) {
        const a = hexToRgb(c1);
        const b = hexToRgb(c2);
        const w = Math.max(0, Math.min(1, t));
        return rgbToHex(
            a.r + (b.r - a.r) * w,
            a.g + (b.g - a.g) * w,
            a.b + (b.b - a.b) * w
        );
    }

    function adjustHex(hex, delta) {
        const { r, g, b } = hexToRgb(hex);
        return rgbToHex(r + delta, g + delta, b + delta);
    }

    /**
     * 依主色產生完整 accent token 表
     */
    function derivePalette(accent) {
        const base = normalizeHex(accent);
        const hover = adjustHex(base, -18);
        const dark = adjustHex(base, -32);
        const ar = hexToRgb(base);
        const hr = hexToRgb(hover);
        const rgb = `${ar.r}, ${ar.g}, ${ar.b}`;
        const hoverRgb = `${hr.r}, ${hr.g}, ${hr.b}`;

        return {
            '--of-accent': base,
            '--of-accent-hover': hover,
            '--of-accent-dark': dark,
            '--of-accent-rgb': rgb,
            '--of-accent-hover-rgb': hoverRgb,
            '--of-accent-light': mixHex(base, '#ffffff', 0.62),
            '--of-accent-lighter': mixHex(base, '#ffffff', 0.48),
            '--of-accent-active': mixHex(base, '#000000', 0.38),
            '--of-accent-muted-bg': mixHex(base, MIX_BASE_DARK, 0.88),
            '--of-accent-muted-bg-hover': mixHex(base, MIX_BASE_DARK, 0.78),
            '--of-accent-muted-border': mixHex(base, '#1a2030', 0.55),
            '--of-accent-muted-border-hover': mixHex(base, '#1a2030', 0.42),
            '--of-accent-muted-text': mixHex(base, '#ffffff', 0.78),
            '--of-accent-on-muted': mixHex(base, '#ffffff', 0.92),
            '--of-accent-on-muted-2': mixHex(base, '#ffffff', 0.85),
            '--of-accent-surface-tint': mixHex(base, MIX_BASE_UI, 0.72),
            '--of-accent-surface-tint-2': mixHex(base, MIX_BASE_UI, 0.68),
            '--of-accent-completed-bg': mixHex(base, '#ffffff', 0.9),
            '--of-accent-completed-bg-2': mixHex(base, '#ffffff', 0.94),
            '--of-accent-completed-border': `rgba(${rgb}, 0.5)`,
            '--of-accent-completed-border-2': mixHex(base, '#ffffff', 0.7),
            '--of-accent-completed-text': mixHex(base, '#000000', 0.55),
            '--of-accent-soft': `rgba(${rgb}, 0.25)`,
            '--of-accent-soft-22': `rgba(${rgb}, 0.22)`,
            '--of-accent-soft-16': `rgba(${rgb}, 0.16)`,
            '--of-accent-soft-14': `rgba(${rgb}, 0.14)`,
            '--of-accent-soft-08': `rgba(${rgb}, 0.08)`,
            '--of-accent-focus': `rgba(${rgb}, 0.2)`,
            '--of-accent-focus-30': `rgba(${rgb}, 0.3)`,
            '--of-accent-glow': `rgba(${rgb}, 0.4)`,
            '--of-accent-glow-30': `rgba(${rgb}, 0.3)`,
            '--of-accent-border-soft': `rgba(${hoverRgb}, 0.26)`,
            '--popup-theme-green': hover,
            '--popup-theme-green-hover': dark,
            '--popup-theme-green-soft': `rgba(${rgb}, 0.25)`,
            '--popup-surface-border': `rgba(${hoverRgb}, 0.26)`,
            /* 互動／面板（隨主色微調） */
            '--of-hover-neutral': mixHex(base, '#3a4150', 0.42),
            '--of-panel-bg': mixHex(base, '#171b24', 0.1),
            '--of-panel-bg-top': mixHex(base, '#1a2130', 0.12),
            '--of-panel-bg-tools': mixHex(base, '#171f2d', 0.12),
            '--of-panel-bg-body': mixHex(base, '#151922', 0.08),
            '--of-panel-bg-row': mixHex(base, '#1b2230', 0.14),
            '--of-panel-bg-row-hover': mixHex(base, '#212b3b', 0.2),
            '--of-panel-border': mixHex(base, '#2b3341', 0.35),
            '--of-panel-border-sub': mixHex(base, '#2c3645', 0.38),
            '--of-panel-border-mid': mixHex(base, '#283244', 0.36),
            '--of-panel-border-row': mixHex(base, '#303a49', 0.42),
            '--of-panel-border-row-hover': mixHex(base, '#4a5c78', 0.48),
            '--of-panel-text-title': mixHex(base, '#f8fafc', 0.15),
            '--of-panel-text-desc': mixHex(base, '#a9b6cb', 0.2),
            '--of-panel-text-master': mixHex(base, '#dbe6f7', 0.35),
            '--of-panel-text-file': mixHex(base, '#eef2ff', 0.4),
            '--of-panel-text-path': mixHex(base, '#94a3b8', 0.18),
            '--of-dev-cmd-match': mixHex(base, '#4d5564', 0.12),
            '--of-dev-cmd-rest': mixHex(base, '#93c5fd', 0.52),
            '--of-dev-cmd-border': mixHex(base, '#2a2f38', 0.3),
        };
    }

    function apply(hex) {
        const palette = derivePalette(hex);
        const root = document.documentElement;
        Object.entries(palette).forEach(([key, value]) => {
            root.style.setProperty(key, value);
        });
        global.__ofThemeColor = palette['--of-accent'];
        if (typeof global.__ofThemeSyncPicker === 'function') {
            global.__ofThemeSyncPicker(global.__ofThemeColor);
        }
        syncAppearancePreview();
        return global.__ofThemeColor;
    }

    function getColor() {
        return global.__ofThemeColor || DEFAULT;
    }

    function syncPickerUI(color) {
        const hex = normalizeHex(color);
        const picker = document.getElementById('theme-color-picker');
        if (picker) picker.value = hex;
        const hexLabel = document.getElementById('theme-color-hex');
        if (hexLabel) hexLabel.textContent = hex.toUpperCase();
        document.querySelectorAll('.theme-preset-btn').forEach((btn) => {
            const preset = normalizeHex(btn.dataset.color || '');
            btn.classList.toggle('active', preset === hex);
        });
    }

    function initSettingsUI(onChange) {
        const grid = document.getElementById('theme-preset-grid');
        if (!grid || grid.dataset.inited === '1') return;
        grid.dataset.inited = '1';

        PRESETS.forEach((p) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'theme-preset-btn';
            btn.dataset.color = p.color;
            btn.title = p.label;
            btn.setAttribute('aria-label', p.label);
            btn.style.background = p.color;
            btn.addEventListener('click', () => {
                apply(p.color);
                if (typeof onChange === 'function') onChange(p.color);
            });
            grid.appendChild(btn);
        });

        const picker = document.getElementById('theme-color-picker');
        if (picker && !picker.hasAttribute('data-listener-added')) {
            picker.addEventListener('input', function () {
                apply(this.value);
            });
            picker.addEventListener('change', function () {
                apply(this.value);
                if (typeof onChange === 'function') onChange(this.value);
            });
            picker.setAttribute('data-listener-added', 'true');
        }

        syncPickerUI(getColor());
        syncAppearancePreview();
    }

    global.__ofThemeSyncPicker = syncPickerUI;

    function syncAppearancePreview() {
        const color = normalizeHex(getColor());
        const matrix = document.getElementById('appearance-panel') || document.documentElement;
        matrix.style.setProperty('--preview-accent', color);

        const hexEl = document.getElementById('appearance-preview-hex');
        if (hexEl) hexEl.textContent = color.toUpperCase();

        const isLight = isLightMode();
        const darkCard = document.getElementById('appearance-preview-dark');
        const lightCard = document.getElementById('appearance-preview-light');

        if (darkCard) {
            darkCard.classList.toggle('active', !isLight);
            darkCard.setAttribute('aria-pressed', (!isLight).toString());
        }
        if (lightCard) {
            lightCard.classList.toggle('active', isLight);
            lightCard.setAttribute('aria-pressed', isLight.toString());
        }
    }

    function applyLightMode(enabled) {
        const on = !!enabled;
        document.body.classList.toggle('light-theme', on);
        global.__ofLightMode = on;
        syncAppearancePreview();
        return on;
    }

    function initAppearanceModeButtons(onChange) {
        const darkCard = document.getElementById('appearance-preview-dark');
        const lightCard = document.getElementById('appearance-preview-light');
        if (!darkCard || !lightCard || darkCard.dataset.inited === '1') return;
        darkCard.dataset.inited = '1';
        lightCard.dataset.inited = '1';

        function selectDark() {
            applyLightMode(false);
            if (typeof onChange === 'function') onChange(false);
        }
        function selectLight() {
            applyLightMode(true);
            if (typeof onChange === 'function') onChange(true);
        }

        darkCard.addEventListener('click', selectDark);
        lightCard.addEventListener('click', selectLight);
        syncAppearancePreview();
    }

    function isLightMode() {
        return document.body.classList.contains('light-theme');
    }

    const OFTheme = {
        DEFAULT,
        PRESETS,
        normalizeHex,
        mixHex,
        derivePalette,
        apply,
        getColor,
        applyLightMode,
        isLightMode,
        initSettingsUI,
        initAppearanceModeButtons,
        syncAppearancePreview,
        syncPickerUI,
    };

    global.OFTheme = OFTheme;
    apply(DEFAULT);
})(typeof window !== 'undefined' ? window : globalThis);
