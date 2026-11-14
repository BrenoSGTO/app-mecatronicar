/**
 * Copiloto Fiscal.
 * - Tela #/fiscal: fila de notas pendentes (GET /api/nf/queue), indicadores,
 *   exportação CSV/TXT (GET /api/nf/export_batch).
 * - Modal por visita (GET /api/nf/data): NFS-e Santos (mão de obra), NF-e 55
 *   (peças) e dados do tomador, com cópia em 1 clique e registro de emissão
 *   (POST /api/nf/status).
 * Dono na Fase 2: T10.
 *
 *   openFiscalVisit({ filePath, plate, visitNum, tab: 'nfse' | 'nfe' | 'tomador' })
 */
import { api, isAbort, openInNewTab } from '../api.js';
import { state, emit } from '../state.js';
import { refresh } from '../data.js';
import { navigate } from '../router.js';
import { html, render, on, $, $$, debounce, busy } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { copyText } from '../ui/clipboard.js';
import { formatMoney, formatPlate, todayIso } from '../lib/format.js';

const OFICINA = { cnpj: '05.961.672/0001-87', cidade: 'Santos / SP' };
const QUEUE_FILTERS = [
    ['pending', 'Pendentes'],
    ['pending_servico', 'Só mão de obra'],
    ['pending_pecas', 'Só peças'],
    ['emitidas', 'Já emitidas'],
    ['all', 'Todas'],
];

/* ================================================================== */
/* Tela: fila de pendências                                            */
/* ================================================================== */

