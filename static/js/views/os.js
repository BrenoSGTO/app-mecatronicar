/**
 * Nova visita / Editar OS (modal) → POST /api/save_order (grava a planilha .xlsx).
 *
 * - Autopreenchimento por placa (GET /api/car_lookup/:placa) e busca de cliente/veículo
 *   recorrente (GET /api/os/autocomplete). Só preenche campos que o usuário não digitou.
 * - Catálogo rápido de peças/serviços (GET /api/quick_suggestions): chips + lista ao digitar.
 * - Peças e mão de obra em grade editável (Tab/Enter/setas, Alt+setas reordena, totais ao vivo).
 *   A planilha comporta 14 peças e 4 serviços (excel_writer.py): a grade respeita esses limites.
 * - Validação antes de salvar, proteção contra duplo envio, contra sobrescrever uma visita
 *   existente e aviso ao fechar com alterações não salvas.
 * - Pode nascer de um agendamento da secretária (marca como concluído ao salvar).
 * Dono na Fase 2: T9.
 *
 *   openNewOs();                       openNewOs({ plate: 'BRA2E19' });
 *   openEditOs(visit);                 openOsFromAgendamento(agendamento);
 */
import { api, isAbort } from '../api.js';
import { emit, state } from '../state.js';
import { refresh } from '../data.js';
import { navigate } from '../router.js';
import { html, render, on, $, $$, debounce, busy, setVar, toElement } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal, confirmDialog } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { openInExcel, openOrcamentoPdf } from '../lib/documents.js';
import { PATIO_STATUSES, statusValue } from '../lib/patio.js';
import {
    cleanPlate, formatDateBr, formatMoney, formatPlate, formatTimeBr, matchesSearchTokens, normalizeText,
} from '../lib/format.js';
import { openChecklist } from './checklist.js';

const SERVICE_SECTION = 'Serviço';
const PAYMENT_OPTIONS = ['Pix', 'Dinheiro', 'Cartão de Débito', 'Cartão de Crédito 1x', 'Cartão de Crédito 2x', 'Cartão de Crédito 3x', 'Faturado', 'Boleto'];
const HIGHLIGHT_COLOR = '#FEF08A';

/** Limites da grade da planilha (linhas 30-43 = peças, 47-50 = serviços). */
const KINDS = {
    pecas: {
        limit: 14, firstRow: 30, title: 'Peças utilizadas', icon: 'package', tag: 'NF-e 55 autopeças',
        add: 'Adicionar peça', head: 'Descrição da peça', unit: 'Valor unit. (R$)', placeholder: 'Ex.: Óleo 5W30 sintético', noun: 'peças',
    },
    servicos: {
        limit: 4, firstRow: 47, title: 'Mão de obra', icon: 'wrench', tag: 'NFS-e Santos 14.01',
        add: 'Adicionar serviço', head: 'Descrição do serviço executado', unit: 'Valor M.O. (R$)', placeholder: 'Ex.: Troca de óleo e filtros', noun: 'serviços',
    },
};

const SECTIONS = [
    ['veiculo', 'Veículo'],
    ['cliente', 'Cliente'],
    ['os', 'Queixa'],
    ['pecas', 'Peças'],
    ['servicos', 'Mão de obra'],
    ['totais', 'Totais'],
    ['checklist', 'Checklist'],
];

let modal = null;
let form = null;
let mode = 'new';              // 'new' | 'edit' | 'agenda'
let existingFilePath = '';
let editVisit = null;
let agendamentoId = null;
let suggestionsCache = null;
let lookupController = null;
let searchController = null;
let lookupInfo = null;         // última resposta de /api/car_lookup (para avisos de hodômetro)
let lookupPlate = '';          // placa cujos dados estão aplicados nos campos
let initialPatioStatus = '';
let layoutBlocked = '';
let userEdited = false;
let saving = false;

/* ------------------------------------------------------------------ */
/* Números pt-BR                                                       */
/* ------------------------------------------------------------------ */

// Aceita "1.234,56", "1234,56", "1234.56", "R$ 1.234,56", "12,5", "12.5", "1.234" (= mil duzentos e trinta e quatro).
// Devolve null para vazio e NaN para texto inválido.
function parseDecimal(raw, decimals = 2) {
    let s = String(raw ?? '').replace(/R\$/gi, '').replace(/\s/g, '');
    if (s === '') return null;
    if (!/^[\d.,]+$/.test(s) || !/\d/.test(s)) return NaN;
    const lastComma = s.lastIndexOf(',');
    const lastDot = s.lastIndexOf('.');
    if (lastComma !== -1 && lastDot !== -1) {
        const decimalSep = lastComma > lastDot ? ',' : '.';
        const thousandSep = decimalSep === ',' ? '.' : ',';
        if (s.split(decimalSep).length > 2) return NaN;
        s = s.split(thousandSep).join('').replace(decimalSep, '.');
    } else if (lastComma !== -1) {
        if (s.split(',').length > 2) return NaN;
        s = s.replace(',', '.');
    } else if (lastDot !== -1) {
        const grouped = /^\d{1,3}(\.\d{3})+$/.test(s) && !/^0\./.test(s);
        if (grouped) s = s.split('.').join('');
        else if (s.split('.').length > 2) return NaN;
    }
    const n = Number(s);
    if (!Number.isFinite(n)) return NaN;
    const factor = 10 ** decimals;
    return Math.round(n * factor) / factor;
}

const NUMBER_FORMATS = {
    2: new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    3: new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 3 }),
};

function numberText(value, decimals = 2) {
    return Number.isFinite(value) ? NUMBER_FORMATS[decimals].format(value) : '';
}

function round6(value) {
    return Math.round(value * 1e6) / 1e6;
}

function isValidDate(text) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
    if (!m) return false;
    const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
    const date = new Date(y, mo - 1, d);
    return y >= 1990 && y <= 2100 && date.getFullYear() === y && date.getMonth() === mo - 1 && date.getDate() === d;
}

function isValidTime(text) {
    const m = /^(\d{2}):(\d{2})$/.exec(text);
    return Boolean(m) && Number(m[1]) < 24 && Number(m[2]) < 60;
}

