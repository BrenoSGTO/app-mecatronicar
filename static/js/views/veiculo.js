/**
 * Ficha do veículo (#/veiculo/:placa): cabeçalho com dados e métricas,
 * ações (nova visita, orçamento, checklist, fiscal, pátio, impressão),
 * filtro de peças/serviços e linha do tempo das visitas (planilha principal,
 * serviços executados, outras abas, notas de célula do Excel).
 * Dono na Fase 2: T8.
 */
import { api } from '../api.js';
import { on as onEvent } from '../state.js';
import { navigate, currentRoute } from '../router.js';
import { html, render, on, $, $$, toElement } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal } from '../ui/modal.js';
import { createMenu } from '../ui/menu.js';
import { toast } from '../ui/toast.js';
import { copyText } from '../ui/clipboard.js';
import { plate, brandLogo, silhouette } from '../ui/vehicle.js';
import { identifyCar } from '../lib/catalog.js';
import { cleanPlate, formatKm, formatPlate, matchesSearchTokens, normalizeText, plural } from '../lib/format.js';
import { openInExcel, openOrcamentoPdf, openHistoryPdf } from '../lib/documents.js';
import { openNewOs, openEditOs } from './os.js';
import { openChecklist } from './checklist.js';
import { openFiscalVisit } from './fiscal.js';
import { openPatioManager } from './patio.js';
import { openPrintSelection } from './impressao.js';
import { highlight } from './busca.js';

const SERVICE_SECTION = 'Serviço';
const OPEN_ALL_UP_TO = 5;      // até 5 visitas: todas abertas
const OPEN_RECENT = 3;         // acima disso: só as 3 mais recentes abertas

let root = null;
let history = null;            // resposta de /api/car_history + visitas ordenadas
let loadingPlate = null;
let showAllServices = false;
let noteModal = null;
let noteCurrent = null;
let printMenu = null;
const visitOpen = new Map();   // file_path -> aberta?
const cardControls = new Map();// índice da visita -> { card, setServicesVisible }

/* ------------------------------------------------------------------ */
/* Helpers de dados                                                    */
/* ------------------------------------------------------------------ */

function sortVisits(visits) {
    return [...visits].sort((a, b) => {
        const da = a.entry_date_sort || '0000-00-00';
        const db = b.entry_date_sort || '0000-00-00';
        if (da !== db) return db.localeCompare(da);
        return (b.odometer_int || 0) - (a.odometer_int || 0);
    });
}

function splitItems(d) {
    const items = d.items || [];
    return {
        pecas: d.pecas_items || items.filter((i) => i.section !== SERVICE_SECTION),
        servicos: d.servicos_items || items.filter((i) => i.section === SERVICE_SECTION),
    };
}

function hasValue(money) {
    return Boolean(money) && money !== 'R$ 0,00';
}

function vehiclePlate() {
    const latest = history?.sorted?.[0];
    return cleanPlate(latest?.plate_clean || latest?.plate || history?.plate || '');
}

function latestVisit() {
    return history?.sorted?.[0] || null;
}

function visitKey(visit) {
    return visit.file_path || `${visit.visit_num}-${visit.entry_date}`;
}

function defaultOpen(index, total) {
    return total <= OPEN_ALL_UP_TO || index < OPEN_RECENT;
}

/* ------------------------------------------------------------------ */
/* Cores originais do Excel com contraste legível                      */
/* ------------------------------------------------------------------ */

const COLOR_RE = /^(#[0-9a-f]{3,8}|rgba?\([\d\s.,%]+\))$/i;

function parseColor(value) {
    const v = String(value || '').trim();
    let m = /^#([0-9a-f]{3})$/i.exec(v);
    if (m) return [...m[1]].map((c) => parseInt(c + c, 16));
    m = /^#([0-9a-f]{6})/i.exec(v);
    if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
    m = /^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)/i.exec(v);
    if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
    return null;
}