let root = null;
let queueFilter = 'pending';
let queueController = null;

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Copiloto Fiscal</h1>
                <p class="page-subtitle">NFS-e Santos (mão de obra, item 14.01) e NF-e modelo 55 (autopeças) · CNPJ ${OFICINA.cnpj}</p>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-secondary" data-action="export" data-format="csv" title="Baixar a fila em planilha CSV para a contabilidade">${icon('file-down', 16)} CSV</button>
                <button type="button" class="btn btn-secondary" data-action="export" data-format="txt" title="Baixar resumo em texto">${icon('file-text', 16)} TXT</button>
                <button type="button" class="btn btn-secondary" data-action="refresh">${icon('refresh-cw', 16)} Atualizar</button>
            </div>
        </header>

        <div class="stat-grid fiscal-kpis">
            <div class="stat"><span class="stat-label">${icon('receipt-text', 14)} Visitas com nota pendente</span><span class="stat-value" data-kpi="visits">—</span></div>
            <div class="stat"><span class="stat-label">${icon('wrench', 14)} NFS-e a emitir (mão de obra)</span><span class="stat-value stat-value-sm" data-kpi="services">—</span><span class="stat-sub" data-kpi="services-sub"></span></div>
            <div class="stat"><span class="stat-label">${icon('package', 14)} NF-e a emitir (peças)</span><span class="stat-value stat-value-sm" data-kpi="parts">—</span><span class="stat-sub" data-kpi="parts-sub"></span></div>
            <div class="stat"><span class="stat-label">${icon('circle-check', 14)} Notas já emitidas</span><span class="stat-value" data-kpi="emitted">—</span></div>
        </div>

        <div class="fiscal-toolbar">
            <div class="segmented" role="group" aria-label="Filtro da fila">
                ${QUEUE_FILTERS.map(([value, label]) => html`<button type="button" class="segmented-item${value === queueFilter ? ' is-active' : ''}" data-filter="${value}">${label}</button>`)}
            </div>
            <div class="input-group fiscal-search">
                ${icon('list-filter', 16, 'input-icon')}
                <input type="search" class="input" data-field="search" placeholder="Filtrar por placa, cliente ou carro" autocomplete="off">
            </div>
        </div>

        <div class="fiscal-queue" data-field="queue"></div>`);

    const searchSoon = debounce(loadQueue, 250);
    on(root, 'input', '[data-field="search"]', () => searchSoon());
    on(root, 'click', '[data-filter]', (e, btn) => {
        queueFilter = btn.dataset.filter;
        $$('[data-filter]', root).forEach((b) => b.classList.toggle('is-active', b === btn));
        loadQueue();
    });
    on(root, 'click', '[data-action]', (e, btn) => queueAction(btn));

    state.watch('nfStats', renderKpis);
}

function renderKpis(stats) {
    if (!root || !stats) return;
    $('[data-kpi="visits"]', root).textContent = String(stats.pending_visits_count || 0);
    $('[data-kpi="services"]', root).textContent = formatMoney(stats.total_pending_services_val || 0);
    $('[data-kpi="services-sub"]', root).textContent = `${stats.pending_servicos_count || 0} visitas`;
    $('[data-kpi="parts"]', root).textContent = formatMoney(stats.total_pending_pecas_val || 0);
    $('[data-kpi="parts-sub"]', root).textContent = `${stats.pending_pecas_count || 0} visitas`;
    $('[data-kpi="emitted"]', root).textContent = String(stats.emitted_count || 0);
}

function queueQuery() {
    return ($('[data-field="search"]', root)?.value || '').trim();
}

async function loadQueue() {
    if (!root) return;
    const listEl = $('[data-field="queue"]', root);
    queueController?.abort();
    queueController = new AbortController();
    if (!listEl.children.length) {
        render(listEl, html`<div class="skeleton-stack">${[1, 2, 3].map(() => html`<div class="skeleton skeleton-block"></div>`)}</div>`);
    }
    try {
        const data = await api.get('/api/nf/queue', { params: { filter: queueFilter, q: queueQuery() }, signal: queueController.signal, errorMessage: 'Erro ao carregar a fila fiscal' });
        if (data.stats) state.set('nfStats', data.stats);
        renderQueue(data.items || []);
    } catch (err) {
        if (isAbort(err)) return;
        render(listEl, html`<div class="callout callout-danger">${icon('circle-alert', 16)}<div>Erro ao carregar a fila fiscal: ${err.message}</div></div>`);
    }
}

function renderQueue(items) {
    const listEl = $('[data-field="queue"]', root);
    if (!items.length) {
        render(listEl, html`<div class="card"><div class="empty-state empty-state-success">
            <span class="empty-state-icon">${icon('circle-check', 20)}</span>
            <div class="empty-state-title">Nenhuma nota neste filtro</div>
            <div class="empty-state-text">Quando houver OS com peças ou mão de obra sem nota emitida, elas aparecem aqui.</div>
        </div></div>`);
        return;
    }
    render(listEl, html`<div class="card fiscal-queue-list">${items.map((item, i) => {
        const servDone = item.status_servico === 'emitida';
        const pecasDone = item.status_pecas === 'emitida';
        return html`<article class="fiscal-queue-item" data-index="${i}">
            <div class="fiscal-queue-main">
                <div class="row row-wrap">
                    <span class="plate-chip">${formatPlate(item.plate_display || item.plate)}</span>
                    <span class="fw-semibold truncate">${item.car_model || 'Veículo'}</span>
                    <span class="text-muted truncate">${item.client_name || 'Cliente'}</span>
                    <span class="text-subtle num text-sm">${item.entry_date || '—'}</span>
                    ${item.visit_num ? html`<span class="tag">Visita #${item.visit_num}</span>` : ''}
                </div>
                <div class="row row-wrap row-gap-3">
                    <span class="fiscal-queue-status">
                        <span class="text-xs text-subtle">Mão de obra</span>
                        ${servDone
                            ? html`<span class="tag tag-success">${icon('circle-check', 12)} NFS-e ${item.nf_servico_num || 's/n'} · <span class="num">${formatMoney(item.valor_servico)}</span></span>`
                            : html`<span class="tag tag-warning">NFS-e pendente · <span class="num">${formatMoney(item.valor_servico)}</span></span>`}
                    </span>
                    <span class="fiscal-queue-status">
                        <span class="text-xs text-subtle">Peças</span>
                        ${pecasDone
                            ? html`<span class="tag tag-success">${icon('circle-check', 12)} NF-e ${item.nf_pecas_num || 's/n'} · <span class="num">${formatMoney(item.valor_pecas)}</span></span>`
                            : html`<span class="tag tag-warning">NF-e pendente · <span class="num">${formatMoney(item.valor_pecas)}</span></span>`}
                    </span>
                </div>
            </div>
            <div class="fiscal-queue-actions">
                <button type="button" class="btn btn-primary btn-sm" data-action="open" data-index="${i}">${icon('receipt-text', 15)} Abrir no Copiloto</button>
                <button type="button" class="btn btn-secondary btn-sm" data-action="copy-nfse" data-index="${i}" title="Copiar discriminação da NFS-e">${icon('copy', 15)} NFS-e</button>
                <button type="button" class="btn btn-secondary btn-sm" data-action="copy-nfe" data-index="${i}" title="Copiar tabela de peças (TSV) da NF-e">${icon('copy', 15)} Peças</button>
            </div>
        </article>`;
    })}</div>`);
    listEl._items = items;
}

async function queueAction(btn) {
    const action = btn.dataset.action;
    if (action === 'refresh') {
        loadQueue();
        refresh('nfStats');
        return;
    }
    if (action === 'export') {
        openInNewTab('/api/nf/export_batch', { format: btn.dataset.format, filter: queueFilter, q: queueQuery() });
        return;
    }
    const item = $('[data-field="queue"]', root)._items?.[Number(btn.dataset.index)];
    if (!item) return;
    const params = { file_path: item.file_path || '', plate: item.plate || '', visit_num: item.visit_num || '' };
    const plateText = formatPlate(item.plate_display || item.plate);
    if (action === 'open') {
        const onlyParts = item.status_servico === 'emitida' && item.status_pecas !== 'emitida';
        openFiscalVisit({ filePath: item.file_path, plate: item.plate, visitNum: item.visit_num, tab: onlyParts ? 'nfe' : 'nfse' });
    } else if (action === 'copy-nfse' || action === 'copy-nfe') {
        try {
            const type = action === 'copy-nfse' ? 'nfse_discriminacao' : 'nfe_pecas_tsv';
            const data = await api.get('/api/nf/copilot_text', { params: { type, ...params } });
            if (!data.text) throw new Error('texto vazio');
            copyText(data.text, action === 'copy-nfse' ? `Discriminação da NFS-e de ${plateText} copiada.` : `Tabela de peças de ${plateText} copiada.`);
        } catch (err) {
            toast(`Não foi possível gerar o texto: ${err.message}`, 'error');
        }
    }
}

/* ================================================================== */
/* Modal: Copiloto de uma visita                                      */
/* ================================================================== */

let modal = null;
let fiscal = { filePath: '', plate: '', visitNum: null, data: null };

function copyRow(label, valueField, buttons) {
    return html`<div class="tomador-field">
        <span class="tomador-label">${label}</span>
        <div class="tomador-row">
            <span class="tomador-value" data-tomador="${valueField}">—</span>
            ${buttons}
        </div>
    </div>`;
}

function copyButton(target, label = 'Copiar') {
    return html`<button type="button" class="btn btn-ghost btn-sm" data-copy-field="${target}">${icon('copy', 14)} ${label}</button>`;
}

function statusRow(kind) {
    const isNfse = kind === 'nfse';
    return html`<div class="fiscal-status-row">
        <div class="fiscal-status-total">
            <span class="text-sm text-muted">${isNfse ? 'Total mão de obra' : 'Total de peças'}</span>
            <strong class="num" data-field="${kind}-total">R$ 0,00</strong>
            <span class="tag" data-field="${kind}-status">Pendente</span>
        </div>
        <div class="fiscal-status-form">
            <input class="input input-sm" data-field="${kind}-number" placeholder="${isNfse ? 'Nº da NFS-e emitida' : 'Nº da NF-e emitida'}" aria-label="Número da nota" autocomplete="off">
            <input class="input input-sm" type="date" data-field="${kind}-date" aria-label="Data de emissão">
            <button type="button" class="btn btn-primary btn-sm" data-action="mark" data-kind="${kind}">${icon('circle-check', 15)} ${isNfse ? 'Marcar NFS-e emitida' : 'Marcar NF-e emitida'}</button>
        </div>
    </div>`;
}

function buildModal() {
    modal = createModal({
        id: 'fiscal-visit',
        title: 'Copiloto Fiscal',
        icon: 'receipt-text',
        size: 'xl',
        body: html`
            <div class="tabs fiscal-tabs" role="tablist">
                <button type="button" class="tab" role="tab" data-tab="nfse">${icon('wrench', 15)} NFS-e Santos (mão de obra)</button>
                <button type="button" class="tab" role="tab" data-tab="nfe">${icon('package', 15)} NF-e 55 (peças)</button>
                <button type="button" class="tab" role="tab" data-tab="tomador">${icon('user', 15)} Dados do tomador</button>
            </div>

            <section class="fiscal-panel stack stack-4" data-panel="nfse">
                <div class="callout callout-info">
                    ${icon('building-2', 16)}
                    <div><div class="callout-title">Prefeitura de Santos · LC 116/03 subitem 14.01</div>
                    <div class="text-muted">CNAE 4520-0/01 — manutenção e reparação mecânica de veículos</div></div>
                </div>
                <div class="field">
                    <div class="row row-between">
                        <span class="field-label">Discriminação dos serviços (placa, modelo, km e itens)</span>
                        <button type="button" class="btn btn-primary btn-sm" data-copy="nfse-desc">${icon('copy', 15)} Copiar discriminação</button>
                    </div>
                    <textarea class="textarea fiscal-textarea" data-field="nfse-desc" readonly rows="8"></textarea>
                </div>
                <div class="row row-wrap row-gap-1">
                    <span class="text-xs text-subtle">Cópia rápida:</span>
                    <button type="button" class="chip" data-copy="tomador">${icon('copy', 12)} Tomador</button>
                    <button type="button" class="chip" data-copy="cpf-raw">${icon('copy', 12)} CPF só números</button>
                    <button type="button" class="chip" data-copy="cep-raw">${icon('copy', 12)} CEP</button>
                    <button type="button" class="chip" data-copy="address">${icon('copy', 12)} Endereço em 1 linha</button>
                    <button type="button" class="chip" data-copy="serv-val">${icon('copy', 12)} Valor da mão de obra</button>
                </div>
                <div class="stack stack-2">
                    <span class="eyebrow">Serviços desta OS</span>
                    <div class="fiscal-services" data-field="nfse-items"></div>
                </div>
                ${statusRow('nfse')}
            </section>

            <section class="fiscal-panel stack stack-4" data-panel="nfe" hidden>
                <div class="callout callout-warning">
                    ${icon('package', 16)}
                    <div><div class="callout-title">Sefaz-SP · NF-e modelo 55 · comércio varejista de autopeças</div>
                    <div class="text-muted">CNAE 4530-7/03 · CFOP padrão 5.405 (autopeças com ICMS-ST) · CSOSN 500</div></div>
                </div>
                <div class="row row-wrap">
                    <button type="button" class="btn btn-primary btn-sm" data-copy="nfe-summary">${icon('copy', 15)} Copiar lista de peças e valores</button>
                    <button type="button" class="btn btn-secondary btn-sm" data-copy="nfe-tsv">${icon('table', 15)} Copiar tabela TSV (Excel / emissor)</button>
                    <button type="button" class="chip" data-copy="parts-val">${icon('copy', 12)} Total de peças</button>
                    <button type="button" class="chip" data-copy="tomador">${icon('copy', 12)} Destinatário</button>
                </div>
                <div class="table-wrap">
                    <table class="table fiscal-parts-table">
                        <thead><tr>
                            <th class="num">#</th><th>Descrição da peça</th><th class="num">Qtd</th><th class="num">Unitário</th><th class="num">Total</th><th class="td-center">CFOP</th><th>NCM sugerido</th>
                        </tr></thead>
                        <tbody data-field="nfe-items"></tbody>
                    </table>
                </div>
                ${statusRow('nfe')}
            </section>

            <section class="fiscal-panel stack stack-4" data-panel="tomador" hidden>
                <div class="row row-between">
                    <span class="text-sm text-muted">Dados cadastrais do tomador do serviço / destinatário</span>
                    <button type="button" class="btn btn-primary btn-sm" data-copy="tomador">${icon('copy', 15)} Copiar todos os dados</button>
                </div>
                <div class="tomador-grid">
                    ${copyRow('Nome / razão social', 'nome', copyButton('nome'))}
                    ${copyRow('CPF / CNPJ', 'cpf', html`${copyButton('cpf', 'Formatado')}<button type="button" class="btn btn-ghost btn-sm" data-copy="cpf-raw">${icon('copy', 14)} Só números</button>`)}
                    ${copyRow('Telefone / WhatsApp', 'telefone', copyButton('telefone'))}
                    ${copyRow('E-mail', 'email', copyButton('email'))}
                    <div class="tomador-wide">${copyRow('Endereço completo em 1 linha', 'linha', copyButton('linha', 'Copiar 1 linha'))}</div>
                    ${copyRow('Logradouro e número', 'logradouro', copyButton('logradouro'))}
                    ${copyRow('Bairro', 'bairro', copyButton('bairro'))}
                    ${copyRow('Cidade / UF', 'cidade', copyButton('cidade'))}
                    ${copyRow('CEP', 'cep', html`${copyButton('cep')}<button type="button" class="btn btn-ghost btn-sm" data-copy="cep-raw">${icon('copy', 14)} Sem traço</button>`)}
                </div>
            </section>`,
        footer: html`
            <span class="text-xs text-subtle push">CNPJ ${OFICINA.cnpj} · ${OFICINA.cidade} · <span data-field="pending-summary"></span></span>
            <a class="btn btn-ghost" href="#/fiscal" data-modal-close>${icon('list-checks', 16)} Fila de pendências</a>
            <button type="button" class="btn btn-secondary" data-modal-close>Fechar</button>`,
    });

    on(modal.el, 'click', '[data-tab]', (e, btn) => switchTab(btn.dataset.tab));
    on(modal.el, 'click', '[data-copy]', (e, btn) => copyAction(btn.dataset.copy));
    on(modal.el, 'click', '[data-copy-field]', (e, btn) => {
        const value = modal.el.querySelector(`[data-tomador="${btn.dataset.copyField}"]`)?.textContent.trim();
        if (value && value !== '—') copyText(value, `Copiado: ${value}`);
        else toast('Campo vazio.', 'error');
    });
    on(modal.el, 'click', '[data-action="mark"]', (e, btn) => markEmitted(btn.dataset.kind, btn));
    state.watch('nfStats', (stats) => {
        if (modal) $('[data-field="pending-summary"]', modal.el).textContent = `${stats?.pending_visits_count || 0} visita(s) com emissão pendente`;
    });
}

function switchTab(tab) {
    for (const btn of $$('[data-tab]', modal.el)) btn.setAttribute('aria-selected', btn.dataset.tab === tab ? 'true' : 'false');
    for (const panel of $$('[data-panel]', modal.el)) panel.hidden = panel.dataset.panel !== tab;
}

function setStatusTag(kind, status, number, noItems) {
    const tag = $(`[data-field="${kind}-status"]`, modal.el);
    const label = kind === 'nfse' ? 'NFS-e' : 'NF-e';
    if (status === 'emitida') {
        tag.className = 'tag tag-success';
        tag.textContent = `Emitida (${label} ${number || 's/n'})`;
    } else if (noItems) {
        tag.className = 'tag';
        tag.textContent = kind === 'nfse' ? 'Não aplicável (sem serviços)' : 'Não aplicável (sem peças)';
    } else {
        tag.className = 'tag tag-warning';
        tag.textContent = 'Pendente';
    }
}

/** O backend devolve o tomador com chaves em inglês (name, cpf, address_single_line…);
 *  versões antigas usavam português (nome, cpf_formatado, endereco_linha_unica…). Aceita ambas. */
function normalizeTomador(data) {
    const t = data.tomador || {};
    const street = [t.address, t.address_num].filter(Boolean).join(', ') + (t.address_compl ? ` (${t.address_compl})` : '');
    return {
        nome: t.nome || t.name || data.client_name || '',
        cpf: t.cpf_formatado || t.cpf || t.cpf_cnpj || '',
        cpfRaw: String(t.cpf_raw || t.cpf_cnpj || t.cpf || '').replace(/\D/g, ''),
        telefone: t.telefone || t.phone || '',
        email: t.email || '',
        linha: t.endereco_linha_unica || t.address_single_line || '',
        logradouro: t.logradouro_numero || street,
        bairro: t.bairro || t.neighborhood || '',
        cidade: `${t.municipio || t.city || 'Santos'} / ${t.uf || 'SP'}`,
        cep: t.cep || '',
        cepRaw: String(t.cep_raw || t.cep || '').replace(/\D/g, ''),
        resumo: t.resumo || t.text || (typeof data.dados_tomador === 'string' ? data.dados_tomador : ''),
    };
}

/** "31/10/2026" → "2026-10-31" (valor aceito por <input type="date">). */
function toDateInput(value) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(String(value || '').trim());
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    return /^\d{4}-\d{2}-\d{2}$/.test(String(value || '')) ? value : todayIso();
}

