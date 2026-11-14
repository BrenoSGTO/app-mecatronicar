/**
 * Tela Início / Pátio (#/inicio).
 * - Centro: carros no pátio (abas "No pátio agora" / "Entregues (48h)", filtros por status).
 * - Lateral: agendamentos (GET /api/agenda) e histórico rápido (veículos indexados).
 *
 * Render sem "pulo": cada card é reaproveitado entre os polls e só é recriado
 * quando algum dado visível dele muda (assinatura por carro); as listas laterais
 * só reescrevem o DOM se a marcação mudou. Dono na Fase 2: T7.
 */
import { api } from '../api.js';
import { state } from '../state.js';
import { refresh } from '../data.js';
import { every, stop } from '../scheduler.js';
import { navigate } from '../router.js';
import { html, render, on, $, h, toElement, readFields, busy } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal, confirmDialog } from '../ui/modal.js';
import { createMenu } from '../ui/menu.js';
import { toast } from '../ui/toast.js';
import { plate, silhouette, statusTag } from '../ui/vehicle.js';
import { PATIO_STATUSES, DELIVERED_STATUS, THIRD_PARTY_STATUS, statusKey, statusLabel, statusValue } from '../lib/patio.js';
import {
    cleanPlate, formatDateBr, formatDelivered, formatPlate, formatRelativeDay, formatTimeBr,
    isoToBr, pad2, parseDateTime, plural, shortName, todayIso,
} from '../lib/format.js';
import { openPatioManager, openPatioEntry, isValidPlate } from './patio.js';

const AGENDA_SERVICES = [
    ['Revisão Geral', 'Revisão geral'],
    ['Troca de Óleo / Filtros', 'Troca de óleo / filtros'],
    ['Freios', 'Freios (pastilhas / discos)'],
    ['Suspensão', 'Suspensão / amortecedores'],
    ['Diagnóstico / Injeção', 'Diagnóstico / injeção'],
    ['Correia Dentada', 'Correia dentada'],
    ['Ar Condicionado', 'Ar-condicionado'],
    ['Alinhamento e Balanceamento', 'Alinhamento e balanceamento'],
    ['Outro', 'Outro serviço'],
];

const AGENDA_LIMIT = 4;
const HISTORY_LIMIT = 6;
const HISTORY_FILTER_LIMIT = 8;
const COMPACT_AUTO_THRESHOLD = 12;
const STALE_MINUTES = 24 * 60;
const TICK = 'view:inicio:tick';

let root = null;
const ui = {
    tab: 'active',          // 'active' | 'delivered'
    statusFilter: 'all',    // 'all' | chave de status
    agendaPeriod: 'all',    // 'all' | 'today' | 'upcoming'
    agendaExpanded: false,
    historyFilter: '',
    historyExpanded: false,
    density: readDensity(), // 'comfortable' | 'compact' | '' (automático)
};
let agendaModal = null;
let statusMenu = null;
let statusMenuBtn = null;
let statusMenuCarId = '';
const cardCache = new Map(); // chave -> { sig, el }

function readDensity() {
    try {
        const value = localStorage.getItem('mc.patio.density');
        return value === 'compact' || value === 'comfortable' ? value : '';
    } catch {
        return '';
    }
}

function saveDensity(value) {
    try {
        localStorage.setItem('mc.patio.density', value);
    } catch {
        /* sem armazenamento: vale só nesta sessão */
    }
}

function vehicleHref(plateValue) {
    return `/veiculo/${encodeURIComponent(plateValue)}`;
}

/** Só reescreve o DOM se a marcação mudou (preserva foco, rolagem e seleção). */
function paint(el, markup) {
    if (!el) return;
    if (el._markup === markup.value) return;
    el._markup = markup.value;
    render(el, markup);
}

/* ------------------------------------------------------------------ */
/* Modelo de exibição de um carro                                      */
/* ------------------------------------------------------------------ */

function knownCar(plateClean) {
    if (!plateClean) return null;
    return (state.get('cars') || []).find((c) => cleanPlate(c.plate_clean || c.plate_display) === plateClean) || null;
}

/** Minutos no status atual. */
function minutesSince(value) {
    const start = parseDateTime(value);
    return start ? Math.floor(Math.max(0, Date.now() - start.getTime()) / 60000) : null;
}