function maskDate(value) {
    const d = value.replace(/\D/g, '').slice(0, 8);
    if (d.length > 4) return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`;
    if (d.length > 2) return `${d.slice(0, 2)}/${d.slice(2)}`;
    return d;
}

function maskTime(value) {
    const d = value.replace(/\D/g, '').slice(0, 4);
    return d.length > 2 ? `${d.slice(0, 2)}:${d.slice(2)}` : d;
}

function plateLooksValid(clean) {
    return /^[A-Z]{3}\d[A-Z0-9]\d{2}$/.test(clean);
}

/* ------------------------------------------------------------------ */
/* Marcação                                                            */
/* ------------------------------------------------------------------ */

function field(name, label, { col = 4, required = false, placeholder = '', cls = '', type = 'text', list = '', inputmode = '', maxlength = '' } = {}) {
    return html`<label class="field col-${col}">
        <span class="field-label"><span>${label}${required ? html` <span class="req">*</span>` : ''}</span></span>
        <input class="input ${cls}" type="${type}" name="${name}" placeholder="${placeholder}" autocomplete="off"${list ? html` list="${list}"` : ''}${inputmode ? html` inputmode="${inputmode}"` : ''}${maxlength ? html` maxlength="${maxlength}"` : ''}>
        <span class="field-hint" data-hint="${name}"></span>
    </label>`;
}

function itemsSection(kind) {
    const k = KINDS[kind];
    return html`<section class="form-section os-items" id="os-sec-${kind}" data-section="${kind}" data-kind="${kind}">
        <div class="form-section-header">
            <h3 class="form-section-title">
                ${icon(k.icon, 16)} ${k.title}
                <span class="tag">${k.tag}</span>
                <span class="tag os-counter" data-counter="${kind}">0/${k.limit}</span>
            </h3>
            <button type="button" class="btn btn-secondary btn-sm" data-action="add-row" data-kind="${kind}">${icon('plus', 15)} ${k.add}</button>
        </div>
        <div class="os-suggestions">
            <span class="text-xs text-subtle">Atalhos</span>
            <div class="chip-list" data-chips="${kind}"></div>
        </div>
        <div class="table-wrap">
            <table class="table os-items-table">
                <thead><tr>
                    <th class="os-col-idx num">#</th>
                    <th>${k.head}</th>
                    <th class="num os-col-qty">Qtd</th>
                    <th class="num os-col-money">${k.unit}</th>
                    <th class="num os-col-money">Total</th>
                    <th class="os-col-tools"><span class="sr-only">Ações da linha</span></th>
                </tr></thead>
                <tbody data-rows="${kind}"></tbody>
            </table>
        </div>
        <p class="field-hint os-grid-hint">Tab ou Enter avançam de célula; setas sobem e descem; Alt + seta reordena a linha; Enter na última linha cria outra.</p>
    </section>`;
}

function build() {
    modal = createModal({
        id: 'os',
        title: 'Nova visita',
        icon: 'wrench',
        size: 'xl',
        closeOnBackdrop: false,
        bodyClass: 'os-body',
        body: html`<form class="os-form" novalidate autocomplete="off">
            <nav class="os-nav" aria-label="Seções da ficha">
                ${SECTIONS.map(([id, label]) => html`<button type="button" class="os-nav-item" data-action="goto" data-target="${id}">${label}</button>`)}
            </nav>
            <fieldset class="os-fieldset">
                <div class="callout callout-danger os-alert" data-field="form-error" role="alert" hidden>
                    ${icon('circle-alert', 16)}
                    <div><div class="callout-title" data-field="form-error-title"></div><span data-field="form-error-text"></span></div>
                    <button type="button" class="btn btn-secondary btn-sm push" data-action="open-excel" data-field="form-error-excel" hidden>${icon('file-spreadsheet', 14)} Abrir no Excel</button>
                </div>

                <div class="os-lookup">
                    <div class="input-group">
                        ${icon('search', 16, 'input-icon')}
                        <input class="input" data-field="client-search" placeholder="Buscar cliente ou carro já cadastrado (placa, nome ou modelo) para preencher sozinho" autocomplete="off" aria-label="Buscar cliente ou carro já cadastrado">
                    </div>
                    <div class="dropdown-list" data-field="client-results" role="listbox" hidden></div>
                </div>

                <section class="form-section" id="os-sec-veiculo" data-section="veiculo">
                    <div class="form-section-header">
                        <h3 class="form-section-title">${icon('car-front', 16)} Veículo e entrada na oficina</h3>
                        <span class="tag" data-field="plate-badge" hidden></span>
                    </div>
                    <div class="form-grid">
                        <label class="field col-2">
                            <span class="field-label"><span>Placa <span class="req">*</span></span>${icon('loader-circle', 14, 'icon-spin os-plate-spinner')}</span>
                            <input class="input input-upper input-mono" name="plate" placeholder="BRA2E19" autocomplete="off" maxlength="8">
                            <span class="field-hint" data-hint="plate"></span>
                        </label>
                        ${field('car_model', 'Modelo', { col: 3, required: true, placeholder: 'Ex.: VW Fox 1.0 8V' })}
                        ${field('car_brand', 'Marca', { col: 2, placeholder: 'VW, GM…' })}
                        ${field('car_year', 'Ano', { col: 1, placeholder: '2018', cls: 'input-num', inputmode: 'numeric', maxlength: 4 })}
                        ${field('car_color', 'Cor', { col: 2, placeholder: 'Prata' })}
                        ${field('car_fuel', 'Combustível', { col: 2, placeholder: 'Flex' })}

                        ${field('car_chassis', 'Chassi (opcional)', { col: 4, placeholder: '9BWAA45ZXF4009621', cls: 'input-mono input-upper' })}
                        <label class="field col-2">
                            <span class="field-label"><span>Nº da visita <span class="req">*</span></span></span>
                            <input class="input input-num is-highlight" name="visit_num" placeholder="1" inputmode="numeric" maxlength="3" autocomplete="off">
                            <span class="field-hint is-info" data-hint="visit_num"></span>
                        </label>
                        <label class="field col-2">
                            <span class="field-label">Hodômetro (km)</span>
                            <input class="input input-num" name="odometer" placeholder="Ex.: 109622" inputmode="numeric" autocomplete="off">
                            <span class="field-hint" data-hint="odometer"></span>
                        </label>
                        ${field('entry_date', 'Data de entrada', { col: 2, placeholder: 'DD/MM/AAAA', cls: 'input-num', inputmode: 'numeric', maxlength: 10 })}
                        ${field('entry_time', 'Hora', { col: 2, placeholder: '08:00', cls: 'input-num', inputmode: 'numeric', maxlength: 5 })}
                    </div>
                </section>

                <section class="form-section" id="os-sec-cliente" data-section="cliente">
                    <div class="form-section-header">
                        <h3 class="form-section-title">${icon('user', 16)} Dados do cliente</h3>
                    </div>
                    <div class="form-grid">
                        ${field('client_name', 'Nome do cliente', { col: 5, required: true, placeholder: 'Ex.: Danilo Pereira da Silva' })}
                        ${field('client_phone', 'Celular / WhatsApp', { col: 3, placeholder: '(13) 99752-9463', inputmode: 'tel' })}
                        ${field('client_cpf', 'CPF / CNPJ', { col: 2, placeholder: '000.000.000-00', inputmode: 'numeric' })}
                        ${field('client_rg', 'RG', { col: 2, placeholder: '00.000.000-0' })}
                        ${field('client_address', 'Endereço', { col: 4, placeholder: 'Rua…' })}
                        ${field('client_num', 'Nº', { col: 1, placeholder: '197' })}
                        ${field('client_compl', 'Compl.', { col: 1, placeholder: 'Ap 3' })}
                        ${field('client_bairro', 'Bairro', { col: 2, placeholder: 'Encruzilhada' })}
                        ${field('client_city', 'Cidade', { col: 2, placeholder: 'Santos' })}
                        ${field('client_cep', 'CEP', { col: 2, placeholder: '11050-241', inputmode: 'numeric' })}
                        ${field('client_tel_res', 'Telefone residencial', { col: 3, placeholder: '(13) 3232-0000', inputmode: 'tel' })}
                        ${field('client_tel_com', 'Telefone comercial', { col: 3, placeholder: '(13) 3232-1111', inputmode: 'tel' })}
                        ${field('client_email', 'E-mail', { col: 6, placeholder: 'cliente@email.com', type: 'email' })}
                    </div>
                </section>

                <section class="form-section" id="os-sec-os" data-section="os">
                    <div class="form-section-header">
                        <h3 class="form-section-title">${icon('clipboard-list', 16)} Ordem de serviço</h3>
                    </div>
                    <div class="form-grid">
                        <label class="field col-12">
                            <span class="field-label">Reclamação do cliente / defeito relatado</span>
                            <textarea class="textarea os-complaint" name="complaint" rows="2" placeholder="Ex.: Vazamento de óleo e luz do ABS acesa"></textarea>
                        </label>
                        <label class="field col-4">
                            <span class="field-label">Status no pátio</span>
                            <select class="select" name="patio_status"></select>
                            <span class="field-hint" data-hint="patio_status"></span>
                        </label>
                        ${field('payment_method', 'Forma de pagamento', { col: 4, placeholder: 'Pix, cartão…', list: 'os-datalist-payment' })}
                    </div>
                </section>

                ${itemsSection('pecas')}
                ${itemsSection('servicos')}

                <section class="form-section" id="os-sec-totais" data-section="totais">
                    <div class="form-section-header">
                        <h3 class="form-section-title">${icon('coins', 16)} Totais</h3>
                    </div>
                    <div class="os-totals">
                        <div class="os-total"><span>Subtotal peças</span><strong class="num" data-total="pecas">R$ 0,00</strong></div>
                        <div class="os-total"><span>Subtotal mão de obra</span><strong class="num" data-total="servicos">R$ 0,00</strong></div>
                        <label class="os-total"><span>Desconto (R$)</span><input class="input input-sm input-num os-discount" name="discount" placeholder="0,00" inputmode="decimal" autocomplete="off"></label>
                        <div class="os-total os-total-final"><span>Total geral</span><strong class="num" data-total="geral">R$ 0,00</strong></div>
                    </div>
                </section>

                <section class="form-section" id="os-sec-checklist" data-section="checklist">
                    <div class="form-section-header">
                        <h3 class="form-section-title">${icon('list-checks', 16)} Checklist da oficina</h3>
                    </div>
                    <div class="os-checklist-row">
                        <p class="text-sm text-muted" data-field="checklist-text"></p>
                        <button type="button" class="btn btn-secondary" data-action="checklist">${icon('clipboard-list', 16)} Configurar checklist</button>
                    </div>
                </section>

                <datalist id="os-datalist-payment">${PAYMENT_OPTIONS.map((p) => html`<option value="${p}"></option>`)}</datalist>
            </fieldset>
        </form>`,
        footer: html`
            <div class="os-footer-total push">
                <span class="os-footer-label">Total geral</span>
                <strong class="num" data-total="footer">R$ 0,00</strong>
                <span class="text-xs text-subtle os-footer-hint">${icon('file-spreadsheet', 14)} Grava na planilha .xlsx da pasta configurada · Ctrl+Enter salva</span>
            </div>
            <button type="button" class="btn btn-secondary" data-modal-close>Cancelar</button>
            <button type="button" class="btn btn-primary" data-action="save">${icon('save', 16)} <span data-field="save-label">Salvar ficha no Excel</span></button>`,
        onClose: () => {
            closeSuggest();
            hideClientResults();
            lookupController?.abort();
            searchController?.abort();
            window.removeEventListener('beforeunload', beforeUnload);
        },
    });

    form = modal.body.querySelector('form');

    // Fechar (X, Esc, Cancelar) pede confirmação quando há alterações; durante o envio não fecha.
    const realClose = modal.close.bind(modal);
    modal.forceClose = realClose;
    modal.close = () => {
        if (saving) return modal;
        if (!userEdited) return realClose();
        confirmDialog({
            title: 'Descartar alterações?',
            message: 'Você alterou esta ficha e ainda não salvou. Se sair agora, as alterações serão perdidas.',
            confirmLabel: 'Descartar e sair',
            cancelLabel: 'Continuar editando',
            danger: true,
        }).then((discard) => { if (discard) realClose(); });
        return modal;
    };

    bindEvents();
}

function beforeUnload(event) {
    if (userEdited) {
        event.preventDefault();
        event.returnValue = '';
    }
}

/* ------------------------------------------------------------------ */
/* Linhas de peças / serviços                                          */
/* ------------------------------------------------------------------ */

function tbodyOf(kind) {
    return $(`[data-rows="${kind}"]`, form);
}

function rowMarkup(kind) {
    const k = KINDS[kind];
    return html`<tr class="os-row" data-kind="${kind}">
        <td class="os-col-idx num" data-col="idx"></td>
        <td class="os-cell-desc">
            <input class="input input-sm" data-col="desc" placeholder="${k.placeholder}" aria-label="Descrição" autocomplete="off" maxlength="120">
            <input class="input input-sm os-note-input" data-col="comment" placeholder="Observação (vira nota na célula do Excel)" aria-label="Observação do item" autocomplete="off" hidden>
        </td>
        <td><input class="input input-sm input-num" data-col="qty" inputmode="decimal" aria-label="Quantidade" autocomplete="off"></td>
        <td><input class="input input-sm input-num" data-col="unit" inputmode="decimal" placeholder="0,00" aria-label="Valor unitário" autocomplete="off"></td>
        <td class="num os-row-total" data-col="total">—</td>
        <td class="os-col-tools">
            <span class="os-tools">
                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="row-note" tabindex="-1" aria-label="Observação" data-tooltip="Observação">${icon('sticky-note', 15)}</button>
                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="row-highlight" tabindex="-1" aria-label="Destacar linha" data-tooltip="Destacar linha">${icon('sparkles', 15)}</button>
                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="row-up" tabindex="-1" aria-label="Subir linha" data-tooltip="Subir (Alt + ↑)">${icon('chevron-up', 15)}</button>
                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="row-down" tabindex="-1" aria-label="Descer linha" data-tooltip="Descer (Alt + ↓)">${icon('chevron-down', 15)}</button>
                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="row-remove" tabindex="-1" aria-label="Remover linha" data-tooltip="Remover linha">${icon('trash-2', 15)}</button>
            </span>
        </td>
    </tr>`;
}

function setRowHighlight(tr, color) {
    tr.dataset.color = color || '';
    tr.classList.toggle('is-highlighted', Boolean(color));
    tr.querySelector('[data-action="row-highlight"]')?.setAttribute('aria-pressed', color ? 'true' : 'false');
}

function setRowNote(tr, text, { open = false } = {}) {
    const input = tr.querySelector('[data-col="comment"]');
    input.value = text || '';
    input.hidden = !(open || input.value);
    tr.querySelector('[data-action="row-note"]')?.setAttribute('aria-pressed', input.value ? 'true' : 'false');
}

/** Adiciona uma linha. Devolve null quando a planilha não comporta mais linhas desse tipo. */
function addRow(kind, { desc = '', qty = '1', unit = '', comment = '', color = '' } = {}) {
    const tbody = tbodyOf(kind);
    if (tbody.rows.length >= KINDS[kind].limit) return null;
    const tr = toElement(rowMarkup(kind));
    tbody.append(tr);
    tr.querySelector('[data-col="desc"]').value = desc;
    tr.querySelector('[data-col="qty"]').value = qty;
    tr.querySelector('[data-col="unit"]').value = unit;
    setRowNote(tr, comment);
    setRowHighlight(tr, color);
    renumber(kind);
    return tr;
}

function renumber(kind) {
    const rows = [...tbodyOf(kind).rows];
    rows.forEach((tr, i) => {
        tr.querySelector('[data-col="idx"]').textContent = String(i + 1);
        tr.querySelector('[data-action="row-up"]').disabled = i === 0;
        tr.querySelector('[data-action="row-down"]').disabled = i === rows.length - 1;
    });
    const { limit } = KINDS[kind];
    const counter = $(`[data-counter="${kind}"]`, form);
    counter.textContent = `${rows.length}/${limit}`;
    counter.classList.toggle('tag-warning', rows.length >= limit);
    const addBtn = $(`[data-action="add-row"][data-kind="${kind}"]`, form);
    addBtn.disabled = rows.length >= limit;
    addBtn.title = rows.length >= limit ? `A planilha comporta no máximo ${limit} ${KINDS[kind].noun}.` : '';
}

function clearRows() {
    for (const kind of Object.keys(KINDS)) {
        render(tbodyOf(kind), '');
        renumber(kind);
    }
}

function moveRow(tr, delta) {
    const sibling = delta < 0 ? tr.previousElementSibling : tr.nextElementSibling;
    if (!sibling) return;
    if (delta < 0) tr.parentElement.insertBefore(tr, sibling);
    else tr.parentElement.insertBefore(sibling, tr);
    renumber(tr.dataset.kind);
    markEdited();
}

function removeRow(tr) {
    const kind = tr.dataset.kind;
    const tbody = tr.parentElement;
    const neighbor = tr.nextElementSibling || tr.previousElementSibling;
    tr.remove();
    if (!tbody.rows.length) addRow(kind);
    renumber(kind);
    recalc();
    markEdited();
    (neighbor || tbody.rows[0])?.querySelector('[data-col="desc"]')?.focus();
}

function firstEmptyRow(kind) {
    return [...tbodyOf(kind).rows].find((tr) => !tr.querySelector('[data-col="desc"]').value.trim()
        && !tr.querySelector('[data-col="unit"]').value.trim());
}

/** Atalho do catálogo: usa a primeira linha vazia ou cria outra. */
function addOrFill(kind, desc) {
    let tr = firstEmptyRow(kind);
    if (!tr) tr = addRow(kind);
    if (!tr) {
        toast(`A planilha comporta no máximo ${KINDS[kind].limit} ${KINDS[kind].noun}.`, 'error');
        return;
    }
    tr.querySelector('[data-col="desc"]').value = desc;
    if (!tr.querySelector('[data-col="qty"]').value.trim()) tr.querySelector('[data-col="qty"]').value = '1';
    tr.querySelector('[data-col="unit"]').focus();
    markEdited();
    recalc();
}

function rowValues(tr) {
    const desc = tr.querySelector('[data-col="desc"]').value.trim();
    const qtyRaw = tr.querySelector('[data-col="qty"]').value;
    const unitRaw = tr.querySelector('[data-col="unit"]').value;
    return {
        tr,
        desc,
        qtyRaw,
        unitRaw,
        qty: parseDecimal(qtyRaw, 3),
        unit: parseDecimal(unitRaw, 2),
        comment: tr.querySelector('[data-col="comment"]').value.trim(),
        color: tr.dataset.color || '',
    };
}

function rowTotal(v) {
    if (v.unit === null || Number.isNaN(v.unit)) return null;
    const qty = v.qty === null ? 1 : (Number.isNaN(v.qty) ? 0 : v.qty);
    return round6(qty * v.unit);
}

function recalc() {
    const sums = {};
    for (const kind of Object.keys(KINDS)) {
        sums[kind] = 0;
        for (const tr of tbodyOf(kind).rows) {
            const total = rowTotal(rowValues(tr));
            tr.querySelector('[data-col="total"]').textContent = total === null ? '—' : formatMoney(total);
            sums[kind] += total || 0;
        }
    }
    const discountRaw = parseDecimal(form.elements.discount.value);
    const discount = Number.isNaN(discountRaw) || discountRaw === null ? 0 : discountRaw;
    const subtotal = round6(sums.pecas + sums.servicos);
    const total = Math.max(0, round6(subtotal - discount));
    $('[data-total="pecas"]', form).textContent = formatMoney(sums.pecas);
    $('[data-total="servicos"]', form).textContent = formatMoney(sums.servicos);
    $('[data-total="geral"]', form).textContent = formatMoney(total);
    $('[data-total="footer"]', modal.footer).textContent = formatMoney(total);
    return { pecas: sums.pecas, servicos: sums.servicos, subtotal, discount, total };
}

/* ------------------------------------------------------------------ */
/* Catálogo rápido (chips + lista ao digitar)                          */
/* ------------------------------------------------------------------ */

let suggestEl = null;
let suggestInput = null;
let suggestItems = [];
let suggestIndex = -1;

async function loadSuggestions() {
    if (!suggestionsCache) {
        try {
            suggestionsCache = await api.get('/api/quick_suggestions');
        } catch (err) {
            console.warn('Sugestões rápidas indisponíveis:', err);
            return;
        }
    }
    const chips = (kind, list) => html`${list.map((text) => html`<button type="button" class="chip" data-action="chip" data-kind="${kind}" data-value="${text}" title="Adicionar “${text}”">${icon('plus', 12)} ${text}</button>`)}`;
    render($('[data-chips="pecas"]', form), chips('pecas', (suggestionsCache.pecas || []).slice(0, 6)));
    render($('[data-chips="servicos"]', form), chips('servicos', (suggestionsCache.servicos || []).slice(0, 5)));
}

function suggestionPool(kind) {
    return (suggestionsCache && suggestionsCache[kind]) || [];
}

function ensureSuggestEl() {
    if (suggestEl) return suggestEl;
    suggestEl = toElement(html`<div class="dropdown-list os-suggest" role="listbox" hidden></div>`);
    modal.el.append(suggestEl);
    suggestEl.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const option = e.target.closest('[data-value]');
        if (option && suggestInput) pickSuggestion(option.dataset.value);
    });
    return suggestEl;
}

function openSuggest(input, { force = false } = {}) {
    const query = input.value.trim();
    if (!query && !force) return closeSuggest();
    const kind = input.closest('tr').dataset.kind;
    const pool = suggestionPool(kind);
    const matches = (query ? pool.filter((text) => matchesSearchTokens(text, query)) : pool).slice(0, 8);
    // Já digitou exatamente uma das sugestões: não precisa mostrar de novo.
    if (!matches.length || (matches.length === 1 && normalizeText(matches[0]) === normalizeText(query))) return closeSuggest();
    suggestInput = input;
    suggestItems = matches;
    suggestIndex = -1;
    const el = ensureSuggestEl();
    render(el, html`${matches.map((text, i) => html`<button type="button" class="dropdown-option" role="option" data-index="${i}" data-value="${text}">${text}</button>`)}`);
    el.hidden = false;
    const rect = input.getBoundingClientRect();
    const width = Math.max(rect.width, 360);
    setVar(el, '--suggest-x', `${Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))}px`);
    setVar(el, '--suggest-w', `${width}px`);
    const below = window.innerHeight - rect.bottom;
    const height = el.offsetHeight;
    setVar(el, '--suggest-y', `${below < height + 12 && rect.top > height + 12 ? rect.top - height - 2 : rect.bottom + 2}px`);
}

function closeSuggest() {
    if (suggestEl) suggestEl.hidden = true;
    suggestInput = null;
    suggestItems = [];
    suggestIndex = -1;
}

function highlightSuggest(index) {
    suggestIndex = (index + suggestItems.length) % suggestItems.length;
    $$('.dropdown-option', suggestEl).forEach((el, i) => {
        el.classList.toggle('is-active', i === suggestIndex);
        if (i === suggestIndex) el.scrollIntoView({ block: 'nearest' });
    });
}

function pickSuggestion(text) {
    const input = suggestInput;
    closeSuggest();
    if (!input) return;
    input.value = text;
    const tr = input.closest('tr');
    if (!tr.querySelector('[data-col="qty"]').value.trim()) tr.querySelector('[data-col="qty"]').value = '1';
    markEdited();
    recalc();
    tr.querySelector('[data-col="unit"]').focus();
}

/** Teclas da lista de sugestões. Devolve true se a tecla foi tratada. */
function handleSuggestKey(e, input) {
    const open = suggestEl && !suggestEl.hidden && suggestInput === input;
    if (!open) {
        if (e.key === 'ArrowDown' && !e.altKey) {
            openSuggest(input, { force: true });
            if (suggestEl && !suggestEl.hidden) {
                e.preventDefault();
                highlightSuggest(0);
                return true;
            }
        }
        return false;
    }
    if (e.key === 'ArrowDown' && !e.altKey) { e.preventDefault(); highlightSuggest(suggestIndex + 1); return true; }
    if (e.key === 'ArrowUp' && !e.altKey) { e.preventDefault(); highlightSuggest(suggestIndex - 1); return true; }
    if (e.key === 'Enter' && suggestIndex >= 0) { e.preventDefault(); pickSuggestion(suggestItems[suggestIndex]); return true; }
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeSuggest(); return true; }
    if (e.key === 'Tab') closeSuggest();
    return false;
}

/* ------------------------------------------------------------------ */
/* Navegação por teclado                                               */
/* ------------------------------------------------------------------ */

function focusCell(tr, col) {
    const input = tr?.querySelector(`[data-col="${col}"]`);
    if (!input || input.hidden) return false;
    input.focus();
    return true;
}

function focusAfterGrid(kind) {
    if (kind === 'pecas') focusCell(tbodyOf('servicos').rows[0], 'desc');
    else form.elements.discount.focus();
}

function nextRowOrNew(tr) {
    const kind = tr.dataset.kind;
    const next = tr.nextElementSibling;
    if (next) { focusCell(next, 'desc'); return; }
    const filled = tr.querySelector('[data-col="desc"]').value.trim();
    const created = filled ? addRow(kind) : null;
    if (created) { focusCell(created, 'desc'); markEdited(); } else focusAfterGrid(kind);
}

function onGridKeydown(e) {
    const input = e.target.closest('input[data-col]');
    if (!input) return false;
    const tr = input.closest('tr');
    const col = input.dataset.col;
    if (col === 'desc' && handleSuggestKey(e, input)) return true;

    if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
        e.preventDefault();
        moveRow(tr, e.key === 'ArrowUp' ? -1 : 1);
        input.focus();
        return true;
    }
    if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && !e.ctrlKey && !e.shiftKey && !e.altKey) {
        const target = e.key === 'ArrowUp' ? tr.previousElementSibling : tr.nextElementSibling;
        if (target && focusCell(target, col)) e.preventDefault();
        return true;
    }
    if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) {
        e.preventDefault();
        if (col === 'desc') {
            if (!focusCell(tr, 'qty')) nextRowOrNew(tr);
        } else if (col === 'qty') {
            focusCell(tr, 'unit');
        } else {
            nextRowOrNew(tr);
        }
        return true;
    }
    if (e.key === 'Tab' && !e.shiftKey && col === 'unit' && !tr.nextElementSibling && tr.querySelector('[data-col="desc"]').value.trim()) {
        const created = addRow(tr.dataset.kind);
        if (created) {
            e.preventDefault();
            focusCell(created, 'desc');
            markEdited();
        }
        return true;
    }
    return false;
}

function focusableFields() {
    return $$('input:not([type="hidden"]):not([readonly]), select, textarea', form)
        .filter((el) => !el.disabled && !el.hidden && el.offsetParent !== null && !el.closest('[data-field="client-results"]'));
}

/* ------------------------------------------------------------------ */
/* Erros de campo                                                      */
/* ------------------------------------------------------------------ */

function hintFor(el) {
    const name = el.name || '';
    return name ? form.querySelector(`[data-hint="${name}"]`) : null;
}

function markInvalid(el, message) {
    el.classList.add('is-invalid');
    el.setAttribute('aria-invalid', 'true');
    el.title = message;
    const hint = hintFor(el);
    if (hint) {
        hint.dataset.prev = hint.textContent;
        hint.textContent = message;
        hint.classList.add('is-error');
    }
}

function clearInvalid(el) {
    if (!el.classList.contains('is-invalid')) return;
    el.classList.remove('is-invalid');
    el.removeAttribute('aria-invalid');
    el.removeAttribute('title');
    const hint = hintFor(el);
    if (hint) {
        hint.textContent = hint.dataset.prev || '';
        hint.classList.remove('is-error');
    }
}

function clearAllInvalid() {
    $$('.is-invalid', form).forEach(clearInvalid);
    showFormError('');
}

function showFormError(title, text = '', { excel = false } = {}) {
    const box = $('[data-field="form-error"]', form);
    box.hidden = !title;
    $('[data-field="form-error-title"]', form).textContent = title || '';
    $('[data-field="form-error-text"]', form).textContent = text;
    $('[data-field="form-error-excel"]', form).hidden = !excel;
    if (title) modal.body.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ------------------------------------------------------------------ */
/* Busca por placa / cliente                                           */
/* ------------------------------------------------------------------ */

const AUTOFILL_FIELDS = [
    'client_name', 'client_phone', 'client_tel_res', 'client_tel_com', 'client_cpf', 'client_rg', 'client_email',
    'client_address', 'client_num', 'client_compl', 'client_bairro', 'client_city', 'client_cep',
    'car_model', 'car_brand', 'car_year', 'car_color', 'car_fuel', 'car_chassis',
];

function setPlateBadge(text, kind) {
    const badge = $('[data-field="plate-badge"]', form);
    badge.hidden = !text;
    badge.className = `tag ${kind === 'found' ? 'tag-success' : kind === 'edit' ? 'tag-info' : 'tag-accent'}`;
    badge.textContent = text || '';
}

function setHint(name, text) {
    const el = form.querySelector(`[data-hint="${name}"]`);
    if (!el) return;
    el.textContent = text || '';
    el.dataset.prev = text || '';
}

/** Preenche um campo sem atropelar o que o usuário digitou. */
function autofill(name, value) {
    const el = form.elements[name];
    if (!el || !value) return;
    if (el.dataset.src === 'user' && el.value.trim()) return;
    el.value = String(value);
    el.dataset.src = 'auto';
}

function clearAutofilled() {
    for (const name of AUTOFILL_FIELDS) {
        const el = form.elements[name];
        if (el && el.dataset.src === 'auto') {
            el.value = '';
            delete el.dataset.src;
        }
    }
}

async function plateLookup(rawPlate) {
    const clean = cleanPlate(rawPlate);
    if (clean.length < 5 || mode === 'edit') return;
    lookupController?.abort();
    lookupController = new AbortController();
    form.classList.add('is-looking-up');
    try {
        const data = await api.get(`/api/car_lookup/${encodeURIComponent(clean)}`, { signal: lookupController.signal });
        if (cleanPlate(form.elements.plate.value) !== clean) return;
        const f = form.elements;
        if (lookupPlate && lookupPlate !== clean) clearAutofilled();
        lookupPlate = clean;
        lookupInfo = data;
        if (data && data.found) {
            // A última visita traz o cadastro completo (telefones fixos incluídos).
            const det = (data.latest_visit && data.latest_visit.details) || {};
            const c = data.client || {};
            const v = data.car || {};
            autofill('client_name', c.client_name || det.client_name);
            autofill('client_phone', c.phone || det.phone);
            autofill('client_tel_res', c.phone_res || det.tel_res);
            autofill('client_tel_com', c.phone_com || det.tel_com);
            autofill('client_cpf', c.cpf || det.cpf);
            autofill('client_rg', c.rg || det.rg);
            autofill('client_email', c.email || det.email);
            autofill('client_address', c.address || det.address);
            autofill('client_num', c.address_num || det.address_num);
            autofill('client_compl', c.address_compl || det.address_compl);
            autofill('client_bairro', c.neighborhood || det.neighborhood);
            autofill('client_city', c.city || det.city);
            autofill('client_cep', c.cep || det.cep);
            autofill('car_model', v.car_model);
            autofill('car_brand', v.car_brand);
            autofill('car_year', v.car_year);
            autofill('car_color', v.car_color);
            autofill('car_fuel', v.car_fuel);
            autofill('car_chassis', v.car_chassis);
            if (f.visit_num.dataset.src !== 'user') {
                f.visit_num.value = String(data.suggested_visit_num || '1');
                f.visit_num.dataset.src = 'auto';
            }
            setHint('visit_num', `Sugerido: visita ${data.suggested_visit_num} (última: ${data.max_visit_num})`);
            setHint('odometer', data.last_odometer ? `Último km: ${data.last_odometer}` : '');
            setPlateBadge(`Veículo recorrente · ${data.visits_count} ${data.visits_count === 1 ? 'visita' : 'visitas'}`, 'found');
        } else {
            clearAutofilled();
            if (f.visit_num.dataset.src !== 'user') {
                f.visit_num.value = '1';
                f.visit_num.dataset.src = 'auto';
            }
            setHint('visit_num', '1ª visita na oficina');
            setHint('odometer', '');
            setPlateBadge('Novo veículo na oficina', 'new');
        }
        clearInvalid(f.plate);
    } catch (err) {
        if (!isAbort(err)) console.warn('Erro na consulta da placa:', err);
    } finally {
        form.classList.remove('is-looking-up');
    }
}

function hideClientResults() {
    const list = modal && $('[data-field="client-results"]', modal.body);
    if (list) {
        list.hidden = true;
        list.dataset.index = '-1';
    }
}

async function searchClients(q) {
    const list = $('[data-field="client-results"]', form);
    if (q.length < 2) {
        hideClientResults();
        return;
    }
    searchController?.abort();
    searchController = new AbortController();
    try {
        const data = await api.get('/api/os/autocomplete', { params: { q }, signal: searchController.signal });
        const results = (data.suggestions || []).slice(0, 10);
        if (!results.length) {
            render(list, html`<div class="os-lookup-empty text-sm text-muted">Nenhum cliente ou carro encontrado para “${q}”.</div>`);
            list.hidden = false;
            return;
        }
        render(list, html`${results.map((r) => html`<button type="button" class="dropdown-option" role="option"
            data-action="pick-client" data-plate="${r.plate_clean || r.plate}" data-client="${r.client_name || ''}">
            <span><strong class="num">${formatPlate(r.plate || r.plate_clean)}</strong> · ${r.car_model || 'Veículo'}${r.car_color ? ` (${r.car_color})` : ''}</span>
            <span class="text-xs text-subtle">${r.client_name || 'Cliente'}${r.phone ? ` · ${r.phone}` : ''} · última visita ${r.last_visit_num || '1'}</span>
        </button>`)}`);
        list.hidden = false;
    } catch (err) {
        if (!isAbort(err)) hideClientResults();
    }
}

function pickClient(btn) {
    const plateInput = form.elements.plate;
    plateInput.value = cleanPlate(btn.dataset.plate);
    plateInput.dataset.src = 'user';
    $('[data-field="client-search"]', form).value = `${formatPlate(btn.dataset.plate)} — ${btn.dataset.client}`;
    hideClientResults();
    markEdited();
    plateLookup(btn.dataset.plate);
    form.elements.odometer.focus();
}

/* ------------------------------------------------------------------ */
/* Eventos                                                             */
/* ------------------------------------------------------------------ */

function markEdited() {
    userEdited = true;
}

/** Posição da seção dentro da área rolável do modal. */
function sectionTop(section) {
    return section.getBoundingClientRect().top - modal.body.getBoundingClientRect().top + modal.body.scrollTop;
}

function scrollToSection(id) {
    const section = $(`#os-sec-${id}`, form);
    if (!section) return;
    const nav = $('.os-nav', form);
    modal.body.scrollTo({ top: Math.max(0, sectionTop(section) - nav.offsetHeight - 8), behavior: 'smooth' });
}

