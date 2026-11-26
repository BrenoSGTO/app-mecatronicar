/**
 * Aba "Cotação de peças" da OS (uso interno da secretária).
 *
 * Planilha: uma linha por peça e uma coluna por autopeça cotada. A secretária digita
 * o VALOR CHEIO (de balcão) e o programa aplica o desconto fixo de cada autopeça,
 * mostrando os dois valores na célula. A grade destaca, por peça, o menor preço
 * com desconto e, no rodapé, qual autopeça sai mais barata para comprar tudo.
 *
 * Nada daqui vai para a planilha .xlsx, o orçamento, o checklist ou a NF:
 * a cotação fica só no banco local (GET/PUT /api/cotacao).
 *
 *   const panel = createCotacaoPanel({ onChange, getOsParts });
 *   panel.el  → nó para inserir no modal da OS
 *   panel.load(cotacao) / panel.getData() / panel.isEmpty() / panel.setSaveState(texto, tipo)
 */
import { state } from '../state.js';
import { html, render, on, $, $$, toElement } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createMenu } from '../ui/menu.js';
import { confirmDialog } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { formatMoney, parseDecimal, plural } from '../lib/format.js';
import { formatPct, loadAutopecas, openAutopecasManager } from './autopecas.js';

const MAX_SUPPLIERS = 12;
const MAX_PARTS = 60;
const NUM = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const QTY = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });
const EPS = 0.005;

const round2 = (n) => Math.round(n * 100) / 100;
const netOf = (full, pct) => round2(full * (1 - (Number(pct) || 0) / 100));
const catalog = () => state.get('autopecas') || [];