/** "agora", "35 min", "1h 43min", "2 dias 3h". */
function sinceText(minutes) {
    if (minutes === null) return '';
    if (minutes < 5) return 'agora';
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ${pad2(minutes % 60)}min`;
    const days = Math.floor(hours / 24);
    const rest = hours % 24;
    return `${days} ${days === 1 ? 'dia' : 'dias'}${rest ? ` ${rest}h` : ''}`;
}

function carModel(car) {
    const rawStatus = car.status_display || car.status || 'Em Diagnóstico';
    const plateClean = cleanPlate(car.plate_clean || car.plate);
    const known = knownCar(plateClean);
    const since = car.updated_at || car.updated_time || '';
    const minutes = minutesSince(since);
    const sinceDate = parseDateTime(since);
    return {
        id: String(car.id),
        plateClean,
        plateText: formatPlate(car.plate_display || car.plate),
        model: car.car_model || known?.car_model || '',
        color: car.car_color || known?.car_color || '',
        client: car.client_name || known?.client_name || '',
        rawStatus,
        statusKey: statusKey(rawStatus),
        statusValue: statusValue(rawStatus),
        statusLabel: statusLabel(rawStatus),
        since,
        minutes,
        sinceText: sinceText(minutes),
        sinceTitle: sinceDate ? `Neste status desde ${formatDateBr(sinceDate)} às ${formatTimeBr(sinceDate)}` : '',
        stale: minutes !== null && minutes >= STALE_MINUTES,
        where: car.box_mecanico || car.mechanic_name || '',
        notes: car.notes || '',
        auth: car.authorized_name || car.third_party_name || '',
        deliveredText: formatDelivered(since),
    };
}

/* ------------------------------------------------------------------ */
/* Marcação                                                            */
/* ------------------------------------------------------------------ */

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Pátio da oficina</h1>
                <p class="page-subtitle" data-field="subtitle"></p>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-secondary" data-action="patio-manage">${icon('warehouse', 16)} Gerenciar pátio</button>
                <button type="button" class="btn btn-secondary" data-action="patio-new">${icon('log-in', 16)} Entrada no pátio</button>
            </div>
        </header>

        <div class="inicio-grid">
            <section class="card inicio-patio" aria-label="Veículos no pátio">
                <div class="inicio-patio-head">
                    <div class="tabs" role="tablist" aria-label="Visão do pátio">
                        <button type="button" class="tab" role="tab" id="tab-patio-active" aria-selected="true" aria-controls="patio-panel" data-tab="active">
                            ${icon('car-front', 16)} No pátio agora <span class="badge" data-count="active">0</span>
                        </button>
                        <button type="button" class="tab" role="tab" id="tab-patio-delivered" aria-selected="false" aria-controls="patio-panel" tabindex="-1" data-tab="delivered">
                            ${icon('package-check', 16)} Entregues (48h) <span class="badge" data-count="delivered">0</span>
                        </button>
                    </div>
                    <div class="segmented" role="group" aria-label="Densidade dos cards" data-field="density"></div>
                </div>
                <div class="inicio-patio-body" id="patio-panel" role="tabpanel">
                    <div class="patio-toolbar" data-field="toolbar">
                        <div class="filter-pills" data-field="filters" role="group" aria-label="Filtrar por status"></div>
                    </div>
                    <p class="text-sm text-muted" data-field="delivered-hint" hidden>
                        Carros entregues saem da visão principal e ficam aqui por 48 horas para consulta rápida.
                    </p>
                    <div class="patio-grid" data-field="skeleton" aria-hidden="true">
                        ${[1, 2, 3].map(() => html`<div class="skeleton skeleton-block patio-card-skeleton"></div>`)}
                    </div>
                    <div class="patio-grid" data-field="grid" hidden></div>
                    <div data-field="empty" hidden></div>
                </div>
            </section>

            <aside class="inicio-side">
                <section class="card inicio-agenda" aria-label="Agendamentos">
                    <div class="card-header">
                        <span class="card-title">${icon('calendar-clock', 16)} Agendamentos <span class="badge" data-count="agenda">0</span></span>
                        <button type="button" class="btn btn-secondary btn-sm" data-action="agenda-new">${icon('plus', 14)} Novo</button>
                    </div>
                    <div class="inicio-side-toolbar">
                        <div class="segmented" role="group" aria-label="Período" data-field="agenda-periods"></div>
                    </div>
                    <div class="inicio-side-list" data-field="agenda"></div>
                </section>

                <section class="card inicio-history" aria-label="Histórico rápido">
                    <div class="card-header">
                        <span class="card-title">${icon('history', 16)} Histórico rápido <span class="badge" data-count="history">0</span></span>
                        <a class="link-button text-sm" href="#/busca">Ver todos</a>
                    </div>
                    <div class="inicio-side-toolbar">
                        <div class="input-group">
                            ${icon('list-filter', 16, 'input-icon')}
                            <input type="search" class="input input-sm" data-field="history-filter" placeholder="Filtrar por placa, cliente ou modelo" aria-label="Filtrar histórico" autocomplete="off">
                        </div>
                    </div>
                    <div class="inicio-side-list" data-field="history"></div>
                </section>
            </aside>
        </div>`);

    bindEvents();

    state.watch('patio', renderPatio);
    state.watch('agendaEvents', renderAgenda);
    state.watch('cars', () => {
        renderHistory();
        renderPatio();
    });
}

/* ------------------------------------------------------------------ */
/* Pátio                                                               */
/* ------------------------------------------------------------------ */

function headerSubtitle(active) {
    const day = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date());
    const parts = [day.charAt(0).toUpperCase() + day.slice(1), `${plural(active.length, 'veículo')} no pátio`];
    const stale = active.filter((c) => (minutesSince(c.updated_at || c.updated_time) ?? 0) >= STALE_MINUTES).length;
    if (stale) parts.push(`${stale} há mais de 24 h no mesmo status`);
    return parts.join(' · ');
}

