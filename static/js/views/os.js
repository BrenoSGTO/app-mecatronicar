/**
 * Nova visita / Editar OS (modal) → POST /api/save_order (grava a planilha .xlsx).
 * - Autopreenchimento por placa (GET /api/car_lookup/:placa) e busca de cliente (GET /api/search).
 * - Sugestões rápidas de peças/serviços (GET /api/quick_suggestions).
 * - Pode nascer de um agendamento da secretária (marca como concluído ao salvar).
 * Dono na Fase 2: T9.
 *
 *   openNewOs();                       openNewOs({ plate: 'BRA2E19' });
 *   openEditOs(visit);                 openOsFromAgendamento(agendamento);
 */
import { api, isAbort } from '../api.js';
import { emit } from '../state.js';
import { refresh } from '../data.js';
import { html, render, on, $, debounce, busy, fillFields } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { PATIO_STATUSES } from '../lib/patio.js';
import {
    cleanPlate, formatDateBr, formatMoney, formatPlate, formatTimeBr, moneyInputValue, parseMoney,
} from '../lib/format.js';

const SERVICE_SECTION = 'Serviço';
const PAYMENT_OPTIONS = ['Pix', 'Dinheiro', 'Cartão de Débito', 'Cartão de Crédito 1x', 'Cartão de Crédito 2x', 'Cartão de Crédito 3x', 'Faturado', 'Boleto'];

let modal = null;
let form = null;
let mode = 'new';              // 'new' | 'edit' | 'agenda'
let existingFilePath = '';
let agendamentoId = null;
let suggestionsCache = null;
let lookupController = null;
let searchController = null;

/* ------------------------------------------------------------------ */
/* Marcação                                                            */
/* ------------------------------------------------------------------ */

function field(name, label, { col = 4, required = false, placeholder = '', cls = '', type = 'text', list = '', hint = false } = {}) {
    return html`<label class="field col-${col}">
        <span class="field-label">
            <span>${label}${required ? html` <span class="req">*</span>` : ''}</span>
            ${hint ? html`<span class="field-hint is-info" data-hint="${name}"></span>` : ''}
        </span>
        <input class="input ${cls}" type="${type}" name="${name}" placeholder="${placeholder}" autocomplete="off"${list ? html` list="${list}"` : ''}${required ? html` required` : ''}>
    </label>`;
}

function itemsSection(kind) {
    const isPecas = kind === 'pecas';
    return html`<section class="form-section os-items" data-kind="${kind}">
        <div class="form-section-header">
            <h3 class="form-section-title">
                ${icon(isPecas ? 'package' : 'wrench', 16)} ${isPecas ? 'Peças utilizadas' : 'Serviços / mão de obra'}
                <span class="tag">${isPecas ? 'NF-e 55 autopeças' : 'NFS-e Santos 14.01'}</span>
            </h3>
            <button type="button" class="btn btn-secondary btn-sm" data-action="add-row" data-kind="${kind}">${icon('plus', 15)} ${isPecas ? 'Adicionar peça' : 'Adicionar serviço'}</button>
        </div>
        <div class="os-suggestions">
            <span class="text-xs text-subtle">Sugestões rápidas</span>
            <div class="chip-list" data-chips="${kind}"></div>
        </div>
        <div class="table-wrap">
            <table class="table os-items-table">
                <thead><tr>
                    <th>${isPecas ? 'Descrição da peça' : 'Descrição do serviço executado'}</th>
                    <th class="num os-col-qty">Qtd</th>
                    <th class="num os-col-money">${isPecas ? 'Valor unit. (R$)' : 'Valor M.O. (R$)'}</th>
                    <th class="num os-col-money">Total</th>
                    <th class="os-col-remove"><span class="sr-only">Remover</span></th>
                </tr></thead>
                <tbody data-rows="${kind}"></tbody>
            </table>
        </div>
    </section>`;
}