function renderData(data) {
    const plateDisp = data.plate_display || data.plate || 'Oficina';
    modal.setTitle(`Copiloto Fiscal · ${formatPlate(plateDisp)} (${data.car_model || 'Veículo'})`);
    const tomador = normalizeTomador(data);
    const client = tomador.nome || 'Cliente';
    modal.setSubtitle(`${data.visit_num ? `Visita #${data.visit_num}` : 'OS'} · ${data.entry_date || '—'} · Tomador: ${client}`);

    const nf = data.nf_control || {};
    const nfse = data.nfse || {};
    $('[data-field="nfse-desc"]', modal.el).value = nfse.discriminacao_completa || data.discriminacao_nfse || '';
    $('[data-field="nfse-total"]', modal.el).textContent = formatMoney(nfse.valor_servicos || data.valor_servicos || 0);
    const nfseNum = nfse.numero_nfse || nf.nf_servico_num || '';
    $('[data-field="nfse-number"]', modal.el).value = nfseNum;
    $('[data-field="nfse-date"]', modal.el).value = toDateInput(nfse.data_emissao || nf.data_emissao_servico);
    setStatusTag('nfse', nfse.status || nf.status_servico, nfseNum, nfse.valor_servicos === 0 && !(nfse.itens_servico || []).length);

    const services = nfse.itens_servico || [];
    render($('[data-field="nfse-items"]', modal.el), services.length
        ? html`<div class="list card">${services.map((s) => html`<div class="list-item"><span class="list-item-row">
            <span>${s.desc}${s.qty > 1 ? ` (${s.qty}x)` : ''}</span><strong class="num">${formatMoney(s.total || s.unit_price || 0)}</strong>
        </span></div>`)}</div>`
        : html`<p class="text-sm text-muted">Nenhum item de mão de obra / serviço nesta OS.</p>`);

    const nfe = data.nfe || {};
    $('[data-field="nfe-total"]', modal.el).textContent = formatMoney(nfe.valor_pecas || data.valor_pecas || 0);
    const nfeNum = nfe.numero_nfe || nf.nf_pecas_num || '';
    $('[data-field="nfe-number"]', modal.el).value = nfeNum;
    $('[data-field="nfe-date"]', modal.el).value = toDateInput(nfe.data_emissao || nf.data_emissao_pecas);
    setStatusTag('nfe', nfe.status || nf.status_pecas, nfeNum, nfe.valor_pecas === 0 && !(nfe.itens_pecas || []).length);

    const parts = nfe.itens_pecas || data.pecas_nfe || [];
    render($('[data-field="nfe-items"]', modal.el), parts.length
        ? html`${parts.map((p, i) => html`<tr>
            <td class="num text-subtle">${i + 1}</td>
            <td class="fw-medium">${p.desc}</td>
            <td class="num">${p.qty || 1}</td>
            <td class="num">${formatMoney(p.unit_price || 0)}</td>
            <td class="num fw-semibold">${formatMoney(p.total || 0)}</td>
            <td class="td-center"><span class="tag tag-warning num">${p.cfop_display || p.cfop || '5.405'}</span></td>
            <td><span class="tag mono" title="${p.ncm_desc || ''}">${p.ncm_sugerido || '8708.29.99'}</span></td>
        </tr>`)}`
        : html`<tr><td colspan="7" class="text-center text-muted">Nenhuma peça faturável nesta OS.</td></tr>`);

    const set = (key, value) => { $(`[data-tomador="${key}"]`, modal.el).textContent = value || '—'; };
    for (const key of ['nome', 'cpf', 'telefone', 'email', 'linha', 'logradouro', 'bairro', 'cidade', 'cep']) set(key, tomador[key]);
}

function copyAction(kind) {
    const d = fiscal.data || {};
    const t = normalizeTomador(d);
    switch (kind) {
        case 'nfse-desc': copyText($('[data-field="nfse-desc"]', modal.el).value, 'Discriminação da NFS-e copiada.'); break;
        case 'tomador': copyText(t.resumo, 'Dados do tomador copiados.'); break;
        case 'cpf-raw': copyText(t.cpfRaw, `CPF/CNPJ copiado: ${t.cpfRaw}`); break;
        case 'cep-raw': copyText(t.cepRaw, `CEP copiado: ${t.cepRaw}`); break;
        case 'address': copyText(t.linha, 'Endereço em 1 linha copiado.'); break;
        case 'serv-val': { const v = (Number(d.nfse?.valor_servicos) || 0).toFixed(2).replace('.', ','); copyText(v, `Valor da mão de obra copiado: R$ ${v}`); break; }
        case 'parts-val': { const v = (Number(d.nfe?.valor_pecas) || 0).toFixed(2).replace('.', ','); copyText(v, `Total de peças copiado: R$ ${v}`); break; }
        case 'nfe-summary': copyText(d.nfe?.resumo_texto, 'Lista de peças e valores copiada.'); break;
        case 'nfe-tsv': copyText(d.nfe?.tabela_tsv, 'Tabela TSV copiada — pronta para colar no Excel ou no emissor.'); break;
        default: break;
    }
}

async function markEmitted(kind, btn) {
    if (!fiscal.plate && !fiscal.filePath) {
        toast('Nenhuma visita selecionada.', 'error');
        return;
    }
    const number = $(`[data-field="${kind}-number"]`, modal.el).value.trim();
    const date = $(`[data-field="${kind}-date"]`, modal.el).value.trim();
    const body = { file_path: fiscal.filePath, plate: fiscal.plate, visit_num: fiscal.visitNum };
    if (kind === 'nfse') Object.assign(body, { status_servico: 'emitida', nf_servico_num: number, data_emissao_servico: date });
    else Object.assign(body, { status_pecas: 'emitida', nf_pecas_num: number, data_emissao_pecas: date });

    const restore = busy(btn, 'Salvando…');
    try {
        await api.post('/api/nf/status', body, { errorMessage: 'Erro ao salvar o status' });
        const label = kind === 'nfse' ? 'NFS-e' : 'NF-e';
        toast(`${label} ${number || 's/n'} marcada como emitida.`, 'success');
        setStatusTag(kind, 'emitida', number, false);
        refresh('nfStats');
        loadQueue();
        emit('fiscal:changed', { plate: fiscal.plate });
    } catch (err) {
        toast(`Erro ao salvar o status: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

/** Abre o Copiloto de uma visita. Sem arquivo nem placa, vai para a fila (#/fiscal). */
export async function openFiscalVisit({ filePath = '', plate = '', visitNum = null, tab = 'nfse' } = {}) {
    if (!filePath && !plate) {
        navigate('/fiscal');
        return;
    }
    if (!modal) buildModal();
    fiscal = { filePath: filePath || '', plate: plate || '', visitNum: visitNum || null, data: null };
    switchTab(tab);
    modal.setTitle('Carregando Copiloto Fiscal…');
    modal.setSubtitle('Buscando dados da OS e do cliente');
    $('[data-field="nfse-desc"]', modal.el).value = 'Carregando…';
    render($('[data-field="nfse-items"]', modal.el), html`<div class="skeleton skeleton-text"></div>`);
    render($('[data-field="nfe-items"]', modal.el), html`<tr><td colspan="7"><div class="skeleton skeleton-text"></div></td></tr>`);
    modal.open({ focus: false });

    try {
        const data = await api.get('/api/nf/data', { params: { file_path: fiscal.filePath, plate: fiscal.plate, visit_num: fiscal.visitNum }, errorMessage: 'Erro ao carregar dados fiscais' });
        fiscal.data = data;
        fiscal.plate = data.plate || fiscal.plate;
        fiscal.filePath = data.file_path || fiscal.filePath;
        fiscal.visitNum = data.visit_num || fiscal.visitNum;
        renderData(data);
        refresh('nfStats');
    } catch (err) {
        toast(`Erro ao abrir o Copiloto Fiscal: ${err.message}`, 'error');
        modal.close();
    }
}

export default {
    id: 'fiscal',
    title: 'Copiloto Fiscal',
    mount,
    enter() {
        loadQueue();
    },
    leave() {
        queueController?.abort();
    },
};
