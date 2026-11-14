/**
 * Agenda (#/agenda): calendário de atendimentos (Dia / Semana / Mês).
 *
 * Duas fontes, mostradas juntas:
 *   - agendamentos da secretária (GET/POST /api/agendamentos, PUT/DELETE /api/agendamentos/:id,
 *     POST /api/agendamentos/:id/status)  -> state 'agendamentos' (polling de 10s);
 *   - eventos da agenda do Início (GET/POST /api/agenda, /api/agenda/status, /to_patio)
 *     -> state 'agendaEvents' (polling de 30s).
 * Novos agendamentos são gravados em /api/agendamentos (mesma fonte da TV e do selo do menu).
 * "Criar ficha" abre a OS pré-preenchida (a planilha só nasce ao salvar).
 * Dono na Fase 2: T11.
 */
import { api } from '../api.js';
import { state } from '../state.js';
import { refresh } from '../data.js';
import { html, render, on, $, $$, readFields, fillFields, busy, setVar } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal, confirmDialog } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { plate as plateBadge } from '../ui/vehicle.js';
import { addDays, cleanPlate, formatPlate, normalizeText, pad2, plural, toIsoDate, todayIso } from '../lib/format.js';
import { openOsFromAgendamento } from './os.js';

/* ------------------------------------------------------------------ */
/* Constantes                                                          */
/* ------------------------------------------------------------------ */

const STATUS = {
    agendado: { label: 'Agendado', tag: 'tag-info', icon: 'calendar-clock' },
    confirmado: { label: 'Confirmado', tag: 'tag-success', icon: 'calendar-check' },
    concluido: { label: 'Concluído', tag: '', icon: 'circle-check' },
    cancelado: { label: 'Cancelado', tag: 'tag-danger', icon: 'ban' },
};

/** Grafia de cada status nos eventos da agenda do Início. */
const EVENT_STATUS_TEXT = { agendado: 'Agendado', confirmado: 'Confirmado', concluido: 'Concluído', cancelado: 'Cancelado' };

const VIEWS = [['dia', 'Dia'], ['semana', 'Semana'], ['mes', 'Mês']];
const DEFAULT_MINUTES = 60;
const VIEW_KEY = 'mc.agenda.view';

const SERVICE_SUGGESTIONS = [
    'Troca de óleo e filtros', 'Revisão preventiva', 'Diagnóstico com scanner', 'Alinhamento e balanceamento',
    'Freios', 'Suspensão', 'Correia dentada', 'Ar-condicionado', 'Injeção eletrônica', 'Bateria e parte elétrica',
];

const MONTH = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric' });
const WEEKDAY_SHORT = new Intl.DateTimeFormat('pt-BR', { weekday: 'short' });
const LONG_DATE = new Intl.DateTimeFormat('pt-BR', { weekday: 'long', day: 'numeric', month: 'long' });
const SHORT_MONTH = new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'short' });

/* ------------------------------------------------------------------ */
/* Estado local da tela                                                */
/* ------------------------------------------------------------------ */

let root = null;
let view = readStoredView();
let cursor = startOfDay(new Date());
let search = '';
let scrollKey = '';          // "visão|início": rola o horário só quando a janela muda
let formModal = null;
let detailModal = null;
let current = null;          // item aberto nos detalhes
let suggestionIndex = -1;

function readStoredView() {
    try {
        const stored = localStorage.getItem(VIEW_KEY);
        return VIEWS.some(([key]) => key === stored) ? stored : 'semana';
    } catch {
        return 'semana';
    }
}

function storeView() {
    try {
        localStorage.setItem(VIEW_KEY, view);
    } catch { /* preferência é só conveniência */ }
}

/* ------------------------------------------------------------------ */
/* Datas                                                               */
/* ------------------------------------------------------------------ */

