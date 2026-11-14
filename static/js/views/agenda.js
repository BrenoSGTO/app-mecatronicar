/**
 * Agenda (#/agenda): agendamentos de atendimento da secretária
 * (GET/POST /api/agendamentos, PUT/DELETE /api/agendamentos/:id).
 * "Dar entrada" abre a ficha de OS pré-preenchida (a planilha só é criada ao salvar).
 * Os dados vêm do polling central (state 'agendamentos', a cada 10s).
 * Dono na Fase 2: T11.
 */
import { api } from '../api.js';
import { state } from '../state.js';
import { refresh } from '../data.js';
import { html, render, on, $, $$, readFields, fillFields, busy } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal, confirmDialog } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { addDays, cleanPlate, formatPlate, toIsoDate, todayIso, plural } from '../lib/format.js';
import { openOsFromAgendamento } from './os.js';

const STATUS = {
    agendado: { label: 'Agendado', tag: 'tag-info', icon: 'calendar-clock' },
    confirmado: { label: 'Confirmado', tag: 'tag-success', icon: 'calendar-check' },
    concluido: { label: 'Atendido', tag: '', icon: 'circle-check' },
    cancelado: { label: 'Cancelado', tag: 'tag-danger', icon: 'ban' },
};

let root = null;
let filter = 'today';   // 'today' | 'upcoming' | 'all'
let search = '';
let modal = null;

