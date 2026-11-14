/**
 * Casca: item ativo da navegação, contadores (badges), versão e
 * recolher/expandir a sidebar (preferência salva no navegador).
 */
import { $, $$, setText } from '../ui/dom.js';
import { on, state } from '../state.js';
import { todayIso } from '../lib/format.js';

const SIDEBAR_KEY = 'mc.sidebar'; // 'auto' | 'collapsed' | 'expanded'
const NARROW_QUERY = '(max-width: 1439.98px)';

// Tela de veículo é "filha" da busca na navegação.
const NAV_FOR_VIEW = { veiculo: 'busca' };

function readPref() {
    try {
        return localStorage.getItem(SIDEBAR_KEY) || 'auto';
    } catch {
        return 'auto';
    }
}

function writePref(value) {
    try {
        localStorage.setItem(SIDEBAR_KEY, value);
    } catch {
        /* armazenamento indisponível: só não lembra */
    }
}

function applySidebar() {
    const pref = readPref();
    const narrow = window.matchMedia(NARROW_QUERY).matches;
    const collapsed = pref === 'collapsed' || (pref === 'auto' && narrow);
    document.documentElement.classList.toggle('sb-collapsed', collapsed);

    const toggle = $('#sidebar-toggle');
    if (toggle) {
        const label = collapsed ? 'Expandir menu' : 'Recolher menu';
        toggle.dataset.tooltip = label;
        setText(toggle.querySelector('.nav-label'), label);
        const use = toggle.querySelector('use');
        if (use) use.setAttribute('href', collapsed ? '#i-panel-left-open' : '#i-panel-left-close');
    }
}

function setBadge(name, count, { alert = false } = {}) {
    const el = document.querySelector(`[data-badge="${name}"]`);
    if (!el) return;
    const n = Number(count) || 0;
    el.hidden = n <= 0;
    el.textContent = n > 99 ? '99+' : String(n);
    el.classList.toggle('is-alert', alert && n > 0);
}

export function initLayout() {
    applySidebar();
    window.matchMedia(NARROW_QUERY).addEventListener('change', applySidebar);

    $('#sidebar-toggle')?.addEventListener('click', () => {
        const collapsed = document.documentElement.classList.contains('sb-collapsed');
        writePref(collapsed ? 'expanded' : 'collapsed');
        applySidebar();
    });

    on('route:changed', ({ viewId }) => {
        const navId = NAV_FOR_VIEW[viewId] || viewId;
        for (const item of $$('[data-nav]')) {
            const active = item.dataset.nav === navId;
            item.classList.toggle('is-active', active);
            if (active) item.setAttribute('aria-current', 'page');
            else item.removeAttribute('aria-current');
        }
    });

    state.watch('appInfo', (info) => {
        if (info && info.version) setText($('#app-version'), `v${info.version}`);
    });

    state.watch('patio', (patio) => setBadge('patio', patio?.active?.length || 0));

    state.watch('agendamentos', (items) => {
        const today = todayIso();
        const pendingToday = (items || []).filter((a) => a.scheduled_date_iso === today && a.status !== 'concluido' && a.status !== 'cancelado');
        setBadge('agenda', pendingToday.length, { alert: true });
    });

    state.watch('nfStats', (stats) => setBadge('fiscal', stats?.pending_visits_count || 0, { alert: true }));
}