function startOfDay(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function fromIso(iso) {
    const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
    return new Date(y || 1970, (m || 1) - 1, d || 1);
}

/** Segunda-feira da semana de `date`. */
function startOfWeek(date) {
    const d = startOfDay(date);
    const shift = (d.getDay() + 6) % 7;
    return addDays(d, -shift);
}

function sameDay(a, b) {
    return toIsoDate(a) === toIsoDate(b);
}

function rangeLabel() {
    if (view === 'dia') return capitalize(LONG_DATE.format(cursor));
    if (view === 'mes') return capitalize(MONTH.format(cursor));
    const first = startOfWeek(cursor);
    const last = addDays(first, 6);
    if (first.getMonth() === last.getMonth()) {
        return `${first.getDate()} a ${last.getDate()} de ${new Intl.DateTimeFormat('pt-BR', { month: 'long' }).format(last)} de ${last.getFullYear()}`;
    }
    return `${SHORT_MONTH.format(first).replace('.', '')} a ${SHORT_MONTH.format(last).replace('.', '')} de ${last.getFullYear()}`;
}

function capitalize(text) {
    return text.charAt(0).toUpperCase() + text.slice(1);
}

function visibleRange() {
    if (view === 'dia') return [startOfDay(cursor), startOfDay(cursor)];
    if (view === 'semana') {
        const first = startOfWeek(cursor);
        return [first, addDays(first, 6)];
    }
    const first = startOfWeek(new Date(cursor.getFullYear(), cursor.getMonth(), 1));
    const monthEnd = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
    return [first, addDays(startOfWeek(monthEnd), 6)];
}

function parseMinutes(time) {
    const m = /^(\d{1,2}):(\d{2})/.exec(String(time || ''));
    if (!m) return 8 * 60;
    return Math.min(23 * 60 + 59, Number(m[1]) * 60 + Number(m[2]));
}

function formatMinutes(total) {
    return `${pad2(Math.floor(total / 60))}:${pad2(total % 60)}`;
}

/* ------------------------------------------------------------------ */
/* Modelo unificado dos agendamentos                                   */
/* ------------------------------------------------------------------ */

function eventStatus(text) {
    const s = normalizeText(text);
    if (s.includes('cancel')) return 'cancelado';
    if (s.includes('conclu') || s.includes('atendimento') || s.includes('atendido') || s.includes('finaliz')) return 'concluido';
    if (s.includes('confirm')) return 'confirmado';
    return 'agendado';
}

function fromAgendamento(a) {
    const time = a.scheduled_time || '08:00';
    const start = parseMinutes(time);
    return {
        key: `a${a.id}`,
        source: 'agendamento',
        id: a.id,
        date: a.scheduled_date_iso || a.scheduled_date || '',
        time: formatMinutes(start),
        start,
        end: start + DEFAULT_MINUTES,
        client: a.client_name || 'Cliente',
        phone: a.phone || '',
        plate: a.car_plate_display || a.car_plate || '',
        model: a.car_model || '',
        service: a.title || 'Atendimento',
        symptoms: a.description || '',
        notes: a.notes || '',
        status: STATUS[a.status] ? a.status : 'agendado',
        raw: a,
    };
}

function fromEvent(e) {
    const start = parseMinutes(e.event_time || '09:00');
    return {
        key: `e${e.id}`,
        source: 'evento',
        id: e.id,
        date: String(e.event_date || '').slice(0, 10),
        time: formatMinutes(start),
        start,
        end: start + DEFAULT_MINUTES,
        client: e.client_name || 'Cliente',
        phone: '',
        plate: e.plate_display || e.plate || '',
        model: e.car_model || '',
        service: e.title || e.service_type || 'Atendimento',
        symptoms: '',
        notes: e.notes || '',
        status: eventStatus(e.status),
        raw: e,
    };
}

function allItems() {
    const ags = (state.get('agendamentos') || []).map(fromAgendamento);
    const evs = (state.get('agendaEvents') || []).map(fromEvent);
    return [...ags, ...evs].filter((it) => it.date).sort((a, b) => a.date.localeCompare(b.date) || a.start - b.start);
}

function matchesSearch(item) {
    if (!search) return true;
    const q = normalizeText(search);
    const qPlate = cleanPlate(search);
    return [item.client, item.model, item.service, item.notes].some((v) => normalizeText(v).includes(q))
        || (qPlate.length >= 2 && cleanPlate(item.plate).includes(qPlate));
}

function groupByDate(items) {
    const map = new Map();
    for (const item of items) {
        if (!map.has(item.date)) map.set(item.date, []);
        map.get(item.date).push(item);
    }
    return map;
}

/** Distribui blocos que se sobrepõem em faixas lado a lado. */
function layoutLanes(items) {
    const sorted = [...items].sort((a, b) => a.start - b.start);
    const out = [];
    let cluster = [];
    let laneEnds = [];
    let clusterEnd = -1;
    const flush = () => {
        for (const entry of cluster) entry.lanes = laneEnds.length;
        out.push(...cluster);
        cluster = [];
        laneEnds = [];
        clusterEnd = -1;
    };
    for (const item of sorted) {
        if (cluster.length && item.start >= clusterEnd) flush();
        let lane = laneEnds.findIndex((end) => end <= item.start);
        if (lane === -1) {
            lane = laneEnds.length;
            laneEnds.push(item.end);
        } else {
            laneEnds[lane] = item.end;
        }
        clusterEnd = Math.max(clusterEnd, item.end);
        cluster.push({ item, lane, lanes: 1 });
    }
    flush();
    return out;
}

/* ------------------------------------------------------------------ */
/* Casca                                                               */
/* ------------------------------------------------------------------ */

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Agenda</h1>
                <p class="page-subtitle" data-field="summary">Atendimentos agendados da oficina</p>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-secondary btn-icon" data-action="refresh" aria-label="Atualizar" data-tooltip="Atualizar">${icon('refresh-cw', 16)}</button>
                <button type="button" class="btn btn-secondary" data-action="new">${icon('calendar-plus', 16)} Novo agendamento</button>
            </div>
        </header>
        <div class="ag-toolbar">
            <div class="ag-nav">
                <button type="button" class="btn btn-secondary" data-action="today">Hoje</button>
                <div class="btn-group">
                    <button type="button" class="btn btn-secondary btn-icon" data-action="prev" aria-label="Anterior" data-tooltip="Anterior">${icon('chevron-left', 16)}</button>
                    <button type="button" class="btn btn-secondary btn-icon" data-action="next" aria-label="Próximo" data-tooltip="Próximo">${icon('chevron-right', 16)}</button>
                </div>
                <h2 class="ag-range" data-field="range" aria-live="polite"></h2>
            </div>
            <div class="ag-toolbar-end">
                <div class="input-group ag-search">
                    ${icon('list-filter', 16, 'input-icon')}
                    <input type="search" class="input" data-field="search" placeholder="Filtrar por cliente, placa ou serviço" aria-label="Filtrar agendamentos" autocomplete="off">
                </div>
                <div class="segmented" role="group" aria-label="Visão do calendário">
                    ${VIEWS.map(([key, label]) => html`<button type="button" class="segmented-item${key === view ? ' is-active' : ''}" aria-pressed="${key === view}" data-mode="${key}">${label}</button>`)}
                </div>
            </div>
        </div>
        <section class="card ag-calendar" data-field="calendar" aria-label="Calendário de agendamentos"></section>`);

    on(root, 'click', '[data-mode]', (e, btn) => {
        view = btn.dataset.mode;
        storeView();
        $$('[data-mode]', root).forEach((b) => {
            b.classList.toggle('is-active', b === btn);
            b.setAttribute('aria-pressed', String(b === btn));
        });
        renderCalendar();
    });
    on(root, 'input', '[data-field="search"]', (e, input) => {
        search = input.value.trim();
        renderCalendar();
    });
    on(root, 'click', '[data-action]', handleAction);
    on(root, 'click', '.ag-col', handleSlotClick);

    state.watch('agendamentos', renderCalendar);
    state.watch('agendaEvents', renderCalendar);
}

function handleAction(e, btn) {
    const action = btn.dataset.action;
    if (action === 'refresh') {
        refresh('agendamentos', 'agendaEvents').then(() => toast('Agenda atualizada.', 'success'));
    } else if (action === 'new') {
        openForm(null, { date: toIsoDate(cursor) === todayIso() || view === 'mes' ? todayIso() : toIsoDate(cursor) });
    } else if (action === 'today') {
        cursor = startOfDay(new Date());
        renderCalendar();
    } else if (action === 'prev' || action === 'next') {
        shift(action === 'next' ? 1 : -1);
    } else if (action === 'goto-day') {
        cursor = fromIso(btn.dataset.date);
        view = 'dia';
        storeView();
        $$('[data-mode]', root).forEach((b) => {
            b.classList.toggle('is-active', b.dataset.mode === view);
            b.setAttribute('aria-pressed', String(b.dataset.mode === view));
        });
        renderCalendar();
    } else if (action === 'open') {
        const item = allItems().find((it) => it.key === btn.dataset.key);
        if (item) openDetail(item);
    } else if (action === 'clear-search') {
        search = '';
        $('[data-field="search"]', root).value = '';
        renderCalendar();
    }
}

function shift(direction) {
    if (view === 'dia') cursor = addDays(cursor, direction);
    else if (view === 'semana') cursor = addDays(cursor, 7 * direction);
    else cursor = new Date(cursor.getFullYear(), cursor.getMonth() + direction, 1);
    renderCalendar();
}

/** Clique num horário vazio da grade cria um agendamento naquele horário. */
function handleSlotClick(e, col) {
    if (e.target !== col) return;
    const rect = col.getBoundingClientRect();
    const hours = Number(col.dataset.hours);
    const first = Number(col.dataset.first);
    const minutes = first * 60 + Math.floor(((e.clientY - rect.top) / rect.height) * hours * 2) * 30;
    openForm(null, { date: col.dataset.date, time: formatMinutes(Math.max(0, Math.min(minutes, 23 * 60))) });
}

/* ------------------------------------------------------------------ */
/* Calendário                                                          */
/* ------------------------------------------------------------------ */

function renderCalendar() {
    if (!root) return;
    const host = $('[data-field="calendar"]', root);
    $('[data-field="range"]', root).textContent = rangeLabel();

    const loaded = state.get('agendamentos') !== undefined && state.get('agendamentos') !== null;
    if (!loaded) {
        render(host, html`<div class="ag-skeleton" aria-hidden="true"><div class="skeleton skeleton-block ag-skeleton-block"></div></div><span class="sr-only">Carregando agenda…</span>`);
        return;
    }

    const items = allItems();
    renderSummary(items);
    const [from, to] = visibleRange();
    const fromIsoText = toIsoDate(from);
    const toIsoText = toIsoDate(to);
    const filtered = items.filter(matchesSearch);
    const inRange = filtered.filter((it) => it.date >= fromIsoText && it.date <= toIsoText);

    if (!inRange.length) {
        renderEmpty(host, filtered);
        return;
    }
    const byDate = groupByDate(inRange);
    if (view === 'mes') renderMonth(host, byDate, from, to);
    else renderTimeGrid(host, byDate, view === 'dia' ? [startOfDay(cursor)] : Array.from({ length: 7 }, (_, i) => addDays(from, i)));
}

function renderSummary(items) {
    const today = todayIso();
    const weekStart = startOfWeek(new Date());
    const weekFrom = toIsoDate(weekStart);
    const weekTo = toIsoDate(addDays(weekStart, 6));
    const open = items.filter((it) => it.status !== 'cancelado' && it.status !== 'concluido');
    const todayCount = open.filter((it) => it.date === today).length;
    const weekCount = open.filter((it) => it.date >= weekFrom && it.date <= weekTo).length;
    $('[data-field="summary"]', root).textContent = `${plural(todayCount, 'atendimento')} hoje · ${plural(weekCount, 'atendimento')} nesta semana`;
}

function statusLabel(status) {
    return (STATUS[status] || STATUS.agendado).label;
}

function itemAria(item) {
    return `${item.time}, ${item.client}${item.plate ? `, placa ${formatPlate(item.plate)}` : ''}, ${item.service}, ${statusLabel(item.status)}`;
}

function renderEmpty(host, filtered) {
    const scopeText = view === 'dia' ? 'neste dia' : view === 'semana' ? 'nesta semana' : 'neste mês';
    const today = todayIso();
    const upcoming = filtered
        .filter((it) => it.date >= today && it.status !== 'cancelado' && it.status !== 'concluido')
        .slice(0, 6);
    render(host, html`<div class="ag-empty">
        <div class="empty-state">
            <span class="empty-state-icon">${icon('calendar', 20)}</span>
            <div class="empty-state-title">${search ? 'Nada encontrado' : `Sem agendamentos ${scopeText}`}</div>
            <div class="empty-state-text">${search ? 'Nenhum agendamento combina com o filtro digitado.' : 'Navegue para outro período ou agende um novo atendimento.'}</div>
            <div class="empty-state-actions">
                ${search ? html`<button type="button" class="btn btn-secondary btn-sm" data-action="clear-search">${icon('x', 15)} Limpar filtro</button>` : ''}
                <button type="button" class="btn btn-secondary btn-sm" data-action="new">${icon('calendar-plus', 15)} Novo agendamento</button>
            </div>
        </div>
        ${upcoming.length ? html`<div class="ag-upcoming">
            <h3 class="ag-upcoming-title">Próximos agendamentos</h3>
            <ul class="ag-upcoming-list">${upcoming.map((it) => html`<li>
                <button type="button" class="ag-upcoming-item" data-action="open" data-key="${it.key}" data-status="${it.status}">
                    <span class="ag-upcoming-when"><span class="ag-upcoming-day">${relativeDay(it.date)}</span><span class="num text-muted">${it.time}</span></span>
                    <span class="ag-upcoming-main"><span class="fw-medium truncate">${it.client}</span><span class="text-sm text-muted truncate">${it.service}</span></span>
                    ${it.plate ? html`<span class="plate-chip">${formatPlate(it.plate)}</span>` : ''}
                    <span class="tag ${STATUS[it.status].tag}">${statusLabel(it.status)}</span>
                </button>
            </li>`)}</ul>
        </div>` : ''}
    </div>`);
}

function relativeDay(iso) {
    const today = startOfDay(new Date());
    const date = fromIso(iso);
    const diff = Math.round((date - today) / 86400000);
    if (diff === 0) return 'Hoje';
    if (diff === 1) return 'Amanhã';
    return capitalize(`${WEEKDAY_SHORT.format(date).replace('.', '')}, ${pad2(date.getDate())}/${pad2(date.getMonth() + 1)}`);
}

/* ---------- Dia e semana: grade de horários ---------- */

function renderTimeGrid(host, byDate, days) {
    const all = [...byDate.values()].flat();
    let first = 7;
    let last = 19;
    for (const it of all) {
        first = Math.min(first, Math.floor(it.start / 60));
        last = Math.max(last, Math.ceil(it.end / 60));
    }
    last = Math.min(24, last);
    const hours = last - first;
    const today = todayIso();
    const now = new Date();
    const nowMinutes = now.getHours() * 60 + now.getMinutes();
    const compact = days.length > 1;

    const hourLabels = Array.from({ length: hours }, (_, i) => html`<div class="ag-hour"><span class="num">${pad2(first + i)}:00</span></div>`);

    const columns = days.map((day) => {
        const iso = toIsoDate(day);
        const laid = layoutLanes(byDate.get(iso) || []);
        const showNow = iso === today && nowMinutes >= first * 60 && nowMinutes <= last * 60;
        return html`<div class="ag-col${iso === today ? ' is-today' : ''}" data-date="${iso}" data-first="${first}" data-hours="${hours}">
            ${laid.map(({ item, lane, lanes }) => html`<button type="button" class="ag-block${compact ? ' is-compact' : ''}" data-action="open" data-key="${item.key}" data-status="${item.status}"
                data-top="${((item.start - first * 60) / (hours * 60)) * 100}" data-height="${((item.end - item.start) / (hours * 60)) * 100}" data-lane="${lane}" data-lanes="${lanes}"
                aria-label="${itemAria(item)}" title="${itemAria(item)}">
                <span class="ag-block-head"><span class="ag-block-time num">${item.time}</span><span class="ag-block-client truncate">${item.client}</span></span>
                <span class="ag-block-body">
                    ${item.plate ? (compact ? html`<span class="plate-chip plate-chip-sm">${formatPlate(item.plate)}</span>` : plateBadge(item.plate, 'sm')) : ''}
                    <span class="ag-block-service truncate">${item.service}</span>
                </span>
            </button>`)}
            ${showNow ? html`<span class="ag-now" data-top="${((nowMinutes - first * 60) / (hours * 60)) * 100}" aria-hidden="true"></span>` : ''}
        </div>`;
    });

    render(host, html`<div class="ag-scroller" data-field="scroller">
        <div class="ag-timegrid" data-days="${days.length}">
            <div class="ag-corner"></div>
            ${days.map((day) => html`<button type="button" class="ag-dayhead${toIsoDate(day) === today ? ' is-today' : ''}" data-action="goto-day" data-date="${toIsoDate(day)}" aria-label="${capitalize(LONG_DATE.format(day))}">
                <span class="ag-dayhead-name">${WEEKDAY_SHORT.format(day).replace('.', '')}</span>
                <span class="ag-dayhead-num num">${day.getDate()}</span>
            </button>`)}
            <div class="ag-hours">${hourLabels}</div>
            ${columns}
        </div>
    </div>`);
    const grid = $('.ag-timegrid', host);
    setVar(grid, '--hours', String(hours));
    setVar(grid, '--days', String(days.length));
    $$('[data-top]', host).forEach((el) => {
        setVar(el, '--top', `${el.dataset.top}%`);
        if (el.dataset.height) setVar(el, '--h', `${el.dataset.height}%`);
        if (el.dataset.lane) {
            setVar(el, '--lane', el.dataset.lane);
            setVar(el, '--lanes', el.dataset.lanes);
        }
    });

    const key = `${view}|${toIsoDate(days[0])}`;
    if (key !== scrollKey) {
        scrollKey = key;
        const scroller = $('[data-field="scroller"]', host);
        const firstItemStart = Math.min(...all.map((it) => it.start));
        const anchor = days.some((d) => toIsoDate(d) === today) ? Math.min(Math.max(nowMinutes - 60, first * 60), firstItemStart) : firstItemStart;
        const hourHeight = scroller.querySelector('.ag-hour')?.offsetHeight || 68;
        scroller.scrollTop = Math.max(0, ((anchor - first * 60) / 60) * hourHeight - hourHeight / 2);
    }
}

/* ---------- Mês ---------- */

function renderMonth(host, byDate, from, to) {
    const today = todayIso();
    const weeks = Math.round((to - from) / 86400000 / 7) + 1;
    const days = Array.from({ length: weeks * 7 }, (_, i) => addDays(from, i));
    const names = days.slice(0, 7).map((d) => WEEKDAY_SHORT.format(d).replace('.', ''));

    render(host, html`<div class="ag-month" data-weeks="${weeks}">
        ${names.map((name) => html`<div class="ag-month-head">${name}</div>`)}
        ${days.map((day) => {
            const iso = toIsoDate(day);
            const list = byDate.get(iso) || [];
            const shown = list.slice(0, 3);
            const more = list.length - shown.length;
            return html`<div class="ag-cell${day.getMonth() !== cursor.getMonth() ? ' is-other' : ''}${iso === today ? ' is-today' : ''}">
                <button type="button" class="ag-daynum num" data-action="goto-day" data-date="${iso}" aria-label="${capitalize(LONG_DATE.format(day))}${list.length ? `, ${plural(list.length, 'agendamento')}` : ''}">${day.getDate()}</button>
                <div class="ag-cell-list">
                    ${shown.map((it) => html`<button type="button" class="ag-chip" data-action="open" data-key="${it.key}" data-status="${it.status}" aria-label="${itemAria(it)}">
                        <span class="ag-chip-time num">${it.time}</span><span class="truncate">${it.client}</span>
                    </button>`)}
                    ${more > 0 ? html`<button type="button" class="ag-more" data-action="goto-day" data-date="${iso}">+${more} ${more === 1 ? 'outro' : 'outros'}</button>` : ''}
                </div>
            </div>`;
        })}
    </div>`);
    setVar($('.ag-month', host), '--weeks', String(weeks));
}

/* ------------------------------------------------------------------ */
/* Detalhes e ações                                                    */
/* ------------------------------------------------------------------ */

function buildDetailModal() {
    detailModal = createModal({
        id: 'agenda-detalhe',
        title: 'Agendamento',
        icon: 'calendar-clock',
        size: 'md',
        body: '',
        footer: html`
            <button type="button" class="btn btn-danger-ghost push" data-action="delete">${icon('trash-2', 16)} Excluir</button>
            <button type="button" class="btn btn-secondary" data-action="edit">${icon('pencil', 16)} Editar</button>
            <button type="button" class="btn btn-secondary" data-action="confirm">${icon('calendar-check', 16)} Confirmar</button>
            <button type="button" class="btn btn-secondary" data-action="done">${icon('circle-check', 16)} Concluir</button>
            <button type="button" class="btn btn-primary" data-action="patio">${icon('warehouse', 16)} Mandar para o pátio</button>`,
    });
    on(detailModal.footer, 'click', '[data-action]', (e, btn) => runAction(btn.dataset.action, btn));
    on(detailModal.body, 'click', '[data-action]', (e, btn) => runAction(btn.dataset.action, btn));
}

function openDetail(item) {
    if (!detailModal) buildDetailModal();
    current = item;
    const status = STATUS[item.status];
    detailModal.setTitle(item.client);
    detailModal.setSubtitle(`${capitalize(LONG_DATE.format(fromIso(item.date)))} · ${item.time}`);
    detailModal.setBody(html`<div class="ag-detail">
        <div class="ag-detail-top">
            ${item.plate ? plateBadge(item.plate, 'md') : html`<span class="tag">Sem placa</span>`}
            <div class="ag-detail-car">
                <span class="fw-medium">${item.model || 'Veículo não informado'}</span>
                <span class="tag ${status.tag}">${icon(status.icon, 12)} ${status.label}</span>
            </div>
        </div>
        <dl class="ag-detail-list">
            <div><dt>${icon('wrench', 16)} Serviço</dt><dd>${item.service}</dd></div>
            ${item.symptoms ? html`<div><dt>${icon('message-square-text', 16)} Sintomas</dt><dd>${item.symptoms}</dd></div>` : ''}
            ${item.phone ? html`<div><dt>${icon('phone', 16)} Contato</dt><dd class="num">${item.phone}</dd></div>` : ''}
            ${item.notes ? html`<div><dt>${icon('sticky-note', 16)} Observação</dt><dd>${item.notes}</dd></div>` : ''}
        </dl>
        ${item.source === 'agendamento' && item.status !== 'concluido' && item.status !== 'cancelado'
            ? html`<button type="button" class="btn btn-ghost btn-sm" data-action="ficha" title="Abre a ficha pré-preenchida. A planilha só é criada quando você salvar.">${icon('log-in', 15)} Criar ficha de entrada</button>` : ''}
    </div>`);
    const open = item.status !== 'concluido' && item.status !== 'cancelado';
    $('[data-action="confirm"]', detailModal.footer).hidden = item.status !== 'agendado';
    $('[data-action="done"]', detailModal.footer).hidden = !open;
    $('[data-action="patio"]', detailModal.footer).hidden = !open;
    detailModal.open();
}

async function runAction(action, btn) {
    const item = current;
    if (!item) return;
    if (action === 'edit') {
        detailModal.close();
        openForm(item);
    } else if (action === 'ficha') {
        detailModal.close();
        openOsFromAgendamento(item.raw);
    } else if (action === 'confirm' || action === 'done') {
        await changeStatus(item, action === 'confirm' ? 'confirmado' : 'concluido', btn);
    } else if (action === 'patio') {
        await sendToYard(item, btn);
    } else if (action === 'delete') {
        await removeItem(item);
    }
}

async function changeStatus(item, status, btn) {
    const restore = busy(btn);
    try {
        if (item.source === 'agendamento') {
            await api.post(`/api/agendamentos/${encodeURIComponent(item.id)}/status`, { status }, { errorMessage: 'Erro ao atualizar o agendamento' });
        } else {
            await api.post('/api/agenda/status', { id: item.id, status: EVENT_STATUS_TEXT[status] }, { errorMessage: 'Erro ao atualizar o agendamento' });
        }
        toast(status === 'confirmado' ? 'Agendamento confirmado.' : 'Agendamento concluído.', 'success');
        detailModal.close();
        await refresh('agendamentos', 'agendaEvents');
    } catch (err) {
        toast(err.message, 'error');
    } finally {
        restore();
    }
}

async function sendToYard(item, btn) {
    const cleaned = cleanPlate(item.plate);
    if (item.source === 'agendamento' && !cleaned) {
        toast('Informe a placa do veículo (em Editar) antes de mandar para o pátio.', 'error');
        return;
    }
    const restore = busy(btn);
    try {
        if (item.source === 'evento') {
            await api.post(`/api/agenda/${encodeURIComponent(item.id)}/to_patio`, { status: 'Em Diagnóstico' }, { errorMessage: 'Erro ao mandar para o pátio' });
        } else {
            await api.post('/api/patio', {
                plate: cleaned,
                client_name: item.client,
                car_model: item.model,
                status: 'Em Diagnóstico',
                notes: [`Agendamento: ${item.service}`, item.notes].filter(Boolean).join(' - '),
            }, { errorMessage: 'Erro ao mandar para o pátio' });
            await api.post(`/api/agendamentos/${encodeURIComponent(item.id)}/status`, { status: 'concluido' }, { errorMessage: 'Erro ao atualizar o agendamento' });
        }
        toast('Veículo adicionado ao pátio.', 'success');
        detailModal.close();
        await refresh('patio', 'agendamentos', 'agendaEvents');
    } catch (err) {
        toast(err.message, 'error');
    } finally {
        restore();
    }
}

async function removeItem(item) {
    const ok = await confirmDialog({
        title: 'Excluir agendamento?',
        message: `${item.client} · ${item.time} — esta ação não pode ser desfeita.`,
        confirmLabel: 'Excluir',
        danger: true,
    });
    if (!ok) return;
    try {
        const path = item.source === 'agendamento' ? '/api/agendamentos' : '/api/agenda';
        await api.del(`${path}/${encodeURIComponent(item.id)}`, { errorMessage: 'Erro ao excluir o agendamento' });
        toast('Agendamento excluído.', 'success');
        detailModal.close();
        await refresh('agendamentos', 'agendaEvents');
    } catch (err) {
        toast(err.message, 'error');
    }
}

/* ------------------------------------------------------------------ */
/* Formulário (criar / editar)                                         */
/* ------------------------------------------------------------------ */

function errorHint(name) {
    return html`<span class="field-hint is-error" data-error="${name}" role="alert" hidden></span>`;
}

function buildFormModal() {
    formModal = createModal({
        id: 'agendamento',
        title: 'Novo agendamento',
        icon: 'calendar-plus',
        size: 'md',
        closeOnBackdrop: false,
        body: html`<form class="form-grid ag-form" id="agendamento-form" novalidate autocomplete="off">
            <input type="hidden" name="id">
            <div class="field col-7 ag-client">
                <label class="field-label" for="ag-client">Cliente <span class="req">*</span></label>
                <input class="input" id="ag-client" name="client_name" placeholder="Nome ou placa já cadastrada" role="combobox" aria-expanded="false" aria-controls="ag-client-list" aria-autocomplete="list" autocomplete="off">
                <div class="dropdown-list" id="ag-client-list" role="listbox" data-field="suggestions" hidden></div>
                ${errorHint('client_name')}
            </div>
            <label class="field col-5"><span class="field-label">Celular / WhatsApp</span><input class="input input-mono" name="phone" inputmode="tel" placeholder="(13) 99752-9463">${errorHint('phone')}</label>
            <label class="field col-4"><span class="field-label">Placa</span><input class="input input-upper input-mono" name="car_plate" maxlength="8" placeholder="BRA2E19">${errorHint('car_plate')}</label>
            <label class="field col-8"><span class="field-label">Veículo</span><input class="input" name="car_model" placeholder="Ex.: VW Fox 1.0 Prata">${errorHint('car_model')}</label>
            <label class="field col-4"><span class="field-label">Data <span class="req">*</span></span><input class="input" type="date" name="scheduled_date">${errorHint('scheduled_date')}</label>
            <label class="field col-3"><span class="field-label">Hora <span class="req">*</span></span><input class="input" type="time" name="scheduled_time" step="900">${errorHint('scheduled_time')}</label>
            <label class="field col-5" data-field="status-field"><span class="field-label">Situação</span>
                <select class="select" name="status">${Object.entries(STATUS).map(([key, s]) => html`<option value="${key}">${s.label}</option>`)}</select>
            </label>
            <label class="field col-12"><span class="field-label">Serviço <span class="req">*</span></span><input class="input" name="title" list="ag-services" placeholder="Ex.: Troca de correia dentada">
                <datalist id="ag-services">${SERVICE_SUGGESTIONS.map((s) => html`<option value="${s}"></option>`)}</datalist>${errorHint('title')}</label>
            <label class="field col-12"><span class="field-label">Observação</span><textarea class="textarea" name="notes" rows="2" placeholder="Ex.: Cliente pediu para verificar barulho no freio"></textarea></label>
        </form>`,
        footer: html`
            <button type="button" class="btn btn-secondary" data-modal-close>Cancelar</button>
            <button type="submit" class="btn btn-primary" form="agendamento-form" data-action="save">${icon('save', 16)} Salvar</button>`,
    });
    const form = $('form', formModal.body);
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        save($('[data-action="save"]', formModal.footer));
    });
    form.addEventListener('input', (e) => clearError(e.target.name));
    wireClientAutocomplete(form);
    wirePlateAutofill(form);
}

export function openAgendamentoModal(ag = null) {
    openForm(ag ? fromAgendamento(ag) : null);
}

function openForm(item = null, defaults = {}) {
    if (!formModal) buildFormModal();
    const form = $('form', formModal.body);
    form.reset();
    $$('[data-error]', form).forEach((el) => { el.hidden = true; });
    $$('[aria-invalid]', form).forEach((el) => el.removeAttribute('aria-invalid'));
    hideSuggestions();
    const nextHour = Math.min(18, new Date().getHours() + 1);
    if (item) {
        formModal.setTitle('Editar agendamento');
        formModal.setSubtitle('');
        fillFields(form, {
            id: `${item.source}:${item.id}`,
            client_name: item.client === 'Cliente' && !item.raw.client_name ? '' : item.client,
            phone: item.phone,
            car_plate: item.plate ? cleanPlate(item.plate) : '',
            car_model: item.model,
            scheduled_date: item.date,
            scheduled_time: item.time,
            status: item.status,
            title: item.service,
            notes: item.notes,
        });
    } else {
        formModal.setTitle('Novo agendamento');
        formModal.setSubtitle('');
        fillFields(form, {
            id: '',
            scheduled_date: defaults.date || todayIso(),
            scheduled_time: defaults.time || `${pad2(nextHour)}:00`,
            status: 'agendado',
        });
    }
    $('[data-field="status-field"]', form).hidden = !item;
    formModal.open({ focus: false });
    setTimeout(() => form.elements.client_name.focus(), 60);
}

function setError(form, name, message) {
    const hint = $(`[data-error="${name}"]`, form);
    const input = form.elements[name];
    if (hint) {
        hint.textContent = message;
        hint.hidden = false;
    }
    if (input) input.setAttribute('aria-invalid', 'true');
}

function clearError(name) {
    if (!name || !formModal) return;
    const form = $('form', formModal.body);
    const hint = $(`[data-error="${name}"]`, form);
    if (hint) hint.hidden = true;
    form.elements[name]?.removeAttribute('aria-invalid');
}

function validate(form, v) {
    const problems = [];
    if (!v.client_name) problems.push(['client_name', 'Informe o nome do cliente.']);
    if (!v.scheduled_date || Number.isNaN(fromIso(v.scheduled_date).getTime())) problems.push(['scheduled_date', 'Escolha a data.']);
    if (!/^\d{2}:\d{2}$/.test(v.scheduled_time || '')) problems.push(['scheduled_time', 'Escolha a hora.']);
    if (!v.title) problems.push(['title', 'Informe o serviço solicitado.']);
    const cleaned = cleanPlate(v.car_plate);
    if (cleaned && cleaned.length !== 7) problems.push(['car_plate', 'A placa tem 7 caracteres.']);
    const digits = String(v.phone || '').replace(/\D/g, '');
    if (digits && (digits.length < 10 || digits.length > 13)) problems.push(['phone', 'Telefone com DDD, ex.: (13) 99752-9463.']);
    $$('[data-error]', form).forEach((el) => { el.hidden = true; });
    $$('[aria-invalid]', form).forEach((el) => el.removeAttribute('aria-invalid'));
    problems.forEach(([name, message]) => setError(form, name, message));
    if (problems.length) form.elements[problems[0][0]].focus();
    return problems.length === 0;
}

async function save(btn) {
    const form = $('form', formModal.body);
    const v = readFields(form);
    if (!validate(form, v)) return;
    const [source, rawId] = String(v.id || '').split(':');
    const plateValue = cleanPlate(v.car_plate);
    const restore = busy(btn, 'Salvando…');
    try {
        if (source === 'evento') {
            const original = (state.get('agendaEvents') || []).find((e) => String(e.id) === rawId) || {};
            await api.post('/api/agenda', {
                id: Number(rawId),
                title: v.title,
                client_name: v.client_name,
                plate: plateValue,
                car_model: v.car_model,
                service_type: original.service_type || v.title,
                event_date: v.scheduled_date,
                event_time: v.scheduled_time,
                notes: v.notes,
                status: EVENT_STATUS_TEXT[v.status] || 'Agendado',
            }, { errorMessage: 'Erro ao salvar o agendamento' });
        } else {
            const payload = {
                client_name: v.client_name,
                phone: v.phone,
                car_plate: plateValue,
                car_model: v.car_model,
                scheduled_date: v.scheduled_date,
                scheduled_time: v.scheduled_time,
                title: v.title,
                notes: v.notes,
            };
            if (source === 'agendamento') await api.put(`/api/agendamentos/${encodeURIComponent(rawId)}`, { ...payload, status: v.status }, { errorMessage: 'Erro ao salvar o agendamento' });
            else await api.post('/api/agendamentos', payload, { errorMessage: 'Erro ao salvar o agendamento' });
        }
        toast(source ? 'Agendamento atualizado.' : 'Agendamento salvo.', 'success');
        formModal.close();
        cursor = fromIso(v.scheduled_date);
        scrollKey = '';
        await refresh('agendamentos', 'agendaEvents');
        renderCalendar();
    } catch (err) {
        toast(`Erro ao salvar: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

/* ---------- Autocompletar cliente ---------- */

function knownClients() {
    const pool = [];
    for (const car of state.get('cars') || []) {
        pool.push({ client: car.client_name || '', plate: car.plate_display || car.plate_clean || '', model: car.car_model || '', phone: '' });
    }
    for (const a of state.get('agendamentos') || []) {
        pool.push({ client: a.client_name || '', plate: a.car_plate_display || a.car_plate || '', model: a.car_model || '', phone: a.phone || '' });
    }
    return pool.filter((p) => p.client);
}

function findSuggestions(query) {
    const q = normalizeText(query);
    const qPlate = cleanPlate(query);
    if (q.length < 2) return [];
    const seen = new Set();
    const result = [];
    for (const p of knownClients()) {
        const key = `${normalizeText(p.client)}|${cleanPlate(p.plate)}`;
        if (seen.has(key)) continue;
        const hit = normalizeText(p.client).includes(q) || normalizeText(p.model).includes(q) || (qPlate.length >= 2 && cleanPlate(p.plate).includes(qPlate));
        if (!hit) continue;
        seen.add(key);
        result.push(p);
        if (result.length >= 8) break;
    }
    return result;
}

function hideSuggestions() {
    if (!formModal) return;
    const list = $('[data-field="suggestions"]', formModal.body);
    list.hidden = true;
    suggestionIndex = -1;
    $('#ag-client', formModal.body)?.setAttribute('aria-expanded', 'false');
}

function highlightSuggestion(list, index) {
    const options = $$('.dropdown-option', list);
    suggestionIndex = options.length ? (index + options.length) % options.length : -1;
    options.forEach((opt, i) => {
        opt.classList.toggle('is-active', i === suggestionIndex);
        opt.setAttribute('aria-selected', String(i === suggestionIndex));
    });
    options[suggestionIndex]?.scrollIntoView({ block: 'nearest' });
}

function pickSuggestion(form, option) {
    const f = form.elements;
    f.client_name.value = option.dataset.client;
    if (option.dataset.plate && !f.car_plate.value) f.car_plate.value = cleanPlate(option.dataset.plate);
    if (option.dataset.model && !f.car_model.value) f.car_model.value = option.dataset.model;
    if (option.dataset.phone && !f.phone.value) f.phone.value = option.dataset.phone;
    clearError('client_name');
    hideSuggestions();
    (f.title.value ? f.scheduled_date : f.title).focus();
}

function wireClientAutocomplete(form) {
    const input = form.elements.client_name;
    const list = $('[data-field="suggestions"]', form);
    input.addEventListener('input', () => {
        const found = findSuggestions(input.value);
        if (!found.length) {
            hideSuggestions();
            return;
        }
        render(list, html`${found.map((p) => html`<button type="button" class="dropdown-option" role="option" aria-selected="false" tabindex="-1"
            data-client="${p.client}" data-plate="${p.plate}" data-model="${p.model}" data-phone="${p.phone}">
            <span class="fw-medium">${p.client}</span>
            <span class="text-xs text-subtle">${[p.plate ? formatPlate(p.plate) : '', p.model].filter(Boolean).join(' · ') || 'Sem veículo vinculado'}</span>
        </button>`)}`);
        list.hidden = false;
        input.setAttribute('aria-expanded', 'true');
        suggestionIndex = -1;
    });
    input.addEventListener('keydown', (e) => {
        if (list.hidden) return;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            highlightSuggestion(list, suggestionIndex + (e.key === 'ArrowDown' ? 1 : -1));
        } else if (e.key === 'Enter' && suggestionIndex >= 0) {
            e.preventDefault();
            pickSuggestion(form, $$('.dropdown-option', list)[suggestionIndex]);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            hideSuggestions();
        }
    });
    input.addEventListener('blur', () => setTimeout(hideSuggestions, 120));
    on(list, 'pointerdown', '.dropdown-option', (e) => e.preventDefault());
    on(list, 'click', '.dropdown-option', (e, option) => pickSuggestion(form, option));
}

/** Placa completa de um cliente conhecido preenche cliente e veículo vazios. */
function wirePlateAutofill(form) {
    const plateInput = form.elements.car_plate;
    plateInput.addEventListener('input', () => {
        const cleaned = cleanPlate(plateInput.value);
        if (plateInput.value !== cleaned) plateInput.value = cleaned;
        if (cleaned.length !== 7) return;
        const known = knownClients().find((p) => cleanPlate(p.plate) === cleaned);
        if (!known) return;
        if (!form.elements.client_name.value) form.elements.client_name.value = known.client;
        if (!form.elements.car_model.value) form.elements.car_model.value = known.model;
        if (!form.elements.phone.value && known.phone) form.elements.phone.value = known.phone;
        clearError('client_name');
    });
}

export default {
    id: 'agenda',
    title: 'Agenda',
    mount,
    enter() {
        cursor = startOfDay(cursor);
        renderCalendar();
        refresh('agendamentos', 'agendaEvents', 'cars');
    },
};