export function createCotacaoPanel({ onChange = () => {}, getOsParts = () => [] } = {}) {
    let data = { suppliers: [], parts: [] };

    const el = toElement(html`<section class="cot" aria-label="Cotação de peças">
        <div class="callout callout-info cot-private">
            ${icon('eye-off', 16)}
            <div>
                <div class="callout-title">Uso interno da oficina</div>
                A cotação não aparece na OS impressa, no orçamento, no checklist nem na nota fiscal.
            </div>
        </div>

        <div class="cot-toolbar">
            <button type="button" class="btn btn-secondary btn-sm" data-action="cot-add-supplier">${icon('plus', 14)} Adicionar autopeça</button>
            <button type="button" class="btn btn-secondary btn-sm" data-action="cot-add-part">${icon('plus', 14)} Adicionar peça</button>
            <button type="button" class="btn btn-ghost btn-sm" data-action="cot-import">${icon('copy', 14)} Copiar peças da OS</button>
            <button type="button" class="btn btn-ghost btn-sm" data-action="cot-manage">${icon('settings', 14)} Cadastro de autopeças</button>
            <span class="cot-save-state push" data-field="cot-state" role="status" aria-live="polite"></span>
        </div>

        <p class="cot-howto">
            ${icon('info', 14)}
            <span>Digite o <strong>valor cheio</strong> de cada peça (o preço de balcão, por unidade). O programa aplica o desconto da autopeça e mostra embaixo o valor <strong>com desconto</strong>.</span>
        </p>

        <div class="cot-body" data-field="cot-body"></div>
        <div class="cot-summary" data-field="cot-summary"></div>
    </section>`);

    const body = $('[data-field="cot-body"]', el);
    const summary = $('[data-field="cot-summary"]', el);
    const stateEl = $('[data-field="cot-state"]', el);

    /* ---------------- helpers ---------------- */

    function supplierById(id) {
        return data.suppliers.find((s) => s.id === String(id));
    }

    function changed() {
        onChange(getData());
    }

    function priceText(n) {
        return Number.isFinite(n) ? NUM.format(n) : '';
    }

    /* ---------------- render da grade ---------------- */

    function headerCell(s) {
        const cat = catalog().find((a) => String(a.id) === s.id);
        const drift = cat && Math.abs((cat.discount_pct || 0) - (s.discount_pct || 0)) > 0.001;
        return html`<th class="cot-col-sup" data-sup="${s.id}" scope="col">
            <div class="cot-sup-head">
                <div class="cot-sup-id">
                    <span class="cot-sup-name" title="${s.name}">${s.name}</span>
                    <span class="cot-sup-meta">${s.attendant ? html`${icon('user', 12)} ${s.attendant}` : 'Sem atendente'}</span>
                </div>
                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="cot-remove-supplier" aria-label="Tirar ${s.name} da cotação" data-tooltip="Tirar coluna">${icon('x', 14)}</button>
            </div>
            <span class="cot-sup-discount${s.discount_pct > 0 ? '' : ' is-zero'}">${s.discount_pct > 0 ? html`Desconto ${formatPct(s.discount_pct)}` : 'Sem desconto'}</span>
            ${drift ? html`<button type="button" class="cot-sup-drift" data-action="cot-sync-discount">${icon('refresh-cw', 12)} Cadastro: ${formatPct(cat.discount_pct)}. Usar</button>` : ''}
        </th>`;
    }

    function priceCell(part, s, pi) {
        const full = part.prices[s.id];
        const has = Number.isFinite(full);
        return html`<td class="cot-cell" data-sup="${s.id}">
            <label class="cot-price">
                <span class="cot-price-prefix" aria-hidden="true">Cheio</span>
                <input class="input input-sm input-num cot-input" data-col="price" data-sup="${s.id}" data-part="${pi}" inputmode="decimal" autocomplete="off" placeholder="0,00" value="${has ? priceText(full) : ''}" aria-label="Valor cheio de ${part.desc || `peça ${pi + 1}`} em ${s.name}">
            </label>
            <div class="cot-net" data-net></div>
        </td>`;
    }

    function renderGrid() {
        if (!data.suppliers.length && !data.parts.length) {
            render(body, html`<div class="empty-state cot-empty">
                <span class="empty-state-icon">${icon('table', 24)}</span>
                <div class="empty-state-title">Monte a cotação desta OS</div>
                <div class="empty-state-text">Adicione as peças (ou copie da aba da OS) e uma coluna para cada autopeça consultada.</div>
                <div class="empty-state-actions">
                    <button type="button" class="btn btn-secondary btn-sm" data-action="cot-import">${icon('copy', 14)} Copiar peças da OS</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-action="cot-add-supplier-inline">${icon('plus', 14)} Adicionar autopeça</button>
                </div>
            </div>`);
            render(summary, '');
            return;
        }
        render(body, html`<div class="table-wrap cot-wrap">
            <table class="table cot-table">
                <thead><tr>
                    <th class="cot-col-idx num" scope="col">#</th>
                    <th class="cot-col-part" scope="col">Peça</th>
                    <th class="cot-col-qty num" scope="col">Qtd</th>
                    ${data.suppliers.map(headerCell)}
                    ${data.suppliers.length ? '' : html`<th class="cot-col-sup cot-col-placeholder" scope="col">
                        <button type="button" class="btn btn-secondary btn-sm" data-action="cot-add-supplier-inline">${icon('plus', 14)} Autopeça</button>
                    </th>`}
                    <th class="cot-col-best" scope="col">Melhor preço</th>
                    <th class="cot-col-tools" scope="col"><span class="sr-only">Ações</span></th>
                </tr></thead>
                <tbody>${data.parts.map((p, pi) => html`<tr data-part="${pi}">
                    <td class="cot-col-idx num text-subtle">${pi + 1}</td>
                    <td class="cot-col-part"><input class="input input-sm" data-col="desc" data-part="${pi}" value="${p.desc}" placeholder="Descrição da peça" maxlength="200" aria-label="Peça ${pi + 1}"></td>
                    <td class="cot-col-qty"><input class="input input-sm input-num" data-col="qty" data-part="${pi}" value="${QTY.format(p.qty || 1)}" inputmode="decimal" aria-label="Quantidade da peça ${pi + 1}"></td>
                    ${data.suppliers.map((s) => priceCell(p, s, pi))}
                    ${data.suppliers.length ? '' : html`<td class="cot-cell cot-col-placeholder"></td>`}
                    <td class="cot-col-best" data-best></td>
                    <td class="cot-col-tools"><button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="cot-remove-part" aria-label="Remover peça ${pi + 1}" data-tooltip="Remover peça">${icon('trash-2', 14)}</button></td>
                </tr>`)}</tbody>
                <tfoot>
                    <tr class="cot-foot-total">
                        <th colspan="3" scope="row">Total com desconto<span class="cot-foot-hint">quantidade × preço com desconto</span></th>
                        ${data.suppliers.map((s) => html`<td class="cot-total" data-total="${s.id}"></td>`)}
                        ${data.suppliers.length ? '' : html`<td></td>`}
                        <td class="cot-col-best" data-total="split"></td>
                        <td></td>
                    </tr>
                </tfoot>
            </table>
        </div>
        <button type="button" class="btn btn-ghost btn-sm cot-add-row" data-action="cot-add-part">${icon('plus', 14)} Adicionar peça</button>`);
        refreshComputed();
    }

    /* ---------------- cálculos (sem recriar os campos) ---------------- */

    function compute() {
        const rows = data.parts.map((p) => {
            const quotes = data.suppliers
                .filter((s) => Number.isFinite(p.prices[s.id]))
                .map((s) => ({ id: s.id, full: p.prices[s.id], net: netOf(p.prices[s.id], s.discount_pct) }));
            const min = quotes.length ? Math.min(...quotes.map((q) => q.net)) : null;
            return { part: p, quotes, min, best: quotes.filter((q) => q.net - min < EPS).map((q) => q.id) };
        });
        const wanted = rows.filter((r) => r.part.desc || r.quotes.length).length;
        const totals = data.suppliers.map((s) => {
            let net = 0;
            let full = 0;
            let count = 0;
            rows.forEach((r) => {
                const q = r.quotes.find((x) => x.id === s.id);
                if (!q) return;
                const qty = r.part.qty || 1;
                net += q.net * qty;
                full += q.full * qty;
                count += 1;
            });
            return { s, net: round2(net), full: round2(full), count, complete: wanted > 0 && count === wanted };
        });
        const complete = totals.filter((t) => t.complete).sort((a, b) => a.net - b.net);
        let split = 0;
        let splitCount = 0;
        const splitSuppliers = new Set();
        rows.forEach((r) => {
            if (r.min === null) return;
            split += r.min * (r.part.qty || 1);
            splitCount += 1;
            splitSuppliers.add(r.best[0]);
        });
        return { rows, totals, complete, wanted, split: round2(split), splitCount, splitSuppliers };
    }

    function refreshComputed() {
        const table = $('.cot-table', body);
        if (!table) return;
        const c = compute();
        const bestAll = c.complete[0] || null;

        c.rows.forEach((r, pi) => {
            const tr = table.tBodies[0].rows[pi];
            if (!tr) return;
            const multiple = r.quotes.length >= 2;
            data.suppliers.forEach((s) => {
                const td = tr.querySelector(`td.cot-cell[data-sup="${CSS.escape(s.id)}"]`);
                if (!td) return;
                const q = r.quotes.find((x) => x.id === s.id);
                const isBest = Boolean(q) && multiple && r.best.includes(s.id);
                td.classList.toggle('is-best', isBest);
                td.classList.toggle('has-value', Boolean(q));
                const net = $('[data-net]', td);
                if (!q) {
                    render(net, '');
                } else if (s.discount_pct > 0) {
                    render(net, html`<span class="cot-net-label">com desconto</span> <strong class="num">${formatMoney(q.net)}</strong>${isBest ? html` <span class="cot-best-tag">${icon('check', 12)} menor</span>` : ''}`);
                } else {
                    render(net, html`<span class="cot-net-label">sem desconto</span> <strong class="num">${formatMoney(q.net)}</strong>${isBest ? html` <span class="cot-best-tag">${icon('check', 12)} menor</span>` : ''}`);
                }
            });
            const bestTd = $('[data-best]', tr);
            if (r.min === null) {
                render(bestTd, html`<span class="text-subtle">—</span>`);
            } else {
                const names = r.best.map((id) => supplierById(id)?.name).filter(Boolean);
                render(bestTd, html`<strong class="num">${formatMoney(r.min)}</strong><span class="cot-best-where" title="${names.join(', ')}">${r.quotes.length < 2 ? 'só ' : ''}${names.join(' / ')}</span>`);
            }
        });

        c.totals.forEach((t) => {
            const td = table.querySelector(`[data-total="${CSS.escape(t.s.id)}"]`);
            if (!td) return;
            const isBest = bestAll && bestAll.s.id === t.s.id && c.complete.length >= 1 && data.suppliers.length >= 2;
            td.classList.toggle('is-best-all', Boolean(isBest));
            td.classList.toggle('is-incomplete', !t.complete && t.count > 0);
            render(td, t.count === 0 ? html`<span class="text-subtle">Sem preços</span>` : html`
                <strong class="num cot-total-net">${formatMoney(t.net)}</strong>
                <span class="cot-total-full num">cheio ${formatMoney(t.full)}</span>
                <span class="cot-total-count${t.complete ? ' is-complete' : ''}">${t.complete ? html`${icon('check', 12)} todas as peças` : `${t.count} de ${c.wanted} ${c.wanted === 1 ? 'peça' : 'peças'}`}</span>
                ${isBest ? html`<span class="cot-best-all-tag">${icon('circle-check', 12)} Melhor para pegar tudo</span>` : ''}`);
        });
        const splitTd = table.querySelector('[data-total="split"]');
        if (splitTd) {
            render(splitTd, c.splitCount ? html`<strong class="num">${formatMoney(c.split)}</strong><span class="cot-best-where">${c.splitSuppliers.size === 1 ? 'tudo em 1 autopeça' : `dividindo em ${c.splitSuppliers.size} autopeças`}</span>` : html`<span class="text-subtle">—</span>`);
        }
        renderSummary(c);
    }

    function renderSummary(c) {
        if (data.suppliers.length < 1 || !c.rows.some((r) => r.quotes.length)) {
            render(summary, '');
            return;
        }
        const best = c.complete[0];
        const second = c.complete[1];
        let main;
        if (best) {
            const saving = second ? round2(second.net - best.net) : 0;
            main = html`<div class="cot-verdict is-good">
                <span class="cot-verdict-icon">${icon('circle-check', 20)}</span>
                <div>
                    <div class="cot-verdict-label">Melhor para pegar tudo em um lugar</div>
                    <div class="cot-verdict-value"><strong>${best.s.name}</strong> · <span class="num">${formatMoney(best.net)}</span> com desconto</div>
                    <div class="cot-verdict-sub">${second
                        ? html`Economia de <strong class="num">${formatMoney(saving)}</strong> em relação a ${second.s.name}.`
                        : c.totals.length > 1 ? 'É a única que cotou todas as peças.' : `Valor cheio: ${formatMoney(best.full)}.`}</div>
                </div>
            </div>`;
        } else {
            const ranked = c.totals.filter((t) => t.count > 0).sort((a, b) => b.count - a.count || a.net - b.net);
            const top = ranked[0];
            main = html`<div class="cot-verdict is-warn">
                <span class="cot-verdict-icon">${icon('triangle-alert', 20)}</span>
                <div>
                    <div class="cot-verdict-label">Nenhuma autopeça cotou todas as peças</div>
                    <div class="cot-verdict-value">${top ? html`A mais completa é <strong>${top.s.name}</strong>: ${top.count} de ${c.wanted} ${c.wanted === 1 ? 'peça' : 'peças'}, <span class="num">${formatMoney(top.net)}</span>.` : ''}</div>
                    <div class="cot-verdict-sub">Preencha os preços que faltam para comparar o total.</div>
                </div>
            </div>`;
        }
        const splitDiff = best ? round2(best.net - c.split) : 0;
        const splitCard = c.splitCount ? html`<div class="cot-verdict">
            <span class="cot-verdict-icon">${icon('coins', 20)}</span>
            <div>
                <div class="cot-verdict-label">Comprando cada peça onde é mais barata</div>
                <div class="cot-verdict-value"><span class="num">${formatMoney(c.split)}</span> em ${plural(c.splitSuppliers.size, 'autopeça')}</div>
                <div class="cot-verdict-sub">${best && splitDiff > EPS
                    ? html`<strong class="num">${formatMoney(splitDiff)}</strong> a menos que pegar tudo na ${best.s.name}.`
                    : best ? 'Mesmo valor de pegar tudo em um lugar só.' : `${c.splitCount} de ${c.wanted} ${c.wanted === 1 ? 'peça cotada' : 'peças cotadas'}.`}</div>
            </div>
        </div>` : '';
        render(summary, html`${main}${splitCard}`);
    }

    /* ---------------- ações ---------------- */

    function addSupplier(a) {
        if (!a) return;
        if (supplierById(a.id)) {
            toast(`${a.name} já está na cotação.`, 'info');
            return;
        }
        if (data.suppliers.length >= MAX_SUPPLIERS) {
            toast(`A cotação comporta no máximo ${MAX_SUPPLIERS} autopeças.`, 'error');
            return;
        }
        data.suppliers.push({ id: String(a.id), name: a.name, attendant: a.attendant || '', discount_pct: Number(a.discount_pct) || 0 });
        if (!data.parts.length) data.parts.push({ desc: '', qty: 1, prices: {} });
        renderGrid();
        changed();
        // Foco no primeiro preço da nova coluna
        const input = $(`.cot-input[data-sup="${CSS.escape(String(a.id))}"]`, body);
        input?.focus();
    }

    function addPart({ desc = '', qty = 1 } = {}, { focus = true } = {}) {
        if (data.parts.length >= MAX_PARTS) {
            toast(`A cotação comporta no máximo ${MAX_PARTS} peças.`, 'error');
            return false;
        }
        data.parts.push({ desc, qty, prices: {} });
        renderGrid();
        changed();
        if (focus) $$('[data-col="desc"]', body).at(-1)?.focus();
        return true;
    }

    function importOsParts() {
        const list = (getOsParts() || []).filter((p) => p.desc);
        if (!list.length) {
            toast('A aba da OS ainda não tem peças. Adicione as peças aqui mesmo.', 'info');
            if (!data.parts.length) addPart();
            return;
        }
        const have = new Set(data.parts.map((p) => p.desc.trim().toLowerCase()));
        // Aproveita linhas vazias antes de criar novas
        data.parts = data.parts.filter((p) => p.desc || Object.keys(p.prices).length);
        let added = 0;
        for (const p of list) {
            if (have.has(p.desc.trim().toLowerCase())) continue;
            if (data.parts.length >= MAX_PARTS) break;
            data.parts.push({ desc: p.desc, qty: p.qty || 1, prices: {} });
            added += 1;
        }
        renderGrid();
        changed();
        toast(added ? `${plural(added, 'peça copiada', 'peças copiadas')} da OS.` : 'As peças da OS já estão na cotação.', added ? 'success' : 'info');
    }

    async function removeSupplier(id) {
        const s = supplierById(id);
        if (!s) return;
        const filled = data.parts.filter((p) => Number.isFinite(p.prices[s.id])).length;
        if (filled) {
            const ok = await confirmDialog({
                title: `Tirar ${s.name} da cotação?`,
                message: `${plural(filled, 'preço digitado será apagado', 'preços digitados serão apagados')}.`,
                confirmLabel: 'Tirar coluna',
                danger: true,
            });
            if (!ok) return;
        }
        data.suppliers = data.suppliers.filter((x) => x.id !== s.id);
        data.parts.forEach((p) => { delete p.prices[s.id]; });
        renderGrid();
        changed();
    }

    function removePart(pi) {
        data.parts.splice(pi, 1);
        renderGrid();
        changed();
    }

    function syncDiscount(id) {
        const s = supplierById(id);
        const cat = catalog().find((a) => String(a.id) === String(id));
        if (!s || !cat) return;
        s.discount_pct = Number(cat.discount_pct) || 0;
        s.name = cat.name;
        s.attendant = cat.attendant || '';
        renderGrid();
        changed();
    }

    // Menu suspenso do "Adicionar autopeça": lista o cadastro (recarregado a cada abertura).
    const addMenu = createMenu($('[data-action="cot-add-supplier"]', el), {
        className: 'cot-add-menu',
        align: 'start',
        onOpen: (menu) => { loadAutopecas({ force: true }).then(() => { if (menu.isOpen()) menu.refresh(); }); },
        render: () => {
            const all = catalog();
            return html`
                <div class="menu-label">Escolha a autopeça</div>
                ${all.length ? all.map((a) => {
                    const used = Boolean(supplierById(a.id));
                    return html`<button type="button" class="menu-item cot-menu-item" role="menuitem" data-action="pick" data-id="${a.id}"${used ? html` disabled` : ''}>
                        <span class="grow"><span class="cot-menu-name">${a.name}</span><span class="cot-menu-meta">${a.attendant || 'Sem atendente'}${used ? ' · já na cotação' : ''}</span></span>
                        <span class="tag${a.discount_pct > 0 ? ' tag-success' : ''}">${a.discount_pct > 0 ? `-${formatPct(a.discount_pct)}` : '0%'}</span>
                    </button>`;
                }) : html`<div class="cot-menu-empty text-sm text-muted">Nenhuma autopeça cadastrada ainda.</div>`}
                <div class="menu-separator"></div>
                <button type="button" class="menu-item" role="menuitem" data-action="new">${icon('plus', 16)} <span class="grow">Cadastrar nova autopeça</span></button>`;
        },
        onAction: (action, item) => {
            if (action === 'pick') addSupplier(catalog().find((a) => String(a.id) === item.dataset.id));
            if (action === 'new') openAutopecasManager({ onSaved: addSupplier });
        },
    });

    /* ---------------- eventos ---------------- */

    on(el, 'click', '[data-action]', (e, btn) => {
        const tr = btn.closest('tr[data-part]');
        const th = btn.closest('[data-sup]');
        switch (btn.dataset.action) {
            case 'cot-add-supplier-inline':
                e.stopPropagation();
                addMenu.open();
                break;
            case 'cot-add-part':
                addPart();
                break;
            case 'cot-import':
                importOsParts();
                break;
            case 'cot-manage':
                openAutopecasManager();
                break;
            case 'cot-remove-supplier':
                if (th) removeSupplier(th.dataset.sup);
                break;
            case 'cot-remove-part':
                if (tr) removePart(Number(tr.dataset.part));
                break;
            case 'cot-sync-discount':
                if (th) syncDiscount(th.dataset.sup);
                break;
            default:
                break;
        }
    });

    on(el, 'input', 'input[data-col]', (e, input) => {
        const pi = Number(input.dataset.part);
        const part = data.parts[pi];
        if (!part) return;
        const col = input.dataset.col;
        if (col === 'desc') {
            part.desc = input.value;
        } else if (col === 'qty') {
            const n = parseDecimal(input.value, 3);
            part.qty = n && n > 0 ? n : 1;
            input.classList.toggle('is-invalid', Number.isNaN(n) || (n !== null && n <= 0));
        } else if (col === 'price') {
            const n = parseDecimal(input.value);
            const bad = Number.isNaN(n) || (n !== null && n < 0);
            input.classList.toggle('is-invalid', bad);
            if (n === null || bad) delete part.prices[input.dataset.sup];
            else part.prices[input.dataset.sup] = n;
        }
        refreshComputed();
        changed();
    });

    on(el, 'focusout', 'input[data-col="price"]', (e, input) => {
        const n = parseDecimal(input.value);
        if (n !== null && !Number.isNaN(n) && n >= 0) input.value = priceText(n);
    });

    // Enter desce para a mesma coluna da peça seguinte (cria a linha no fim); setas ↑/↓ também.
    on(el, 'keydown', 'input[data-col]', (e, input) => {
        if (!['Enter', 'ArrowDown', 'ArrowUp'].includes(e.key) || e.altKey || e.ctrlKey) return;
        e.preventDefault();
        e.stopPropagation();
        const pi = Number(input.dataset.part);
        const delta = e.key === 'ArrowUp' ? -1 : 1;
        const selector = input.dataset.col === 'price'
            ? `input[data-col="price"][data-sup="${CSS.escape(input.dataset.sup)}"][data-part="${pi + delta}"]`
            : `input[data-col="${input.dataset.col}"][data-part="${pi + delta}"]`;
        let next = $(selector, body);
        if (!next && e.key === 'Enter' && pi === data.parts.length - 1) {
            if (addPart({}, { focus: false })) next = $(selector, body);
        }
        next?.focus();
        next?.select?.();
    });

    // Desconto alterado no cadastro: o cabeçalho oferece atualizar a coluna.
    state.watch('autopecas', () => { if (data.suppliers.length) renderGrid(); });

    /* ---------------- API do painel ---------------- */

    function getData() {
        return {
            suppliers: data.suppliers.map((s) => ({ ...s })),
            parts: data.parts
                .filter((p) => p.desc.trim() || Object.keys(p.prices).length)
                .map((p) => ({ desc: p.desc.trim(), qty: p.qty || 1, prices: { ...p.prices } })),
        };
    }

    function load(cot) {
        const src = cot || {};
        data = {
            suppliers: (src.suppliers || []).map((s) => ({ id: String(s.id), name: s.name || '', attendant: s.attendant || '', discount_pct: Number(s.discount_pct) || 0 })),
            parts: (src.parts || []).map((p) => {
                const prices = {};
                Object.entries(p.prices || {}).forEach(([k, v]) => {
                    const n = Number(v);
                    if (Number.isFinite(n)) prices[String(k)] = n;
                });
                return { desc: p.desc || '', qty: Number(p.qty) || 1, prices };
            }),
        };
        addMenu.close();
        setSaveState('', '');
        renderGrid();
        loadAutopecas();
    }

    function setSaveState(text, kind = '') {
        stateEl.textContent = text;
        stateEl.dataset.kind = kind;
    }

    function counts() {
        const d = getData();
        return { suppliers: d.suppliers.length, parts: d.parts.length };
    }

    return {
        el,
        load,
        getData,
        isEmpty: () => { const c = counts(); return !c.suppliers && !c.parts; },
        counts,
        setSaveState,
        close: () => addMenu.close(),
    };
}
