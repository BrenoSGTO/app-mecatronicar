/**
 * Modais do pátio (POST /api/patio, DELETE /api/patio/:id).
 *
 *   import { openPatioManager, openPatioEntry } from './patio.js';
 *   openPatioEntry();                                        // "Entrada no pátio": só o formulário
 *   openPatioEntry({ prefill: { plate, client_name, car_model, car_color } });
 *   openPatioManager();                                      // "Gerenciar pátio": lista + formulário
 *   openPatioManager({ car, status });                       // abre já editando um carro (e, opcional, outro status)
 *
 * Os dois modais compartilham o mesmo formulário (validação da placa, dados do
 * veículo conhecido, bloco de retirada por terceiro). Dono na Fase 2: T7.
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
import { cleanPlate, formatPlate, plural } from '../lib/format.js';

const EMPTY = {
    id: '', plate: '', client_name: '', car_model: '', car_color: '',
    status: PATIO_STATUSES[0].value, box_mecanico: '', notes: '',
    authorized_name: '', authorized_doc: '', authorized_phone: '',
};

/** Placa antiga (ABC1234) ou Mercosul (ABC1D23), com ou sem hífen. */
export function isValidPlate(value) {
    return /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/.test(cleanPlate(value));
}

function carPlate(car) {
    return cleanPlate(car.plate_clean || car.plate || car.plate_display);
}

function findInYard(plateClean) {
    return (state.get('patio')?.active || []).find((c) => carPlate(c) === plateClean) || null;
}

function findKnown(plateClean) {
    return (state.get('cars') || []).find((c) => cleanPlate(c.plate_clean || c.plate_display) === plateClean) || null;
}

/* ------------------------------------------------------------------ */
/* Formulário (compartilhado)                                          */
/* ------------------------------------------------------------------ */

function formMarkup() {
    return html`<form class="patio-form stack" novalidate autocomplete="off">
        <input type="hidden" name="id">
        <div class="form-grid">
            <label class="field col-5">
                <span class="field-label">Placa <span class="req">*</span></span>
                <input class="input input-upper input-mono" name="plate" placeholder="ABC1D23" maxlength="8" autocomplete="off" spellcheck="false" aria-describedby="patio-plate-hint" required>
                <span class="field-hint" id="patio-plate-hint" data-hint="plate" role="status">Formato ABC1D23 (Mercosul) ou ABC-1234.</span>
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
                    ${PATIO_STATUSES.map((s) => html`<option value="${s.value}">${s.label}</option>`)}
                </select>
            </label>
            <label class="field col-5">
                <span class="field-label">Local ou elevador</span>
                <input class="input" name="box_mecanico" placeholder="Ex.: Elevador 1" autocomplete="off">
            </label>
            <label class="field col-12">
                <span class="field-label">Observações</span>
                <textarea class="textarea" name="notes" rows="2" placeholder="Queixa principal, o que foi combinado…"></textarea>
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
    </form>`;
}

/**
 * Cria um modal do pátio.
 * mode 'entry'  : só o formulário (dar entrada ou atualizar um carro que já está no pátio).
 * mode 'manage' : lista dos carros no pátio à esquerda + formulário à direita.
 */