function renderPatio() {
    if (!root) return;
    const patio = state.get('patio');
    const active = patio?.active || [];
    const delivered = patio?.delivered || [];

    $('[data-count="active"]', root).textContent = String(active.length);
    $('[data-count="delivered"]', root).textContent = String(delivered.length);
    $('[data-field="subtitle"]', root).textContent = patio ? headerSubtitle(active) : formatDateBr(new Date());

    for (const tab of root.querySelectorAll('[data-tab]')) {
        const selected = tab.dataset.tab === ui.tab;
        tab.setAttribute('aria-selected', selected ? 'true' : 'false');
        tab.tabIndex = selected ? 0 : -1;
    }
    $('#patio-panel', root).setAttribute('aria-labelledby', `tab-patio-${ui.tab}`);

    const toolbar = $('[data-field="toolbar"]', root);
    const hint = $('[data-field="delivered-hint"]', root);
    const grid = $('[data-field="grid"]', root);
    const skeleton = $('[data-field="skeleton"]', root);
    const empty = $('[data-field="empty"]', root);
    toolbar.hidden = ui.tab !== 'active' || !active.length;
    $('[data-field="density"]', root).hidden = ui.tab !== 'active' || !active.length;
    hint.hidden = ui.tab !== 'delivered';

    if (!patio) {
        skeleton.hidden = false;
        grid.hidden = true;
        empty.hidden = true;
        toolbar.hidden = true;
        $('[data-field="density"]', root).hidden = true;
        return;
    }
    skeleton.hidden = true;

    let list;
    if (ui.tab === 'active') {
        const counts = {};
        for (const car of active) {
            const key = statusKey(car.status_display || car.status);
            counts[key] = (counts[key] || 0) + 1;
        }
        if (ui.statusFilter !== 'all' && !counts[ui.statusFilter]) ui.statusFilter = 'all';
        paint($('[data-field="filters"]', root), html`
            <button type="button" class="filter-pill${ui.statusFilter === 'all' ? ' is-active' : ''}" data-filter="all" aria-pressed="${ui.statusFilter === 'all' ? 'true' : 'false'}">Todos <span class="count">${active.length}</span></button>
            ${PATIO_STATUSES.filter((s) => counts[s.key]).map((s) => html`
                <button type="button" class="filter-pill${ui.statusFilter === s.key ? ' is-active' : ''}" data-filter="${s.key}" data-status="${s.key}" aria-pressed="${ui.statusFilter === s.key ? 'true' : 'false'}">
                    <span class="status-dot"></span>${s.label} <span class="count">${counts[s.key]}</span>
                </button>`)}`);
        list = ui.statusFilter === 'all'
            ? active
            : active.filter((c) => statusKey(c.status_display || c.status) === ui.statusFilter);
    } else {
        list = delivered;
    }

    const compact = ui.tab === 'active' && (ui.density ? ui.density === 'compact' : active.length > COMPACT_AUTO_THRESHOLD);
    grid.classList.toggle('is-compact', compact);
    paint($('[data-field="density"]', root), html`
        <button type="button" class="segmented-item${compact ? '' : ' is-active'}" data-density="comfortable" aria-pressed="${compact ? 'false' : 'true'}">Cards</button>
        <button type="button" class="segmented-item${compact ? ' is-active' : ''}" data-density="compact" aria-pressed="${compact ? 'true' : 'false'}">Compacto</button>`);

    if (!list.length) {
        grid.hidden = true;
        reconcileCards(grid, []);
        paint(empty, emptyState(ui.tab === 'delivered'));
        empty.hidden = false;
        return;
    }
    empty.hidden = true;
    grid.hidden = false;
    reconcileCards(grid, list.map((car) => carModel(car)));
}

function emptyState(delivered) {
    if (delivered) {
        return html`<div class="empty-state patio-empty">
            <span class="empty-state-icon">${icon('package-check', 20)}</span>
            <div class="empty-state-title">Nenhum veículo entregue nas últimas 48 horas</div>
            <div class="empty-state-text">Ao marcar um carro como entregue, ele aparece aqui por dois dias.</div>
        </div>`;
    }
    return html`<div class="empty-state patio-empty">
        <span class="empty-state-icon">${icon('warehouse', 20)}</span>
        <div class="empty-state-title">O pátio está vazio</div>
        <div class="empty-state-text">Nenhum veículo na oficina agora. Quando um carro chegar, dê entrada para ele aparecer aqui e no Painel TV.</div>
        <div class="empty-state-actions">
            <button type="button" class="btn btn-secondary" data-action="patio-new">${icon('log-in', 16)} Entrada no pátio</button>
        </div>
    </div>`;
}

/**
 * Reconciliação por chave: reaproveita o elemento de cada carro enquanto a
 * assinatura (tudo o que aparece no card) não mudar; só recria o que mudou e
 * só move o que saiu de ordem. O polling deixa de reconstruir o grid inteiro.
 */
function reconcileCards(grid, models) {
    const delivered = ui.tab === 'delivered';
    const keep = new Set();
    const els = [];
    for (const m of models) {
        const key = `${delivered ? 'e' : 'a'}:${m.id}`;
        keep.add(key);
        const sig = JSON.stringify([m.plateText, m.model, m.color, m.client, m.rawStatus, m.sinceText, m.stale, m.where, m.notes, m.auth, m.deliveredText]);
        let entry = cardCache.get(key);
        if (!entry || entry.sig !== sig) {
            const el = toElement(delivered ? deliveredCard(m) : activeCard(m));
            entry?.el.remove();
            entry = { sig, el };
            cardCache.set(key, entry);
        }
        els.push(entry.el);
    }
    for (const [key, entry] of cardCache) {
        if (!keep.has(key)) {
            entry.el.remove();
            cardCache.delete(key);
        }
    }
    let cursor = grid.firstElementChild;
    for (const el of els) {
        if (el === cursor) {
            cursor = cursor.nextElementSibling;
        } else {
            grid.insertBefore(el, cursor);
        }
    }
}

function vehicleBlock(m) {
    return html`<div class="patio-card-vehicle">
        <span class="patio-card-art">${silhouette(m.model)}</span>
        <div class="patio-card-id">
            <div class="patio-card-model" title="${m.model}">${m.model || 'Modelo não informado'}</div>
            ${m.color ? html`<div class="patio-card-color">${m.color}</div>` : ''}
            <div class="patio-card-owner" title="${m.client}">${icon('user', 14)} <span class="truncate">${m.client ? shortName(m.client) : 'Cliente não informado'}</span></div>
        </div>
    </div>`;
}