function updateScrollSpy() {
    const nav = $('.os-nav', form);
    const probe = modal.body.scrollTop + nav.offsetHeight + 40;
    let current = SECTIONS[0][0];
    for (const [id] of SECTIONS) {
        const section = $(`#os-sec-${id}`, form);
        if (section && sectionTop(section) <= probe) current = id;
    }
    if (modal.body.scrollTop + modal.body.clientHeight >= modal.body.scrollHeight - 4) current = SECTIONS[SECTIONS.length - 1][0];
    $$('.os-nav-item', form).forEach((btn) => btn.classList.toggle('is-active', btn.dataset.target === current));
}

function bindEvents() {
    const plateInput = form.elements.plate;
    const lookupSoon = debounce((value) => plateLookup(value), 250);

    // Marca o que o usuário digitou (autopreenchimento não atropela) e limpa o erro do campo.
    form.addEventListener('input', (e) => {
        if (!e.isTrusted) return;
        const el = e.target;
        markEdited();
        if (el.name) el.dataset.src = 'user';
        if (el.matches('[data-field="client-search"]')) return;
        clearInvalid(el);
    });

    plateInput.addEventListener('input', () => {
        const cleaned = cleanPlate(plateInput.value);
        if (plateInput.value !== cleaned) plateInput.value = cleaned;
        if (cleaned.length >= 7) lookupSoon(cleaned);
        else if (mode !== 'edit') setPlateBadge('', '');
    });
    plateInput.addEventListener('blur', () => {
        const cleaned = cleanPlate(plateInput.value);
        if (cleaned.length >= 5) plateLookup(cleaned);
    });

    // Máscaras curtas para preencher rápido.
    form.elements.entry_date.addEventListener('input', (e) => { e.target.value = maskDate(e.target.value); });
    form.elements.entry_time.addEventListener('input', (e) => { e.target.value = maskTime(e.target.value); });
    form.elements.visit_num.addEventListener('input', (e) => { e.target.value = e.target.value.replace(/\D/g, ''); });
    form.elements.car_year.addEventListener('input', (e) => { e.target.value = e.target.value.replace(/\D/g, ''); });

    // Valores em R$ e quantidades: normaliza ao sair do campo ("1234.5" vira "1.234,50").
    form.addEventListener('focusout', (e) => {
        const el = e.target;
        if (el.matches('[data-col="unit"], [name="discount"]')) normalizeNumber(el, 2);
        else if (el.matches('[data-col="qty"]')) normalizeNumber(el, 3);
        else if (el.name === 'odometer' && el.value.trim()) {
            const digits = el.value.replace(/\D/g, '');
            if (digits) el.value = Number(digits).toLocaleString('pt-BR');
        }
        if (el.matches('[data-col="desc"]')) setTimeout(() => { if (document.activeElement !== el) closeSuggest(); }, 120);
    });
    form.addEventListener('focusin', (e) => {
        if (e.target.matches('[data-col="qty"], [data-col="unit"], [name="discount"]')) e.target.select();
    });

    // Busca de cliente/veículo recorrente
    const searchInput = $('[data-field="client-search"]', form);
    const searchSoon = debounce((q) => searchClients(q), 250);
    searchInput.addEventListener('input', () => searchSoon(searchInput.value.trim()));
    searchInput.addEventListener('keydown', (e) => {
        const list = $('[data-field="client-results"]', form);
        const options = $$('.dropdown-option', list);
        const open = !list.hidden && options.length;
        const index = Number(list.dataset.index ?? -1);
        const setIndex = (i) => {
            const n = (i + options.length) % options.length;
            list.dataset.index = String(n);
            options.forEach((el, k) => el.classList.toggle('is-active', k === n));
            options[n].scrollIntoView({ block: 'nearest' });
        };
        if (e.key === 'Escape' && !list.hidden) {
            e.preventDefault();
            e.stopPropagation();
            hideClientResults();
        } else if (e.key === 'ArrowDown' && open) {
            e.preventDefault();
            setIndex(index + 1);
        } else if (e.key === 'ArrowUp' && open) {
            e.preventDefault();
            setIndex(index - 1);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (open) pickClient(options[index >= 0 ? index : 0]);
        }
    });
    modal.el.addEventListener('pointerdown', (e) => {
        if (!e.target.closest('.os-lookup')) hideClientResults();
    });

    on(form, 'click', '[data-action]', (e, btn) => {
        const action = btn.dataset.action;
        if (action === 'goto') {
            scrollToSection(btn.dataset.target);
        } else if (action === 'add-row') {
            const row = addRow(btn.dataset.kind);
            if (row) {
                focusCell(row, 'desc');
                markEdited();
            } else {
                toast(`A planilha comporta no máximo ${KINDS[btn.dataset.kind].limit} ${KINDS[btn.dataset.kind].noun}.`, 'error');
            }
        } else if (action === 'row-remove') {
            removeRow(btn.closest('tr'));
        } else if (action === 'row-up' || action === 'row-down') {
            moveRow(btn.closest('tr'), action === 'row-up' ? -1 : 1);
        } else if (action === 'row-note') {
            const tr = btn.closest('tr');
            const input = tr.querySelector('[data-col="comment"]');
            if (input.hidden) {
                input.hidden = false;
                input.focus();
            } else if (!input.value.trim()) {
                input.hidden = true;
            } else {
                input.focus();
            }
        } else if (action === 'row-highlight') {
            const tr = btn.closest('tr');
            setRowHighlight(tr, tr.dataset.color ? '' : HIGHLIGHT_COLOR);
            markEdited();
        } else if (action === 'chip') {
            addOrFill(btn.dataset.kind, btn.dataset.value);
        } else if (action === 'pick-client') {
            pickClient(btn);
        } else if (action === 'checklist') {
            openChecklistFromForm();
        } else if (action === 'open-excel') {
            openInExcel(existingFilePath);
        }
    });

    modal.body.addEventListener('scroll', () => {
        closeSuggest();
        updateScrollSpy();
    }, { passive: true });

    on(form, 'input', '[data-col="qty"], [data-col="unit"], [name="discount"], [data-col="desc"]', (e, el) => {
        recalc();
        if (el.matches('[data-col="desc"]') && e.isTrusted) openSuggest(el);
    });

    form.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && (e.key === 'Enter' || e.key.toLowerCase() === 's')) {
            e.preventDefault();
            save();
            return;
        }
        if (onGridKeydown(e)) return;
        // Enter nunca salva por engano: avança para o próximo campo.
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && e.target.matches('input:not([data-field="client-search"]), select')) {
            e.preventDefault();
            const fields = focusableFields();
            const next = fields[fields.indexOf(e.target) + 1];
            next?.focus();
        }
    });
    form.addEventListener('submit', (e) => e.preventDefault());

    modal.footer.querySelector('[data-action="save"]').addEventListener('click', save);
}