function createController(mode) {
    const manage = mode === 'manage';
    let form = null;
    let listEl = null;
    let unwatch = null;
    let lookupKey = '';

    const modal = createModal({
        id: manage ? 'patio-manager' : 'patio-entry',
        title: manage ? 'Gerenciar pátio' : 'Entrada no pátio',
        subtitle: manage
            ? 'Entrada, status e saída dos veículos. O Painel TV atualiza ao vivo.'
            : 'Registre a chegada de um veículo à oficina.',
        icon: manage ? 'warehouse' : 'log-in',
        size: manage ? 'xl' : 'md',
        body: manage
            ? html`<div class="patio-manager">
                <section class="patio-manager-list" aria-label="Veículos no pátio">
                    <div class="row row-between">
                        <span class="eyebrow">No pátio agora <span class="num" data-field="count">0</span></span>
                        <a class="link-button text-sm" href="/tv" target="_blank" rel="noopener">${icon('tv', 14)} Abrir Painel TV</a>
                    </div>
                    <div class="patio-manager-rows" data-field="list"></div>
                </section>
                <section class="patio-manager-editor" aria-label="Dados do veículo">
                    <div class="patio-editor-head">
                        <span class="eyebrow" data-field="editor-title">Novo veículo</span>
                    </div>
                    ${formMarkup()}
                </section>
            </div>`
            : formMarkup(),
        footer: manage
            ? html`
                <button type="button" class="btn btn-danger-ghost push" data-action="remove" hidden>${icon('trash-2', 16)} Remover do pátio</button>
                <button type="button" class="btn btn-secondary" data-action="clear">${icon('plus', 16)} Novo veículo</button>
                <button type="button" class="btn btn-primary" data-action="save">${icon('save', 16)} Salvar no pátio</button>`
            : html`
                <button type="button" class="btn btn-secondary" data-modal-close>Cancelar</button>
                <button type="button" class="btn btn-primary" data-action="save">${icon('log-in', 16)} <span data-field="save-label">Dar entrada</span></button>`,
        onClose: () => {
            unwatch?.();
            unwatch = null;
        },
    });

    form = modal.body.querySelector('form');
    listEl = modal.body.querySelector('[data-field="list"]');
    const saveBtn = () => modal.footer.querySelector('[data-action="save"]');

    /* ---------- campos ---------- */

    function setHint(text, tone = '') {
        const hint = form.querySelector('[data-hint="plate"]');
        hint.textContent = text;
        hint.classList.toggle('is-error', tone === 'error');
        hint.classList.toggle('is-info', tone === 'info');
    }

    function setInvalid(name, invalid) {
        const field = form.elements[name];
        if (field) field.setAttribute('aria-invalid', invalid ? 'true' : 'false');
    }

    function clearErrors() {
        for (const el of form.querySelectorAll('[aria-invalid="true"]')) el.setAttribute('aria-invalid', 'false');
    }

    function syncThirdParty() {
        const isThird = form.elements.status.value === THIRD_PARTY_STATUS;
        form.querySelector('[data-field="third-party"]').hidden = !isThird;
        form.elements.authorized_name.required = isThird;
        form.elements.authorized_doc.required = isThird;
    }

    function syncChrome() {
        const editing = Boolean(form.elements.id.value);
        if (manage) {
            modal.footer.querySelector('[data-action="remove"]').hidden = !editing;
            modal.body.querySelector('[data-field="editor-title"]').textContent = editing
                ? `Editando ${formatPlate(form.elements.plate.value)}`
                : 'Novo veículo';
        } else {
            const label = editing ? 'Salvar alterações' : 'Dar entrada';
            modal.footer.querySelector('[data-field="save-label"]').textContent = label;
            modal.setTitle(editing ? 'Veículo já está no pátio' : 'Entrada no pátio');
        }
    }

    function highlightRow(id) {
        if (!listEl) return;
        for (const row of listEl.querySelectorAll('[data-car-id]')) {
            row.classList.toggle('is-selected', String(row.dataset.carId) === String(id || ''));
        }
    }

    function fill(car) {
        fillFields(form, {
            ...EMPTY,
            id: car.id || '',
            plate: car.plate_display || car.plate || '',
            client_name: car.client_name || '',
            car_model: car.car_model || '',
            car_color: car.car_color || '',
            status: (car.status || car.status_display) ? statusValue(car.status_display || car.status) : EMPTY.status,
            box_mecanico: car.box_mecanico || car.mechanic_name || '',
            notes: car.notes || '',
            authorized_name: car.authorized_name || car.third_party_name || '',
            authorized_doc: car.authorized_doc || car.third_party_doc || '',
            authorized_phone: car.authorized_phone || car.third_party_phone || '',
        });
        clearErrors();
        lookupKey = carPlate(car);
        setHint(car.id ? 'Veículo já registrado no pátio.' : 'Formato ABC1D23 (Mercosul) ou ABC-1234.', car.id ? 'info' : '');
        syncThirdParty();
        syncChrome();
        highlightRow(car.id);
    }

    /** Preenche só o que ainda está vazio (não sobrescreve o que a secretária digitou). */
    function fillMissing(values) {
        for (const [name, value] of Object.entries(values)) {
            const el = form.elements[name];
            if (el && !el.value && value) el.value = value;
        }
    }

    /** Ao completar a placa: acha o carro no pátio ou no histórico e sugere os dados. */
    function lookupPlate() {
        const clean = cleanPlate(form.elements.plate.value);
        if (clean === lookupKey) return;
        lookupKey = clean;
        if (!isValidPlate(clean)) {
            if (form.elements.id.value) {
                form.elements.id.value = '';
                syncChrome();
                highlightRow('');
            }
            return;
        }
        setInvalid('plate', false);
        const inYard = findInYard(clean);
        if (inYard) {
            fillMissing({
                client_name: inYard.client_name,
                car_model: inYard.car_model,
                car_color: inYard.car_color,
                box_mecanico: inYard.box_mecanico || inYard.mechanic_name,
                notes: inYard.notes,
            });
            form.elements.status.value = statusValue(inYard.status_display || inYard.status);
            form.elements.id.value = inYard.id;
            syncThirdParty();
            syncChrome();
            highlightRow(inYard.id);
            setHint(`Já está no pátio (${statusLabel(inYard.status_display || inYard.status)}). Salvar atualiza o registro.`, 'info');
            return;
        }
        if (form.elements.id.value) {
            form.elements.id.value = '';
            syncChrome();
            highlightRow('');
        }
        const known = findKnown(clean);
        if (known) {
            fillMissing({ client_name: known.client_name, car_model: known.car_model, car_color: known.car_color });
            setHint(`Veículo conhecido: ${plural(known.visit_count || 1, 'visita')} no histórico.`, 'info');
        } else {
            setHint('Veículo sem histórico. Preencha cliente e modelo.');
        }
    }

    /* ---------- lista (modo gerenciar) ---------- */

    function renderList(patio) {
        if (!listEl) return;
        const cars = patio?.active || [];
        modal.body.querySelector('[data-field="count"]').textContent = String(cars.length);
        if (!cars.length) {
            render(listEl, html`<div class="empty-state empty-state-compact">
                <span class="empty-state-icon">${icon('warehouse', 20)}</span>
                <div class="empty-state-title">Pátio vazio</div>
                <div class="empty-state-text">Preencha o formulário para dar entrada em um veículo.</div>
            </div>`);
            return;
        }
        render(listEl, html`${cars.map((car) => {
            const status = car.status_display || car.status;
            const auth = car.authorized_name || car.third_party_name;
            const where = car.box_mecanico || car.mechanic_name;
            const owner = car.client_name || '';
            const sub = [owner, where].filter(Boolean).join(' · ');
            return html`<button type="button" class="patio-manager-row" data-car-id="${car.id}">
                <span class="plate-chip">${formatPlate(car.plate_display || car.plate)}</span>
                <span class="patio-manager-row-main">
                    <span class="truncate fw-medium" title="${car.car_model || ''}">${car.car_model || 'Modelo não informado'}${car.car_color ? ` · ${car.car_color}` : ''}</span>
                    ${sub ? html`<span class="truncate text-xs text-subtle" title="${sub}">${sub}</span>` : ''}
                    ${auth ? html`<span class="truncate text-xs text-danger">Retira: ${auth} (doc. ${car.authorized_doc || car.third_party_doc || 's/ doc'})</span>` : ''}
                </span>
                ${statusTag(status, statusLabel(status))}
            </button>`;
        })}`);
        highlightRow(form.elements.id.value);
    }

    /* ---------- ações ---------- */

    function validate(values) {
        clearErrors();
        const plateClean = cleanPlate(values.plate);
        if (!plateClean) {
            setInvalid('plate', true);
            setHint('Informe a placa do veículo.', 'error');
            form.elements.plate.focus();
            return false;
        }
        if (!isValidPlate(plateClean)) {
            setInvalid('plate', true);
            setHint('Placa inválida. Use ABC1D23 (Mercosul) ou ABC-1234.', 'error');
            form.elements.plate.focus();
            return false;
        }
        if (values.status === THIRD_PARTY_STATUS) {
            const missing = !values.authorized_name ? 'authorized_name' : (!values.authorized_doc ? 'authorized_doc' : '');
            if (missing) {
                setInvalid('authorized_name', !values.authorized_name);
                setInvalid('authorized_doc', !values.authorized_doc);
                toast('Informe nome e documento de quem vai retirar o carro.', 'error');
                form.elements[missing].focus();
                return false;
            }
        }
        return true;
    }

    async function save() {
        const values = readFields(form);
        if (!validate(values)) return;
        const payload = {
            id: values.id ? parseInt(values.id, 10) : null,
            plate: cleanPlate(values.plate),
            client_name: values.client_name,
            car_model: values.car_model,
            car_color: values.car_color,
            status: values.status,
            box_mecanico: values.box_mecanico,
            notes: values.notes,
            authorized_name: values.status === THIRD_PARTY_STATUS ? values.authorized_name : '',
            authorized_doc: values.status === THIRD_PARTY_STATUS ? values.authorized_doc : '',
            authorized_phone: values.status === THIRD_PARTY_STATUS ? values.authorized_phone : '',
        };
        const wasEditing = Boolean(payload.id);
        const restore = busy(saveBtn(), 'Salvando…');
        try {
            await api.post('/api/patio', payload, { errorMessage: 'Falha ao salvar no pátio' });
            toast(wasEditing
                ? `Veículo ${formatPlate(payload.plate)} atualizado no pátio.`
                : `Veículo ${formatPlate(payload.plate)} entrou no pátio.`, 'success');
            await refresh('patio');
            if (manage) fill(EMPTY);
            else modal.close();
        } catch (err) {
            toast(`Não foi possível salvar: ${err.message}`, 'error');
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
            message: `O veículo ${plateText} sai da lista do pátio e do Painel TV. O histórico dele nas planilhas não muda.`,
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
            toast(`Não foi possível remover: ${err.message}`, 'error');
        }
    }

    /* ---------- eventos ---------- */

    form.elements.status.addEventListener('change', syncThirdParty);
    form.elements.plate.addEventListener('input', () => {
        const el = form.elements.plate;
        const upper = el.value.toUpperCase().replace(/[^A-Z0-9-]/g, '');
        if (upper !== el.value) el.value = upper;
        if (el.getAttribute('aria-invalid') === 'true') {
            setInvalid('plate', false);
            setHint('Formato ABC1D23 (Mercosul) ou ABC-1234.');
        }
        lookupPlate();
    });
    form.elements.plate.addEventListener('blur', () => {
        const clean = cleanPlate(form.elements.plate.value);
        if (clean && !isValidPlate(clean)) {
            setInvalid('plate', true);
            setHint('Placa inválida. Use ABC1D23 (Mercosul) ou ABC-1234.', 'error');
        }
    });
    form.addEventListener('input', (e) => {
        if (e.target.getAttribute?.('aria-invalid') === 'true' && e.target.name !== 'plate') e.target.setAttribute('aria-invalid', 'false');
    });
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
        const action = btn.dataset.action;
        if (action === 'save') save();
        else if (action === 'clear') {
            fill(EMPTY);
            form.elements.plate.focus();
        } else if (action === 'remove') remove();
    });

    if (listEl) {
        on(listEl, 'click', '[data-car-id]', (e, row) => {
            const car = (state.get('patio')?.active || []).find((c) => String(c.id) === row.dataset.carId);
            if (car) {
                fill(car);
                form.elements.status.focus();
            }
        });
    }

    /* ---------- API do controlador ---------- */

    return {
        modal,
        /** @param {{prefill?: object, car?: object, status?: string}} opts */
        async open({ prefill = null, car = null, status = '' } = {}) {
            fill(EMPTY);
            modal.open({ focus: false });
            if (manage) {
                unwatch?.();
                unwatch = state.watch('patio', renderList);
            }
            const loading = refresh('patio');

            if (car) {
                fill(car);
                if (status) {
                    form.elements.status.value = statusValue(status);
                    syncThirdParty();
                }
                const needsAuth = form.elements.status.value === THIRD_PARTY_STATUS && !form.elements.authorized_name.value;
                (needsAuth ? form.elements.authorized_name : form.elements.status).focus();
                return;
            }
            if (prefill) {
                fill({ ...EMPTY, ...prefill, id: '' });
                form.elements.plate.focus();
                await loading;
                lookupKey = '';
                lookupPlate();
                return;
            }
            form.elements.plate.focus();
        },
    };
}

const controllers = {};

function controller(mode) {
    if (!controllers[mode]) controllers[mode] = createController(mode);
    return controllers[mode];
}

/** "Entrada no pátio": formulário enxuto (também edita um carro que já está no pátio). */
export function openPatioEntry(options = {}) {
    return controller('entry').open(options);
}

/**
 * "Gerenciar pátio": lista + formulário. Com `prefill` (chamado pela ficha do
 * veículo), abre a entrada já preenchida; com `car`, edita aquele carro.
 */
export function openPatioManager(options = {}) {
    if (options.prefill) return openPatioEntry(options);
    return controller('manage').open(options);
}
