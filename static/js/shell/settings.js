/**
 * Menu de configurações (engrenagem na barra superior):
 * pasta de planilhas (alterar / atualizar lista), tema (claro, escuro,
 * automático), zoom da interface e verificação de atualizações.
 *
 * Tema e zoom ficam no config do servidor (`theme`, `ui_zoom`) e também no
 * localStorage, para o theme-boot.js aplicá-los antes da primeira pintura.
 */
import { $, html } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createMenu } from '../ui/menu.js';
import { toast } from '../ui/toast.js';
import { api } from '../api.js';
import { state, emit } from '../state.js';
import { refresh } from '../data.js';
import { openUpdatesModal } from './updates.js';

const THEME_KEY = 'mc.theme';
const ZOOM_KEY = 'mecatronicar_zoom'; // mesma chave da v2
const THEMES = [
    { value: 'light', label: 'Claro', icon: 'sun' },
    { value: 'dark', label: 'Escuro', icon: 'moon' },
    { value: 'auto', label: 'Automático', icon: 'monitor' },
];
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

function store(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch {
        /* sem armazenamento local */
    }
}

function read(key) {
    try {
        return localStorage.getItem(key);
    } catch {
        return null;
    }
}

function saveConfig(patch) {
    api.post('/api/config', patch, { timeout: 60000 }).catch((err) => {
        console.warn('Não foi possível salvar a configuração:', err);
    });
    state.update('config', (cfg) => ({ ...(cfg || {}), ...patch }));
}

/* ------------------------------ Tema ------------------------------ */

export function getThemePref() {
    const pref = document.documentElement.dataset.themePref || read(THEME_KEY) || 'light';
    return THEMES.some((t) => t.value === pref) ? pref : 'light';
}

export function applyTheme(pref) {
    const value = THEMES.some((t) => t.value === pref) ? pref : 'light';
    const dark = value === 'dark' || (value === 'auto' && darkQuery.matches);
    const root = document.documentElement;
    root.dataset.theme = dark ? 'dark' : 'light';
    root.dataset.themePref = value;
    store(THEME_KEY, value);
}

export function setTheme(pref) {
    applyTheme(pref);
    saveConfig({ theme: getThemePref() });
}

darkQuery.addEventListener('change', () => {
    if (getThemePref() === 'auto') applyTheme('auto');
});

/* ------------------------------ Zoom ------------------------------ */

let zoom = clampZoom(parseInt(read(ZOOM_KEY) || '100', 10));

function clampZoom(value) {
    const n = Number.isFinite(value) ? value : 100;
    return Math.max(50, Math.min(150, Math.round(n / 5) * 5));
}

export function getZoom() {
    return zoom;
}

export function applyZoom(value, { save = false, announce = false } = {}) {
    zoom = clampZoom(value);
    document.documentElement.style.setProperty('--ui-zoom', String(zoom / 100));
    store(ZOOM_KEY, String(zoom));
    if (save) saveConfig({ ui_zoom: zoom });
    if (announce) toast(zoom === 100 ? 'Zoom restaurado para 100%' : `Zoom ajustado para ${zoom}%`);
}

/* ------------------------------ Pasta ------------------------------ */

async function changeFolder() {
    toast('Selecione a pasta das planilhas na janela do Windows…');
    try {
        const data = await api.post('/api/select_folder', {}, { allowFailure: true, timeout: 90000 });
        if (!data.success) {
            toast('Nenhuma pasta foi alterada.');
            return;
        }
        state.update('config', (cfg) => ({ ...(cfg || {}), spreadsheet_folder: data.folder }));
        const total = data.stats?.total_files ?? '?';
        toast(`Pasta configurada. ${total} planilhas indexadas.`, 'success');
        await refresh('cars', 'patio', 'nfStats');
        emit('data:reindexed', {});
    } catch (err) {
        toast(`Erro ao selecionar a pasta: ${err.message}`, 'error');
    }
}

export async function reindex() {
    toast('Atualizando a lista de planilhas…');
    try {
        const data = await api.post('/api/reindex', {}, { timeout: 180000, errorMessage: 'Erro ao reindexar' });
        toast(`Lista atualizada: ${data.stats?.total_files ?? '?'} planilhas.`, 'success');
        await refresh('cars', 'nfStats');
        emit('data:reindexed', {});
    } catch (err) {
        toast(`Erro ao atualizar as planilhas: ${err.message}`, 'error');
    }
}

/* ------------------------------ Menu ------------------------------ */

