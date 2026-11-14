/**
 * Tela de Busca (#/busca?q=...).
 * - Sem termo: diretório de todos os veículos indexados (filtro local).
 * - Com termo: GET /api/search, agrupado por veículo, com o termo destacado.
 *   O primeiro resultado já vem selecionado: setas movem a seleção, Enter abre.
 *   Placa completa (7 caracteres) com um único veículo abre a ficha direto.
 * Dono na Fase 2: T8 (Busca e Ficha do veículo).
 */
import { api, isAbort } from '../api.js';
import { state, on as onEvent } from '../state.js';
import { navigate, currentRoute } from '../router.js';
import { html, render, $, $$, on } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { plate, brandLogo } from '../ui/vehicle.js';
import { focusSearch } from '../shell/search.js';
import { cleanPlate, formatKm, formatPlate, isoToBr, normalizeText, plural } from '../lib/format.js';
import { openNewOs } from './os.js';

let root = null;
let controller = null;
let currentQuery = '';
let directoryFilter = '';
let activeIndex = -1;
let lastRenderedQuery = null;

function vehicleHash(plateValue) {
    return `#/veiculo/${encodeURIComponent(plateValue)}`;
}

/* ------------------------------------------------------------------ */
/* Destaque do termo (usado também pela ficha do veículo)              */
/* ------------------------------------------------------------------ */

function foldWithMap(text) {
    let folded = '';
    const map = [];
    for (let i = 0; i < text.length; i++) {
        const piece = text[i].normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
        for (const ch of piece) {
            folded += ch;
            map.push(i);
        }
    }
    return { folded, map };
}

function mergeRanges(ranges) {
    const sorted = ranges.filter((r) => r[1] > r[0]).sort((a, b) => a[0] - b[0]);
    const merged = [];
    for (const range of sorted) {
        const last = merged[merged.length - 1];
        if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
        else merged.push([...range]);
    }
    return merged;
}

function applyRanges(source, ranges) {
    if (!ranges.length) return html`${source}`;
    const parts = [];
    let cursor = 0;
    for (const [start, end] of ranges) {
        if (start > cursor) parts.push(source.slice(cursor, start));
        parts.push(html`<mark class="hit">${source.slice(start, end)}</mark>`);
        cursor = end;
    }
    if (cursor < source.length) parts.push(source.slice(cursor));
    return html`${parts}`;
}

/**
 * Texto com o termo destacado (ignora acentos e caixa). Seguro: tudo passa
 * pelo template `html`.  `plateMode` também casa "FNB1A77" com "FNB-1A77".
 */
export function highlight(text, query, { plateMode = false } = {}) {
    const source = text === null || text === undefined ? '' : String(text);
    const q = String(query || '').trim();
    if (!source || !q) return html`${source}`;
    const { folded, map } = foldWithMap(source);
    const ranges = [];

    const tokens = normalizeText(q).split(/\s+/).filter(Boolean);
    for (const token of tokens) {
        let from = 0;
        while (token && from <= folded.length) {
            const at = folded.indexOf(token, from);
            if (at < 0) break;
            ranges.push([map[at], map[at + token.length - 1] + 1]);
            from = at + token.length;
        }
    }

    if (plateMode) {
        const wanted = cleanPlate(q);
        if (wanted.length >= 2) {
            const alnum = [];
            const positions = [];
            for (let i = 0; i < source.length; i++) {
                if (/[A-Za-z0-9]/.test(source[i])) {
                    alnum.push(source[i].toUpperCase());
                    positions.push(i);
                }
            }
            const at = alnum.join('').indexOf(wanted);
            if (at >= 0) ranges.push([positions[at], positions[at + wanted.length - 1] + 1]);
        }
    }
    return applyRanges(source, mergeRanges(ranges));
}