function build() {
    modal = createModal({
        id: 'os',
        title: 'Nova visita / ordem de serviço',
        icon: 'wrench',
        size: 'xl',
        closeOnBackdrop: false,
        body: html`<form class="os-form stack stack-4" novalidate autocomplete="off">
            <div class="os-lookup">
                <div class="input-group">
                    ${icon('search', 16, 'input-icon')}
                    <input class="input" data-field="client-search" placeholder="Buscar cliente ou carro já cadastrado (placa ou nome) para preencher automaticamente" autocomplete="off" aria-label="Buscar cliente ou carro já cadastrado">
                </div>
                <div class="dropdown-list" data-field="client-results" role="listbox" hidden></div>
            </div>

            <section class="form-section">
                <div class="form-section-header">
                    <h3 class="form-section-title">${icon('car-front', 16)} Veículo e entrada na oficina</h3>
                    <span class="tag" data-field="plate-badge" hidden></span>
                </div>
                <div class="form-grid">
                    <label class="field col-2">
                        <span class="field-label"><span>Placa <span class="req">*</span></span>${icon('loader-circle', 14, 'icon-spin os-plate-spinner')}</span>
                        <input class="input input-upper input-mono" name="plate" placeholder="BRA2E19" autocomplete="off" required>
                    </label>
                    ${field('car_model', 'Modelo', { col: 4, required: true, placeholder: 'Ex.: VW Fox 1.0 8V / Onix 1.0 Turbo' })}
                    ${field('car_brand', 'Marca', { col: 2, placeholder: 'VW, GM…' })}
                    ${field('car_year', 'Ano', { col: 1, placeholder: '2018', cls: 'num' })}
                    ${field('car_color', 'Cor', { col: 1, placeholder: 'Prata' })}
                    ${field('car_fuel', 'Combustível', { col: 2, placeholder: 'Flex' })}

                    <label class="field col-2">
                        <span class="field-label"><span>Nº da visita <span class="req">*</span></span></span>
                        <input class="input input-num is-highlight" name="visit_num" placeholder="1" required>
                        <span class="field-hint is-info" data-hint="visit_num"></span>
                    </label>
                    <label class="field col-2">
                        <span class="field-label">Hodômetro (km)</span>
                        <input class="input input-num" name="odometer" placeholder="Ex.: 109622">
                        <span class="field-hint" data-hint="odometer"></span>
                    </label>
                    ${field('entry_date', 'Data de entrada', { col: 2, placeholder: 'DD/MM/AAAA', cls: 'num' })}
                    ${field('entry_time', 'Hora', { col: 1, placeholder: '08:00', cls: 'num' })}
                    <label class="field col-3">
                        <span class="field-label">Status no pátio</span>
                        <select class="select" name="patio_status">
                            ${PATIO_STATUSES.map((s) => html`<option value="${s.value}">${s.value}</option>`)}
                        </select>
                    </label>
                    ${field('payment_method', 'Forma de pagamento', { col: 2, placeholder: 'Pix, cartão…', list: 'os-datalist-payment' })}

                    ${field('car_chassis', 'Chassi (opcional)', { col: 4, placeholder: 'Ex.: 9BWAA45ZX F4009621', cls: 'input-mono' })}
                    ${field('complaint', 'Reclamação do cliente / defeito relatado', { col: 8, placeholder: 'Ex.: Vazamento de óleo e luz do ABS acesa' })}
                </div>
            </section>

            <section class="form-section">
                <div class="form-section-header">
                    <h3 class="form-section-title">${icon('user', 16)} Dados do cliente</h3>
                </div>
                <div class="form-grid">
                    ${field('client_name', 'Nome do cliente', { col: 5, required: true, placeholder: 'Ex.: Danilo Pereira da Silva' })}
                    ${field('client_phone', 'Celular / WhatsApp', { col: 3, placeholder: '(13) 99752-9463' })}
                    ${field('client_cpf', 'CPF / CNPJ', { col: 2, placeholder: '000.000.000-00' })}
                    ${field('client_rg', 'RG', { col: 2, placeholder: '00.000.000-0' })}
                    ${field('client_address', 'Endereço', { col: 4, placeholder: 'Rua…' })}
                    ${field('client_num', 'Nº', { col: 1, placeholder: '197' })}
                    ${field('client_compl', 'Compl.', { col: 1, placeholder: 'Ap 3' })}
                    ${field('client_bairro', 'Bairro', { col: 2, placeholder: 'Encruzilhada' })}
                    ${field('client_city', 'Cidade', { col: 2, placeholder: 'Santos' })}
                    ${field('client_cep', 'CEP', { col: 2, placeholder: '11050-241' })}
                    ${field('client_tel_res', 'Telefone residencial', { col: 3, placeholder: '(13) 3232-0000' })}
                    ${field('client_tel_com', 'Telefone comercial', { col: 3, placeholder: '(13) 3232-1111' })}
                    ${field('client_email', 'E-mail', { col: 6, placeholder: 'cliente@email.com', type: 'email' })}
                </div>
            </section>

            ${itemsSection('pecas')}
            ${itemsSection('servicos')}

            <div class="os-totals">
                <div class="os-total"><span>Subtotal peças</span><strong class="num" data-total="pecas">R$ 0,00</strong></div>
                <div class="os-total"><span>Subtotal serviços</span><strong class="num" data-total="servicos">R$ 0,00</strong></div>
                <label class="os-total"><span>Desconto</span><input class="input input-sm input-num os-discount" name="discount" placeholder="R$ 0,00"></label>
                <div class="os-total os-total-final"><span>Total geral</span><strong class="num" data-total="geral">R$ 0,00</strong></div>
            </div>

            <datalist id="os-datalist-payment">${PAYMENT_OPTIONS.map((p) => html`<option value="${p}"></option>`)}</datalist>
            <datalist id="os-datalist-pecas"></datalist>
            <datalist id="os-datalist-servicos"></datalist>
        </form>`,
        footer: html`
            <span class="text-xs text-subtle push">${icon('file-spreadsheet', 14)} A ficha é gravada na planilha .xlsx da pasta configurada.</span>
            <button type="button" class="btn btn-secondary" data-modal-close>Cancelar</button>
            <button type="button" class="btn btn-primary" data-action="save">${icon('save', 16)} <span data-field="save-label">Salvar ficha no Excel</span></button>`,
        onClose: () => {
            hideClientResults();
            lookupController?.abort();
        },
    });

    form = modal.body.querySelector('form');
    bindEvents();
}