function luminance([r, g, b]) {
    const lin = (c) => {
        const s = c / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a, b) {
    const la = luminance(a);
    const lb = luminance(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Texto da planilha se tiver contraste AA; senão preto ou branco, o que ler melhor. */
function readableText(bgValue, preferredValue) {
    const bg = parseColor(bgValue);
    if (!bg) return null;
    const preferred = parseColor(preferredValue);
    if (preferred && contrast(bg, preferred) >= 4.5) return preferredValue;
    const dark = [17, 24, 39];
    const light = [255, 255, 255];
    return contrast(bg, dark) >= contrast(bg, light) ? '#111827' : '#ffffff';
}

/** Aplica as cores de linha vindas do Excel (dado dinâmico, então via custom property). */
function applyRowColors(container) {
    for (const tr of container.querySelectorAll('tr[data-row-color]')) {
        const bg = tr.dataset.rowColor;
        if (!bg || !COLOR_RE.test(bg)) {
            tr.classList.remove('has-color');
            continue;
        }
        const fg = readableText(bg, COLOR_RE.test(tr.dataset.rowFg || '') ? tr.dataset.rowFg : '');
        tr.style.setProperty('--row-bg', bg);
        if (fg) tr.style.setProperty('--row-fg', fg);
    }
}

/* ------------------------------------------------------------------ */
/* Marcação base                                                       */
/* ------------------------------------------------------------------ */

function mount(el) {
    root = el;
    render(el, html`
        <div class="veiculo-back">
            <button type="button" class="btn btn-ghost btn-sm" data-action="back">${icon('arrow-left', 15)} Voltar</button>
        </div>
        <div data-field="content"></div>`);

    on(root, 'click', '[data-action]', handleAction);
    on(root, 'input', '[data-field="item-filter"]', (e, input) => {
        $('[data-action="clear-filter"]', root).hidden = !input.value;
        filterItems(input.value);
    });
    on(root, 'keydown', '[data-field="item-filter"]', (e, input) => {
        if (e.key === 'Escape' && input.value) {
            e.preventDefault();
            input.value = '';
            $('[data-action="clear-filter"]', root).hidden = true;
            filterItems('');
        }
    });

    // Recarrega a ficha quando algo muda para este veículo
    const reloadIfCurrent = ({ plate: p } = {}) => {
        if (currentRoute()?.name !== 'veiculo') return;
        if (!p || cleanPlate(p) === vehiclePlate()) load(vehiclePlate() || loadingPlate, { quiet: true });
    };
    onEvent('os:saved', reloadIfCurrent);
    onEvent('fiscal:changed', reloadIfCurrent);
    onEvent('vehicle:reload', reloadIfCurrent);
}

function renderSkeleton() {
    render($('[data-field="content"]', root), html`
        <div class="card veiculo-header" aria-busy="true">
            <div class="veiculo-top">
                <div class="skeleton veiculo-skeleton-plate"></div>
                <div class="skeleton-stack veiculo-skeleton-main">
                    <div class="skeleton skeleton-title"></div>
                    <div class="skeleton skeleton-text"></div>
                </div>
            </div>
            <div class="skeleton skeleton-block"></div>
        </div>
        <div class="visits-list">
            <div class="skeleton skeleton-block veiculo-skeleton-visit"></div>
            <div class="skeleton skeleton-block veiculo-skeleton-visit"></div>
            <div class="skeleton skeleton-block veiculo-skeleton-visit"></div>
        </div>`);
}

function renderNotFound(plateValue, message) {
    render($('[data-field="content"]', root), html`<div class="card"><div class="empty-state">
        <span class="empty-state-icon">${icon('car', 20)}</span>
        <div class="empty-state-title">Nenhuma visita encontrada para ${formatPlate(plateValue)}</div>
        <div class="empty-state-text">${message || 'Confira a placa ou atualize a lista de planilhas nas configurações.'}</div>
        <div class="empty-state-actions">
            <button type="button" class="btn btn-secondary btn-sm" data-action="new-visit-plate" data-plate="${plateValue}">${icon('plus', 15)} Nova visita para esta placa</button>
            <a class="btn btn-secondary btn-sm" href="#/busca">Buscar outro veículo</a>
        </div>
    </div></div>`);
}

/* ------------------------------------------------------------------ */
/* Cabeçalho                                                           */
/* ------------------------------------------------------------------ */

function headerMarkup(visits) {
    const latest = visits[0];
    const d = latest.details || {};
    const kms = visits.map((v) => v.odometer_int).filter((k) => k > 0);
    const maxKm = kms.length ? Math.max(...kms) : 0;
    const minKm = kms.length ? Math.min(...kms) : 0;
    const lastKm = maxKm ? formatKm(maxKm) : (latest.odometer ? formatKm(latest.odometer) : '—');
    const kmDiff = kms.length > 1 && maxKm > minKm ? `+${(maxKm - minKm).toLocaleString('pt-BR')} km` : (kms.length ? '1 registro' : '—');
    const info = identifyCar(latest.car_model);

    return html`
        <section class="card veiculo-header">
            <div class="veiculo-top">
                <div class="veiculo-plate">${plate(latest.plate_display || latest.plate, 'lg')}</div>
                <div class="veiculo-identity-main">
                    <div class="veiculo-owner-row">
                        <h1 class="veiculo-owner">${latest.client_name || 'Cliente'}</h1>
                        ${d.phone ? html`<span class="veiculo-phone">
                            <span class="tag tag-lg">${icon('phone', 14)} <span class="num">${d.phone}</span></span>
                            <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="copy-phone" data-text="${d.phone}" aria-label="Copiar telefone" data-tooltip="Copiar telefone">${icon('copy', 15)}</button>
                        </span>` : ''}
                    </div>
                    <div class="veiculo-tags">
                        <span class="tag tag-lg tag-accent">${icon('car-front', 14)} ${latest.car_model || 'Veículo'}</span>
                        ${latest.car_year ? html`<span class="tag tag-lg">Ano ${latest.car_year}</span>` : ''}
                        ${latest.car_color ? html`<span class="tag tag-lg">${latest.car_color}</span>` : ''}
                        ${d.car_fuel ? html`<span class="tag tag-lg">${d.car_fuel}</span>` : ''}
                        ${d.model_comment ? html`<span class="tag tag-lg" title="Nota da célula do modelo na planilha">${icon('sticky-note', 14)} ${d.model_comment}</span>` : ''}
                        ${d.car_chassis ? html`<button type="button" class="tag tag-lg mono" data-action="copy-chassis" data-text="${d.car_chassis}" title="Copiar chassi">Chassi ${d.car_chassis} ${icon('copy', 12)}</button>` : ''}
                    </div>
                </div>
                <div class="veiculo-vehicle" aria-label="Montadora e modelo">
                    ${silhouette(latest.car_model)}
                    <div class="veiculo-vehicle-caption">
                        ${brandLogo(latest.car_model, 'sm')}
                        <span class="veiculo-vehicle-name truncate">${info.brandName}${info.modelName && info.modelName !== info.brandName && info.modelName !== 'Veículo' ? ` · ${info.modelName}` : ''}</span>
                    </div>
                </div>
            </div>

            <div class="veiculo-metrics">
                <div class="veiculo-metric"><span class="stat-label">${icon('history', 14)} Visitas</span><span class="stat-value">${visits.length}</span></div>
                <div class="veiculo-metric"><span class="stat-label">${icon('calendar', 14)} Última visita</span><span class="stat-value num">${latest.entry_date || '—'}</span></div>
                <div class="veiculo-metric"><span class="stat-label">${icon('gauge', 14)} Último hodômetro</span><span class="stat-value">${lastKm}</span></div>
                <div class="veiculo-metric"><span class="stat-label">${icon('chart-column', 14)} Evolução de km</span><span class="stat-value">${kmDiff}</span></div>
            </div>

            <div class="veiculo-actions">
                <button type="button" class="btn btn-secondary" data-action="new-visit">${icon('plus', 16)} Nova visita</button>
                <button type="button" class="btn btn-secondary" data-action="orcamento-latest" title="Orçamento / OS da visita mais recente em PDF">${icon('file-text', 16)} Orçamento (PDF)</button>
                <button type="button" class="btn btn-secondary" data-action="checklist-latest" title="Checklist da visita mais recente (sem valores)">${icon('clipboard-list', 16)} Checklist</button>
                <button type="button" class="btn btn-secondary" data-action="fiscal-vehicle" title="Copiloto Fiscal deste veículo">${icon('receipt-text', 16)} Copiloto Fiscal</button>
                <button type="button" class="btn btn-secondary" data-action="patio" title="Adicionar ao pátio ou alterar status na TV">${icon('warehouse', 16)} Status no pátio</button>
                <button type="button" class="btn btn-secondary push" data-field="print-trigger">${icon('printer', 16)} Imprimir ${icon('chevron-down', 14)}</button>
            </div>
        </section>`;
}

/* ------------------------------------------------------------------ */
/* Linha do tempo                                                      */
/* ------------------------------------------------------------------ */

function nfBadge(visit, pecas, servicos) {
    const nf = visit.nf_control || {};
    const servDone = nf.status_servico === 'emitida' || nf.nfse_status === 'emitida';
    const pecasDone = nf.status_pecas === 'emitida' || nf.nfe_status === 'emitida';
    const hasServ = nf.valor_servico > 0 || servicos.length > 0;
    const hasPecas = nf.valor_pecas > 0 || pecas.length > 0;
    if (servDone && pecasDone) {
        const s = nf.nf_servico_num || nf.nfse_number;
        const p = nf.nf_pecas_num || nf.nfe_number;
        return html`<button type="button" class="tag tag-success" data-action="fiscal" title="Notas fiscais emitidas">${icon('circle-check', 12)} ${s ? `NFS-e ${s}` : 'NFS-e'} · ${p ? `NF-e ${p}` : 'NF-e'}</button>`;
    }
    if (servDone || pecasDone) {
        return html`<button type="button" class="tag tag-info" data-action="fiscal" title="Uma nota emitida e outra pendente">${icon('receipt-text', 12)} NF parcial</button>`;
    }
    if (hasServ || hasPecas) {
        return html`<button type="button" class="tag tag-warning" data-action="fiscal" title="Notas fiscais pendentes. Clique para abrir no Copiloto.">${icon('receipt-text', 12)} NF pendente</button>`;
    }
    return html`<button type="button" class="tag" data-action="fiscal" title="Nenhuma nota fiscal emitida">${icon('receipt-text', 12)} NF</button>`;
}

function itemsTable(items, { main = false, mode = 'pecas' } = {}) {
    const descHeader = mode === 'servicos' ? 'Serviço executado / mão de obra' : 'Peça / anotação da planilha';
    const showType = new Set(items.map((i) => i.section || 'Item')).size > 1;
    return html`<div class="table-wrap table-flush items-table-wrap">
        <table class="table items-table${main ? ' main-sheet-table' : ''}">
            <thead><tr>
                ${showType ? html`<th class="items-col-type">Tipo</th>` : ''}
                <th>${descHeader}</th>
                <th class="num items-col-qty">Qtd</th>
                <th class="num col-price items-col-money">Valor unit.</th>
                <th class="num col-price items-col-money">Valor total</th>
            </tr></thead>
            <tbody>
                ${items.map((it) => {
                    const hasNote = Boolean(it.comment);
                    const isService = it.section === SERVICE_SECTION;
                    return html`<tr class="${it.color ? 'has-color' : ''}"
                        data-row-color="${it.color || ''}" data-row-fg="${it.text_color || ''}"
                        data-item-desc="${it.description || ''}" data-item-comment="${it.comment || ''}"
                        data-item-section="${it.section || 'Item'}" data-item-qty="${it.quantity || ''}" data-item-price="${it.total_price || ''}">
                        ${showType ? html`<td class="items-type${isService ? ' is-service' : ''}">${it.section || 'Item'}</td>` : ''}
                        <td class="items-desc${hasNote ? ' has-excel-note' : ''}"${hasNote ? html` data-action="note"` : ''}>
                            <span class="items-desc-text">${it.description || ''}</span>
                            ${hasNote ? html`<span class="note-chip">
                                <button type="button" class="btn btn-ghost btn-sm" data-action="note" title="Ler a nota desta célula">${icon('sticky-note', 14)} Ver nota</button>
                                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="note-whatsapp" aria-label="Copiar nota para o WhatsApp" data-tooltip="Copiar para o WhatsApp">${icon('message-square-text', 15)}</button>
                            </span>` : ''}
                        </td>
                        <td class="num">${it.quantity || '—'}</td>
                        <td class="num col-price">${it.unit_price || '—'}</td>
                        <td class="num col-price fw-semibold">${it.total_price || '—'}</td>
                    </tr>`;
                })}
            </tbody>
        </table>
    </div>`;
}

function servicesPanel(servicos, totalServicos, main) {
    return html`<div class="services-panel" data-field="services" hidden>
        <div class="sheet-bar sheet-bar-services">
            <span class="sheet-bar-title">${icon('wrench', 14)} Serviços executados / mão de obra <span class="badge">${servicos.length}</span></span>
            ${hasValue(totalServicos) ? html`<span class="sheet-bar-total col-price">Subtotal de mão de obra <strong class="num">${totalServicos}</strong></span>` : ''}
        </div>
        ${servicos.length
            ? itemsTable(servicos, { main, mode: 'servicos' })
            : html`<p class="items-empty">Nenhum serviço preenchido separadamente no campo “Serviço” desta planilha.</p>`}
    </div>`;
}

function visitCardMarkup(visit, index) {
    const d = visit.details || {};
    const { pecas, servicos } = splitItems(d);
    const extras = d.extra_sheets_data || [];
    const open = visitOpen.has(visitKey(visit)) ? visitOpen.get(visitKey(visit)) : defaultOpen(index, history.sorted.length);
    const totals = [
        hasValue(d.total_pecas) && ['Peças', d.total_pecas],
        hasValue(d.total_servicos) && ['Serviços', d.total_servicos],
        hasValue(d.subtotal) && ['Subtotal', d.subtotal],
        d.discount && ['Desconto', d.discount],
    ].filter(Boolean);

    return html`<article class="visit-card" data-visit-index="${index}" data-open="${open ? 'true' : 'false'}">
        <header class="visit-head">
            <button type="button" class="visit-toggle" data-action="toggle-visit" aria-expanded="${open ? 'true' : 'false'}" title="Abrir ou recolher esta visita">
                ${icon('chevron-down', 16, 'visit-chevron')}
                <span class="visit-date num">${visit.entry_date || 'Data não informada'}</span>
                <span class="tag">${icon('gauge', 12)} <span class="num">${visit.odometer ? formatKm(visit.odometer) : 'KM não informado'}</span></span>
                ${visit.visit_num ? html`<span class="tag tag-accent">Visita #${visit.visit_num}</span>` : ''}
            </button>
            ${nfBadge(visit, pecas, servicos)}
            <span class="visit-summary truncate">${visit.complaint || ''}</span>
            ${hasValue(d.total) ? html`<span class="visit-head-total col-price">Total <strong class="num">${d.total}</strong></span>` : ''}
        </header>

        <div class="visit-body" data-field="body"${open ? '' : ' hidden'}>
            <div class="visit-toolbar">
                <div class="visit-file truncate" title="${visit.file_name || ''}">${icon('file-spreadsheet', 12)} ${visit.file_name || ''}</div>
                <div class="visit-actions">
                    <button type="button" class="btn btn-secondary btn-sm" data-action="orcamento" title="Orçamento / OS em PDF">${icon('file-text', 15)} Orçamento</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-action="checklist" title="Checklist para os mecânicos (sem valores)">${icon('clipboard-list', 15)} Checklist</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-action="fiscal" title="Copiloto Fiscal desta OS">${icon('receipt-text', 15)} Copiloto NF</button>
                    <button type="button" class="btn btn-ghost btn-sm" data-action="edit" title="Editar dados, peças ou serviços desta OS">${icon('pencil', 15)} Editar OS</button>
                    <button type="button" class="btn btn-ghost btn-sm" data-action="excel" title="Abrir a planilha original no Excel">${icon('file-spreadsheet', 15)} Abrir no Excel</button>
                </div>
            </div>

            ${(visit.complaint || d.complaint_comment) ? html`<div class="visit-complaint">
                ${icon('message-square-text', 16)}
                <div class="visit-complaint-text"><span class="text-subtle">Queixa / motivo:</span> ${visit.complaint || 'Visita para revisão / manutenção'}</div>
                ${d.complaint_comment ? html`<span class="visit-complaint-actions">
                    <button type="button" class="btn btn-secondary btn-sm" data-action="scanner-note">${icon('scan-line', 15)} Relatório do scanner</button>
                    <button type="button" class="btn btn-secondary btn-icon btn-sm" data-action="scanner-whatsapp" aria-label="Copiar relatório do scanner para o WhatsApp" data-tooltip="Copiar para o WhatsApp">${icon('message-square-text', 15)}</button>
                </span>` : ''}
            </div>` : ''}

            <div class="sheet-bar">
                <span class="sheet-bar-title">${icon('package', 14)} Peças da planilha <span class="badge">${pecas.length}</span></span>
                ${hasValue(d.total_pecas) ? html`<span class="sheet-bar-total col-price">Total de peças <strong class="num">${d.total_pecas}</strong></span>` : ''}
                <button type="button" class="btn btn-ghost btn-sm push" data-action="toggle-services" aria-expanded="false">
                    ${icon('wrench', 15)} <span data-field="services-label">Ver serviços executados</span> <span class="badge">${servicos.length}</span>
                    ${hasValue(d.total_servicos) ? html`<span class="text-subtle num col-price">${d.total_servicos}</span>` : ''}
                </button>
            </div>
            ${pecas.length
                ? itemsTable(pecas, { main: true, mode: 'pecas' })
                : html`<p class="items-empty">Nenhuma peça discriminada na seção de peças desta planilha.</p>`}
            ${servicesPanel(servicos, d.total_servicos, true)}

            <footer class="visit-footer">
                <div class="visit-extras">
                    ${extras.length ? html`<span class="text-xs text-subtle">Outras abas:</span>
                        ${extras.map((sheet, i) => html`<button type="button" class="btn btn-ghost btn-sm extra-sheet-btn" data-action="extra-sheet" data-sheet-index="${i}" title="${sheet.title || `Ver a aba ${sheet.sheet_name}`}">
                            ${icon('table', 14)} ${sheet.sheet_name}${sheet.items && sheet.items.length ? html` <span class="badge">${sheet.items.length}</span>` : ''}
                        </button>`)}` : ''}
                </div>
                <div class="visit-totals totals-group">
                    ${totals.map(([label, value]) => html`<span class="visit-total-item">${label} <strong class="num">${value}</strong></span>`)}
                    ${hasValue(d.total) ? html`<span class="visit-total-final">Total da visita <strong class="num">${d.total}</strong></span>` : ''}
                </div>
            </footer>
            <div class="extra-sheets-holder" data-field="extras"></div>
        </div>
    </article>`;
}

function extraSheetMarkup(sheet) {
    const all = sheet.items || [];
    const pecas = sheet.pecas_items || all.filter((i) => i.section !== SERVICE_SECTION);
    const servicos = sheet.servicos_items || all.filter((i) => i.section === SERVICE_SECTION);
    let body;
    if (all.length) {
        body = html`
            <div class="sheet-bar">
                <span class="sheet-bar-title">${icon('package', 14)} Peças da aba <span class="badge">${pecas.length}</span></span>
                ${sheet.total_pecas ? html`<span class="sheet-bar-total col-price">Subtotal peças <strong class="num">${sheet.total_pecas}</strong></span>` : ''}
                <button type="button" class="btn btn-ghost btn-sm push" data-action="toggle-services" aria-expanded="false">
                    ${icon('wrench', 15)} <span data-field="services-label">Ver serviços executados</span> <span class="badge">${servicos.length}</span>
                </button>
            </div>
            ${pecas.length ? itemsTable(pecas) : html`<p class="items-empty">Nenhuma peça listada nesta aba.</p>`}
            ${servicesPanel(servicos, sheet.total_servicos, false)}`;
    } else if (sheet.grid_rows && sheet.grid_rows.length) {
        body = html`<div class="table-wrap table-flush"><table class="table table-compact"><tbody>
            ${sheet.grid_rows.map((cells) => html`<tr>${cells.map((c) => html`<td>${c || ''}</td>`)}</tr>`)}
        </tbody></table></div>`;
    } else {
        body = html`<p class="items-empty">Aba sem conteúdo legível.</p>`;
    }
    const totals = [
        sheet.total_pecas && ['Peças', sheet.total_pecas],
        sheet.total_servicos && ['Serviços', sheet.total_servicos],
        sheet.subtotal && ['Subtotal', sheet.subtotal],
        sheet.discount && ['Desconto', sheet.discount],
    ].filter(Boolean);
    return html`<section class="extra-sheet-panel">
        <header class="extra-sheet-header">
            <span class="fw-semibold">${icon('table', 14)} Aba: ${sheet.sheet_name}</span>
            ${sheet.title ? html`<span class="text-subtle truncate">— ${sheet.title}</span>` : ''}
            <span class="visit-totals totals-group push">
                ${totals.map(([l, v]) => html`<span class="visit-total-item">${l} <strong class="num">${v}</strong></span>`)}
                ${sheet.total ? html`<span class="visit-total-final">Total <strong class="num">${sheet.total}</strong></span>` : ''}
            </span>
        </header>
        ${body}
    </section>`;
}

/** Liga o botão "Ver serviços" de um contêiner (corpo da visita ou aba extra). */
function setupServicesToggle(container, initiallyOpen) {
    const panel = container.querySelector(':scope > [data-field="services"], :scope > .services-panel');
    const button = container.querySelector(':scope > .sheet-bar [data-action="toggle-services"]');
    const setVisible = (visible) => {
        if (!panel) return;
        panel.hidden = !visible;
        if (button) {
            button.setAttribute('aria-expanded', visible ? 'true' : 'false');
            button.classList.toggle('is-active', visible);
            const label = button.querySelector('[data-field="services-label"]');
            if (label) label.textContent = visible ? 'Ocultar serviços executados' : 'Ver serviços executados';
        }
    };
    setVisible(initiallyOpen);
    container._setServicesVisible = setVisible;
    return setVisible;
}

/** Abre/recolhe uma visita. `remember: false` para aberturas temporárias (filtro, impressão). */
function setCardOpen(card, open, { remember = true } = {}) {
    const body = $('[data-field="body"]', card);
    if (!body) return;
    body.hidden = !open;
    card.dataset.open = open ? 'true' : 'false';
    $('[data-action="toggle-visit"]', card)?.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (remember) {
        const visit = history?.sorted?.[Number(card.dataset.visitIndex)];
        if (visit) visitOpen.set(visitKey(visit), open);
    }
}

function restoreCardOpenState(card) {
    const index = Number(card.dataset.visitIndex);
    const visit = history.sorted[index];
    const stored = visitOpen.get(visitKey(visit));
    setCardOpen(card, stored === undefined ? defaultOpen(index, history.sorted.length) : stored, { remember: false });
}

function renderTimeline() {
    const list = $('[data-field="visits"]', root);
    cardControls.clear();
    render(list, html`${history.sorted.map((v, i) => visitCardMarkup(v, i))}`);
    applyRowColors(list);
    for (const card of $$('.visit-card', list)) {
        const index = Number(card.dataset.visitIndex);
        const visit = history.sorted[index];
        const { pecas, servicos } = splitItems(visit.details || {});
        const autoOpen = showAllServices || (pecas.length === 0 && servicos.length > 0);
        card._autoOpen = autoOpen;
        const body = $('[data-field="body"]', card);
        const setVisible = setupServicesToggle(body, autoOpen);
        card._setServicesVisible = setVisible;
        cardControls.set(index, { card, setServicesVisible: setVisible });
    }
    syncGlobalButtons();
}

function syncGlobalButtons() {
    const servicesBtn = $('[data-action="toggle-all-services"]', root);
    if (servicesBtn) {
        servicesBtn.classList.toggle('is-active', showAllServices);
        servicesBtn.setAttribute('aria-pressed', showAllServices ? 'true' : 'false');
        servicesBtn.querySelector('[data-field="label"]').textContent = showAllServices ? 'Ocultar serviços de todas as planilhas' : 'Mostrar serviços de todas as planilhas';
    }
    const cards = $$('.visit-card', root);
    const allOpen = cards.length > 0 && cards.every((c) => c.dataset.open === 'true');
    const openBtn = $('[data-action="toggle-all-visits"]', root);
    if (openBtn) {
        openBtn.hidden = cards.length < 2;
        openBtn.querySelector('[data-field="label"]').textContent = allOpen ? 'Recolher todas' : 'Expandir todas';
        openBtn.dataset.mode = allOpen ? 'collapse' : 'expand';
    }
}

function renderVehicle() {
    const visits = history.sorted;
    render($('[data-field="content"]', root), html`
        ${headerMarkup(visits)}

        <section class="veiculo-filter card">
            <div class="veiculo-toolbar">
                <h2 class="section-title veiculo-timeline-title">${icon('history', 18)} Linha do tempo <span class="badge">${visits.length}</span></h2>
                <div class="input-group veiculo-search">
                    ${icon('search', 16, 'input-icon')}
                    <input type="search" class="input" data-field="item-filter" aria-label="Buscar peça ou serviço neste veículo" placeholder="Buscar peça ou serviço neste veículo (ex.: óleo, correia, pastilha)" autocomplete="off">
                    <button type="button" class="btn btn-ghost btn-icon btn-sm input-action" data-action="clear-filter" aria-label="Limpar filtro" hidden>${icon('x', 15)}</button>
                </div>
                <div class="row row-gap-1 row-wrap">
                    <button type="button" class="btn btn-ghost btn-sm" data-action="toggle-all-visits" data-mode="expand">${icon('chevron-down', 15)} <span data-field="label">Expandir todas</span></button>
                    <button type="button" class="btn btn-secondary btn-sm" data-action="toggle-all-services" aria-pressed="false">${icon('wrench', 15)} <span data-field="label">Mostrar serviços de todas as planilhas</span></button>
                </div>
            </div>
            <div class="veiculo-matches" data-field="matches" hidden></div>
        </section>

        <div class="visits-list" data-field="visits"></div>`);

    renderTimeline();

    const printTrigger = $('[data-field="print-trigger"]', root);
    printMenu?.el.remove();
    printMenu = createMenu(printTrigger, {
        align: 'end',
        render: () => html`
            <button type="button" class="menu-item" data-action="print-with">${icon('printer', 16)} Imprimir com valores</button>
            <button type="button" class="menu-item" data-action="print-without">${icon('eye-off', 16)} Imprimir sem valores</button>`,
        onAction: (action) => startPrint(action === 'print-without'),
    });
}

/* ------------------------------------------------------------------ */
/* Filtro de peças / serviços                                          */
/* ------------------------------------------------------------------ */

/** Marca os trechos encontrados com a CSS Custom Highlight API (sem mexer no DOM). */
function paintHits(rows, query) {
    if (typeof CSS === 'undefined' || !CSS.highlights || typeof Highlight === 'undefined') return;
    const ranges = [];
    const tokens = normalizeText(query).split(/\s+/).filter(Boolean);
    for (const tr of rows) {
        const cell = tr.querySelector('.items-desc-text');
        const node = cell?.firstChild;
        if (!node || node.nodeType !== Node.TEXT_NODE) continue;
        const text = node.data;
        let folded = '';
        const map = [];
        for (let i = 0; i < text.length; i++) {
            for (const ch of text[i].normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()) {
                folded += ch;
                map.push(i);
            }
        }
        for (const token of tokens) {
            let from = 0;
            while (token) {
                const at = folded.indexOf(token, from);
                if (at < 0) break;
                const range = new Range();
                range.setStart(node, map[at]);
                range.setEnd(node, map[at + token.length - 1] + 1);
                ranges.push(range);
                from = at + token.length;
            }
        }
    }
    if (ranges.length) CSS.highlights.set('item-hit', new Highlight(...ranges));
    else CSS.highlights.delete('item-hit');
}

function clearHits() {
    if (typeof CSS !== 'undefined' && CSS.highlights) CSS.highlights.delete('item-hit');
}

function filterItems(rawQuery) {
    if (!history) return;
    const q = (rawQuery || '').trim();
    const matchesEl = $('[data-field="matches"]', root);
    const cards = $$('.visit-card', root);

    if (!q) {
        matchesEl.hidden = true;
        clearHits();
        for (const card of cards) {
            card.hidden = false;
            card.querySelectorAll('tr.is-match').forEach((tr) => tr.classList.remove('is-match'));
            card._setServicesVisible?.(showAllServices || card._autoOpen === true);
            restoreCardOpenState(card);
        }
        syncGlobalButtons();
        return;
    }

    const occurrences = [];
    const matchedRows = [];
    for (const card of cards) {
        const visit = history.sorted[Number(card.dataset.visitIndex)];
        if (!visit) continue;
        const d = visit.details || {};
        let cardMatch = false;
        let serviceMatch = false;

        if (matchesSearchTokens(`${visit.complaint || ''} ${d.complaint_comment || ''}`, q)) {
            cardMatch = true;
            occurrences.push({ visit, card, section: 'Queixa', description: visit.complaint || 'Nota técnica / diagnóstico' });
        }

        for (const tr of card.querySelectorAll('.main-sheet-table tbody tr')) {
            const ds = tr.dataset;
            if (matchesSearchTokens(`${ds.itemDesc || ''} ${ds.itemComment || ''}`, q)) {
                tr.classList.add('is-match');
                matchedRows.push(tr);
                cardMatch = true;
                const isService = ds.itemSection === SERVICE_SECTION;
                if (isService) serviceMatch = true;
                occurrences.push({ visit, card, row: tr, isService, section: ds.itemSection || 'Item', description: ds.itemDesc, quantity: ds.itemQty, price: ds.itemPrice });
            } else {
                tr.classList.remove('is-match');
            }
        }
        if (serviceMatch) card._setServicesVisible?.(true);

        for (const sheet of d.extra_sheets_data || []) {
            for (const it of sheet.items || []) {
                if (matchesSearchTokens(`${it.description || ''} ${it.comment || ''}`, q)) {
                    cardMatch = true;
                    occurrences.push({ visit, card, section: `${sheet.sheet_name} · ${it.section || 'Item'}`, description: it.description, quantity: it.quantity, price: it.total_price });
                }
            }
        }
        card.hidden = !cardMatch;
        if (cardMatch) setCardOpen(card, true, { remember: false });
    }

    matchesEl.hidden = false;
    matchesEl._occurrences = occurrences;
    render(matchesEl, html`
        <div class="row row-between veiculo-matches-head">
            <span class="fw-semibold">Histórico de “${q}” neste veículo</span>
            <span class="badge badge-accent">${plural(occurrences.length, 'registro')}</span>
        </div>
        ${occurrences.length ? html`<div class="veiculo-matches-list">${occurrences.map((o, i) => html`
            <button type="button" class="match-row" data-action="goto-match" data-match-index="${i}">
                <span class="match-row-meta">
                    <span class="num">${o.visit.entry_date || 'Sem data'}</span>
                    <span class="num">${o.visit.odometer ? formatKm(o.visit.odometer) : 'KM não inf.'}</span>
                    ${o.visit.visit_num ? html`<span>Visita #${o.visit.visit_num}</span>` : ''}
                </span>
                <span class="match-row-desc"><span class="tag">${o.section}</span> ${highlight(o.description || '', q)}${o.quantity && o.quantity !== '-' ? ` (qtd. ${o.quantity})` : ''}</span>
                ${o.price && o.price !== '-' ? html`<span class="match-row-price num col-price">${o.price}</span>` : ''}
            </button>`)}</div>`
            : html`<p class="text-sm text-muted">Nenhuma peça ou serviço com “${q}” nas visitas deste veículo.</p>`}`);

    paintHits(matchedRows.filter((tr) => !tr.closest('[hidden]')), q);
    syncGlobalButtons();
}

/* ------------------------------------------------------------------ */
/* Notas de célula (triângulo vermelho) e relatório do scanner         */
/* ------------------------------------------------------------------ */

function whatsappMessage({ heading, visit, item, text }) {
    const ctx = vehicleContext();
    const lines = [
        `*${heading}*`,
        `Veículo: ${ctx.car} (${ctx.plateDisplay})`,
    ];
    if (visit?.entry_date) lines.push(`Data: ${visit.entry_date}${visit.odometer ? ` · ${formatKm(visit.odometer)}` : ''}`);
    if (item) lines.push(`Item: ${item}`);
    lines.push('', String(text || '').replace(/\r\n?/g, '\n').trim(), '', '_MecatroniCar_');
    return lines.join('\n');
}

function openNote(note) {
    if (!noteModal) {
        noteModal = createModal({
            id: 'cell-note',
            icon: 'sticky-note',
            size: 'md',
            body: html`<pre class="preformatted" data-field="text"></pre>`,
            footer: html`
                <button type="button" class="btn btn-secondary" data-action="copy-whatsapp">${icon('message-square-text', 16)} Copiar para o WhatsApp</button>
                <button type="button" class="btn btn-secondary" data-action="copy">${icon('copy', 16)} Copiar texto</button>
                <button type="button" class="btn btn-primary push" data-modal-close>Fechar</button>`,
        });
        on(noteModal.footer, 'click', '[data-action]', (e, btn) => {
            if (!noteCurrent) return;
            if (btn.dataset.action === 'copy') copyText(noteCurrent.text, 'Texto copiado.');
            else if (btn.dataset.action === 'copy-whatsapp') copyText(whatsappMessage(noteCurrent), 'Nota copiada. É só colar no WhatsApp.');
        });
    }
    noteCurrent = note;
    noteModal.setTitle(note.title);
    noteModal.setSubtitle(note.subtitle);
    noteModal.body.querySelector('[data-field="text"]').textContent = note.text || '';
    noteModal.open();
}

function rowNote(tr, visit) {
    return {
        heading: 'Nota da planilha',
        title: 'Nota da planilha (Excel)',
        subtitle: `Item: ${tr.dataset.itemDesc || 'Célula'} (${tr.dataset.itemSection || 'Geral'})`,
        item: tr.dataset.itemDesc || '',
        text: tr.dataset.itemComment,
        visit,
    };
}

function scannerNote(visit) {
    return {
        heading: 'Relatório do scanner / diagnóstico',
        title: 'Relatório do scanner / diagnóstico',
        subtitle: `Veículo: ${visit.car_model || visit.plate} · Data: ${visit.entry_date || ''}`,
        text: visit.details?.complaint_comment,
        visit,
    };
}

/* ------------------------------------------------------------------ */
/* Ações                                                               */
/* ------------------------------------------------------------------ */

function visitFromEvent(target) {
    const card = target.closest('.visit-card');
    if (!card) return null;
    return { card, visit: history.sorted[Number(card.dataset.visitIndex)] };
}

function vehicleContext() {
    const latest = latestVisit();
    return {
        plate: vehiclePlate(),
        plateDisplay: formatPlate(latest?.plate_display || latest?.plate),
        car: latest?.car_model || 'Veículo',
        client: latest?.client_name || '',
    };
}

function startPrint(withoutPrices) {
    if (!history?.sorted?.length) {
        toast('Nenhum veículo com visitas carregado.', 'error');
        return;
    }
    const ctx = vehicleContext();
    openPrintSelection({
        visits: history.sorted,
        subtitle: `${ctx.plateDisplay} · ${ctx.car}${ctx.client ? ` (${ctx.client})` : ''} · ${plural(history.sorted.length, 'visita')}`,
        withoutPrices,
        onPrint: printOnScreen,
        onPdf: ({ indices, withoutPrices: noPrices }) => {
            openHistoryPdf({ plate: ctx.plate, selected_indices: indices, without_prices: noPrices, auto_print: false });
        },
    });
}

/** Impressão da própria tela: esconde visitas não selecionadas e (opcional) valores. */
function printOnScreen({ indices, withoutPrices, expandServices }) {
    const selected = new Set(indices);
    const cards = $$('.visit-card', root);
    const previousHidden = cards.map((c) => c.hidden);
    const previousOpen = cards.map((c) => c.dataset.open === 'true');
    document.body.classList.toggle('print-no-prices', Boolean(withoutPrices));
    for (const card of cards) {
        const idx = Number(card.dataset.visitIndex);
        card.hidden = false;
        card.classList.toggle('print-excluded', !selected.has(idx));
        if (selected.has(idx)) {
            setCardOpen(card, true, { remember: false });
            if (expandServices) card._setServicesVisible?.(true);
        }
    }
    $$('.extra-sheet-panel', root).forEach((p) => p.classList.add('print-excluded'));

    const cleanup = () => {
        document.body.classList.remove('print-no-prices');
        cards.forEach((card, i) => {
            card.classList.remove('print-excluded');
            card.hidden = previousHidden[i];
            setCardOpen(card, previousOpen[i], { remember: false });
        });
        $$('.extra-sheet-panel', root).forEach((p) => p.classList.remove('print-excluded'));
        window.removeEventListener('afterprint', cleanup);
        syncGlobalButtons();
    };
    window.addEventListener('afterprint', cleanup);
    setTimeout(() => window.print(), 150);
}

function handleAction(event, el) {
    const action = el.dataset.action;
    const ctx = visitFromEvent(el);

    switch (action) {
        case 'back':
            if (window.history.length > 1) window.history.back();
            else navigate('/busca');
            return;
        case 'clear-filter': {
            const input = $('[data-field="item-filter"]', root);
            input.value = '';
            el.hidden = true;
            filterItems('');
            input.focus();
            return;
        }
        case 'copy-phone':
            copyText(el.dataset.text, 'Telefone copiado.');
            return;
        case 'copy-chassis':
            copyText(el.dataset.text, 'Chassi copiado.');
            return;
        case 'new-visit':
            openNewOs({ plate: vehiclePlate() });
            return;
        case 'new-visit-plate':
            openNewOs({ plate: el.dataset.plate });
            return;
        case 'orcamento-latest':
            openOrcamentoPdf(latestVisit()?.file_path);
            return;
        case 'checklist-latest':
            if (latestVisit()) openChecklist(latestVisit(), vehicleContext());
            return;
        case 'fiscal-vehicle':
            openFiscalVisit({ plate: vehiclePlate() });
            return;
        case 'patio': {
            const latest = latestVisit();
            if (!latest) return;
            openPatioManager({ prefill: {
                plate: latest.plate_display || latest.plate || vehiclePlate(),
                client_name: latest.client_name || '',
                car_model: latest.car_model || '',
                car_color: latest.car_color || '',
            } });
            return;
        }
        case 'toggle-all-visits': {
            const expand = el.dataset.mode !== 'collapse';
            for (const card of $$('.visit-card', root)) setCardOpen(card, expand);
            syncGlobalButtons();
            return;
        }
        case 'toggle-all-services':
            showAllServices = !showAllServices;
            for (const { card } of cardControls.values()) {
                card._autoOpen = showAllServices || card._autoOpen;
                card._setServicesVisible?.(showAllServices);
            }
            $$('.extra-sheet-panel', root).forEach((p) => p._setServicesVisible?.(showAllServices));
            syncGlobalButtons();
            toast(showAllServices ? 'Mostrando os serviços executados em todas as planilhas.' : 'Mostrando apenas as peças. Abra os serviços de cada planilha quando precisar.');
            return;
        case 'goto-match': {
            const occ = $('[data-field="matches"]', root)._occurrences?.[Number(el.dataset.matchIndex)];
            if (!occ) return;
            setCardOpen(occ.card, true, { remember: false });
            if (occ.isService) occ.card._setServicesVisible?.(true);
            (occ.row || occ.card).scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }
        default:
            break;
    }

    if (!ctx || !ctx.visit) {
        // botões que dependem de um painel (ex.: toggle-services dentro de aba extra)
        if (action === 'toggle-services') {
            const container = el.closest('.extra-sheet-panel');
            if (container) container._setServicesVisible?.(container.querySelector('.services-panel')?.hidden);
        }
        return;
    }
    const { card, visit } = ctx;
    const d = visit.details || {};
    const body = $('[data-field="body"]', card);

    switch (action) {
        case 'toggle-visit':
            setCardOpen(card, body.hidden);
            syncGlobalButtons();
            break;
        case 'orcamento':
            openOrcamentoPdf(visit.file_path);
            break;
        case 'checklist':
            openChecklist(visit, vehicleContext());
            break;
        case 'fiscal':
            openFiscalVisit({ filePath: visit.file_path, plate: vehiclePlate(), visitNum: visit.visit_num });
            break;
        case 'edit':
            openEditOs(visit);
            break;
        case 'excel':
            openInExcel(visit.file_path);
            break;
        case 'scanner-note':
            openNote(scannerNote(visit));
            break;
        case 'scanner-whatsapp':
            copyText(whatsappMessage(scannerNote(visit)), 'Relatório copiado. É só colar no WhatsApp.');
            break;
        case 'note':
            openNote(rowNote(el.closest('tr'), visit));
            break;
        case 'note-whatsapp':
            copyText(whatsappMessage(rowNote(el.closest('tr'), visit)), 'Nota copiada. É só colar no WhatsApp.');
            break;
        case 'toggle-services': {
            const container = el.closest('.extra-sheet-panel') || body;
            const panel = container.querySelector(':scope > .services-panel');
            (container._setServicesVisible || card._setServicesVisible)?.(panel ? panel.hidden : true);
            break;
        }
        case 'extra-sheet': {
            const holder = card.querySelector('[data-field="extras"]');
            const idx = el.dataset.sheetIndex;
            let panel = holder.querySelector(`[data-sheet="${idx}"]`);
            if (panel) {
                panel.hidden = !panel.hidden;
                el.classList.toggle('is-active', !panel.hidden);
            } else {
                const sheet = (d.extra_sheets_data || [])[Number(idx)];
                if (!sheet) break;
                panel = toElement(extraSheetMarkup(sheet));
                panel.dataset.sheet = idx;
                holder.append(panel);
                applyRowColors(panel);
                const s = splitItems(sheet);
                setupServicesToggle(panel, showAllServices || (s.pecas.length === 0 && s.servicos.length > 0));
                el.classList.add('is-active');
            }
            break;
        }
        default:
            break;
    }
}

/* ------------------------------------------------------------------ */
/* Carregamento                                                        */
/* ------------------------------------------------------------------ */

async function load(plateParam, { quiet = false } = {}) {
    const requested = cleanPlate(plateParam);
    loadingPlate = requested;
    if (!quiet) {
        renderSkeleton();
        const scroller = root.closest('.main');
        if (scroller) scroller.scrollTop = 0;
    }
    try {
        const data = await api.get(`/api/car_history/${encodeURIComponent(requested)}`, { errorMessage: 'Erro ao carregar histórico' });
        if (loadingPlate !== requested) return;
        const visits = data.visits || [];
        if (!visits.length) {
            history = null;
            renderNotFound(requested);
            return;
        }
        history = { plate: data.plate || requested, visits, sorted: sortVisits(visits) };
        const filterValue = quiet ? $('[data-field="item-filter"]', root)?.value || '' : '';
        renderVehicle();
        if (filterValue) {
            const input = $('[data-field="item-filter"]', root);
            input.value = filterValue;
            $('[data-action="clear-filter"]', root).hidden = false;
            filterItems(filterValue);
        }
        const latest = latestVisit();
        document.title = `${formatPlate(latest.plate_display || latest.plate)} · ${latest.client_name || 'Veículo'} · MecatroniCar`;
    } catch (err) {
        if (loadingPlate !== requested) return;
        history = null;
        renderNotFound(requested, err.message);
        toast(`Erro ao carregar o histórico: ${err.message}`, 'error');
    }
}

export default {
    id: 'veiculo',
    title: 'Ficha do veículo',
    mount,
    enter(params) {
        showAllServices = false;
        visitOpen.clear();
        load(params.placa);
    },
    leave() {
        clearHits();
    },
};