/* ------------------------------------------------------------------ */
/* Casca da tela                                                       */
/* ------------------------------------------------------------------ */

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title" data-field="title">Veículos</h1>
                <p class="page-subtitle" data-field="subtitle">Busque por placa, nome do cliente ou modelo na barra superior.</p>
            </div>
            <div class="page-actions">
                <div class="busca-hint" data-field="hint" hidden>
                    <span class="kbd" aria-label="Seta para cima">${icon('chevron-up', 12)}</span><span class="kbd" aria-label="Seta para baixo">${icon('chevron-down', 12)}</span> navegar
                    <span class="kbd">Enter</span> abrir
                </div>
                <div class="input-group busca-filter" data-field="directory-tools">
                    ${icon('list-filter', 16, 'input-icon')}
                    <input type="search" class="input" data-field="filter" placeholder="Filtrar esta lista" aria-label="Filtrar a lista de veículos" autocomplete="off">
                </div>
            </div>
        </header>
        <div data-field="results" aria-live="polite"></div>`);

    on(root, 'input', '[data-field="filter"]', (e, input) => {
        directoryFilter = input.value.trim();
        activeIndex = -1;
        renderDirectory();
    });

    // Linha inteira clicável + Enter/Espaço em linhas focadas
    on(root, 'click', '[data-plate]', (e, row) => {
        if (e.target.closest('a, button')) return;
        navigate(`/veiculo/${encodeURIComponent(row.dataset.plate)}`);
    });
    on(root, 'keydown', 'tr[data-plate]', (e, row) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            navigate(`/veiculo/${encodeURIComponent(row.dataset.plate)}`);
        }
    });
    on(root, 'click', '[data-action="new-visit-plate"]', (e, btn) => openNewOs({ plate: btn.dataset.plate }));

    state.watch('cars', () => {
        if (currentRoute()?.name !== 'busca') return;
        if (!currentQuery) renderDirectory();
    });

    // Após reindexar, refaz a busca atual
    onEvent('data:reindexed', () => {
        if (currentRoute()?.name === 'busca' && currentQuery) runSearch(currentQuery);
    });

    document.addEventListener('keydown', handleKeys, true);
}

function setHeader(title, subtitle, { tools = false, hint = false } = {}) {
    $('[data-field="title"]', root).textContent = title;
    $('[data-field="subtitle"]', root).textContent = subtitle;
    $('[data-field="directory-tools"]', root).hidden = !tools;
    $('[data-field="hint"]', root).hidden = !hint;
}

/* ------------------------------------------------------------------ */
/* Teclado: setas movem a seleção, Enter abre                          */
/* ------------------------------------------------------------------ */

function navItems() {
    return $$('[data-nav-item]', root).filter((el) => !el.closest('[hidden]'));
}

function setActive(index, { scroll = true } = {}) {
    const items = navItems();
    items.forEach((el, i) => {
        const on = i === index;
        el.classList.toggle('is-active', on);
        el.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    activeIndex = items.length ? Math.max(-1, Math.min(index, items.length - 1)) : -1;
    if (scroll && items[activeIndex]) items[activeIndex].scrollIntoView({ block: 'nearest' });
}

function openActive() {
    const item = navItems()[activeIndex];
    if (!item) return false;
    navigate(`/veiculo/${encodeURIComponent(item.dataset.plate)}`);
    return true;
}

function handleKeys(event) {
    if (currentRoute()?.name !== 'busca' || event.defaultPrevented) return;
    if (document.body.classList.contains('has-modal')) return;
    const target = event.target;
    const inSearch = target?.id === 'global-search';
    const inFilter = target?.matches?.('[data-field="filter"]');
    const inRow = target?.closest?.('[data-nav-item]');
    const neutral = target === document.body || target === document.documentElement;
    if (!(inSearch || inFilter || inRow || neutral)) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;

    const items = navItems();
    if (!items.length) return;

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const step = event.key === 'ArrowDown' ? 1 : -1;
        const next = activeIndex < 0 ? (step > 0 ? 0 : items.length - 1) : (activeIndex + step + items.length) % items.length;
        setActive(next);
        if (inRow) items[next].focus({ preventScroll: true });
    } else if (event.key === 'Enter' && (inSearch || inFilter) && activeIndex >= 0) {
        event.preventDefault();
        event.stopImmediatePropagation();
        openActive();
    }
}

/* ------------------------------------------------------------------ */
/* Diretório (sem termo)                                               */
/* ------------------------------------------------------------------ */

function skeleton(rows = 5) {
    return html`<div class="card busca-skeleton">${Array.from({ length: rows }, () => html`<div class="busca-skeleton-row">
        <div class="skeleton busca-skeleton-plate"></div>
        <div class="skeleton-stack"><div class="skeleton skeleton-title"></div><div class="skeleton skeleton-text"></div></div>
    </div>`)}</div>`;
}

function renderDirectory() {
    lastRenderedQuery = '';
    const cars = state.get('cars');
    const resultsEl = $('[data-field="results"]', root);
    if (!cars) {
        render(resultsEl, skeleton());
        return;
    }
    const q = directoryFilter;
    const list = q
        ? cars.filter((c) => {
            const hay = [c.plate_clean, c.plate_display, c.client_name, c.car_model, c.car_color].map(normalizeText).join(' ');
            const tokens = normalizeText(q).split(/\s+/).filter(Boolean);
            const plateQ = cleanPlate(q).toLowerCase();
            return tokens.every((t) => hay.includes(t)) || (plateQ.length >= 2 && cleanPlate(c.plate_clean).toLowerCase().includes(plateQ));
        })
        : cars;
    const subtitle = q
        ? `${list.length} de ${plural(cars.length, 'veículo')}. Use a busca (/) para procurar também dentro das visitas.`
        : `${plural(cars.length, 'veículo')} nas planilhas. Use a busca (/) para procurar também dentro das visitas.`;
    setHeader('Veículos', subtitle, { tools: true, hint: list.length > 0 });

    if (!list.length) {
        render(resultsEl, html`<div class="card"><div class="empty-state">
            <span class="empty-state-icon">${icon('search', 20)}</span>
            <div class="empty-state-title">Nenhum veículo encontrado</div>
            <div class="empty-state-text">Ajuste o filtro ou confira a pasta de planilhas nas configurações.</div>
        </div></div>`);
        activeIndex = -1;
        return;
    }

    render(resultsEl, html`<div class="table-wrap busca-table-wrap">
        <table class="table busca-table">
            <thead><tr>
                <th>Placa</th><th>Cliente</th><th>Veículo</th><th class="num">Visitas</th><th class="num">Último km</th><th class="num">Última visita</th><th class="busca-col-open"><span class="sr-only">Abrir</span></th>
            </tr></thead>
            <tbody role="listbox" aria-label="Veículos">
                ${list.map((car) => {
                    const p = car.plate_clean || car.plate_display || '';
                    return html`<tr class="is-clickable" tabindex="0" role="option" aria-selected="false" data-nav-item data-plate="${p}">
                        <td><span class="plate-chip">${formatPlate(car.plate_display || car.plate_clean)}</span></td>
                        <td class="truncate busca-col-client" title="${car.client_name || ''}">${highlight(car.client_name || 'Cliente', q)}</td>
                        <td class="truncate busca-col-model" title="${car.car_model || ''}">${highlight(car.car_model || 'Veículo', q)}${car.car_color ? html` <span class="text-subtle">· ${car.car_color}</span>` : ''}</td>
                        <td class="num">${car.visit_count || 1}</td>
                        <td class="num">${car.latest_odometer ? formatKm(car.latest_odometer) : '—'}</td>
                        <td class="num">${isoToBr(car.latest_date_sort) || '—'}</td>
                        <td class="td-center"><a class="btn btn-ghost btn-sm" href="${vehicleHash(p)}" aria-label="Abrir ${formatPlate(car.plate_display || car.plate_clean)}">${icon('arrow-right', 14)}</a></td>
                    </tr>`;
                })}
            </tbody>
        </table>
    </div>`);
    activeIndex = -1;
}

/* ------------------------------------------------------------------ */
/* Resultados (com termo)                                              */
/* ------------------------------------------------------------------ */

function plateScore(plateClean, q) {
    const wanted = cleanPlate(q);
    if (wanted.length < 2) return 3;
    if (plateClean === wanted) return 0;
    if (plateClean.startsWith(wanted)) return 1;
    if (plateClean.includes(wanted)) return 2;
    return 3;
}

function groupByPlate(results, q) {
    const carsByPlate = new Map((state.get('cars') || []).map((c) => [c.plate_clean, c]));
    const groups = new Map();
    for (const r of results) {
        const key = r.plate_clean || r.plate || 'SEM PLACA';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(r);
    }
    const tokens = normalizeText(q).split(/\s+/).filter(Boolean);
    const matchesComplaint = (v) => {
        const text = normalizeText(v.complaint || '');
        return tokens.length > 0 && tokens.every((t) => text.includes(t));
    };
    return [...groups.entries()].map(([key, visits]) => {
        visits.sort((a, b) => String(b.entry_date_sort || '').localeCompare(String(a.entry_date_sort || '')));
        const latest = visits[0];
        const known = carsByPlate.get(key);
        const complaintVisit = visits.find(matchesComplaint) || latest;
        return {
            key,
            latest,
            complaintVisit,
            complaintIsMatch: complaintVisit !== latest || matchesComplaint(latest),
            matched: visits.length,
            total: known?.visit_count || visits.length,
            score: plateScore(key, q),
        };
    }).sort((a, b) => a.score - b.score || String(b.latest.entry_date_sort || '').localeCompare(String(a.latest.entry_date_sort || '')));
}

/** Distância de edição simples (placas têm 7 caracteres, custo irrelevante). */
function editDistance(a, b) {
    const dp = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
    for (let j = 1; j <= b.length; j++) dp[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
        for (let j = 1; j <= b.length; j++) {
            dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        }
    }
    return dp[a.length][b.length];
}

function looksLikePlate(q) {
    const c = cleanPlate(q);
    return c.length >= 5 && c.length <= 8 && /[A-Z]/.test(c) && /\d/.test(c);
}

function similarCars(q) {
    const wanted = cleanPlate(q);
    const cars = state.get('cars') || [];
    if (wanted.length < 4) return [];
    return cars
        .map((c) => ({ c, d: editDistance(wanted, c.plate_clean || '') }))
        .filter(({ d }) => d <= 2)
        .sort((a, b) => a.d - b.d)
        .slice(0, 4)
        .map(({ c }) => c);
}

function renderNotFound(q) {
    const similar = similarCars(q);
    const isPlate = looksLikePlate(q);
    return html`<div class="card"><div class="empty-state">
        <span class="empty-state-icon">${icon('search', 20)}</span>
        <div class="empty-state-title">Nada encontrado para “${q}”</div>
        <div class="empty-state-text">
            ${isPlate
                ? 'Esta placa não aparece em nenhuma planilha. Confira as letras e os números; hífen e espaço não fazem diferença.'
                : 'Procure pela placa (com ou sem hífen), por parte do nome do cliente ou pelo modelo. Tente menos palavras ou só o sobrenome.'}
        </div>
        ${similar.length ? html`<div class="busca-suggest">
            <span class="text-sm text-muted">Você quis dizer:</span>
            ${similar.map((c) => html`<a class="busca-suggest-item" href="${vehicleHash(c.plate_clean)}">
                <span class="plate-chip">${formatPlate(c.plate_display || c.plate_clean)}</span>
                <span class="truncate">${c.client_name || 'Cliente'} · ${c.car_model || 'Veículo'}</span>
            </a>`)}
        </div>` : ''}
        <div class="empty-state-actions">
            ${isPlate ? html`<button type="button" class="btn btn-secondary btn-sm" data-action="new-visit-plate" data-plate="${cleanPlate(q)}">${icon('plus', 15)} Nova visita para ${formatPlate(cleanPlate(q))}</button>` : ''}
            <a class="btn btn-secondary btn-sm" href="#/busca">Ver todos os veículos</a>
        </div>
    </div></div>`;
}

function renderResults(q, results) {
    lastRenderedQuery = q;
    const resultsEl = $('[data-field="results"]', root);
    resultsEl.classList.remove('is-loading');
    const groups = groupByPlate(results, q);
    setHeader(
        `Resultados para “${q}”`,
        `${plural(groups.length, 'veículo')} · ${plural(results.length, 'visita encontrada', 'visitas encontradas')}`,
        { hint: groups.length > 0 },
    );

    if (!results.length) {
        render(resultsEl, renderNotFound(q));
        activeIndex = -1;
        return;
    }

    render(resultsEl, html`<div class="busca-list" role="listbox" aria-label="Resultados da busca">${groups.map(({ key, latest: item, complaintVisit, complaintIsMatch, matched, total }) => {
        const complaint = complaintVisit.complaint || '';
        return html`<a class="busca-row" role="option" aria-selected="false" data-nav-item data-plate="${key}" href="${vehicleHash(key)}">
            ${plate(item.plate_display || item.plate || key, 'sm')}
            ${brandLogo(item.car_model, 'sm')}
            <span class="busca-row-main">
                <span class="busca-row-client truncate">${highlight(item.client_name || 'Cliente não identificado', q)}</span>
                <span class="busca-row-car truncate">${highlight(item.car_model || 'Veículo', q)}${item.car_year ? ` · ${item.car_year}` : ''}${item.car_color ? ` · ${item.car_color}` : ''}</span>
            </span>
            <span class="busca-row-complaint${complaintIsMatch ? ' is-match' : ''} truncate" title="${complaint}">${complaint ? highlight(complaint, q) : ''}</span>
            <span class="busca-row-meta">
                <span class="num">${item.entry_date || 'Sem data'}${item.odometer ? ` · ${formatKm(item.odometer)}` : ''}</span>
                <span class="text-subtle">${plural(total, 'visita')}${matched !== total ? ` (${matched} com o termo)` : ''}</span>
            </span>
            ${icon('chevron-right', 16, 'busca-row-go')}
        </a>`;
    })}</div>`);

    // Primeiro resultado já selecionado: Enter abre
    setActive(0, { scroll: false });
}

async function runSearch(q) {
    controller?.abort();
    controller = new AbortController();
    const resultsEl = $('[data-field="results"]', root);
    if (lastRenderedQuery && resultsEl.querySelector('.busca-list')) {
        // Mantém a lista anterior enquanto a nova chega (sem piscar)
        resultsEl.classList.add('is-loading');
    } else {
        setHeader(`Buscando “${q}”…`, 'Procurando em todas as planilhas');
        render(resultsEl, skeleton(4));
    }
    try {
        const data = await api.get('/api/search', { params: { q }, signal: controller.signal, errorMessage: 'Erro na busca' });
        if (q !== currentQuery) return;
        const results = data.results || [];
        const plates = [...new Set(results.map((r) => r.plate_clean).filter(Boolean))];
        // Placa completa com um único veículo: abre a ficha direto
        if (plates.length === 1 && cleanPlate(q).length === 7 && looksLikePlate(q) && currentRoute()?.name === 'busca') {
            navigate(`/veiculo/${encodeURIComponent(plates[0])}`, { replace: true });
            return;
        }
        renderResults(q, results);
    } catch (err) {
        if (isAbort(err)) return;
        resultsEl.classList.remove('is-loading');
        setHeader('Erro na busca', err.message);
        render(resultsEl, html`<div class="callout callout-danger">${icon('circle-alert', 16)} <div>${err.message}</div></div>`);
    }
}

export default {
    id: 'busca',
    title: 'Busca',
    mount,
    enter(params, query) {
        currentQuery = (query.q || '').trim();
        if (currentQuery) {
            runSearch(currentQuery);
        } else {
            controller?.abort();
            activeIndex = -1;
            renderDirectory();
            if (!state.get('cars')?.length) focusSearch();
        }
    },
    leave() {
        controller?.abort();
    },
};