/* ------------------------------------------------------------------ */
/* Linhas de peças / serviços                                          */
/* ------------------------------------------------------------------ */

function rowMarkup(kind, desc = '', qty = 1, unit = '') {
    const q = parseFloat(qty) || 1;
    const total = q * parseMoney(unit);
    return html`<tr>
        <td><input class="input input-sm" data-col="desc" list="os-datalist-${kind}" value="${desc}" placeholder="${kind === 'pecas' ? 'Ex.: Óleo 5W30 sintético' : 'Ex.: Troca de óleo e filtros'}" aria-label="Descrição"></td>
        <td><input class="input input-sm input-num" data-col="qty" type="number" step="any" min="0" value="${q}" aria-label="Quantidade"></td>
        <td><input class="input input-sm input-num" data-col="unit" value="${moneyInputValue(unit)}" placeholder="0,00" aria-label="Valor unitário"></td>
        <td class="num os-row-total" data-col="total">${formatMoney(total)}</td>
        <td class="td-center"><button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="remove-row" aria-label="Remover linha">${icon('x', 15)}</button></td>
    </tr>`;
}

function addRow(kind, desc = '', qty = 1, unit = '') {
    const tbody = $(`[data-rows="${kind}"]`, form);
    tbody.insertAdjacentHTML('beforeend', rowMarkup(kind, desc, qty, unit).value);
    return tbody.lastElementChild;
}

function clearRows() {
    render($('[data-rows="pecas"]', form), '');
    render($('[data-rows="servicos"]', form), '');
}

function addOrFill(kind, desc) {
    const tbody = $(`[data-rows="${kind}"]`, form);
    let row = [...tbody.rows].find((tr) => !tr.querySelector('[data-col="desc"]').value.trim());
    if (row) row.querySelector('[data-col="desc"]').value = desc;
    else row = addRow(kind, desc, 1, '');
    row.querySelector('[data-col="unit"]').focus();
    recalc();
}

function readRows(kind) {
    return [...$(`[data-rows="${kind}"]`, form).rows].map((tr) => {
        const desc = tr.querySelector('[data-col="desc"]').value.trim();
        const qty = parseFloat(tr.querySelector('[data-col="qty"]').value) || 1;
        const unit = parseMoney(tr.querySelector('[data-col="unit"]').value);
        return { description: desc, desc, quantity: qty, qty, unit_price: unit, price: unit };
    }).filter((it) => it.description);
}

