/**
 * Theme Manager Module
 * Handles theme switching between dark/system modes and accent colors
 */
const ThemeManager = (function() {
    const VALID_MODES = ['dark', 'system'];
    const VALID_ACCENTS = ['green', 'blue', 'purple', 'orange'];
    let themeMode = 'dark';
    let themeAccent = 'blue';
    let systemMq = null;

    function normalizeMode(mode) {
        return VALID_MODES.includes(mode) ? mode : 'dark';
    }

    function normalizeAccent(accent) {
        return VALID_ACCENTS.includes(accent) ? accent : 'blue';
    }

    function getResolvedTheme() {
        if (themeMode === 'system') {
            try {
                return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
            } catch (e) {
                return 'dark';
            }
        }
        return 'dark';
    }

    function applyToDocument() {
        const resolved = getResolvedTheme();
        const accent = normalizeAccent(themeAccent);
        const root = document.documentElement;
        root.setAttribute('data-theme', resolved);
        root.setAttribute('data-accent', accent);
        root.setAttribute('data-theme-mode', normalizeMode(themeMode));
        document.body.classList.toggle('light-theme', resolved === 'light');
    }

    function syncThemeModeCards(mode) {
        const picker = document.getElementById('theme-mode-picker');
        if (!picker) return;
        const m = normalizeMode(mode);
        picker.querySelectorAll('.theme-mode-card').forEach(card => {
            const active = card.getAttribute('data-theme-mode') === m;
            card.classList.toggle('selected', active);
            card.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
    }

    function syncAccentSwatches(accent) {
        const picker = document.getElementById('accent-picker');
        if (!picker) return;
        const a = normalizeAccent(accent);
        picker.querySelectorAll('.accent-swatch').forEach(btn => {
            const active = btn.getAttribute('data-accent') === a;
            btn.classList.toggle('selected', active);
            btn.setAttribute('aria-pressed', active ? 'true' : 'false');
        });
    }

    function bindSystemListener() {
        if (systemMq && systemMq._ofHandler) {
            try {
                if (systemMq.removeEventListener) {
                    systemMq.removeEventListener('change', systemMq._ofHandler);
                } else if (systemMq.removeListener) {
                    systemMq.removeListener(systemMq._ofHandler);
                }
            } catch (e) { /* ignore */ }
        }
        if (themeMode !== 'system') {
            systemMq = null;
            return;
        }
        try {
            systemMq = window.matchMedia('(prefers-color-scheme: dark)');
            systemMq._ofHandler = function() {
                applyToDocument();
            };
            if (systemMq.addEventListener) {
                systemMq.addEventListener('change', systemMq._ofHandler);
            } else if (systemMq.addListener) {
                systemMq.addListener(systemMq._ofHandler);
            }
        } catch (e) {
            console.warn('[ThemeManager] 無法監聽系統主題:', e);
        }
    }

    function applyTheme(mode, accent, options) {
        const opts = options || {};
        if (mode !== undefined && mode !== null) {
            themeMode = normalizeMode(mode);
        }
        if (accent !== undefined && accent !== null) {
            themeAccent = normalizeAccent(accent);
        }
        applyToDocument();
        if (!opts.skipUi) {
            syncThemeModeCards(themeMode);
            syncAccentSwatches(themeAccent);
        }
        bindSystemListener();
    }

    function loadThemeFromSettings(settings) {
        if (!settings) return;
        applyTheme(
            settings.themeMode || 'dark',
            settings.themeAccent || 'blue'
        );
    }

    function getThemeSettings() {
        return {
            themeMode: normalizeMode(themeMode),
            themeAccent: normalizeAccent(themeAccent)
        };
    }

    function initThemePickerEvents() {
        const modePicker = document.getElementById('theme-mode-picker');
        if (modePicker && !modePicker.hasAttribute('data-listener-added')) {
            modePicker.addEventListener('click', function(ev) {
                const card = ev.target.closest('.theme-mode-card');
                if (!card) return;
                const mode = card.getAttribute('data-theme-mode');
                if (!mode) return;
                applyTheme(mode, themeAccent);
                if (typeof saveSettings === 'function') {
                    saveSettings(true);
                }
            });
            modePicker.setAttribute('data-listener-added', 'true');
        }
        const accentPicker = document.getElementById('accent-picker');
        if (accentPicker && !accentPicker.hasAttribute('data-listener-added')) {
            accentPicker.addEventListener('click', function(ev) {
                const btn = ev.target.closest('.accent-swatch');
                if (!btn) return;
                const accent = btn.getAttribute('data-accent');
                if (!accent) return;
                applyTheme(themeMode, accent);
                if (typeof saveSettings === 'function') {
                    saveSettings(true);
                }
            });
            accentPicker.setAttribute('data-listener-added', 'true');
        }
    }

    function initThemeOnStartup() {
        const root = document.documentElement;
        const injectedMode = root.getAttribute('data-theme-mode');
        const injectedAccent = root.getAttribute('data-accent');
        if (injectedMode) themeMode = normalizeMode(injectedMode);
        if (injectedAccent) themeAccent = normalizeAccent(injectedAccent);
        applyToDocument();
        syncThemeModeCards(themeMode);
        syncAccentSwatches(themeAccent);
        bindSystemListener();
        initThemePickerEvents();
    }

    function loadThemeFromApi() {
        if (window.pywebview && window.pywebview.api) {
            return window.pywebview.api.load_settings()
                .then(settings => {
                    loadThemeFromSettings(settings);
                    initThemePickerEvents();
                })
                .catch(err => {
                    console.warn('[ThemeManager] 載入主題設定失敗:', err);
                    initThemeOnStartup();
                });
        }
        initThemeOnStartup();
        return Promise.resolve();
    }

    return {
        applyTheme,
        loadThemeFromSettings,
        getThemeSettings,
        getResolvedTheme,
        initThemeOnStartup,
        initThemePickerEvents,
        loadThemeFromApi,
        syncThemeModeCards,
        syncAccentSwatches
    };
})();
