/**
 * Modal "Gerenciar pátio": lista dos carros no pátio + formulário para
 * dar entrada / editar / remover (POST /api/patio, DELETE /api/patio/:id).
 * Dono na Fase 2: T7 (Início / Pátio).
 *
 *   import { openPatioManager } from './patio.js';
 *   openPatioManager();                                   // formulário vazio
 *   openPatioManager({ prefill: { plate, client_name, car_model, car_color } });
 */
import { api } from '../api.js';
import { state } from '../state.js';
import { refresh } from '../data.js';
import { html, render, on, readFields, fillFields, busy } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal, confirmDialog } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { statusTag } from '../ui/vehicle.js';
import { PATIO_STATUSES, THIRD_PARTY_STATUS, statusLabel, statusValue } from '../lib/patio.js';
import { cleanPlate, formatPlate } from '../lib/format.js';

let modal = null;
let form = null;
let listEl = null;
let unwatch = null;

const EMPTY = {
    id: '', plate: '', client_name: '', car_model: '', car_color: '',
    status: PATIO_STATUSES[0].value, box_mecanico: '', notes: '',
    authorized_name: '', authorized_doc: '', authorized_phone: '',
};

function build() {
    modal = createModal({
        id: 'patio-manager',
        title: 'Gerenciar pátio',
        subtitle: 'Entrada, status e saída dos veículos (atualiza o Painel TV ao vivo)',
        icon: 'warehouse',
        size: 'lg',
        body: html`
            <div class="patio-manager">
                <section class="patio-manager-list">
                    <div class="row row-between">
                        <span class="eyebrow">No pátio agora (<span data-field="count">0</span>)</span>
                        <a class="link-button text-sm" href="/tv" target="_blank" rel="noopener">${icon('tv', 14)} Abrir Painel TV</a>
                    </div>
                    <div class="patio-manager-rows" data-field="list"></div>
                </section>
                <form class="patio-manager-form stack" novalidate>
                    <input type="hidden" name="id">
                    <div class="form-grid">
                        <label class="field col-5">
                            <span class="field-label">Placa <span class="req">*</span></span>
                            <input class="input input-upper input-mono" name="plate" placeholder="Ex.: FNB1A77" autocomplete="off" required>
                        </label>
                        <label class="field col-7">
                            <span class="field-label">Cliente</span>
                            <input class="input" name="client_name" placeholder="Nome do cliente" autocomplete="off">
                        </label>
                        <label class="field col-7">
                            <span class="field-label">Modelo</span>
                            <input class="input" name="car_model" placeholder="Ex.: Fox 1.0, Sentra 2.0" autocomplete="off">
                        </label>
                        <label class="field col-5">
                            <span class="field-label">Cor</span>
                            <input class="input" name="car_color" placeholder="Ex.: Prata" autocomplete="off">
                        </label>
                        <label class="field col-7">
                            <span class="field-label">Status no pátio <span class="req">*</span></span>
                            <select class="select" name="status">
                                ${PATIO_STATUSES.map((s) => html`<option value="${s.value}">${s.value}</option>`)}
                            </select>
                        </label>
                        <label class="field col-5">
                            <span class="field-label">Box / mecânico</span>
                            <input class="input" name="box_mecanico" placeholder="Ex.: Elevador 1" autocomplete="off">
                        </label>
                        <label class="field col-12">
                            <span class="field-label">Observações / queixa principal</span>
                            <input class="input" name="notes" placeholder="Ex.: Troca de óleo e correia" autocomplete="off">
                        </label>
                    </div>
                    <fieldset class="patio-third-party callout callout-danger" data-field="third-party" hidden>
                        ${icon('user-check', 16)}
                        <div class="form-grid grow">
                            <div class="col-12 callout-title">Quem está autorizado a buscar o carro</div>
                            <label class="field col-7">
                                <span class="field-label">Nome do autorizado <span class="req">*</span></span>
                                <input class="input" name="authorized_name" placeholder="Nome completo" autocomplete="off">
                            </label>
                            <label class="field col-5">
                                <span class="field-label">RG ou CPF <span class="req">*</span></span>
                                <input class="input input-upper" name="authorized_doc" placeholder="Documento" autocomplete="off">
                            </label>
                            <label class="field col-12">
                                <span class="field-label">Telefone de contato</span>
                                <input class="input" name="authorized_phone" placeholder="(13) 99999-9999" autocomplete="off">
                            </label>
                        </div>
                    </fieldset>
                </form>
            </div>`,
        footer: html`
            <button type="button" class="btn btn-danger-ghost push" data-action="remove" hidden>${icon('trash-2', 16)} Remover do pátio</button>
            <button type="button" class="btn btn-secondary" data-action="clear">Limpar</button>
            <button type="button" class="btn btn-primary" data-action="save">${icon('save', 16)} Salvar no pátio</button>`,
        onClose: () => {
            unwatch?.();
            unwatch = null;
        },
    });

    form = modal.body.querySelector('form');
    listEl = modal.body.querySelector('[data-field="list"]');

    form.elements.status.addEventListener('change', syncThirdParty);
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        save();
    });
    form.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
            e.preventDefault();
            save();
        }
    });

    on(modal.footer, 'click', '[data-action]', (e, btn) => {
        if (btn.dataset.action === 'save') save();
        else if (btn.dataset.action === 'clear') fill(EMPTY);
        else if (btn.dataset.action === 'remove') remove();
    });

    on(listEl, 'click', '[data-car-id]', (e, row) => {
        const car = (state.get('patio')?.active || []).find((c) => String(c.id) === row.dataset.carId);
        if (car) fill(car);
    });
}