function recalc() {
    const sum = (kind) => [...$(`[data-rows="${kind}"]`, form).rows].reduce((acc, tr) => {
        const q = parseFloat(tr.querySelector('[data-col="qty"]').value) || 0;
        const u = parseMoney(tr.querySelector('[data-col="unit"]').value);
        tr.querySelector('[data-col="total"]').textContent = formatMoney(q * u);
        return acc + q * u;
    }, 0);
    const pecas = sum('pecas');
    const servicos = sum('servicos');
    const discount = parseMoney(form.elements.discount.value);
    $('[data-total="pecas"]', form).textContent = formatMoney(pecas);
    $('[data-total="servicos"]', form).textContent = formatMoney(servicos);
    $('[data-total="geral"]', form).textContent = formatMoney(Math.max(0, pecas + servicos - discount));
}

/* ------------------------------------------------------------------ */
/* Sugestões rápidas                                                   */
/* ------------------------------------------------------------------ */

async function loadSuggestions() {
    if (!suggestionsCache) {
        try {
            suggestionsCache = await api.get('/api/quick_suggestions');
        } catch (err) {
            console.warn('Sugestões rápidas indisponíveis:', err);
            return;
        }
    }
    const pecas = suggestionsCache.pecas || [];
    const servicos = suggestionsCache.servicos || [];
    render($('#os-datalist-pecas'), html`${pecas.map((p) => html`<option value="${p}"></option>`)}`);
    render($('#os-datalist-servicos'), html`${servicos.map((s) => html`<option value="${s}"></option>`)}`);
    const chips = (kind, list) => html`${list.map((text) => html`<button type="button" class="chip" data-action="chip" data-kind="${kind}" data-value="${text}" title="Adicionar “${text}”">${icon('plus', 12)} ${text}</button>`)}`;
    render($('[data-chips="pecas"]', form), chips('pecas', pecas.slice(0, 10)));
    render($('[data-chips="servicos"]', form), chips('servicos', servicos.slice(0, 8)));
}

/* ------------------------------------------------------------------ */
/* Busca por placa / cliente                                           */
/* ------------------------------------------------------------------ */

function setPlateBadge(text, kind) {
    const badge = $('[data-field="plate-badge"]', form);
    badge.hidden = !text;
    badge.className = `tag ${kind === 'found' ? 'tag-success' : kind === 'edit' ? 'tag-info' : 'tag-accent'}`;
    badge.textContent = text || '';
}

function setHint(name, text) {
    const el = form.querySelector(`[data-hint="${name}"]`);
    if (el) el.textContent = text || '';
}

async function plateLookup(rawPlate) {
    const clean = cleanPlate(rawPlate);
    if (clean.length < 5) return;
    lookupController?.abort();
    lookupController = new AbortController();
    form.classList.add('is-looking-up');
    try {
        const data = await api.get(`/api/car_lookup/${encodeURIComponent(clean)}`, { signal: lookupController.signal });
        const f = form.elements;
        if (data && data.found) {
            const c = data.client || {};
            const set = (name, value) => { if (value) f[name].value = value; };
            set('client_name', c.client_name);
            set('client_phone', c.phone);
            set('client_tel_res', c.phone_res);
            set('client_tel_com', c.phone_com);
            set('client_cpf', c.cpf);
            set('client_rg', c.rg);
            set('client_email', c.email);
            set('client_address', c.address);
            set('client_num', c.address_num);
            set('client_compl', c.address_compl);
            set('client_bairro', c.neighborhood);
            set('client_city', c.city);
            set('client_cep', c.cep);
            const v = data.car || {};
            set('car_model', v.car_model);
            set('car_brand', v.car_brand);
            set('car_year', v.car_year);
            set('car_color', v.car_color);
            set('car_fuel', v.car_fuel);
            set('car_chassis', v.car_chassis);
            if (!existingFilePath) f.visit_num.value = data.suggested_visit_num || '1';
            setHint('visit_num', `Sugerido: visita ${data.suggested_visit_num} (última: ${data.max_visit_num})`);
            setHint('odometer', data.last_odometer ? `Último km: ${data.last_odometer}` : '');
            if (!existingFilePath) setPlateBadge(`Veículo recorrente · ${data.visits_count} visitas`, 'found');
        } else {
            if (!existingFilePath && (!f.visit_num.value || f.visit_num.value === '1')) f.visit_num.value = '1';
            setHint('visit_num', '1ª visita na oficina');
            setHint('odometer', '');
            if (!existingFilePath) setPlateBadge('Novo veículo na oficina', 'new');
        }
    } catch (err) {
        if (!isAbort(err)) console.warn('Erro na consulta da placa:', err);
    } finally {
        form.classList.remove('is-looking-up');
    }
}