function normalizeNumber(el, decimals) {
    const n = parseDecimal(el.value, decimals);
    if (n === null || Number.isNaN(n)) return;
    el.value = numberText(n, decimals);
}

/* ------------------------------------------------------------------ */
/* Abrir em cada modo                                                  */
/* ------------------------------------------------------------------ */

function setPatioOptions({ current = '', allowNone = true, noneLabel = '' } = {}) {
    const select = form.elements.patio_status;
    const options = [];
    if (allowNone) options.push({ value: '', label: noneLabel });
    for (const s of PATIO_STATUSES) options.push({ value: s.value, label: s.value });
    if (current && !options.some((o) => o.value === current)) options.push({ value: current, label: current });
    render(select, html`${options.map((o) => html`<option value="${o.value}">${o.label}</option>`)}`);
    select.value = current;
}

function reset({ title, saveLabel }) {
    if (!modal) build();
    form.reset();
    existingFilePath = '';
    editVisit = null;
    agendamentoId = null;
    lookupInfo = null;
    lookupPlate = '';
    layoutBlocked = '';
    userEdited = false;
    saving = false;
    lookupController?.abort();
    closeSuggest();
    clearRows();
    hideClientResults();
    setPlateBadge('', '');
    $$('[data-hint]', form).forEach((el) => { setHint(el.dataset.hint, ''); el.classList.remove('is-error'); });
    $$('[name]', form).forEach((el) => { delete el.dataset.src; el.readOnly = false; });
    clearAllInvalid();
    $('[data-field="client-search"]', form).value = '';
    modal.setTitle(title);
    modal.setSubtitle('');
    $('[data-field="save-label"]', modal.footer).textContent = saveLabel;
    modal.footer.querySelector('[data-action="save"]').disabled = false;
    $('.os-fieldset', form).disabled = false;
    const now = new Date();
    form.elements.entry_date.value = formatDateBr(now);
    form.elements.entry_time.value = formatTimeBr(now);
    form.elements.client_city.value = '';
    $('[data-field="checklist-text"]', form).textContent = 'O checklist é gerado a partir das peças e serviços desta ficha.';
    modal.body.scrollTop = 0;
    loadSuggestions();
}

