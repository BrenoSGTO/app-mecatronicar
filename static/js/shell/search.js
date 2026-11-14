/**
 * Busca global da barra superior + atalhos de teclado globais.
 *   /  ou  Ctrl+K   → foca a busca
 *   Esc (na busca)  → limpa / sai
 *   Enter           → busca imediatamente
 * Digitar 3+ caracteres leva para #/busca?q=... (a tela de busca faz a consulta).
 */
import { $, debounce } from '../ui/dom.js';
import { on } from '../state.js';
import { navigate, currentRoute } from '../router.js';

const MIN_CHARS = 3;

function isTypingTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

export function focusSearch({ select = true } = {}) {
    const input = $('#global-search');
    if (!input) return;
    input.focus();
    if (select) input.select();
}

export function setSearchValue(value) {
    const input = $('#global-search');
    if (!input) return;
    input.value = value || '';
    syncClear();
}

function syncClear() {
    const input = $('#global-search');
    const hasValue = Boolean(input && input.value);
    $('#topbar-search')?.classList.toggle('has-value', hasValue);
    const clear = $('#global-search-clear');
    if (clear) clear.hidden = !hasValue;
}

function goSearch(query, { force = false } = {}) {
    const q = query.trim();
    const onSearch = currentRoute()?.name === 'busca';
    if (!q) {
        if (onSearch) navigate('/busca', { replace: true });
        return;
    }
    if (q.length < MIN_CHARS && !force) return;
    navigate('/busca', { query: { q }, replace: onSearch });
}

export function initSearch() {
    const input = $('#global-search');
    if (!input) return;

    const debounced = debounce((value) => goSearch(value), 250);

    input.addEventListener('input', () => {
        syncClear();
        debounced(input.value);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            debounced.cancel();
            goSearch(input.value, { force: true });
        } else if (event.key === 'Escape') {
            event.preventDefault();
            if (input.value) {
                input.value = '';
                syncClear();
                debounced.cancel();
                goSearch('');
            } else {
                input.blur();
            }
        }
    });

    $('#global-search-clear')?.addEventListener('click', () => {
        input.value = '';
        syncClear();
        debounced.cancel();
        goSearch('');
        input.focus();
    });

    // Atalhos globais
    document.addEventListener('keydown', (event) => {
        if (event.defaultPrevented) return;
        const modalOpen = document.body.classList.contains('has-modal');
        if ((event.ctrlKey || event.metaKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === 'k') {
            if (modalOpen) return;
            event.preventDefault();
            focusSearch();
            return;
        }
        if (event.key === '/' && !event.ctrlKey && !event.metaKey && !event.altKey && !isTypingTarget(document.activeElement) && !modalOpen) {
            event.preventDefault();
            focusSearch();
        }
    });

    // Mantém o campo coerente com a rota
    on('route:changed', ({ viewId, query }) => {
        if (viewId === 'busca') {
            if (document.activeElement !== input) setSearchValue(query.q || '');
        } else if (viewId !== 'veiculo') {
            if (document.activeElement !== input) setSearchValue('');
        }
    });
}