function activeCard(m) {
    return html`<article class="patio-card" data-status="${m.statusKey}" data-car-id="${m.id}" data-plate="${m.plateClean}" tabindex="0" aria-label="${m.plateText}, ${m.model || 'modelo não informado'}, ${m.statusLabel}. Enter abre o histórico.">
        <div class="patio-card-top">
            ${plate(m.plateText, 'sm')}
            <button type="button" class="status-tag status-trigger" data-action="status-menu" data-status="${m.statusKey}" aria-label="Status: ${m.statusLabel}. Alterar status" aria-haspopup="menu" aria-expanded="false">${m.statusLabel} ${icon('chevron-down', 12)}</button>
        </div>
        ${vehicleBlock(m)}
        <div class="patio-card-meta">
            <span class="patio-card-since${m.stale ? ' is-stale' : ''}" title="${m.sinceTitle}">${icon('clock', 14)} <span class="num">${m.sinceText || 'Recém chegado'}</span> <span class="patio-card-since-label">neste status</span></span>
            ${m.where ? html`<span class="patio-card-where" title="${m.where}">${icon('map-pin', 14)} <span class="truncate">${m.where}</span></span>` : ''}
        </div>
        ${m.statusKey === 'terceiro' ? html`<div class="patio-card-pickup" title="Retira: ${m.auth}">${icon('user-check', 14)} <span class="truncate">Retira: ${m.auth || 'autorizado não informado'}</span></div>` : ''}
        ${m.notes ? html`<p class="patio-card-notes" title="${m.notes}">${m.notes}</p>` : ''}
        <div class="patio-card-actions">
            <button type="button" class="btn btn-secondary btn-sm patio-card-deliver" data-action="deliver">${icon('package-check', 14)} Entregar</button>
            <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="edit" aria-label="Editar dados do veículo" data-tooltip="Editar dados">${icon('pencil', 14)}</button>
            <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="history" aria-label="Abrir histórico do veículo" data-tooltip="Histórico">${icon('history', 14)}</button>
        </div>
    </article>`;
}

function deliveredCard(m) {
    return html`<article class="patio-card is-delivered" data-status="entregue" data-car-id="${m.id}" data-plate="${m.plateClean}" tabindex="0" aria-label="${m.plateText}, ${m.model || 'modelo não informado'}, entregue. Enter abre o histórico.">
        <div class="patio-card-top">
            ${plate(m.plateText, 'sm')}
            ${statusTag('Entregue')}
        </div>
        ${vehicleBlock(m)}
        <div class="patio-card-meta">
            <span class="text-success">${icon('circle-check', 14)} ${m.deliveredText}</span>
        </div>
        ${m.notes ? html`<p class="patio-card-notes" title="${m.notes}">${m.notes}</p>` : ''}
        <div class="patio-card-actions">
            <button type="button" class="btn btn-secondary btn-sm" data-action="reactivate">${icon('undo-2', 14)} Retornar ao pátio</button>
            <button type="button" class="btn btn-ghost btn-sm" data-action="history">${icon('history', 14)} Histórico</button>
        </div>
    </article>`;
}

function findCar(id) {
    const patio = state.get('patio');
    return [...(patio?.active || []), ...(patio?.delivered || [])].find((c) => String(c.id) === String(id)) || null;
}

/** Toast com botão "Desfazer" (o toast base só tem texto). */
function undoToast(message, onUndo) {
    const el = toast(message, 'success', { duration: 8000 });
    const button = h('button', { type: 'button', class: 'toast-action', text: 'Desfazer' });
    button.addEventListener('click', async (event) => {
        event.stopPropagation();
        button.disabled = true;
        try {
            await onUndo();
            toast('Alteração desfeita.', 'info');
        } catch (err) {
            toast(`Não foi possível desfazer: ${err.message}`, 'error');
        }
        el.click();
    });
    el.append(button);
}

async function postStatus(id, status) {
    await api.post('/api/patio/status', { id, status }, { errorMessage: 'Erro ao alterar status' });
    await refresh('patio');
}

/**
 * Troca o status de um carro, com feedback e desfazer.
 * `message` aparece no toast; o desfazer volta ao status anterior.
 */
async function changeStatus(car, value, message) {
    const current = statusValue(car.status_display || car.status);
    if (value === current) return true;
    const cardEl = root.querySelector(`[data-car-id="${car.id}"]`);
    cardEl?.classList.add('is-busy');
    try {
        await postStatus(car.id, value);
        undoToast(message, () => postStatus(car.id, current));
        return true;
    } catch (err) {
        toast(`Não foi possível alterar o status: ${err.message}`, 'error');
        return false;
    } finally {
        cardEl?.classList.remove('is-busy');
    }
}

function chooseStatus(car, value) {
    const m = carModel(car);
    if (value === THIRD_PARTY_STATUS && !m.auth) {
        // Retirada por terceiro exige nome e documento: abre o editor já nesse status.
        openPatioManager({ car, status: value });
        return;
    }
    if (value === DELIVERED_STATUS) {
        changeStatus(car, value, `${m.plateText} entregue. Ficou em “Entregues (48h)”.`);
        return;
    }
    changeStatus(car, value, `${m.plateText}: status alterado para ${statusLabel(value)}.`);
}