function afterOpen() {
    recalc();
    userEdited = false;
    initialPatioStatus = form.elements.patio_status.value;
    modal.open({ focus: false });
    window.addEventListener('beforeunload', beforeUnload);
    setTimeout(updateScrollSpy, 30);
}

export function openNewOs({ plate } = {}) {
    mode = 'new';
    reset({ title: 'Nova visita', saveLabel: 'Salvar ficha no Excel' });
    setPatioOptions({ current: PATIO_STATUSES[0].value, noneLabel: 'Não adicionar ao pátio' });
    $('[data-field="checklist-text"]', form).textContent = 'Disponível depois de salvar: o aviso de sucesso traz o atalho do checklist.';
    $('[data-action="checklist"]', form).disabled = true;
    addRow('pecas');
    addRow('pecas');
    addRow('servicos');
    afterOpen();
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
    setPatioOptions({ current: PATIO_STATUSES[0].value, noneLabel: 'Não adicionar ao pátio' });
    $('[data-field="checklist-text"]', form).textContent = 'Disponível depois de salvar: o aviso de sucesso traz o atalho do checklist.';
    $('[data-action="checklist"]', form).disabled = true;
    agendamentoId = ag.id;
    modal.setSubtitle(`Agendamento #${ag.id} · ${formatPlate(ag.car_plate_display || ag.car_plate || '') || 'sem placa'} — a planilha só é criada quando você salvar`);
    const f = form.elements;
    if (ag.car_plate) f.plate.value = cleanPlate(ag.car_plate_display || ag.car_plate);
    if (ag.car_model) f.car_model.value = ag.car_model;
    if (ag.client_name) f.client_name.value = ag.client_name;
    if (ag.phone) f.client_phone.value = ag.phone;
    f.complaint.value = [ag.title, ag.description].filter(Boolean).join(' - ');
    addRow('pecas');
    addRow('servicos', { desc: ag.title || '' });
    afterOpen();
    if (ag.car_plate) {
        plateLookup(ag.car_plate);
        setTimeout(() => f.odometer.focus(), 60);
    } else {
        setTimeout(() => f.plate.focus(), 60);
    }
}

