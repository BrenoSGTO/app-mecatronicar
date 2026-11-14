/**
 * Modal "Configurar checklist da oficina" → POST /api/checklist_pdf.
 * Permite escolher itens da visita, incluir o relatório do scanner e
 * adicionar itens manuais. Dono na Fase 2: T9 (OS / checklist).
 *
 *   openChecklist(visit, { plateDisplay, car, client })
 */
import { html, render, on, $, $$ } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { openChecklistPdf } from '../lib/documents.js';
import { formatPlate } from '../lib/format.js';

const SERVICE_SECTION = 'Serviço';

let modal = null;
let visit = null;
let manualItems = [];

function typeTag(type) {
    return type === 'servico'
        ? html`<span class="tag tag-info">${icon('wrench', 12)} Serviço</span>`
        : html`<span class="tag tag-warning">${icon('package', 12)} Peça</span>`;
}

function build() {
    modal = createModal({
        id: 'checklist',
        title: 'Checklist da oficina',
        icon: 'clipboard-list',
        size: 'md',
        body: html`
            <div class="stack stack-4">
                <label class="check checklist-option">
                    <input type="checkbox" data-field="scanner" checked>
                    <span class="check-text">
                        <strong>${icon('scan-line', 14)} Incluir códigos de falha / diagnóstico (scanner OBD2)</strong>
                        <span class="check-desc" data-field="scanner-desc"></span>
                    </span>
                </label>

                <section class="stack stack-2">
                    <div class="row row-between">
                        <span class="eyebrow">Peças e serviços desta visita <span class="badge" data-field="count">0</span></span>
                        <span class="row row-gap-1">
                            <button type="button" class="btn btn-ghost btn-sm" data-action="select-all">Marcar todos</button>
                            <button type="button" class="btn btn-ghost btn-sm" data-action="select-none">Desmarcar todos</button>
                        </span>
                    </div>
                    <div class="checklist-items" data-field="items"></div>
                </section>

                <section class="stack stack-2">
                    <span class="eyebrow">Adicionar item manualmente</span>
                    <div class="checklist-manual-form">
                        <select class="select" data-field="manual-type" aria-label="Tipo">
                            <option value="peca">Peça / componente</option>
                            <option value="servico">Serviço / mão de obra</option>
                        </select>
                        <input class="input input-num" data-field="manual-qty" value="1" aria-label="Quantidade" autocomplete="off">
                        <input class="input" data-field="manual-desc" placeholder="Ex.: Higienização do ar-condicionado" autocomplete="off" aria-label="Descrição">
                        <button type="button" class="btn btn-secondary" data-action="add-manual">${icon('plus', 16)} Adicionar</button>
                    </div>
                    <div class="checklist-items" data-field="manual" hidden></div>
                </section>
            </div>`,
        footer: html`
            <button type="button" class="btn btn-secondary push" data-modal-close>Cancelar</button>
            <button type="button" class="btn btn-secondary" data-action="preview" title="Abre o checklist em nova janela sem imprimir">${icon('eye', 16)} Visualizar</button>
            <button type="button" class="btn btn-primary" data-action="print">${icon('printer', 16)} Gerar e imprimir</button>`,
    });

    on(modal.el, 'click', '[data-action]', (e, btn) => {
        const action = btn.dataset.action;
        if (action === 'select-all' || action === 'select-none') {
            $$('[data-field="items"] input[type="checkbox"]', modal.body).forEach((cb) => { cb.checked = action === 'select-all'; });
        } else if (action === 'add-manual') {
            addManual();
        } else if (action === 'remove-manual') {
            manualItems.splice(Number(btn.dataset.index), 1);
            renderManual();
        } else if (action === 'preview') {
            submit(false);
        } else if (action === 'print') {
            submit(true);
        }
    });
    $('[data-field="manual-desc"]', modal.body).addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addManual();
        }
    });
}

