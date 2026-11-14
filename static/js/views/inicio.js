/**
 * Tela Início / Pátio (#/inicio).
 * - Centro: carros no pátio (abas Ativos / Entregues nas últimas 48h, filtros por status).
 * - Coluna lateral: eventos da agenda (GET /api/agenda) e histórico rápido (veículos indexados).
 * Dono na Fase 2: T7.
 */
import { api } from '../api.js';
import { state } from '../state.js';
import { refresh } from '../data.js';
import { navigate } from '../router.js';
import { html, render, on, $, readFields, busy } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal, confirmDialog } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { plate, statusTag } from '../ui/vehicle.js';
import { PATIO_STATUSES, statusKey, statusLabel, statusValue } from '../lib/patio.js';
import {
    formatDateBr, formatDelivered, formatPlate, formatRelativeDay, formatTimeInYard,
    isoToBr, plural, shortName, todayIso,
} from '../lib/format.js';
import { openPatioManager } from './patio.js';

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

let root = null;
const ui = {
    tab: 'active',          // 'active' | 'delivered'
    statusFilter: 'all',    // 'all' | chave de status
    agendaPeriod: 'all',    // 'all' | 'today' | 'upcoming'
    historyFilter: '',
};
let agendaModal = null;

function vehicleHref(plateValue) {
    return `/veiculo/${encodeURIComponent(plateValue)}`;
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
                <p class="page-subtitle" data-field="subtitle">${formatDateBr(new Date())}</p>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-secondary" data-action="patio-manage">${icon('warehouse', 16)} Gerenciar pátio</button>
                <button type="button" class="btn btn-secondary" data-action="patio-new">${icon('log-in', 16)} Entrada no pátio</button>
            </div>
        </header>

        <div class="inicio-grid">
            <section class="card inicio-patio" aria-label="Veículos no pátio">
                <div class="inicio-patio-head">
                    <div class="tabs" role="tablist">
                        <button type="button" class="tab" role="tab" aria-selected="true" data-tab="active">
                            ${icon('car-front', 16)} No pátio agora <span class="badge" data-count="active">0</span>
                        </button>
                        <button type="button" class="tab" role="tab" aria-selected="false" data-tab="delivered">
                            ${icon('package-check', 16)} Entregues (48h) <span class="badge" data-count="delivered">0</span>
                        </button>
                    </div>
                </div>
                <div class="inicio-patio-body">
                    <div class="filter-pills" data-field="filters"></div>
                    <p class="text-sm text-muted" data-field="delivered-hint" hidden>
                        Carros entregues saem da visão principal e ficam aqui por 48 horas para consulta rápida.
                    </p>
                    <div class="patio-grid" data-field="grid"></div>
                </div>
            </section>

            <aside class="inicio-side">
                <section class="card inicio-agenda" aria-label="Agendamentos">
                    <div class="card-header">
                        <div class="stack stack-1">
                            <span class="card-title">${icon('calendar-clock', 16)} Agendamentos <span class="badge" data-count="agenda">0</span></span>
                        </div>
                        <button type="button" class="btn btn-secondary btn-sm" data-action="agenda-new">${icon('plus', 15)} Novo</button>
                    </div>
                    <div class="inicio-side-toolbar">
                        <div class="segmented" role="group" aria-label="Período">
                            <button type="button" class="segmented-item is-active" data-period="all">Todos</button>
                            <button type="button" class="segmented-item" data-period="today">Hoje</button>
                            <button type="button" class="segmented-item" data-period="upcoming">Próximos</button>
                        </div>
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
                            <input type="search" class="input input-sm" data-field="history-filter" placeholder="Filtrar por placa, cliente ou modelo" autocomplete="off">
                        </div>
                    </div>
                    <div class="inicio-side-list" data-field="history"></div>
                </section>
            </aside>
        </div>`);

    bindEvents();

    state.watch('patio', renderPatio);
    state.watch('agendaEvents', renderAgenda);
    state.watch('cars', renderHistory);
}

/* ------------------------------------------------------------------ */
/* Pátio                                                               */
/* ------------------------------------------------------------------ */

function renderPatio() {
    if (!root) return;
    const patio = state.get('patio');
    const active = patio?.active || [];
    const delivered = patio?.delivered || [];

    $('[data-count="active"]', root).textContent = String(active.length);
    $('[data-count="delivered"]', root).textContent = String(delivered.length);
    $('[data-field="subtitle"]', root).textContent = `${formatDateBr(new Date())} · ${plural(active.length, 'veículo')} no pátio`;

    for (const tab of root.querySelectorAll('[data-tab]')) {
        tab.setAttribute('aria-selected', tab.dataset.tab === ui.tab ? 'true' : 'false');
    }

    const filtersEl = $('[data-field="filters"]', root);
    const hintEl = $('[data-field="delivered-hint"]', root);
    filtersEl.hidden = ui.tab !== 'active';
    hintEl.hidden = ui.tab !== 'delivered';

    if (!patio) {
        render($('[data-field="grid"]', root), html`${[1, 2, 3].map(() => html`<div class="skeleton skeleton-block patio-card-skeleton"></div>`)}`);
        return;
    }

    if (ui.tab === 'active') {
        const counts = {};
        for (const car of active) {
            const key = statusKey(car.status_display || car.status);
            counts[key] = (counts[key] || 0) + 1;
        }
        if (ui.statusFilter !== 'all' && !counts[ui.statusFilter]) ui.statusFilter = 'all';
        render(filtersEl, html`
            <button type="button" class="filter-pill${ui.statusFilter === 'all' ? ' is-active' : ''}" data-filter="all">Todos <span class="count">${active.length}</span></button>
            ${PATIO_STATUSES.filter((s) => counts[s.key]).map((s) => html`
                <button type="button" class="filter-pill${ui.statusFilter === s.key ? ' is-active' : ''}" data-filter="${s.key}" data-status="${s.key}">
                    <span class="status-dot"></span>${s.label} <span class="count">${counts[s.key]}</span>
                </button>`)}`);

        const list = ui.statusFilter === 'all'
            ? active
            : active.filter((c) => statusKey(c.status_display || c.status) === ui.statusFilter);
        renderCards(list, false);
    } else {
        renderCards(delivered, true);
    }
}

function renderCards(cars, delivered) {
    const grid = $('[data-field="grid"]', root);
    if (!cars.length) {
        render(grid, delivered
            ? html`<div class="empty-state patio-empty">
                <span class="empty-state-icon">${icon('package-check', 20)}</span>
                <div class="empty-state-title">Nenhum veículo entregue nas últimas 48 horas</div>
                <div class="empty-state-text">Ao marcar um carro como entregue, ele aparece aqui por dois dias.</div>
            </div>`
            : html`<div class="empty-state patio-empty">
                <span class="empty-state-icon">${icon('warehouse', 20)}</span>
                <div class="empty-state-title">Nenhum veículo neste status</div>
                <div class="empty-state-text">Use “Entrada no pátio” para registrar a chegada de um carro.</div>
                <div class="empty-state-actions"><button type="button" class="btn btn-secondary btn-sm" data-action="patio-new">${icon('log-in', 15)} Entrada no pátio</button></div>
            </div>`);
        return;
    }
    render(grid, html`${cars.map((car) => (delivered ? deliveredCard(car) : activeCard(car)))}`);
}

function activeCard(car) {
    const status = car.status_display || car.status || 'Em Diagnóstico';
    const currentValue = statusValue(status);
    const plateValue = car.plate_clean || car.plate || '';
    const mechanic = car.mechanic_name || car.box_mecanico;
    return html`<article class="patio-card" data-status="${statusKey(status)}" data-car-id="${car.id}" data-plate="${plateValue}" tabindex="0" aria-label="Abrir histórico de ${formatPlate(car.plate_display || car.plate)}">
        <div class="patio-card-top">
            ${plate(car.plate_display || car.plate, 'sm')}
            ${statusTag(status, statusLabel(status))}
        </div>
        <div class="patio-card-body">
            <div class="patio-card-model truncate" title="${car.car_model || ''}">${car.car_model || 'Modelo não informado'}${car.car_color ? html` <span class="text-subtle">· ${car.car_color}</span>` : ''}</div>
            <div class="patio-card-owner truncate" title="${car.client_name || ''}">${icon('user', 14)} ${shortName(car.client_name)}</div>
        </div>
        <div class="patio-card-meta">
            <span title="Tempo no pátio">${icon('clock', 14)} ${formatTimeInYard(car.updated_at || car.updated_time || car.entry_date)}</span>
            ${mechanic ? html`<span class="truncate" title="${mechanic}">${icon('wrench', 14)} ${mechanic}</span>` : ''}
        </div>
        ${car.notes ? html`<p class="patio-card-notes" title="${car.notes}">${car.notes}</p>` : ''}
        <div class="patio-card-actions">
            <select class="select input-sm" data-action="status" aria-label="Alterar status">
                ${PATIO_STATUSES.map((s) => html`<option value="${s.value}"${s.value === currentValue ? html` selected` : ''}>${s.label}</option>`)}
            </select>
            <button type="button" class="btn btn-secondary btn-sm" data-action="deliver" title="Marcar como entregue">${icon('package-check', 15)} Entregar</button>
        </div>
    </article>`;
}

function deliveredCard(car) {
    const plateValue = car.plate_clean || car.plate || '';
    return html`<article class="patio-card is-delivered" data-status="entregue" data-car-id="${car.id}" data-plate="${plateValue}" tabindex="0">
        <div class="patio-card-top">
            ${plate(car.plate_display || car.plate, 'sm')}
            ${statusTag('Entregue')}
        </div>
        <div class="patio-card-body">
            <div class="patio-card-model truncate">${car.car_model || 'Modelo não informado'}${car.car_color ? html` <span class="text-subtle">· ${car.car_color}</span>` : ''}</div>
            <div class="patio-card-owner truncate">${icon('user', 14)} ${shortName(car.client_name)}</div>
        </div>
        <div class="patio-card-meta">
            <span class="text-success">${icon('circle-check', 14)} ${formatDelivered(car.updated_at || car.updated_time)}</span>
        </div>
        ${car.notes ? html`<p class="patio-card-notes">${car.notes}</p>` : ''}
        <div class="patio-card-actions">
            <button type="button" class="btn btn-secondary btn-sm" data-action="reactivate">${icon('undo-2', 15)} Retornar ao pátio</button>
            <button type="button" class="btn btn-ghost btn-sm" data-action="history">${icon('history', 15)} Histórico</button>
        </div>
    </article>`;
}

async function setPatioStatus(id, status, message) {
    try {
        await api.post('/api/patio/status', { id, status }, { errorMessage: 'Erro ao alterar status' });
        toast(message, 'success');
        await refresh('patio');
        return true;
    } catch (err) {
        toast(`Não foi possível alterar o status: ${err.message}`, 'error');
        return false;
    }
}

/* ------------------------------------------------------------------ */
/* Agenda (eventos do calendário)                                      */
/* ------------------------------------------------------------------ */

function renderAgenda(events) {
    if (!root) return;
    const listEl = $('[data-field="agenda"]', root);
    const today = todayIso();
    let list = events || [];
    if (ui.agendaPeriod === 'today') list = list.filter((ev) => ev.event_date === today);
    else if (ui.agendaPeriod === 'upcoming') list = list.filter((ev) => ev.event_date >= today);

    $('[data-count="agenda"]', root).textContent = String(list.length);
    for (const btn of root.querySelectorAll('[data-period]')) {
        btn.classList.toggle('is-active', btn.dataset.period === ui.agendaPeriod);
    }

    if (!events) {
        render(listEl, html`<div class="skeleton-stack inicio-side-pad"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>`);
        return;
    }
    if (!list.length) {
        render(listEl, html`<div class="empty-state empty-state-compact">
            <span class="empty-state-icon">${icon('calendar', 20)}</span>
            <div class="empty-state-title">Nenhum agendamento</div>
            <div class="empty-state-actions"><button type="button" class="btn btn-secondary btn-sm" data-action="agenda-new">${icon('plus', 15)} Agendar horário</button></div>
        </div>`);
        return;
    }

    render(listEl, html`${list.map((ev) => {
        const isToday = ev.event_date === today;
        const done = /conclu/i.test(ev.status || '');
        return html`<article class="agenda-event${done ? ' is-done' : ''}" data-event-id="${ev.id}">
            <div class="agenda-event-when">
                <span class="agenda-event-day${isToday ? ' is-today' : ''}">${formatRelativeDay(ev.event_date)}</span>
                <span class="agenda-event-time num">${ev.event_time || '09:00'}</span>
            </div>
            <div class="agenda-event-main">
                <div class="agenda-event-title">${ev.title || 'Agendamento'}</div>
                <div class="agenda-event-meta">
                    <span>${shortName(ev.client_name)}</span>
                    ${ev.plate ? html`<span class="plate-chip plate-chip-sm">${formatPlate(ev.plate_display || ev.plate)}</span>` : ''}
                    ${ev.car_model ? html`<span class="truncate">${ev.car_model}</span>` : ''}
                </div>
                ${ev.notes ? html`<p class="agenda-event-notes">${ev.notes}</p>` : ''}
                <div class="agenda-event-footer">
                    <span class="tag${done ? ' tag-success' : ''}">${ev.status || 'Agendado'}</span>
                    <div class="row row-gap-1">
                        <button type="button" class="btn btn-ghost btn-sm" data-action="event-to-patio" data-tooltip="Dar entrada no pátio">${icon('log-in', 15)} Pátio</button>
                        <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="event-done" aria-label="Marcar como concluído" data-tooltip="Concluir">${icon('check', 15)}</button>
                        <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="event-delete" aria-label="Excluir agendamento" data-tooltip="Excluir">${icon('trash-2', 15)}</button>
                    </div>
                </div>
            </div>
        </article>`;
    })}`);
}

function openAgendaModal() {
    if (!agendaModal) {
        agendaModal = createModal({
            id: 'agenda-event',
            title: 'Novo agendamento',
            icon: 'calendar-plus',
            size: 'sm',
            body: html`<form class="form-grid" novalidate>
                <label class="field col-12">
                    <span class="field-label">Título ou motivo <span class="req">*</span></span>
                    <input class="input" name="title" placeholder="Ex.: Revisão geral e troca de óleo" autocomplete="off" required>
                </label>
                <label class="field col-6"><span class="field-label">Data <span class="req">*</span></span><input class="input" type="date" name="event_date" required></label>
                <label class="field col-6"><span class="field-label">Horário <span class="req">*</span></span><input class="input" type="time" name="event_time" value="09:00" required></label>
                <label class="field col-6"><span class="field-label">Cliente <span class="req">*</span></span><input class="input" name="client_name" placeholder="Nome do cliente" autocomplete="off" required></label>
                <label class="field col-6"><span class="field-label">Placa</span><input class="input input-upper input-mono" name="plate" placeholder="Opcional" autocomplete="off"></label>
                <label class="field col-6"><span class="field-label">Modelo do carro</span><input class="input" name="car_model" placeholder="Ex.: VW Fox 1.0" autocomplete="off"></label>
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
        agendaModal.body.querySelector('form').addEventListener('submit', (e) => {
            e.preventDefault();
            saveAgendaEvent();
        });
    }
    const formEl = agendaModal.body.querySelector('form');
    formEl.reset();
    formEl.elements.event_date.value = todayIso();
    formEl.elements.event_time.value = '09:00';
    agendaModal.open();
}