/* Menu de status: uma única instância, ancorada no botão do card clicado. */
function ensureStatusMenu() {
    if (statusMenu) return statusMenu;
    const anchor = {
        setAttribute() {},
        addEventListener() {},
        getBoundingClientRect: () => statusMenuBtn.getBoundingClientRect(),
        contains: (node) => statusMenuBtn.contains(node),
        focus: () => statusMenuBtn?.isConnected && statusMenuBtn.focus(),
    };
    statusMenu = createMenu(anchor, {
        align: 'end',
        className: 'status-menu',
        render: () => {
            const car = findCar(statusMenuCarId);
            const current = car ? statusValue(car.status_display || car.status) : '';
            return html`
                <div class="menu-label">Mudar status</div>
                ${PATIO_STATUSES.map((s) => html`<button type="button" class="menu-item status-menu-item${s.value === current ? ' is-current' : ''}" role="menuitemradio" aria-checked="${s.value === current ? 'true' : 'false'}" data-action="set-status" data-value="${s.value}" data-status="${s.key}">
                    <span class="status-dot"></span><span class="grow">${s.label}</span>${s.value === current ? icon('check', 14) : ''}
                </button>`)}
                <div class="menu-separator"></div>
                <button type="button" class="menu-item" role="menuitem" data-action="set-status" data-value="${DELIVERED_STATUS}">${icon('package-check', 16)} <span class="grow">Marcar como entregue</span></button>`;
        },
        onAction: (action, item) => {
            if (action !== 'set-status') return;
            const car = findCar(statusMenuCarId);
            if (car) chooseStatus(car, item.dataset.value);
        },
    });
    return statusMenu;
}

function toggleStatusMenu(btn, carId) {
    const menu = ensureStatusMenu();
    if (menu.isOpen() && statusMenuBtn === btn) {
        menu.close();
        return;
    }
    statusMenuBtn = btn;
    statusMenuCarId = carId;
    menu.open();
}

/* ------------------------------------------------------------------ */
/* Agenda (eventos do calendário)                                      */
/* ------------------------------------------------------------------ */

const isDone = (ev) => /conclu|cancel/i.test(ev.status || '');
const inService = (ev) => /atendimento/i.test(ev.status || '');

function sortedEvents(events) {
    const today = todayIso();
    return (events || [])
        // Eventos passados já resolvidos não interessam aqui; atrasados ainda pendentes continuam à vista.
        .filter((ev) => !(ev.event_date < today && (isDone(ev) || inService(ev))))
        .sort((a, b) => `${a.event_date || ''} ${a.event_time || ''}`.localeCompare(`${b.event_date || ''} ${b.event_time || ''}`));
}

function periodMatch(ev, period, today) {
    if (period === 'today') return ev.event_date === today;
    if (period === 'upcoming') return ev.event_date > today;
    return true;
}

function renderAgenda(events) {
    if (!root) return;
    const listEl = $('[data-field="agenda"]', root);
    const today = todayIso();

    if (!events) {
        $('[data-count="agenda"]', root).textContent = '0';
        paint(listEl, html`<div class="skeleton-stack inicio-side-pad"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>`);
        return;
    }

    const all = sortedEvents(events);
    const counts = {
        all: all.length,
        today: all.filter((ev) => periodMatch(ev, 'today', today)).length,
        upcoming: all.filter((ev) => periodMatch(ev, 'upcoming', today)).length,
    };
    $('[data-count="agenda"]', root).textContent = String(counts.all);
    paint($('[data-field="agenda-periods"]', root), html`${[['all', 'Todos'], ['today', 'Hoje'], ['upcoming', 'Próximos']].map(([key, label]) => html`
        <button type="button" class="segmented-item${ui.agendaPeriod === key ? ' is-active' : ''}" data-period="${key}" aria-pressed="${ui.agendaPeriod === key ? 'true' : 'false'}">${label} <span class="count">${counts[key]}</span></button>`)}`);

    const list = all.filter((ev) => periodMatch(ev, ui.agendaPeriod, today));
    if (!list.length) {
        paint(listEl, html`<div class="empty-state empty-state-compact">
            <span class="empty-state-icon">${icon('calendar', 20)}</span>
            <div class="empty-state-title">${ui.agendaPeriod === 'today' ? 'Nada agendado para hoje' : 'Nenhum agendamento'}</div>
            <div class="empty-state-actions"><button type="button" class="btn btn-secondary btn-sm" data-action="agenda-new">${icon('plus', 14)} Agendar horário</button></div>
        </div>`);
        return;
    }

    const visible = ui.agendaExpanded ? list : list.slice(0, AGENDA_LIMIT);
    const hidden = list.length - visible.length;
    paint(listEl, html`
        ${visible.map((ev) => agendaItem(ev, today))}
        ${hidden > 0 ? html`<button type="button" class="inicio-more" data-action="agenda-more">${icon('chevron-down', 14)} Mostrar mais ${hidden}</button>` : ''}
        ${ui.agendaExpanded && list.length > AGENDA_LIMIT ? html`<button type="button" class="inicio-more" data-action="agenda-less">${icon('chevron-up', 14)} Mostrar menos</button>` : ''}
        <a class="inicio-more inicio-more-link" href="#/agenda">${icon('calendar-days', 14)} Abrir agenda completa</a>`);
}