/** Planilha só com texto: "R$ 1.234,50" → "1.234,50"; "" → "". */
function moneyText(value) {
    const n = parseDecimal(value);
    return n === null || Number.isNaN(n) ? '' : numberText(n);
}

function qtyText(value) {
    const n = parseDecimal(value, 3);
    return n === null || Number.isNaN(n) ? '' : numberText(n, 3);
}

/** Detalhes da visita: usa os do cache ou lê a planilha sob demanda (nunca abre vazio). */
async function resolveDetails(visit) {
    if (visit.details && Object.keys(visit.details).length) return visit.details;
    const plate = cleanPlate(visit.plate_clean || visit.plate_display || visit.plate);
    if (!plate) return null;
    try {
        const data = await api.get(`/api/car_history/${encodeURIComponent(plate)}`);
        const found = (data.visits || []).find((v) => v.file_path === visit.file_path);
        return (found && found.details) || null;
    } catch (err) {
        console.warn('Falha ao carregar os detalhes da visita:', err);
        return null;
    }
}

function patioStatusOf(visit) {
    const all = (state.get('patio') && state.get('patio').all) || [];
    const plate = cleanPlate(visit.plate_clean || visit.plate_display || visit.plate);
    const car = all.find((c) => c.file_path && c.file_path === visit.file_path)
        || all.find((c) => cleanPlate(c.plate_clean || c.plate_display || c.plate) === plate);
    return car ? (car.status || car.status_display || '') : '';
}

