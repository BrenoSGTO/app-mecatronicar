/**
 * Modal "Selecionar visitas para impressão" (com/sem valores, expandir
 * serviços, relatório consolidado em PDF). A impressão em si é feita por
 * quem chamou (veiculo.js) através dos callbacks.
 * Dono na Fase 2: T8.
 *
 *   openPrintSelection({ visits, subtitle, withoutPrices, onPrint, onPdf })
 *     onPrint({ indices, withoutPrices, expandServices })
 *     onPdf({ indices, withoutPrices })
 */
import { html, render, on, $, $$ } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { formatKm } from '../lib/format.js';

let modal = null;
let current = null;

function build() {
    modal = createModal({
        id: 'print-selection',
        title: 'Selecionar visitas para impressão',
        icon: 'printer',
        size: 'md',
        body: html`
            <div class="stack">
                <div class="row row-wrap row-between">
                    <div class="row row-wrap row-gap-1" role="group" aria-label="Atalhos de seleção">
                        <button type="button" class="btn btn-ghost btn-sm" data-select="all">Todas</button>
                        <button type="button" class="btn btn-ghost btn-sm" data-select="none">Nenhuma</button>
                        <button type="button" class="btn btn-ghost btn-sm" data-select="1">Mais recente</button>
                        <button type="button" class="btn btn-ghost btn-sm" data-select="3">Últimas 3</button>
                        <button type="button" class="btn btn-ghost btn-sm" data-select="5">Últimas 5</button>
                    </div>
                    <span class="text-sm text-muted num" data-field="counter"></span>
                </div>
                <div class="print-visit-list" data-field="list"></div>
                <div class="stack stack-2 print-options">
                    <label class="check">
                        <input type="checkbox" data-field="no-prices">
                        <span class="check-text"><strong>Ocultar valores</strong><span class="check-desc">Imprime sem os preços das peças e serviços.</span></span>
                    </label>
                    <label class="check">
                        <input type="checkbox" data-field="expand" checked>
                        <span class="check-text"><strong>Expandir serviços executados</strong><span class="check-desc">Mostra a tabela de serviços em todas as visitas selecionadas.</span></span>
                    </label>
                </div>
            </div>`,
        footer: html`
            <button type="button" class="btn btn-secondary push" data-modal-close>Cancelar</button>
            <button type="button" class="btn btn-secondary" data-action="pdf" title="Gerar relatório consolidado em nova janela">${icon('file-down', 16)} Relatório consolidado</button>
            <button type="button" class="btn btn-primary" data-action="print">${icon('printer', 16)} Imprimir selecionadas</button>`,
    });

    const listEl = $('[data-field="list"]', modal.body);
    on(listEl, 'change', 'input[type="checkbox"]', updateCounter);
    on(modal.body, 'click', '[data-select]', (e, btn) => {
        const mode = btn.dataset.select;
        $$('input[data-idx]', listEl).forEach((cb, i) => {
            cb.checked = mode === 'all' ? true : mode === 'none' ? false : i < Number(mode);
        });
        updateCounter();
    });
    on(modal.footer, 'click', '[data-action]', (e, btn) => {
        const indices = selectedIndices();
        if (!indices.length) {
            toast('Selecione ao menos uma visita.', 'error');
            return;
        }
        const withoutPrices = $('[data-field="no-prices"]', modal.body).checked;
        const expandServices = $('[data-field="expand"]', modal.body).checked;
        modal.close();
        if (btn.dataset.action === 'print') current.onPrint?.({ indices, withoutPrices, expandServices });
        else current.onPdf?.({ indices, withoutPrices });
    });
}

function selectedIndices() {
    return $$('input[data-idx]:checked', modal.body).map((cb) => Number(cb.dataset.idx));
}

function updateCounter() {
    const total = current.visits.length;
    const checked = selectedIndices().length;
    $('[data-field="counter"]', modal.body).textContent = `${checked} de ${total} selecionadas`;
}

export function openPrintSelection(options) {
    if (!modal) build();
    current = options;
    modal.setSubtitle(options.subtitle || '');
    $('[data-field="no-prices"]', modal.body).checked = Boolean(options.withoutPrices);
    $('[data-field="expand"]', modal.body).checked = true;

    render($('[data-field="list"]', modal.body), html`${options.visits.map((v, idx) => {
        const vNum = v.visit_num || String(options.visits.length - idx);
        const total = v.details?.total || '';
        return html`<label class="print-visit-row">
            <input type="checkbox" class="checkbox" data-idx="${idx}" checked>
            <span class="print-visit-main">
                <span class="row row-wrap row-gap-3">
                    <span class="tag tag-accent">Visita #${vNum}</span>
                    <span class="num text-sm">${v.entry_date || 'Sem data'}</span>
                    <span class="num text-sm text-muted">${v.odometer ? formatKm(v.odometer) : 'KM não inf.'}</span>
                    ${total ? html`<span class="num text-sm fw-semibold push">${total}</span>` : ''}
                </span>
                <span class="text-sm text-muted truncate">${v.complaint || 'Revisão / manutenção preventiva'}</span>
            </span>
        </label>`;
    })}`);
    updateCounter();
    modal.open();
}