function agendaItem(ev, today) {
    const isToday = ev.event_date === today;
    const late = ev.event_date < today && !isDone(ev);
    const done = isDone(ev);
    const active = inService(ev);
    const plateText = ev.plate ? formatPlate(ev.plate_display || ev.plate) : '';
    const statusText = late ? 'Atrasado' : (active ? 'No pátio' : (ev.status || 'Agendado'));
    const tone = late ? ' tag-danger' : (done ? ' tag-success' : (active ? ' tag-info' : (/confirm/i.test(ev.status || '') ? ' tag-success' : '')));
    return html`<article class="agenda-event${done ? ' is-done' : ''}" data-event-id="${ev.id}">
        <div class="agenda-event-when">
            <span class="agenda-event-day${isToday ? ' is-today' : ''}">${formatRelativeDay(ev.event_date)}</span>
            <span class="agenda-event-time num">${ev.event_time || '09:00'}</span>
        </div>
        <div class="agenda-event-main">
            <div class="agenda-event-title">${ev.title || 'Agendamento'}</div>
            <div class="agenda-event-meta">
                <span class="truncate">${shortName(ev.client_name)}</span>
                ${plateText ? html`<span class="plate-chip plate-chip-sm">${plateText}</span>` : ''}
            </div>
            <div class="agenda-event-sub">
                <span class="agenda-event-car truncate" title="${ev.car_model || ev.service_type || ''}">${ev.car_model || ev.service_type || ''}</span>
                <span class="tag${tone}">${statusText}</span>
            </div>
            ${ev.notes ? html`<p class="agenda-event-notes" title="${ev.notes}">${ev.notes}</p>` : ''}
            <div class="agenda-event-actions">
                ${!done && !active && !/confirm/i.test(ev.status || '') ? html`<button type="button" class="btn btn-ghost btn-sm" data-action="event-confirm" aria-label="Confirmar agendamento">${icon('check', 14)} Confirmar</button>` : ''}
                ${!done && !active ? html`<button type="button" class="btn btn-secondary btn-sm" data-action="event-to-patio" aria-label="Mandar para o pátio" data-tooltip="Dar entrada no pátio">${icon('log-in', 14)} Pátio</button>` : ''}
                ${active ? html`<button type="button" class="btn btn-ghost btn-sm" data-action="event-done" aria-label="Concluir agendamento">${icon('check', 14)} Concluir</button>` : ''}
                <button type="button" class="btn btn-ghost btn-icon btn-sm push" data-action="event-delete" aria-label="Excluir agendamento" data-tooltip="Excluir">${icon('trash-2', 14)}</button>
            </div>
        </div>
    </article>`;
}

function openAgendaModal() {
    if (!agendaModal) {
        agendaModal = createModal({
            id: 'agenda-event',
            title: 'Novo agendamento',
            subtitle: 'Reserve um horário para o cliente trazer o carro.',
            icon: 'calendar-plus',
            size: 'md',
            body: html`<form class="form-grid" novalidate autocomplete="off">
                <label class="field col-12">
                    <span class="field-label">Título ou motivo <span class="req">*</span></span>
                    <input class="input" name="title" placeholder="Ex.: Revisão geral e troca de óleo" required>
                </label>
                <label class="field col-6"><span class="field-label">Data <span class="req">*</span></span><input class="input" type="date" name="event_date" required></label>
                <label class="field col-6"><span class="field-label">Horário <span class="req">*</span></span><input class="input" type="time" name="event_time" value="09:00" required></label>
                <label class="field col-6"><span class="field-label">Cliente <span class="req">*</span></span><input class="input" name="client_name" placeholder="Nome do cliente" required></label>
                <label class="field col-6">
                    <span class="field-label">Placa</span>
                    <input class="input input-upper input-mono" name="plate" placeholder="Opcional" maxlength="8" spellcheck="false">
                    <span class="field-hint" data-hint="plate">Sem a placa não dá para mandar direto para o pátio.</span>
                </label>
                <label class="field col-6"><span class="field-label">Modelo do carro</span><input class="input" name="car_model" placeholder="Ex.: VW Fox 1.0"></label>
                <label class="field col-6"><span class="field-label">Tipo de serviço</span>
                    <select class="select" name="service_type">${AGENDA_SERVICES.map(([v, l]) => html`<option value="${v}">${l}</option>`)}</select>
                </label>
                <label class="field col-12"><span class="field-label">Observações</span><textarea class="textarea" name="notes" rows="3" placeholder="Sintomas relatados pelo cliente…"></textarea></label>
            </form>`,
            footer: html`
                <button type="button" class="btn btn-secondary" data-modal-close>Cancelar</button>
                <button type="button" class="btn btn-primary" data-action="save">${icon('save', 16)} Salvar agendamento</button>`,
        });
        agendaModal.footer.querySelector('[data-action="save"]').addEventListener('click', saveAgendaEvent);
        const formEl = agendaModal.body.querySelector('form');
        formEl.addEventListener('submit', (e) => {
            e.preventDefault();
            saveAgendaEvent();
        });
        formEl.addEventListener('input', (e) => {
            if (e.target.name === 'plate') e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, '');
            e.target.setAttribute?.('aria-invalid', 'false');
        });
    }
    const formEl = agendaModal.body.querySelector('form');
    formEl.reset();
    for (const el of formEl.querySelectorAll('[aria-invalid]')) el.setAttribute('aria-invalid', 'false');
    formEl.elements.event_date.value = todayIso();
    formEl.elements.event_time.value = '09:00';
    agendaModal.open();
}

