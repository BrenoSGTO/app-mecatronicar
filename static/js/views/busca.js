/**
 * Tela de Busca (#/busca?q=...).
 * - Sem termo: diretório de todos os veículos indexados (filtro local).
 * - Com termo: GET /api/search; se todos os resultados forem de UMA placa,
 *   abre direto a ficha do veículo (comportamento da v2).
 * Dono na Fase 2: T8 (Busca e Ficha do veículo).
 */
import { api, isAbort } from '../api.js';
import { state, on as onEvent } from '../state.js';
import { navigate, currentRoute } from '../router.js';
import { html, render, $, on } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { plate, brandLogo, silhouette } from '../ui/vehicle.js';
import { focusSearch } from '../shell/search.js';
import { formatKm, formatPlate, isoToBr, plural, shortName } from '../lib/format.js';

let root = null;
let controller = null;
let currentQuery = '';
let directoryFilter = '';

function vehicleHash(plateValue) {
    return `#/veiculo/${encodeURIComponent(plateValue)}`;
}

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title" data-field="title">Veículos</h1>
                <p class="page-subtitle" data-field="subtitle">Busque por placa, nome do cliente ou modelo na barra superior.</p>
            </div>
            <div class="page-actions" data-field="directory-tools">
                <div class="input-group busca-filter">
                    ${icon('list-filter', 16, 'input-icon')}
                    <input type="search" class="input" data-field="filter" placeholder="Filtrar esta lista" autocomplete="off">
                </div>
            </div>
        </header>
        <div data-field="results"></div>`);

    on(root, 'input', '[data-field="filter"]', (e, input) => {
        directoryFilter = input.value.trim().toLowerCase();
        renderDirectory();
    });

    on(root, 'click', 'tr[data-plate]', (e, row) => {
        if (e.target.closest('a, button')) return;
        navigate(`/veiculo/${encodeURIComponent(row.dataset.plate)}`);
    });

    state.watch('cars', () => {
        if (!currentQuery) renderDirectory();
    });

    // Após reindexar, refaz a busca atual
    onEvent('data:reindexed', () => {
        if (currentRoute()?.name === 'busca' && currentQuery) runSearch(currentQuery);
    });
}

function setHeader(title, subtitle, showTools) {
    $('[data-field="title"]', root).textContent = title;
    $('[data-field="subtitle"]', root).textContent = subtitle;
    $('[data-field="directory-tools"]', root).hidden = !showTools;
}

/* ------------------------- Diretório (sem termo) ------------------------- */

function renderDirectory() {
    const cars = state.get('cars');
    const resultsEl = $('[data-field="results"]', root);
    if (!cars) {
        render(resultsEl, skeleton());
        return;
    }
    const list = directoryFilter
        ? cars.filter((c) => [c.plate_clean, c.plate_display, c.client_name, c.car_model].some((v) => String(v || '').toLowerCase().includes(directoryFilter)))
        : cars;
    setHeader('Veículos', `${plural(cars.length, 'veículo')} nas planilhas. Use a busca (/) para procurar também em todas as visitas.`, true);

    if (!list.length) {
        render(resultsEl, html`<div class="card"><div class="empty-state">
            <span class="empty-state-icon">${icon('search', 20)}</span>
            <div class="empty-state-title">Nenhum veículo encontrado</div>
            <div class="empty-state-text">Ajuste o filtro ou confira a pasta de planilhas nas configurações.</div>
        </div></div>`);
        return;
    }

    render(resultsEl, html`<div class="table-wrap">
        <table class="table busca-table">
            <thead><tr>
                <th>Placa</th><th>Modelo</th><th>Cliente</th><th class="num">Visitas</th><th class="num">Última visita</th><th></th>
            </tr></thead>
            <tbody>
                ${list.map((car) => {
                    const p = car.plate_clean || car.plate_display || '';
                    return html`<tr class="is-clickable" data-plate="${p}">
                        <td><span class="plate-chip">${formatPlate(car.plate_display || car.plate_clean)}</span></td>
                        <td class="truncate busca-col-model" title="${car.car_model || ''}">${car.car_model || 'Veículo'}</td>
                        <td class="truncate" title="${car.client_name || ''}">${car.client_name || 'Cliente'}</td>
                        <td class="num">${car.visit_count || 1}</td>
                        <td class="num">${isoToBr(car.latest_date_sort) || '—'}</td>
                        <td class="td-center"><a class="btn btn-ghost btn-sm" href="${vehicleHash(p)}">Abrir ${icon('arrow-right', 14)}</a></td>
                    </tr>`;
                })}
            </tbody>
        </table>
    </div>`);
}

/* ------------------------- Resultados (com termo) ------------------------- */

function skeleton() {
    return html`<div class="busca-grid">${[1, 2, 3, 4].map(() => html`<div class="card busca-card-skeleton"><div class="skeleton skeleton-block"></div></div>`)}</div>`;
}

function groupByPlate(results) {
    const groups = new Map();
    for (const r of results) {
        const key = r.plate_clean || r.plate || 'SEM PLACA';
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(r);
    }
    return [...groups.entries()].map(([key, visits]) => {
        visits.sort((a, b) => String(b.entry_date_sort || '').localeCompare(String(a.entry_date_sort || '')));
        return { key, latest: visits[0], count: visits.length };
    });
}

function renderResults(q, results) {
    const resultsEl = $('[data-field="results"]', root);
    const groups = groupByPlate(results);
    setHeader(`Resultados para “${q}”`, `${plural(groups.length, 'veículo')} · ${plural(results.length, 'visita encontrada', 'visitas encontradas')}`, false);

    if (!results.length) {
        render(resultsEl, html`<div class="card"><div class="empty-state">
            <span class="empty-state-icon">${icon('search', 20)}</span>
            <div class="empty-state-title">Nada encontrado para “${q}”</div>
            <div class="empty-state-text">Confira a placa ou o nome do cliente. Placas podem ser digitadas com ou sem hífen.</div>
            <div class="empty-state-actions"><a class="btn btn-secondary btn-sm" href="#/busca">Ver todos os veículos</a></div>
        </div></div>`);
        return;
    }

    render(resultsEl, html`<div class="busca-grid">${groups.map(({ key, latest: item, count }) => html`
        <a class="card card-interactive busca-card" href="${vehicleHash(key)}">
            <div class="busca-card-top">
                ${plate(item.plate_display || item.plate || key, 'md')}
                ${brandLogo(item.car_model, 'sm')}
            </div>
            ${silhouette(item.car_model)}
            <div class="busca-card-owner truncate">${icon('user', 14)} ${item.client_name || 'Cliente não identificado'}</div>
            <div class="busca-card-car truncate">
                <strong>${item.car_model || 'Veículo'}</strong>${item.car_year ? ` (${item.car_year})` : ''}${item.car_color ? ` · ${item.car_color}` : ''}
            </div>
            <div class="busca-card-meta">
                <span>${icon('calendar', 14)} ${item.entry_date || 'Sem data'}</span>
                ${item.odometer ? html`<span>${icon('gauge', 14)} ${formatKm(item.odometer)}</span>` : ''}
                <span>${icon('history', 14)} ${plural(count, 'visita')}</span>
            </div>
            ${item.complaint ? html`<p class="busca-card-complaint" title="${item.complaint}">${item.complaint}</p>` : ''}
        </a>`)}</div>`);
}

async function runSearch(q) {
    controller?.abort();
    controller = new AbortController();
    const resultsEl = $('[data-field="results"]', root);
    setHeader(`Buscando “${q}”…`, 'Procurando em todas as planilhas', false);
    render(resultsEl, skeleton());
    try {
        const data = await api.get('/api/search', { params: { q }, signal: controller.signal, errorMessage: 'Erro na busca' });
        if (q !== currentQuery) return;
        const results = data.results || [];
        const plates = [...new Set(results.map((r) => r.plate_clean).filter(Boolean))];
        if (plates.length === 1 && currentRoute()?.name === 'busca') {
            navigate(`/veiculo/${encodeURIComponent(plates[0])}`, { replace: true });
            return;
        }
        renderResults(q, results);
    } catch (err) {
        if (isAbort(err)) return;
        setHeader('Erro na busca', err.message, false);
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
            renderDirectory();
            if (!state.get('cars')?.length) focusSearch();
        }
    },
    leave() {
        controller?.abort();
    },
};