export async function openEditOs(visit) {
    if (!visit) return;
    if (!visit.file_path) {
        toast('Esta visita não tem planilha para editar.', 'error');
        return;
    }
    const d = await resolveDetails(visit);
    if (!d) {
        toast('Não foi possível ler a planilha desta visita. Tente de novo em instantes ou abra no Excel.', 'error');
        return;
    }
    mode = 'edit';
    reset({ title: `Editar ordem de serviço · visita #${visit.visit_num || d.visit_num || '1'}`, saveLabel: 'Salvar alterações na planilha' });
    existingFilePath = visit.file_path;
    editVisit = visit;
    modal.setSubtitle(`${formatPlate(visit.plate_display || visit.plate)} · ${visit.file_name || ''}`);

    const values = {
        plate: cleanPlate(visit.plate_display || visit.plate),
        car_model: d.car_model || visit.car_model || '',
        car_brand: d.car_brand || '',
        car_year: d.car_year || visit.car_year || '',
        car_color: d.car_color || visit.car_color || '',
        car_fuel: d.car_fuel || '',
        car_chassis: d.car_chassis || '',
        visit_num: visit.visit_num || d.visit_num || '1',
        odometer: visit.odometer || d.odometer || '',
        entry_date: visit.entry_date || d.entry_date || '',
        entry_time: d.entry_time || '',
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
        client_city: d.city || '',
        client_cep: d.cep || '',
        discount: moneyText(d.discount),
    };
    for (const [name, value] of Object.entries(values)) {
        const el = form.elements[name];
        if (el) el.value = value === null || value === undefined ? '' : String(value);
    }
    form.elements.plate.readOnly = true;
    setHint('plate', 'Para corrigir a placa, ajuste a planilha no Excel.');
    setHint('visit_num', `Visita atual da planilha: #${values.visit_num}`);
    setHint('odometer', visit.odometer ? `Km atual: ${visit.odometer}` : '');
    setPlateBadge('Editando planilha existente', 'edit');

    const current = patioStatusOf(visit);
    setPatioOptions({ current: current ? statusValue(current) : '', noneLabel: current ? '' : 'Fora do pátio (não alterar)' });
    if (current) setHint('patio_status', 'Só é alterado se você escolher outro status.');
    else setHint('patio_status', 'Esta visita não está no pátio. Escolha um status para colocá-la lá.');

    const items = d.items || [];
    const pecas = d.pecas_items || items.filter((i) => i.section !== SERVICE_SECTION);
    const servicos = d.servicos_items || items.filter((i) => i.section === SERVICE_SECTION);
    const load = (kind, list) => {
        list.forEach((it) => addRow(kind, {
            desc: it.description || '',
            qty: qtyText(it.quantity),
            unit: moneyText(it.unit_price),
            comment: it.comment || '',
            color: it.color || '',
        }));
        if (!list.length) addRow(kind);
    };
    load('pecas', pecas);
    load('servicos', servicos);

    // A grade da planilha tem posições fixas. Se a planilha foge do modelo, gravar apagaria dados.
    const outside = (list, first, limit) => list.some((it) => Number.isInteger(it.row_index) && (it.row_index < first || it.row_index >= first + limit));
    if (pecas.length > KINDS.pecas.limit || servicos.length > KINDS.servicos.limit
        || outside(pecas, KINDS.pecas.firstRow, KINDS.pecas.limit) || outside(servicos, KINDS.servicos.firstRow, KINDS.servicos.limit)) {
        layoutBlocked = 'Esta planilha tem itens fora das linhas do modelo padrão (14 peças e 4 serviços). Para não apagar dados, edite-a direto no Excel.';
        showFormError('Planilha fora do modelo padrão', layoutBlocked, { excel: true });
        modal.footer.querySelector('[data-action="save"]').disabled = true;
    }

    $('[data-field="checklist-text"]', form).textContent = 'Abre o checklist com as peças e serviços que estão na ficha agora (inclusive alterações ainda não salvas).';
    $('[data-action="checklist"]', form).disabled = false;
    afterOpen();
}

/* ------------------------------------------------------------------ */
/* Checklist a partir da ficha                                         */
/* ------------------------------------------------------------------ */

function currentItems() {
    const out = {};
    for (const kind of Object.keys(KINDS)) {
        out[kind] = [...tbodyOf(kind).rows].map(rowValues).filter((v) => v.desc).map((v) => ({
            description: v.desc,
            quantity: v.qtyRaw.trim() || '1',
            comment: v.comment,
            section: kind === 'servicos' ? SERVICE_SECTION : 'Peças',
        }));
    }
    return out;
}

function openChecklistFromForm() {
    if (!editVisit) return;
    const items = currentItems();
    openChecklist({ ...editVisit, details: { ...(editVisit.details || {}), pecas_items: items.pecas, servicos_items: items.servicos } }, {
        plateDisplay: formatPlate(editVisit.plate_display || editVisit.plate),
        car: form.elements.car_model.value,
        client: form.elements.client_name.value,
    });
}

/* ------------------------------------------------------------------ */
/* Validação e payload                                                 */
/* ------------------------------------------------------------------ */

function validate() {
    const f = form.elements;
    const errors = [];
    const warnings = [];
    const fail = (el, message) => errors.push({ el, message });
    const value = (name) => (f[name].value || '').trim();

    const plate = cleanPlate(value('plate'));
    if (!plate) fail(f.plate, 'Informe a placa do veículo.');
    else if (!plateLooksValid(plate)) warnings.push(`A placa “${plate}” não segue o padrão (ABC1234 ou ABC1D23).`);
    if (!value('client_name')) fail(f.client_name, 'Informe o nome do cliente.');
    if (!value('car_model')) fail(f.car_model, 'Informe o modelo do veículo.');

    const visit = value('visit_num');
    if (!/^\d+$/.test(visit) || Number(visit) < 1) fail(f.visit_num, 'Informe o nº da visita (1, 2, 3…).');

    const year = value('car_year');
    if (year && (!/^\d{4}$/.test(year) || Number(year) < 1900 || Number(year) > new Date().getFullYear() + 1)) fail(f.car_year, 'Ano inválido.');

    const km = value('odometer');
    if (km) {
        const digits = km.replace(/\D/g, '');
        if (!digits || !/^[\d.\s]+$/.test(km)) fail(f.odometer, 'Use só números (ex.: 109622).');
        else if (Number(digits) > 3000000) fail(f.odometer, 'Hodômetro inválido.');
        else if (mode !== 'edit' && lookupInfo && lookupInfo.found && Number(String(lookupInfo.last_odometer).replace(/\D/g, '')) > Number(digits)) {
            warnings.push(`O hodômetro (${km}) é menor que o da última visita (${lookupInfo.last_odometer}).`);
        }
    }

    const date = value('entry_date');
    if (date && !isValidDate(date)) fail(f.entry_date, 'Data inválida. Use DD/MM/AAAA.');
    const time = value('entry_time');
    if (time && !isValidTime(time)) fail(f.entry_time, 'Hora inválida. Use HH:MM.');

    const email = value('client_email');
    if (email && !/^\S+@\S+\.\S+$/.test(email)) fail(f.client_email, 'E-mail inválido.');
    const doc = value('client_cpf').replace(/\D/g, '');
    if (doc && doc.length !== 11 && doc.length !== 14) warnings.push('O CPF/CNPJ não tem 11 ou 14 dígitos.');

    const discountRaw = parseDecimal(f.discount.value);
    if (Number.isNaN(discountRaw) || (discountRaw !== null && discountRaw < 0)) fail(f.discount, 'Desconto inválido.');

    const items = { pecas: [], servicos: [] };
    let missingPrice = 0;
    for (const kind of Object.keys(KINDS)) {
        const label = kind === 'pecas' ? 'Peça' : 'Serviço';
        [...tbodyOf(kind).rows].forEach((tr, i) => {
            const v = rowValues(tr);
            const where = `${label} ${i + 1}`;
            const touched = v.desc || v.unitRaw.trim() || v.comment;
            if (!touched) return;
            if (!v.desc) {
                fail(tr.querySelector('[data-col="desc"]'), `${where}: descreva o item ou apague os valores.`);
                return;
            }
            if (Number.isNaN(v.qty) || (v.qty !== null && v.qty <= 0)) fail(tr.querySelector('[data-col="qty"]'), `${where}: quantidade inválida.`);
            if (Number.isNaN(v.unit) || (v.unit !== null && v.unit < 0)) fail(tr.querySelector('[data-col="unit"]'), `${where}: valor inválido.`);
            if (v.unit !== null && !Number.isNaN(v.unit) && v.unit > 0 && v.qty === null) fail(tr.querySelector('[data-col="qty"]'), `${where}: informe a quantidade.`);
            if (!v.unit) missingPrice += 1;
            items[kind].push(v);
        });
        if (items[kind].length > KINDS[kind].limit) fail(tbodyOf(kind).rows[0].querySelector('[data-col="desc"]'), `A planilha comporta no máximo ${KINDS[kind].limit} ${KINDS[kind].noun}.`);
    }
    if (missingPrice) warnings.push(`${missingPrice} ${missingPrice === 1 ? 'item está' : 'itens estão'} sem valor.`);

    const totals = recalc();
    if (discountRaw && discountRaw > totals.subtotal) fail(f.discount, 'O desconto é maior que o subtotal.');

    return { errors, warnings, items, discount: discountRaw || 0 };
}