function renderMenu() {
    const cfg = state.get('config') || {};
    const info = state.get('appInfo') || {};
    const folder = cfg.spreadsheet_folder || '';
    const pref = getThemePref();
    const totalFiles = info.stats?.total_files;

    return html`
        <div class="menu-label">Pasta de planilhas</div>
        <div class="menu-section settings-folder">
            <div class="settings-folder-path" title="${folder}">
                ${icon('folder', 16)}
                <span class="truncate">${folder || 'Nenhuma pasta selecionada'}</span>
            </div>
            ${totalFiles !== undefined ? html`<div class="settings-folder-meta">${totalFiles} planilhas indexadas</div>` : ''}
            <div class="settings-folder-actions">
                <button type="button" class="btn btn-secondary btn-sm" data-action="change-folder">${icon('folder-open', 16)} Alterar pasta</button>
                <button type="button" class="btn btn-secondary btn-sm" data-action="reindex">${icon('refresh-cw', 16)} Atualizar lista</button>
            </div>
        </div>
        <div class="menu-separator"></div>
        <div class="menu-label">Tema</div>
        <div class="menu-section">
            <div class="segmented settings-theme" role="group" aria-label="Tema">
                ${THEMES.map((t) => html`<button type="button" class="segmented-item${t.value === pref ? ' is-active' : ''}" aria-pressed="${t.value === pref ? 'true' : 'false'}" data-action="theme" data-value="${t.value}" data-keep-open>${icon(t.icon, 14)} ${t.label}</button>`)}
            </div>
        </div>
        <div class="menu-label">Tamanho da interface</div>
        <div class="menu-section settings-zoom">
            <button type="button" class="btn btn-secondary btn-icon btn-sm" data-action="zoom-out" data-keep-open aria-label="Diminuir (Ctrl -)" data-tooltip="Diminuir (Ctrl -)">${icon('minus', 16)}</button>
            <button type="button" class="btn btn-ghost btn-sm settings-zoom-value num" data-action="zoom-reset" data-keep-open data-tooltip="Voltar para 100% (Ctrl 0)">${zoom}%</button>
            <button type="button" class="btn btn-secondary btn-icon btn-sm" data-action="zoom-in" data-keep-open aria-label="Aumentar (Ctrl +)" data-tooltip="Aumentar (Ctrl +)">${icon('plus', 16)}</button>
        </div>
        <div class="menu-separator"></div>
        <button type="button" class="menu-item" data-action="updates">${icon('download', 16)} Verificar atualizações</button>
        <div class="settings-version">MecatroniCar ${info.version ? `v${info.version}` : ''}</div>`;
}

export function initSettings() {
    const trigger = $('#btn-settings');
    if (!trigger) return;

    const menu = createMenu(trigger, {
        className: 'settings-menu',
        render: renderMenu,
        onAction: (action, item) => {
            switch (action) {
                case 'change-folder':
                    changeFolder();
                    break;
                case 'reindex':
                    reindex();
                    break;
                case 'theme':
                    setTheme(item.dataset.value);
                    menu.refresh();
                    break;
                case 'zoom-in':
                    applyZoom(zoom + 10, { save: true });
                    menu.refresh();
                    break;
                case 'zoom-out':
                    applyZoom(zoom - 10, { save: true });
                    menu.refresh();
                    break;
                case 'zoom-reset':
                    applyZoom(100, { save: true });
                    menu.refresh();
                    break;
                case 'updates':
                    openUpdatesModal();
                    break;
                default:
                    break;
            }
        },
    });

    // Ctrl + / Ctrl - / Ctrl 0 (como na v2)
    document.addEventListener('keydown', (event) => {
        if (!event.ctrlKey || event.altKey) return;
        if (event.key === '-' || event.key === '_') {
            event.preventDefault();
            applyZoom(zoom - 10, { save: true, announce: true });
        } else if (event.key === '+' || event.key === '=') {
            event.preventDefault();
            applyZoom(zoom + 10, { save: true, announce: true });
        } else if (event.key === '0') {
            event.preventDefault();
            applyZoom(100, { save: true, announce: true });
        } else {
            return;
        }
        if (menu.isOpen()) menu.refresh();
    });
}

/** Aplica tema/zoom vindos do config do servidor (fonte da verdade). */
export function applyServerConfig(cfg) {
    if (!cfg) return;
    if (cfg.theme) applyTheme(cfg.theme);
    if (cfg.ui_zoom) applyZoom(parseInt(cfg.ui_zoom, 10));
}