async function saveAgendaEvent() {
    const formEl = agendaModal.body.querySelector('form');
    const v = readFields(formEl);
    const missing = ['title', 'event_date', 'event_time', 'client_name'].find((k) => !v[k]);
    if (missing) {
        toast('Preencha título, data, horário e cliente.', 'error');
        formEl.elements[missing].focus();
        return;
    }
    const restore = busy(agendaModal.footer.querySelector('[data-action="save"]'), 'Salvando…');
    try {
        await api.post('/api/agenda', {
            title: v.title,
            event_date: v.event_date,
            event_time: v.event_time || '09:00',
            client_name: v.client_name,
            plate: (v.plate || '').toUpperCase(),
            car_model: v.car_model,
            service_type: v.service_type || 'Revisão Geral',
            notes: v.notes,
            status: 'Agendado',
        }, { errorMessage: 'Erro ao salvar agendamento' });
        toast('Agendamento salvo.', 'success');
        agendaModal.close();
        await refresh('agendaEvents');
    } catch (err) {
        toast(`Erro ao salvar agendamento: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

async function eventAction(action, id) {
    try {
        if (action === 'event-to-patio') {
            await api.post(`/api/agenda/${encodeURIComponent(id)}/to_patio`, { status: 'Em Diagnóstico' }, { errorMessage: 'Erro ao dar entrada no pátio' });
            toast('Veículo adicionado ao pátio.', 'success');
            ui.tab = 'active';
            await refresh('patio', 'agendaEvents');
        } else if (action === 'event-done') {
            await api.post('/api/agenda/status', { id, status: 'Concluído' }, { errorMessage: 'Erro ao atualizar agendamento' });
            toast('Agendamento concluído.', 'success');
            await refresh('agendaEvents');
        } else if (action === 'event-delete') {
            const ok = await confirmDialog({ title: 'Excluir agendamento?', message: 'Esta ação não pode ser desfeita.', confirmLabel: 'Excluir', danger: true });
            if (!ok) return;
            await api.del(`/api/agenda/${encodeURIComponent(id)}`, { errorMessage: 'Erro ao excluir agendamento' });
            toast('Agendamento removido.', 'success');
            await refresh('agendaEvents');
        }
    } catch (err) {
        toast(err.message, 'error');
    }
}

/* ------------------------------------------------------------------ */
/* Histórico rápido                                                    */
/* ------------------------------------------------------------------ */

function renderHistory() {
    if (!root) return;
    const listEl = $('[data-field="history"]', root);
    const cars = state.get('cars');
    if (!cars) {
        render(listEl, html`<div class="skeleton-stack inicio-side-pad"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text"></div></div>`);
        return;
    }
    const q = ui.historyFilter.toLowerCase();
    const list = q
        ? cars.filter((c) => (c.plate_clean || '').toLowerCase().includes(q)
            || (c.client_name || '').toLowerCase().includes(q)
            || (c.car_model || '').toLowerCase().includes(q))
        : cars;
    $('[data-count="history"]', root).textContent = String(list.length);

    if (!list.length) {
        render(listEl, html`<div class="empty-state empty-state-compact"><div class="empty-state-title">Nenhum veículo encontrado</div></div>`);
        return;
    }
    render(listEl, html`<div class="list">${list.slice(0, 50).map((car) => {
        const date = isoToBr(car.latest_date_sort);
        return html`<a class="list-item" href="#${vehicleHref(car.plate_clean || car.plate_display || '')}">
            <span class="list-item-row">
                <span class="plate-chip">${formatPlate(car.plate_display || car.plate_clean)}</span>
                <span class="list-item-meta num">${plural(car.visit_count || 1, 'visita')}</span>
            </span>
            <span class="list-item-title truncate" title="${car.car_model || ''}">${car.car_model || 'Veículo'}</span>
            <span class="list-item-row list-item-meta">
                <span class="truncate" title="${car.client_name || ''}">${shortName(car.client_name)}</span>
                ${date ? html`<span class="num">${date}</span>` : ''}
            </span>
        </a>`;
    })}</div>`);
}

/* ------------------------------------------------------------------ */
/* Eventos                                                             */
/* ------------------------------------------------------------------ */

function bindEvents() {
    on(root, 'click', '[data-tab]', (e, btn) => {
        ui.tab = btn.dataset.tab;
        renderPatio();
    });

    on(root, 'click', '[data-filter]', (e, btn) => {
        ui.statusFilter = btn.dataset.filter;
        renderPatio();
    });

    on(root, 'click', '[data-period]', (e, btn) => {
        ui.agendaPeriod = btn.dataset.period;
        renderAgenda(state.get('agendaEvents'));
    });

    on(root, 'input', '[data-field="history-filter"]', (e, input) => {
        ui.historyFilter = input.value.trim();
        renderHistory();
    });

    on(root, 'click', '[data-action]', async (e, btn) => {
        const action = btn.dataset.action;
        const card = btn.closest('[data-car-id]');
        const eventEl = btn.closest('[data-event-id]');
        if (action === 'status') return; // tratado no 'change'
        e.stopPropagation();

        switch (action) {
            case 'patio-manage':
                openPatioManager();
                break;
            case 'patio-new':
                openPatioManager();
                break;
            case 'agenda-new':
                openAgendaModal();
                break;
            case 'deliver': {
                const restore = busy(btn);
                const ok = await setPatioStatus(card.dataset.carId, 'Entregue', `Veículo ${formatPlate(card.dataset.plate)} entregue e movido para "Entregues".`);
                if (!ok) restore();
                break;
            }
            case 'reactivate': {
                const ok = await setPatioStatus(card.dataset.carId, 'Em Diagnóstico', 'Veículo retornou ao pátio em Diagnóstico.');
                if (ok) {
                    ui.tab = 'active';
                    renderPatio();
                }
                break;
            }
            case 'history':
                if (card?.dataset.plate) navigate(vehicleHref(card.dataset.plate));
                break;
            case 'event-to-patio':
            case 'event-done':
            case 'event-delete':
                if (eventEl) eventAction(action, eventEl.dataset.eventId);
                break;
            default:
                break;
        }
    });

    on(root, 'change', 'select[data-action="status"]', (e, select) => {
        const card = select.closest('[data-car-id]');
        setPatioStatus(card.dataset.carId, select.value, `Status alterado para: ${select.value}`);
    });

    // Clique no corpo do card (fora de controles) abre o histórico do veículo
    on(root, 'click', '.patio-card', (e, card) => {
        if (e.target.closest('button, select, a, input')) return;
        if (card.dataset.plate) navigate(vehicleHref(card.dataset.plate));
    });
    on(root, 'keydown', '.patio-card', (e, card) => {
        if (e.key === 'Enter' && e.target === card && card.dataset.plate) navigate(vehicleHref(card.dataset.plate));
    });
}

export default {
    id: 'inicio',
    title: 'Início',
    mount,
    enter() {
        refresh('patio', 'agendaEvents');
    },
};