function ranges() {
    const today = todayIso();
    const next7 = toIsoDate(addDays(new Date(), 7));
    return {
        today: (a) => a.scheduled_date_iso === today,
        upcoming: (a) => a.scheduled_date_iso > today && a.scheduled_date_iso <= next7,
        all: () => true,
    };
}

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Agenda</h1>
                <p class="page-subtitle">Chegadas e agendamentos de atendimento · atualiza sozinha a cada 10 segundos</p>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-secondary" data-action="refresh">${icon('refresh-cw', 16)} Atualizar</button>
                <button type="button" class="btn btn-secondary" data-action="new">${icon('calendar-plus', 16)} Novo agendamento</button>
            </div>
        </header>
        <div class="agenda-toolbar">
            <div class="segmented" role="group" aria-label="Período">
                <button type="button" class="segmented-item is-active" data-filter="today">Hoje <span class="count" data-count="today">0</span></button>
                <button type="button" class="segmented-item" data-filter="upcoming">Próximos 7 dias <span class="count" data-count="upcoming">0</span></button>
                <button type="button" class="segmented-item" data-filter="all">Todos <span class="count" data-count="all">0</span></button>
            </div>
            <div class="input-group agenda-search">
                ${icon('list-filter', 16, 'input-icon')}
                <input type="search" class="input" data-field="search" placeholder="Filtrar por placa, cliente, carro ou serviço" autocomplete="off">
            </div>
        </div>
        <div data-field="list"></div>`);

    on(root, 'click', '[data-filter]', (e, btn) => {
        filter = btn.dataset.filter;
        $$('[data-filter]', root).forEach((b) => b.classList.toggle('is-active', b === btn));
        renderList();
    });
    on(root, 'input', '[data-field="search"]', (e, input) => {
        search = input.value.trim();
        renderList();
    });
    on(root, 'click', '[data-action]', (e, btn) => {
        const action = btn.dataset.action;
        const card = btn.closest('[data-id]');
        const ag = card ? (state.get('agendamentos') || []).find((a) => String(a.id) === card.dataset.id) : null;
        if (action === 'refresh') {
            refresh('agendamentos').then(() => toast('Agenda atualizada.', 'success'));
        } else if (action === 'new') {
            openAgendamentoModal();
        } else if (action === 'edit' && ag) {
            openAgendamentoModal(ag);
        } else if (action === 'checkin' && ag) {
            openOsFromAgendamento(ag);
        }
    });

    state.watch('agendamentos', renderList);
}

function renderList() {
    if (!root) return;
    const items = state.get('agendamentos');
    const listEl = $('[data-field="list"]', root);
    if (!items) {
        render(listEl, html`<div class="agenda-grid">${[1, 2, 3].map(() => html`<div class="skeleton skeleton-block"></div>`)}</div>`);
        return;
    }
    const r = ranges();
    $('[data-count="today"]', root).textContent = String(items.filter(r.today).length);
    $('[data-count="upcoming"]', root).textContent = String(items.filter(r.upcoming).length);
    $('[data-count="all"]', root).textContent = String(items.length);

    let list = items.filter(r[filter]);
    if (search) {
        const q = search.toLowerCase();
        const qPlate = cleanPlate(search);
        list = list.filter((a) => [a.client_name, a.car_model, a.title].some((v) => String(v || '').toLowerCase().includes(q))
            || (qPlate && String(a.car_plate_clean || '').includes(qPlate)));
    }

    if (!list.length) {
        render(listEl, html`<div class="card"><div class="empty-state">
            <span class="empty-state-icon">${icon('calendar', 20)}</span>
            <div class="empty-state-title">Sem agendamentos ${filter === 'today' ? 'para hoje' : filter === 'upcoming' ? 'nos próximos 7 dias' : ''}</div>
            <div class="empty-state-text">Nenhum atendimento previsto para o filtro selecionado.</div>
            <div class="empty-state-actions"><button type="button" class="btn btn-secondary btn-sm" data-action="new">${icon('calendar-plus', 15)} Agendar atendimento</button></div>
        </div></div>`);
        return;
    }

    render(listEl, html`<div class="agenda-grid">${list.map((ag) => {
        const st = STATUS[ag.status] || STATUS.agendado;
        const done = ag.status === 'concluido';
        const plateText = ag.car_plate_display || ag.car_plate;
        return html`<article class="card agenda-card${done ? ' is-done' : ''}${ag.status === 'cancelado' ? ' is-cancelled' : ''}" data-id="${ag.id}">
            <div class="agenda-card-top">
                <span class="agenda-card-time num">${ag.scheduled_time || '08:00'}</span>
                <span class="text-sm text-muted num">${ag.scheduled_date_display || ag.scheduled_date || ''}</span>
                <span class="tag ${st.tag} push">${icon(st.icon, 12)} ${st.label}</span>
            </div>
            <div class="row row-wrap">
                ${plateText ? html`<span class="plate-chip">${formatPlate(plateText)}</span>` : html`<span class="tag">Sem placa</span>`}
                <span class="fw-medium truncate">${ag.car_model || 'Veículo'}</span>
            </div>
            <div class="row row-wrap text-sm text-muted">
                <span>${icon('user', 14)} ${ag.client_name || 'Cliente'}</span>
                <span class="num">${icon('phone', 14)} ${ag.phone || 'sem telefone'}</span>
            </div>
            <div class="agenda-card-issue">
                <div class="fw-medium">${ag.title || 'Atendimento'}</div>
                ${ag.description ? html`<p class="text-sm text-muted">${ag.description}</p>` : ''}
                ${ag.notes ? html`<p class="text-xs text-subtle">${icon('sticky-note', 12)} ${ag.notes}</p>` : ''}
            </div>
            <div class="agenda-card-actions">
                ${done
                    ? html`<button type="button" class="btn btn-secondary btn-sm" disabled>${icon('circle-check', 15)} Entrada realizada</button>`
                    : html`<button type="button" class="btn btn-secondary btn-sm" data-action="checkin" title="Abre a ficha pré-preenchida. A planilha só é criada quando você salvar.">${icon('log-in', 15)} Dar entrada / criar ficha</button>`}
                <button type="button" class="btn btn-ghost btn-sm push" data-action="edit">${icon('pencil', 15)} Editar</button>
            </div>
        </article>`;
    })}</div>
    <p class="text-xs text-subtle agenda-footnote">${plural(list.length, 'agendamento')} exibido(s)</p>`);
}

/* ------------------------------ Modal ------------------------------ */

function buildModal() {
    modal = createModal({
        id: 'agendamento',
        title: 'Novo agendamento',
        icon: 'calendar-plus',
        size: 'md',
        body: html`<form class="form-grid" novalidate>
            <input type="hidden" name="id">
            <label class="field col-7"><span class="field-label">Nome do cliente <span class="req">*</span></span><input class="input" name="client_name" placeholder="Ex.: Danilo Rodrigues" autocomplete="off"></label>
            <label class="field col-5"><span class="field-label">Celular / WhatsApp</span><input class="input" name="phone" placeholder="(13) 99752-9463" autocomplete="off"></label>
            <label class="field col-4"><span class="field-label">Placa</span><input class="input input-upper input-mono" name="car_plate" maxlength="10" placeholder="FNB1A77" autocomplete="off"></label>
            <label class="field col-8"><span class="field-label">Modelo do carro</span><input class="input" name="car_model" placeholder="Ex.: VW Fox 1.0" autocomplete="off"></label>
            <label class="field col-4"><span class="field-label">Data <span class="req">*</span></span><input class="input" type="date" name="scheduled_date"></label>
            <label class="field col-3"><span class="field-label">Horário <span class="req">*</span></span><input class="input" type="time" name="scheduled_time" value="08:30"></label>
            <label class="field col-5"><span class="field-label">Status</span>
                <select class="select" name="status">
                    <option value="agendado">Agendado</option>
                    <option value="confirmado">Confirmado</option>
                    <option value="concluido">Atendido / concluído</option>
                    <option value="cancelado">Cancelado</option>
                </select>
            </label>
            <label class="field col-12"><span class="field-label">Problema / serviço solicitado <span class="req">*</span></span><input class="input" name="title" placeholder="Ex.: Troca de correia / revisão 50 mil km" autocomplete="off"></label>
            <label class="field col-12"><span class="field-label">Sintomas relatados</span><textarea class="textarea" name="description" rows="3" placeholder="Ex.: Barulho agudo na roda dianteira em lombadas"></textarea></label>
            <label class="field col-12"><span class="field-label">Observações internas</span><input class="input" name="notes" placeholder="Ex.: Ligar para confirmar um dia antes" autocomplete="off"></label>
        </form>`,
        footer: html`
            <button type="button" class="btn btn-danger-ghost push" data-action="delete" hidden>${icon('trash-2', 16)} Excluir</button>
            <button type="button" class="btn btn-secondary" data-modal-close>Cancelar</button>
            <button type="button" class="btn btn-primary" data-action="save">${icon('save', 16)} Salvar agendamento</button>`,
    });
    on(modal.footer, 'click', '[data-action]', (e, btn) => {
        if (btn.dataset.action === 'save') save(btn);
        else if (btn.dataset.action === 'delete') remove();
    });
    modal.body.querySelector('form').addEventListener('submit', (e) => {
        e.preventDefault();
        save(modal.footer.querySelector('[data-action="save"]'));
    });
}

export function openAgendamentoModal(ag = null) {
    if (!modal) buildModal();
    const form = modal.body.querySelector('form');
    form.reset();
    if (ag) {
        modal.setTitle('Editar agendamento');
        fillFields(form, {
            id: ag.id,
            client_name: ag.client_name || '',
            phone: ag.phone || '',
            car_plate: ag.car_plate || '',
            car_model: ag.car_model || '',
            scheduled_date: ag.scheduled_date_iso || ag.scheduled_date || todayIso(),
            scheduled_time: ag.scheduled_time || '08:30',
            status: ag.status || 'agendado',
            title: ag.title || '',
            description: ag.description || '',
            notes: ag.notes || '',
        });
    } else {
        modal.setTitle('Novo agendamento');
        fillFields(form, { id: '', scheduled_date: todayIso(), scheduled_time: '08:30', status: 'agendado' });
    }
    modal.footer.querySelector('[data-action="delete"]').hidden = !ag;
    modal.open();
}

async function save(btn) {
    const form = modal.body.querySelector('form');
    const v = readFields(form);
    const checks = [['client_name', 'O nome do cliente é obrigatório.'], ['title', 'Informe o problema ou serviço solicitado.'], ['scheduled_date', 'A data é obrigatória.']];
    for (const [name, message] of checks) {
        if (!v[name]) {
            toast(message, 'error');
            form.elements[name].focus();
            return;
        }
    }
    const payload = {
        client_name: v.client_name,
        phone: v.phone,
        car_plate: (v.car_plate || '').toUpperCase(),
        car_model: v.car_model,
        scheduled_date: v.scheduled_date,
        scheduled_time: v.scheduled_time || '08:30',
        status: v.status,
        title: v.title,
        description: v.description,
        notes: v.notes,
    };
    const restore = busy(btn, 'Salvando…');
    try {
        if (v.id) await api.put(`/api/agendamentos/${encodeURIComponent(v.id)}`, payload, { errorMessage: 'Erro ao salvar agendamento' });
        else await api.post('/api/agendamentos', payload, { errorMessage: 'Erro ao salvar agendamento' });
        toast(v.id ? 'Agendamento atualizado.' : 'Agendamento salvo.', 'success');
        modal.close();
        await refresh('agendamentos');
    } catch (err) {
        toast(`Erro ao salvar: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

async function remove() {
    const id = modal.body.querySelector('form').elements.id.value;
    if (!id) return;
    const ok = await confirmDialog({ title: 'Excluir agendamento?', message: 'Esta ação não pode ser desfeita.', confirmLabel: 'Excluir', danger: true });
    if (!ok) return;
    try {
        await api.del(`/api/agendamentos/${encodeURIComponent(id)}`, { errorMessage: 'Erro ao excluir' });
        toast('Agendamento excluído.', 'success');
        modal.close();
        await refresh('agendamentos');
    } catch (err) {
        toast(`Erro ao excluir: ${err.message}`, 'error');
    }
}

export default {
    id: 'agenda',
    title: 'Agenda',
    mount,
    enter() {
        refresh('agendamentos');
    },
};