function renderItems(pecas, servicos) {
    const all = [
        ...pecas.map((p) => ({ ...p, type: 'peca' })),
        ...servicos.map((s) => ({ ...s, type: 'servico' })),
    ];
    $('[data-field="count"]', modal.body).textContent = String(all.length);
    const listEl = $('[data-field="items"]', modal.body);
    if (!all.length) {
        render(listEl, html`<p class="text-sm text-muted checklist-empty">Nenhuma peça ou serviço registrado nesta visita. Adicione itens manualmente abaixo.</p>`);
        return;
    }
    render(listEl, html`${all.map((it) => html`<label class="checklist-item">
        <input type="checkbox" class="checkbox" checked
            data-type="${it.type}" data-qty="${it.quantity || '1'}" data-desc="${it.description || 'Item sem descrição'}" data-comment="${it.comment || ''}">
        ${typeTag(it.type)}
        <span class="num text-sm checklist-qty">${it.quantity || '1'}x</span>
        <span class="checklist-desc">${it.description || 'Item sem descrição'}${it.comment ? html` <span class="text-subtle text-xs">(obs.: ${it.comment})</span>` : ''}</span>
    </label>`)}`);
}

function renderManual() {
    const listEl = $('[data-field="manual"]', modal.body);
    listEl.hidden = manualItems.length === 0;
    render(listEl, html`${manualItems.map((it, i) => html`<div class="checklist-item">
        ${typeTag(it.type)}
        <span class="num text-sm checklist-qty">${it.quantity}x</span>
        <span class="checklist-desc">${it.description} <span class="text-subtle text-xs">(manual)</span></span>
        <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="remove-manual" data-index="${i}" aria-label="Remover item">${icon('x', 15)}</button>
    </div>`)}`);
}

function addManual() {
    const descEl = $('[data-field="manual-desc"]', modal.body);
    const qtyEl = $('[data-field="manual-qty"]', modal.body);
    const desc = descEl.value.trim();
    if (!desc) {
        toast('Informe a descrição do item.', 'error');
        descEl.focus();
        return;
    }
    manualItems.push({
        type: $('[data-field="manual-type"]', modal.body).value,
        quantity: qtyEl.value.trim() || '1',
        description: desc,
    });
    descEl.value = '';
    qtyEl.value = '1';
    renderManual();
    descEl.focus();
}

function submit(autoPrint) {
    if (!visit) return;
    const items = $$('[data-field="items"] input[type="checkbox"]:checked', modal.body).map((cb) => ({
        type: cb.dataset.type,
        quantity: cb.dataset.qty,
        description: cb.dataset.desc,
        comment: cb.dataset.comment || '',
    }));
    openChecklistPdf({
        file_path: visit.file_path,
        plate: visit.plate_clean || visit.plate,
        include_scanner: $('[data-field="scanner"]', modal.body).checked,
        auto_print: autoPrint,
        items: [...items, ...manualItems],
    });
    modal.close();
}

export function openChecklist(targetVisit, context = {}) {
    if (!targetVisit) {
        toast('Nenhuma visita disponível para o checklist.', 'error');
        return;
    }
    if (!modal) build();
    visit = targetVisit;
    manualItems = [];

    const plateText = formatPlate(targetVisit.plate_display || targetVisit.plate || context.plateDisplay);
    const car = targetVisit.car_model || context.car || 'Veículo';
    const client = targetVisit.client_name || context.client || '';
    modal.setSubtitle(`${plateText} · ${car} · Visita #${targetVisit.visit_num || '1'}${client ? ` · ${client}` : ''}`);

    const d = targetVisit.details || {};
    const items = d.items || [];
    const pecas = d.pecas_items || items.filter((i) => i.section !== SERVICE_SECTION);
    const servicos = d.servicos_items || items.filter((i) => i.section === SERVICE_SECTION);

    $('[data-field="scanner"]', modal.body).checked = true;
    const note = (d.complaint_comment || '').trim();
    $('[data-field="scanner-desc"]', modal.body).textContent = note
        ? `Diagnóstico registrado: “${note.split('\n')[0].slice(0, 60)}…”`
        : 'Nenhum código gravado nesta visita.';

    $('[data-field="manual-desc"]', modal.body).value = '';
    $('[data-field="manual-qty"]', modal.body).value = '1';
    renderItems(pecas, servicos);
    renderManual();
    modal.open();
}