function hideClientResults() {
    const list = modal && $('[data-field="client-results"]', modal.body);
    if (list) list.hidden = true;
}

async function searchClients(q) {
    const list = $('[data-field="client-results"]', form);
    if (q.length < 2) {
        list.hidden = true;
        return;
    }
    searchController?.abort();
    searchController = new AbortController();
    try {
        const data = await api.get('/api/search', { params: { q }, signal: searchController.signal });
        const seen = new Set();
        const results = (data.results || []).filter((r) => {
            const key = r.plate_clean || r.plate;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        }).slice(0, 12);
        if (!results.length) {
            list.hidden = true;
            return;
        }
        render(list, html`${results.map((r) => html`<button type="button" class="dropdown-option" role="option"
            data-action="pick-client" data-plate="${r.plate_clean || r.plate}" data-plate-display="${r.plate_display || r.plate}" data-client="${r.client_name || ''}">
            <span><strong class="mono">${formatPlate(r.plate_display || r.plate)}</strong> · ${r.car_model || ''}${r.car_color ? ` (${r.car_color})` : ''}</span>
            <span class="text-xs text-subtle">${r.client_name || 'Cliente'} · visita ${r.visit_num || '1'}</span>
        </button>`)}`);
        list.hidden = false;
    } catch (err) {
        if (!isAbort(err)) list.hidden = true;
    }
}

/* ------------------------------------------------------------------ */
/* Eventos                                                             */
/* ------------------------------------------------------------------ */

function bindEvents() {
    const plateInput = form.elements.plate;
    const lookupSoon = debounce((value) => plateLookup(value), 250);

    plateInput.addEventListener('input', () => {
        const cleaned = cleanPlate(plateInput.value);
        if (plateInput.value !== cleaned) plateInput.value = cleaned;
        if (cleaned.length >= 7) lookupSoon(cleaned);
        else if (!existingFilePath) setPlateBadge('', '');
    });
    plateInput.addEventListener('blur', () => {
        const cleaned = cleanPlate(plateInput.value);
        if (cleaned.length >= 5) plateLookup(cleaned);
    });

    const searchInput = $('[data-field="client-search"]', form);
    const searchSoon = debounce((q) => searchClients(q), 250);
    searchInput.addEventListener('input', () => searchSoon(searchInput.value.trim()));
    searchInput.addEventListener('keydown', (e) => {
        const list = $('[data-field="client-results"]', form);
        if (e.key === 'Escape' && !list.hidden) {
            e.preventDefault();
            list.hidden = true;
        } else if (e.key === 'ArrowDown' && !list.hidden) {
            e.preventDefault();
            list.querySelector('.dropdown-option')?.focus();
        }
    });
    modal.el.addEventListener('pointerdown', (e) => {
        if (!e.target.closest('.os-lookup')) hideClientResults();
    });

    on(form, 'click', '[data-action]', (e, btn) => {
        const action = btn.dataset.action;
        if (action === 'add-row') {
            const row = addRow(btn.dataset.kind);
            row.querySelector('[data-col="desc"]').focus();
            recalc();
        } else if (action === 'remove-row') {
            btn.closest('tr').remove();
            recalc();
        } else if (action === 'chip') {
            addOrFill(btn.dataset.kind, btn.dataset.value);
        } else if (action === 'pick-client') {
            plateInput.value = cleanPlate(btn.dataset.plateDisplay || btn.dataset.plate);
            searchInput.value = `${formatPlate(btn.dataset.plateDisplay)} — ${btn.dataset.client}`;
            hideClientResults();
            plateLookup(btn.dataset.plate);
        }
    });

    on(form, 'input', '[data-col="qty"], [data-col="unit"], [name="discount"]', recalc);
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        save();
    });
    modal.footer.querySelector('[data-action="save"]').addEventListener('click', save);
}