function syncThirdParty() {
    const isThird = form.elements.status.value === THIRD_PARTY_STATUS;
    modal.body.querySelector('[data-field="third-party"]').hidden = !isThird;
    form.elements.authorized_name.required = isThird;
    form.elements.authorized_doc.required = isThird;
}

function fill(car) {
    fillFields(form, {
        ...EMPTY,
        id: car.id || '',
        plate: car.plate_display || car.plate || '',
        client_name: car.client_name || '',
        car_model: car.car_model || '',
        car_color: car.car_color || '',
        status: car.status || car.status_display ? statusValue(car.status_display || car.status) : EMPTY.status,
        box_mecanico: car.box_mecanico || car.mechanic_name || '',
        notes: car.notes || '',
        authorized_name: car.authorized_name || car.third_party_name || '',
        authorized_doc: car.authorized_doc || car.third_party_doc || '',
        authorized_phone: car.authorized_phone || '',
    });
    modal.footer.querySelector('[data-action="remove"]').hidden = !car.id;
    syncThirdParty();
    highlightRow(car.id);
}

function highlightRow(id) {
    for (const row of listEl.querySelectorAll('[data-car-id]')) {
        row.classList.toggle('is-selected', String(row.dataset.carId) === String(id || ''));
    }
}

function renderList(patio) {
    const cars = patio?.active || [];
    modal.body.querySelector('[data-field="count"]').textContent = String(cars.length);
    if (!cars.length) {
        render(listEl, html`<div class="empty-state empty-state-compact">
            <span class="empty-state-icon">${icon('warehouse', 20)}</span>
            <div class="empty-state-title">Pátio vazio</div>
            <div class="empty-state-text">Use o formulário ao lado para dar entrada em um veículo.</div>
        </div>`);
        return;
    }
    render(listEl, html`${cars.map((car) => {
        const auth = car.authorized_name || car.third_party_name;
        const sub = [car.box_mecanico || car.mechanic_name, car.notes].filter(Boolean).join(' • ');
        return html`<button type="button" class="patio-manager-row" data-car-id="${car.id}">
            <span class="plate-chip">${formatPlate(car.plate_display || car.plate)}</span>
            <span class="patio-manager-row-main">
                <span class="truncate fw-medium">${car.car_model || 'Veículo'}${car.car_color ? ` (${car.car_color})` : ''} — ${car.client_name || 'Cliente'}</span>
                ${sub ? html`<span class="truncate text-xs text-subtle">${sub}</span>` : ''}
                ${auth ? html`<span class="truncate text-xs text-danger">Autorizado: ${auth} (doc.: ${car.authorized_doc || car.third_party_doc || 's/ doc'})</span>` : ''}
            </span>
            ${statusTag(car.status_display || car.status, statusLabel(car.status_display || car.status))}
        </button>`;
    })}`);
    highlightRow(form.elements.id.value);
}

async function save() {
    const values = readFields(form);
    if (!values.plate) {
        toast('Informe a placa do veículo.', 'error');
        form.elements.plate.focus();
        return;
    }
    if (values.status === THIRD_PARTY_STATUS && (!values.authorized_name || !values.authorized_doc)) {
        toast('Informe nome e documento de quem vai retirar o carro.', 'error');
        (values.authorized_name ? form.elements.authorized_doc : form.elements.authorized_name).focus();
        return;
    }
    const payload = {
        id: values.id ? parseInt(values.id, 10) : null,
        plate: values.plate,
        client_name: values.client_name,
        car_model: values.car_model,
        car_color: values.car_color,
        status: values.status,
        box_mecanico: values.box_mecanico,
        notes: values.notes,
        authorized_name: values.authorized_name,
        authorized_doc: values.authorized_doc,
        authorized_phone: values.authorized_phone,
    };
    const restore = busy(modal.footer.querySelector('[data-action="save"]'), 'Salvando…');
    try {
        await api.post('/api/patio', payload, { errorMessage: 'Falha ao salvar no pátio' });
        toast(`Veículo ${formatPlate(payload.plate)} atualizado no pátio.`, 'success');
        fill(EMPTY);
        await refresh('patio');
    } catch (err) {
        toast(`Erro ao salvar: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

async function remove() {
    const id = form.elements.id.value;
    if (!id) return;
    const plateText = formatPlate(form.elements.plate.value);
    const ok = await confirmDialog({
        title: 'Remover do pátio?',
        message: `O veículo ${plateText} sai da lista do pátio e do Painel TV.`,
        confirmLabel: 'Remover',
        danger: true,
    });
    if (!ok) return;
    try {
        await api.del(`/api/patio/${encodeURIComponent(id)}`, { errorMessage: 'Falha ao remover' });
        toast(`Veículo ${plateText} removido do pátio.`, 'success');
        fill(EMPTY);
        await refresh('patio');
    } catch (err) {
        toast(`Erro ao remover: ${err.message}`, 'error');
    }
}

/**
 * Abre o gerenciador. Com `prefill`, preenche o formulário e, se o carro já
 * estiver no pátio (mesma placa), carrega o registro existente para edição.
 */
export async function openPatioManager({ prefill = null } = {}) {
    if (!modal) build();
    fill(EMPTY);
    modal.open({ focus: false });
    unwatch = state.watch('patio', renderList);
    const loading = refresh('patio');

    if (prefill) {
        fill({ ...EMPTY, ...prefill, id: '' });
        form.elements.status.focus();
        await loading;
        const plateClean = cleanPlate(prefill.plate);
        const existing = (state.get('patio')?.active || []).find((c) => cleanPlate(c.plate_clean || c.plate) === plateClean);
        if (existing) fill(existing);
    } else {
        form.elements.plate.focus();
    }
}