async function saveAgendaEvent() {
    const formEl = agendaModal.body.querySelector('form');
    const v = readFields(formEl);
    const fail = (name, message) => {
        formEl.elements[name].setAttribute('aria-invalid', 'true');
        formEl.elements[name].focus();
        toast(message, 'error');
    };
    for (const el of formEl.querySelectorAll('[aria-invalid="true"]')) el.setAttribute('aria-invalid', 'false');
    if (!v.title) return fail('title', 'Informe o título ou motivo do agendamento.');
    if (!v.event_date) return fail('event_date', 'Informe a data.');
    if (!v.event_time) return fail('event_time', 'Informe o horário.');
    if (!v.client_name) return fail('client_name', 'Informe o nome do cliente.');
    if (v.plate && !isValidPlate(v.plate)) return fail('plate', 'Placa inválida. Use ABC1D23 ou ABC-1234, ou deixe em branco.');

    const restore = busy(agendaModal.footer.querySelector('[data-action="save"]'), 'Salvando…');
    try {
        await api.post('/api/agenda', {
            title: v.title,
            event_date: v.event_date,
            event_time: v.event_time || '09:00',
            client_name: v.client_name,
            plate: cleanPlate(v.plate),
            car_model: v.car_model,
            service_type: v.service_type || 'Revisão Geral',
            notes: v.notes,
            status: 'Agendado',
        }, { errorMessage: 'Erro ao salvar agendamento' });
        toast('Agendamento salvo.', 'success');
        agendaModal.close();
        await refresh('agendaEvents');
    } catch (err) {
        toast(`Não foi possível salvar o agendamento: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

async function eventAction(action, id) {
    const ev = (state.get('agendaEvents') || []).find((e) => String(e.id) === String(id));
    if (!ev) return;
    try {
        if (action === 'event-confirm') {
            await api.post('/api/agenda/status', { id, status: 'Confirmado' }, { errorMessage: 'Erro ao confirmar agendamento' });
            toast('Agendamento confirmado.', 'success');
            await refresh('agendaEvents');
        } else if (action === 'event-to-patio') {
            await eventToPatio(ev);
        } else if (action === 'event-done') {
            await api.post('/api/agenda/status', { id, status: 'Concluído' }, { errorMessage: 'Erro ao atualizar agendamento' });
            toast('Agendamento concluído.', 'success');
            await refresh('agendaEvents');
        } else if (action === 'event-delete') {
            const when = `${formatRelativeDay(ev.event_date).toLowerCase()} às ${ev.event_time || '09:00'}`;
            const ok = await confirmDialog({
                title: 'Excluir agendamento?',
                message: `“${ev.title || 'Agendamento'}” de ${shortName(ev.client_name)} (${when}) será removido da agenda. Esta ação não pode ser desfeita.`,
                confirmLabel: 'Excluir',
                danger: true,
            });
            if (!ok) return;
            await api.del(`/api/agenda/${encodeURIComponent(id)}`, { errorMessage: 'Erro ao excluir agendamento' });
            toast('Agendamento excluído.', 'success');
            await refresh('agendaEvents');
        }
    } catch (err) {
        toast(err.message, 'error');
    }
}

async function eventToPatio(ev) {
    const plateClean = cleanPlate(ev.plate_clean || ev.plate);
    if (!isValidPlate(plateClean)) {
        // Sem placa válida não há como registrar no pátio: abre a entrada para completar os dados.
        toast('Esse agendamento não tem placa. Complete os dados para dar entrada.', 'info');
        openPatioEntry({ prefill: { plate: '', client_name: ev.client_name || '', car_model: ev.car_model || '', notes: ev.title || '' } });
        return;
    }
    const inYard = (state.get('patio')?.active || []).find((c) => cleanPlate(c.plate_clean || c.plate) === plateClean);
    if (inYard) {
        // Já está no pátio: não mexe no status atual, só marca o agendamento como em atendimento.
        await api.post('/api/agenda/status', { id: ev.id, status: 'Em Atendimento' }, { errorMessage: 'Erro ao atualizar agendamento' });
        toast(`${formatPlate(plateClean)} já está no pátio (${statusLabel(inYard.status_display || inYard.status)}).`, 'info');
        await refresh('agendaEvents');
        return;
    }
    await api.post(`/api/agenda/${encodeURIComponent(ev.id)}/to_patio`, { status: 'Em Diagnóstico' }, { errorMessage: 'Erro ao dar entrada no pátio' });
    toast(`${formatPlate(plateClean)} entrou no pátio em Diagnóstico.`, 'success');
    ui.tab = 'active';
    await refresh('patio', 'agendaEvents');
}

/* ------------------------------------------------------------------ */
/* Histórico rápido                                                    */
/* ------------------------------------------------------------------ */

function renderHistory() {
    if (!root) return;
    const listEl = $('[data-field="history"]', root);
    const cars = state.get('cars');
    if (!cars) {
        paint(listEl, html`<div class="skeleton-stack inicio-side-pad"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>`);
        return;
    }
    const q = ui.historyFilter.toLowerCase();
    const qPlate = cleanPlate(q).toLowerCase();
    const list = q
        ? cars.filter((c) => (qPlate && (c.plate_clean || '').toLowerCase().includes(qPlate))
            || (c.client_name || '').toLowerCase().includes(q)
            || (c.car_model || '').toLowerCase().includes(q))
        : cars;
    $('[data-count="history"]', root).textContent = String(list.length);

    if (!list.length) {
        paint(listEl, html`<div class="empty-state empty-state-compact">
            <span class="empty-state-icon">${icon('search', 20)}</span>
            <div class="empty-state-title">Nenhum veículo encontrado</div>
            <div class="empty-state-text">Tente outra placa, nome ou modelo.</div>
        </div>`);
        return;
    }
    const limit = q ? HISTORY_FILTER_LIMIT : HISTORY_LIMIT;
    const visible = ui.historyExpanded && !q ? list.slice(0, 20) : list.slice(0, limit);
    const hidden = list.length - visible.length;
    paint(listEl, html`<div class="list">${visible.map((car) => {
        const date = isoToBr(car.latest_date_sort);
        const model = car.car_model || 'Veículo';
        return html`<a class="list-item inicio-history-item" href="#${vehicleHref(car.plate_clean || car.plate_display || '')}">
            <span class="list-item-row">
                <span class="plate-chip">${formatPlate(car.plate_display || car.plate_clean)}</span>
                <span class="list-item-meta num">${plural(car.visit_count || 1, 'visita')}</span>
            </span>
            <span class="list-item-title truncate" title="${model}">${model}</span>
            <span class="list-item-row list-item-meta">
                <span class="truncate" title="${car.client_name || ''}">${shortName(car.client_name)}</span>
                ${date ? html`<span class="num">${date}</span>` : ''}
            </span>
        </a>`;
    })}</div>
    ${hidden > 0 && !q ? html`<button type="button" class="inicio-more" data-action="history-more">${icon('chevron-down', 14)} Mostrar mais ${Math.min(hidden, 20 - visible.length)}</button>` : ''}
    ${hidden > 0 && q ? html`<a class="inicio-more inicio-more-link" href="#/busca?q=${encodeURIComponent(ui.historyFilter)}">${icon('search', 14)} Ver todos os ${list.length} na busca</a>` : ''}
    ${!q && ui.historyExpanded ? html`<a class="inicio-more inicio-more-link" href="#/busca">${icon('search', 14)} Abrir busca completa</a>` : ''}`);
}

/* ------------------------------------------------------------------ */
/* Eventos                                                             */
/* ------------------------------------------------------------------ */

function selectTab(tab) {
    ui.tab = tab;
    renderPatio();
}

function bindEvents() {
    on(root, 'click', '[data-tab]', (e, btn) => selectTab(btn.dataset.tab));
    on(root, 'keydown', '[data-tab]', (e, btn) => {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        const tabs = [...root.querySelectorAll('[data-tab]')];
        const next = tabs[(tabs.indexOf(btn) + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
        e.preventDefault();
        selectTab(next.dataset.tab);
        next.focus();
    });

    on(root, 'click', '[data-filter]', (e, btn) => {
        ui.statusFilter = btn.dataset.filter;
        renderPatio();
    });

    on(root, 'click', '[data-density]', (e, btn) => {
        ui.density = btn.dataset.density;
        saveDensity(ui.density);
        renderPatio();
    });

    on(root, 'click', '[data-period]', (e, btn) => {
        ui.agendaPeriod = btn.dataset.period;
        ui.agendaExpanded = false;
        renderAgenda(state.get('agendaEvents'));
    });

    on(root, 'input', '[data-field="history-filter"]', (e, input) => {
        ui.historyFilter = input.value.trim();
        renderHistory();
    });

    on(root, 'click', '[data-action]', (e, btn) => {
        const action = btn.dataset.action;
        const card = btn.closest('[data-car-id]');
        const eventEl = btn.closest('[data-event-id]');
        e.stopPropagation();

        switch (action) {
            case 'patio-manage':
                openPatioManager();
                break;
            case 'patio-new':
                openPatioEntry();
                break;
            case 'agenda-new':
                openAgendaModal();
                break;
            case 'agenda-more':
                ui.agendaExpanded = true;
                renderAgenda(state.get('agendaEvents'));
                break;
            case 'agenda-less':
                ui.agendaExpanded = false;
                renderAgenda(state.get('agendaEvents'));
                break;
            case 'history-more':
                ui.historyExpanded = true;
                renderHistory();
                break;
            case 'status-menu':
                if (card) toggleStatusMenu(btn, card.dataset.carId);
                break;
            case 'deliver': {
                const car = card && findCar(card.dataset.carId);
                if (car) chooseStatus(car, DELIVERED_STATUS);
                break;
            }
            case 'edit': {
                const car = card && findCar(card.dataset.carId);
                if (car) openPatioManager({ car });
                break;
            }
            case 'reactivate': {
                const car = card && findCar(card.dataset.carId);
                if (!car) break;
                const m = carModel(car);
                changeStatus(car, PATIO_STATUSES[0].value, `${m.plateText} voltou ao pátio em Diagnóstico.`).then((ok) => {
                    if (ok) selectTab('active');
                });
                break;
            }
            case 'history':
                if (card?.dataset.plate) navigate(vehicleHref(card.dataset.plate));
                break;
            case 'event-confirm':
            case 'event-to-patio':
            case 'event-done':
            case 'event-delete':
                if (eventEl) eventAction(action, eventEl.dataset.eventId);
                break;
            default:
                break;
        }
    });

    // Clique no corpo do card (fora dos controles) abre o histórico do veículo
    on(root, 'click', '.patio-card', (e, card) => {
        if (e.target.closest('button, select, a, input')) return;
        if (card.dataset.plate) navigate(vehicleHref(card.dataset.plate));
    });
    on(root, 'keydown', '.patio-card', (e, card) => {
        if ((e.key === 'Enter' || e.key === ' ') && e.target === card && card.dataset.plate) {
            e.preventDefault();
            navigate(vehicleHref(card.dataset.plate));
        }
    });
}

export default {
    id: 'inicio',
    title: 'Início',
    mount,
    enter() {
        refresh('patio', 'agendaEvents');
        renderPatio();
        // Atualiza os "há quanto tempo" a cada minuto, mesmo sem dado novo do servidor.
        every(TICK, 60000, () => {
            renderPatio();
            renderAgenda(state.get('agendaEvents'));
        }, { immediate: false });
    },
    leave() {
        stop(TICK);
        statusMenu?.close();
    },
};