/* ------------------------------------------------------------------ */
/* Abrir em cada modo                                                  */
/* ------------------------------------------------------------------ */

function reset({ title, saveLabel }) {
    if (!modal) build();
    form.reset();
    existingFilePath = '';
    agendamentoId = null;
    lookupController?.abort();
    clearRows();
    hideClientResults();
    setPlateBadge('', '');
    setHint('visit_num', '');
    setHint('odometer', '');
    modal.setTitle(title);
    modal.setSubtitle('');
    $('[data-field="save-label"]', modal.footer).textContent = saveLabel;
    const now = new Date();
    form.elements.entry_date.value = formatDateBr(now);
    form.elements.entry_time.value = formatTimeBr(now);
    form.elements.patio_status.value = PATIO_STATUSES[0].value;
    form.elements.client_city.value = '';
    loadSuggestions();
}

export function openNewOs({ plate } = {}) {
    mode = 'new';
    reset({ title: 'Nova visita / ordem de serviço', saveLabel: 'Salvar ficha no Excel' });
    addRow('pecas');
    addRow('pecas');
    addRow('servicos');
    recalc();
    modal.open({ focus: false });
    if (plate) {
        form.elements.plate.value = cleanPlate(plate);
        plateLookup(plate);
        setTimeout(() => form.elements.odometer.focus(), 60);
    } else {
        setTimeout(() => form.elements.plate.focus(), 60);
    }
}

export function openOsFromAgendamento(ag) {
    if (!ag) return;
    mode = 'agenda';
    reset({ title: 'Criar ficha de entrada', saveLabel: 'Confirmar e salvar ficha no Excel' });
    agendamentoId = ag.id;
    modal.setSubtitle(`Agendamento #${ag.id} · ${formatPlate(ag.car_plate_display || ag.car_plate || '') || 'sem placa'} — a planilha só é criada quando você salvar`);
    const f = form.elements;
    if (ag.car_plate) f.plate.value = cleanPlate(ag.car_plate_display || ag.car_plate);
    if (ag.car_model) f.car_model.value = ag.car_model;
    if (ag.client_name) f.client_name.value = ag.client_name;
    if (ag.phone) f.client_phone.value = ag.phone;
    f.complaint.value = [ag.title, ag.description].filter(Boolean).join(' - ');
    addRow('pecas');
    addRow('servicos', ag.title || '', 1, '');
    recalc();
    modal.open({ focus: false });
    if (ag.car_plate) {
        plateLookup(ag.car_plate);
        setTimeout(() => f.odometer.focus(), 60);
    } else {
        setTimeout(() => f.plate.focus(), 60);
    }
}