function buildPayload(items, discount) {
    const f = form.elements;
    const value = (name) => (f[name].value || '').trim();
    const toItem = (v) => {
        const qty = v.qty === null ? '' : v.qty;
        const unit = v.unit === null ? 0 : v.unit;
        return { description: v.desc, desc: v.desc, quantity: qty, qty, unit_price: unit, price: unit, comment: v.comment, color: v.color };
    };
    const edit = mode === 'edit';
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
            plate: cleanPlate(value('plate')),
            model: value('car_model'),
            brand: value('car_brand'),
            year: value('car_year'),
            color: value('car_color'),
            fuel: value('car_fuel'),
            chassis: value('car_chassis'),
        },
        os: {
            visit_num: String(Number(value('visit_num'))),
            odometer: value('odometer').replace(/\D/g, ''),
            // Na edição, data e hora em branco ficam em branco (não viram "agora").
            entry_date: value('entry_date') || (edit ? '' : formatDateBr(new Date())),
            entry_time: value('entry_time') || (edit ? '' : formatTimeBr(new Date())),
            payment_method: value('payment_method'),
            complaint: value('complaint'),
            discount,
        },
        pecas: items.pecas.map(toItem),
        servicos: items.servicos.map(toItem),
    };
    // Na edição o status do pátio só vai se o usuário escolheu outro.
    const status = f.patio_status.value;
    if (status && (!edit || status !== initialPatioStatus)) payload.patio_status = status;
    return payload;
}

/** Já existe a mesma visita para a placa? Gravar por cima destruiria a planilha daquela visita. */
async function findVisitConflict(plate, visitNum) {
    try {
        const data = await api.get(`/api/car_history/${encodeURIComponent(plate)}`);
        const same = (data.visits || []).filter((v) => cleanPlate(v.plate_clean || v.plate_display || v.plate) === plate
            && Number(String(v.visit_num || '').replace(/\D/g, '')) === Number(visitNum)
            && v.file_path !== existingFilePath);
        return same[0] || null;
    } catch (err) {
        console.warn('Não foi possível conferir as visitas existentes:', err);
        return null;
    }
}

/* ------------------------------------------------------------------ */
/* Salvar                                                              */
/* ------------------------------------------------------------------ */

function failValidation(errors) {
    errors.forEach((e) => markInvalid(e.el, e.message));
    const first = errors[0];
    const extra = errors.length > 1 ? ` (mais ${errors.length - 1} ${errors.length === 2 ? 'campo' : 'campos'} para corrigir)` : '';
    toast(`${first.message}${extra}`, 'error');
    first.el.focus();
    first.el.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

async function save() {
    if (saving || !form) return;
    if (layoutBlocked) {
        toast(layoutBlocked, 'error');
        return;
    }
    clearAllInvalid();
    closeSuggest();

    const { errors, warnings, items, discount } = validate();
    if (errors.length) {
        failValidation(errors);
        return;
    }

    const payload = buildPayload(items, discount);
    const plate = payload.car.plate;

    saving = true;
    const saveBtn = modal.footer.querySelector('[data-action="save"]');
    const restore = busy(saveBtn, 'Conferindo…');
    try {
        const conflict = await findVisitConflict(plate, payload.os.visit_num);
        if (conflict) {
            const el = form.elements.visit_num;
            markInvalid(el, `A visita ${payload.os.visit_num} deste veículo já existe (${conflict.client_name || conflict.file_name}).`);
            showFormError(`A visita ${payload.os.visit_num} deste veículo já existe`, mode === 'edit'
                ? 'Outra planilha deste carro já usa esse número. Escolha outro número de visita.'
                : 'Salvar por cima apagaria a planilha existente. Use o próximo número de visita ou abra aquela visita em Editar OS.');
            el.focus();
            return;
        }
        if (warnings.length) {
            saving = false;
            restore();
            const proceed = await confirmDialog({
                title: 'Salvar mesmo assim?',
                message: `${warnings.join('\n')}\n\nConfira os dados antes de gravar na planilha.`,
                confirmLabel: 'Salvar assim mesmo',
                cancelLabel: 'Voltar e conferir',
            });
            if (!proceed) return;
            saving = true;
            busy(saveBtn, 'Salvando no Excel…');
        } else {
            busy(saveBtn, 'Salvando no Excel…');
        }
        $('.os-fieldset', form).disabled = true;

        const data = await api.post('/api/save_order', payload, { timeout: 90000, errorMessage: 'Não foi possível salvar a planilha no Excel' });

        if (agendamentoId) {
            try {
                await api.post(`/api/agendamentos/${encodeURIComponent(agendamentoId)}/status`, { status: 'concluido' });
            } catch (err) {
                console.error('Erro ao atualizar o agendamento vinculado:', err);
                toast('A ficha foi salva, mas o agendamento não foi marcado como concluído.', 'info');
            }
        }
        userEdited = false;
        saving = false;
        modal.forceClose();
        announceSaved(data, payload);
        refresh('cars', 'patio', 'agendamentos', 'nfStats');
        emit('os:saved', { plate: cleanPlate(data.plate_clean || data.plate || plate), mode, silent: true });
    } catch (err) {
        saving = false;
        $('.os-fieldset', form).disabled = false;
        showFormError('Não foi possível salvar a ficha', err.message || 'Erro desconhecido.');
        toast(`Erro ao salvar a ficha: ${err.message}`, 'error');
    } finally {
        saving = false;
        $('.os-fieldset', form).disabled = false;
        restore();
    }
}

/** Aviso de sucesso com atalhos: abrir ficha, orçamento em PDF, checklist. */
function announceSaved(data, payload) {
    const plateClean = cleanPlate(data.plate_clean || data.plate || payload.car.plate);
    const filePath = data.file_path;
    const visit = {
        file_path: filePath,
        file_name: data.file_name,
        plate: plateClean,
        plate_clean: plateClean,
        plate_display: data.plate || formatPlate(plateClean),
        visit_num: data.visit_num || payload.os.visit_num,
        car_model: payload.car.model,
        client_name: payload.client.name,
        details: data.details || {
            pecas_items: payload.pecas.map((p) => ({ description: p.description, quantity: String(p.quantity || 1), comment: p.comment })),
            servicos_items: payload.servicos.map((p) => ({ description: p.description, quantity: String(p.quantity || 1), comment: p.comment })),
        },
    };
    const verb = mode === 'edit' ? 'Alterações salvas' : 'Ficha salva';
    toast(`${verb}: ${data.file_name || data.filename || 'planilha atualizada'}`, 'success', {
        actions: [
            { label: 'Abrir ficha', onClick: () => navigate(`/veiculo/${encodeURIComponent(plateClean)}`) },
            { label: 'Orçamento PDF', onClick: () => openOrcamentoPdf(filePath) },
            { label: 'Checklist', onClick: () => openChecklist(visit, { plateDisplay: visit.plate_display, car: visit.car_model, client: visit.client_name }) },
        ],
    });
}