export function openEditOs(visit) {
    if (!visit) return;
    mode = 'edit';
    const d = visit.details || {};
    reset({ title: `Editar ordem de serviço · visita #${visit.visit_num || '1'}`, saveLabel: 'Salvar alterações na planilha' });
    existingFilePath = visit.file_path || '';
    modal.setSubtitle(`${formatPlate(visit.plate_display || visit.plate)} · ${visit.file_name || ''}`);

    fillFields(form, {
        plate: cleanPlate(visit.plate_display || visit.plate),
        car_model: d.car_model || visit.car_model || '',
        car_brand: d.car_brand || '',
        car_year: d.car_year || visit.car_year || '',
        car_color: d.car_color || visit.car_color || '',
        car_fuel: d.car_fuel || '',
        car_chassis: d.car_chassis || '',
        visit_num: visit.visit_num || d.visit_num || '1',
        odometer: visit.odometer || d.odometer || '',
        entry_date: visit.entry_date || d.entry_date || formatDateBr(new Date()),
        entry_time: d.entry_time || formatTimeBr(new Date()),
        patio_status: 'Em Execução',
        payment_method: d.payment_method || '',
        complaint: visit.complaint || d.complaint || '',
        client_name: d.client_name || visit.client_name || '',
        client_phone: d.phone || '',
        client_tel_res: d.tel_res || '',
        client_tel_com: d.tel_com || '',
        client_cpf: d.cpf || '',
        client_rg: d.rg || '',
        client_email: d.email || '',
        client_address: d.address || '',
        client_num: d.address_num || '',
        client_compl: d.address_compl || '',
        client_bairro: d.neighborhood || '',
        client_city: d.city || 'Santos',
        client_cep: d.cep || '',
        discount: moneyInputValue(d.discount),
    });
    setHint('visit_num', `Visita atual da planilha: #${visit.visit_num || '1'}`);
    setHint('odometer', visit.odometer ? `Km atual: ${visit.odometer}` : '');
    setPlateBadge('Editando planilha existente', 'edit');

    const items = d.items || [];
    const pecas = d.pecas_items || items.filter((i) => i.section !== SERVICE_SECTION);
    const servicos = d.servicos_items || items.filter((i) => i.section === SERVICE_SECTION);
    if (pecas.length) pecas.forEach((p) => addRow('pecas', p.description || '', p.quantity || 1, p.unit_price || ''));
    else addRow('pecas');
    if (servicos.length) servicos.forEach((s) => addRow('servicos', s.description || '', s.quantity || 1, s.unit_price || ''));
    else addRow('servicos');
    recalc();
    modal.open();
}

/* ------------------------------------------------------------------ */
/* Salvar                                                              */
/* ------------------------------------------------------------------ */

async function save() {
    const f = form.elements;
    const value = (name) => (f[name].value || '').trim();
    const plateValue = value('plate').toUpperCase();
    const required = [
        ['plate', 'Informe a placa do veículo.'],
        ['client_name', 'Informe o nome do cliente.'],
        ['car_model', 'Informe o modelo do veículo.'],
    ];
    for (const [name, message] of required) {
        if (!value(name)) {
            toast(message, 'error');
            f[name].focus();
            return;
        }
    }

    const payload = {
        existing_file_path: existingFilePath || null,
        client: {
            name: value('client_name'),
            phone: value('client_phone'),
            tel_res: value('client_tel_res'),
            tel_com: value('client_tel_com'),
            cpf: value('client_cpf'),
            rg: value('client_rg'),
            email: value('client_email'),
            address: value('client_address'),
            address_num: value('client_num'),
            address_compl: value('client_compl'),
            neighborhood: value('client_bairro'),
            city: value('client_city') || 'Santos',
            cep: value('client_cep'),
        },
        car: {
            plate: plateValue,
            model: value('car_model'),
            brand: value('car_brand'),
            year: value('car_year'),
            color: value('car_color'),
            fuel: value('car_fuel'),
            chassis: value('car_chassis'),
        },
        os: {
            visit_num: value('visit_num') || '1',
            odometer: value('odometer'),
            entry_date: value('entry_date') || formatDateBr(new Date()),
            entry_time: value('entry_time') || formatTimeBr(new Date()),
            payment_method: value('payment_method'),
            complaint: value('complaint'),
            discount: parseMoney(f.discount.value),
        },
        patio_status: f.patio_status.value || PATIO_STATUSES[0].value,
        pecas: readRows('pecas'),
        servicos: readRows('servicos'),
    };

    const restore = busy(modal.footer.querySelector('[data-action="save"]'), 'Salvando no Excel…');
    try {
        const data = await api.post('/api/save_order', payload, { timeout: 90000, errorMessage: 'Não foi possível salvar a planilha no Excel' });
        toast(`Ficha salva: ${data.file_name || data.filename || 'planilha atualizada'}`, 'success');

        if (agendamentoId) {
            try {
                await api.post(`/api/agendamentos/${encodeURIComponent(agendamentoId)}/status`, { status: 'concluido' });
            } catch (err) {
                console.error('Erro ao atualizar o agendamento vinculado:', err);
            }
        }
        modal.close();
        refresh('cars', 'patio', 'agendamentos', 'nfStats');
        emit('os:saved', { plate: cleanPlate(data.plate || plateValue), mode });
    } catch (err) {
        toast(`Erro ao salvar a ficha: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

