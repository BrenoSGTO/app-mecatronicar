/**
 * Copiloto Fiscal.
 *
 * - Tela #/fiscal: fila de notas pendentes (GET /api/nf/queue). Ponto de entrada:
 *   filtros, ordenação por data, avisos de dados faltando e exportação em lote.
 * - Modal por visita (GET /api/nf/data): fluxo vertical na ordem em que a nota é
 *   digitada no emissor (Tomador -> NFS-e de serviços -> NF-e de peças), com cópia em
 *   1 clique, atalhos de teclado e registro/estorno da emissão (POST /api/nf/status).
 * - Exportação em lote para a contabilidade (GET /api/nf/export_batch).
 *
 * Dono na Fase 2: T10.
 *
 *   openFiscalVisit({ filePath, plate, visitNum, tab })   // `tab` é aceito por compatibilidade
 */
import { api, apiUrl, isAbort } from '../api.js';
import { state, emit } from '../state.js';
import { refresh } from '../data.js';
import { navigate } from '../router.js';
import { html, render, on, $, $$, debounce, busy, setVar } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { copyText } from '../ui/clipboard.js';
import { formatMoney, formatPlate, isoToBr, plural, todayIso } from '../lib/format.js';

const OFICINA = { cnpj: '05.961.672/0001-87' };

const QUEUE_FILTERS = [
    { value: 'pending', label: 'Pendentes', stat: 'pending_visits_count' },
    { value: 'pending_servico', label: 'NFS-e a emitir', stat: 'pending_servicos_count' },
    { value: 'pending_pecas', label: 'NF-e a emitir', stat: 'pending_pecas_count' },
    { value: 'emitidas', label: 'Emitidas', stat: 'emitted_count' },
    { value: 'all', label: 'Todas', stat: 'total_visits' },
];

const SORTS = {
    oldest: { label: 'Mais antigas primeiro', cmp: (a, b) => dateKey(a).localeCompare(dateKey(b)) },
    newest: { label: 'Mais recentes primeiro', cmp: (a, b) => dateKey(b).localeCompare(dateKey(a)) },
    value: { label: 'Maior valor primeiro', cmp: (a, b) => (b.valor_total || 0) - (a.valor_total || 0) },
};

const LEAVE_MS = 220;

function dateKey(item) {
    return `${item.entry_date_sort || '9999-99-99'}|${item.plate_clean || ''}|${String(item.visit_num || '').padStart(5, '0')}`;
}

function itemKey(item) {
    return `${item.file_path || item.plate_clean || item.plate}|${item.visit_num || ''}`;
}

function digits(value) {
    return String(value || '').replace(/\D/g, '');
}

function moneyPlain(value) {
    return (Number(value) || 0).toFixed(2).replace('.', ',');
}

/** "2026-11-11" -> "11/11/2026"; outros formatos passam direto. */
function displayDate(value) {
    if (!value) return '';
    return /^\d{4}-\d{2}-\d{2}/.test(String(value)) ? isoToBr(value) : String(value);
}

/** "11/11/2026" -> "2026-11-11" (valor de <input type="date">); sem data = hoje. */
function toDateInput(value) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(String(value || '').trim());
    if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    return /^\d{4}-\d{2}-\d{2}$/.test(String(value || '')) ? value : todayIso();
}

/** Problemas que a secretária precisa resolver antes de emitir (fila e modal usam a mesma regra). */
function cpfProblem(cpf) {
    const n = digits(cpf).length;
    if (!n) return 'missing';
    return n === 11 || n === 14 ? null : 'incomplete';
}

function queueIssues(item) {
    const issues = [];
    const cpf = cpfProblem(item.cpf);
    if (cpf === 'missing') issues.push({ tone: 'danger', label: 'Sem CPF/CNPJ' });
    else if (cpf === 'incomplete') issues.push({ tone: 'warning', label: 'CPF/CNPJ incompleto' });
    const zeroed = (item.status_servico === 'pendente' && !(item.valor_servico > 0))
        || (item.status_pecas === 'pendente' && !(item.valor_pecas > 0));
    if (zeroed) issues.push({ tone: 'warning', label: 'Valor zerado' });
    return issues;
}

/* ================================================================== */
/* Tela: fila de pendências                                            */
/* ================================================================== */

let root = null;
let queueFilter = 'pending';
let sortMode = 'oldest';
let onlyIssues = false;
let queueItems = [];
let queueLoaded = false;
let queueDirty = false;
let queueController = null;
let queueSeq = 0;

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Copiloto Fiscal</h1>
                <p class="page-subtitle">Visitas com nota a emitir: NFS-e de Santos (mão de obra, item 14.01) e NF-e modelo 55 (peças).</p>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-secondary" data-action="export">${icon('file-down', 16)} Exportar lote</button>
                <button type="button" class="btn btn-secondary btn-icon" data-action="refresh" aria-label="Atualizar fila" data-tooltip="Atualizar fila">${icon('refresh-cw', 16)}</button>
            </div>
        </header>

        <div class="stat-grid fiscal-kpis">
            <div class="stat"><span class="stat-label">${icon('receipt-text', 14)} Visitas pendentes</span><span class="stat-value num" data-kpi="visits">-</span><span class="stat-sub" data-kpi="visits-sub">&nbsp;</span></div>
            <div class="stat"><span class="stat-label">${icon('wrench', 14)} NFS-e a emitir (mão de obra)</span><span class="stat-value num" data-kpi="services">-</span><span class="stat-sub" data-kpi="services-sub">&nbsp;</span></div>
            <div class="stat"><span class="stat-label">${icon('package', 14)} NF-e a emitir (peças)</span><span class="stat-value num" data-kpi="parts">-</span><span class="stat-sub" data-kpi="parts-sub">&nbsp;</span></div>
            <div class="stat"><span class="stat-label">${icon('circle-check', 14)} Visitas com nota emitida</span><span class="stat-value num" data-kpi="emitted">-</span><span class="stat-sub" data-kpi="emitted-sub">&nbsp;</span></div>
        </div>

        <div class="fiscal-toolbar">
            <div class="filter-pills" role="group" aria-label="Filtro da fila" data-field="filters"></div>
            <div class="fiscal-toolbar-tools">
                <div class="input-group fiscal-search">
                    ${icon('search', 16, 'input-icon')}
                    <input type="search" class="input" data-field="search" placeholder="Placa, cliente ou carro" aria-label="Filtrar a fila por placa, cliente ou carro" autocomplete="off">
                </div>
                <select class="select fiscal-sort" data-field="sort" aria-label="Ordenar a fila">
                    ${Object.entries(SORTS).map(([value, s]) => html`<option value="${value}"${value === sortMode ? ' selected' : ''}>${s.label}</option>`)}
                </select>
            </div>
        </div>

        <div data-field="queue" aria-live="polite"></div>`);

    renderFilters();

    const searchSoon = debounce(() => loadQueue(), 250);
    on(root, 'input', '[data-field="search"]', () => searchSoon());
    on(root, 'change', '[data-field="sort"]', (e, select) => {
        sortMode = select.value;
        renderQueue();
    });
    on(root, 'click', '[data-filter]', (e, btn) => {
        queueFilter = btn.dataset.filter;
        renderFilters();
        loadQueue();
    });
    on(root, 'click', '[data-toggle="issues"]', () => {
        onlyIssues = !onlyIssues;
        renderFilters();
        renderQueue();
    });
    on(root, 'click', '[data-action]', (e, btn) => {
        if (btn.dataset.action === 'refresh') {
            loadQueue();
            refresh('nfStats');
        } else if (btn.dataset.action === 'export') {
            openExport();
        }
    });
    on(root, 'click', '.fiscal-row[data-index]', (e, row) => openFromQueue(Number(row.dataset.index)));
    on(root, 'keydown', '.fiscal-row[data-index]', (e, row) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openFromQueue(Number(row.dataset.index));
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const rows = $$('.fiscal-row[data-index]:not(.is-leaving)', root);
            rows[rows.indexOf(row) + (e.key === 'ArrowDown' ? 1 : -1)]?.focus();
        }
    });

    const reloadSoon = debounce(() => {
        if (root.hidden || !queueLoaded) return;
        if (modal?.isOpen()) queueDirty = true;
        else loadQueue({ animate: true, quiet: true });
    }, 400);
    state.watch('nfStats', (stats) => {
        renderKpis(stats);
        renderFilters();
        reloadSoon();
    });
    on(root, 'click', '[data-action="retry"]', () => loadQueue());
}

function renderKpis(stats) {
    if (!root || !stats) return;
    const set = (key, text) => { $(`[data-kpi="${key}"]`, root).textContent = text; };
    set('visits', String(stats.pending_visits_count || 0));
    set('visits-sub', `de ${plural(stats.total_visits || 0, 'visita')} no histórico`);
    set('services', formatMoney(stats.total_pending_services_val || 0));
    set('services-sub', plural(stats.pending_servicos_count || 0, 'nota'));
    set('parts', formatMoney(stats.total_pending_pecas_val || 0));
    set('parts-sub', plural(stats.pending_pecas_count || 0, 'nota'));
    set('emitted', String(stats.emitted_count || 0));
    set('emitted-sub', 'com ao menos uma nota registrada');
}

function renderFilters() {
    if (!root) return;
    const stats = state.get('nfStats') || {};
    const issuesCount = queueItems.filter((i) => queueIssues(i).length).length;
    render($('[data-field="filters"]', root), html`
        ${QUEUE_FILTERS.map((f) => html`<button type="button" class="filter-pill${f.value === queueFilter ? ' is-active' : ''}" data-filter="${f.value}" aria-pressed="${f.value === queueFilter}">${f.label}${stats[f.stat] !== undefined ? html` <span class="count">${stats[f.stat]}</span>` : ''}</button>`)}
        <button type="button" class="filter-pill${onlyIssues ? ' is-active' : ''}" data-toggle="issues" aria-pressed="${onlyIssues}">${icon('triangle-alert', 14)} Dados faltando <span class="count">${issuesCount}</span></button>`);
}

function queueQuery() {
    return ($('[data-field="search"]', root)?.value || '').trim();
}

async function loadQueue({ animate = false, quiet = false } = {}) {
    if (!root) return;
    const listEl = $('[data-field="queue"]', root);
    queueController?.abort();
    queueController = new AbortController();
    const seq = ++queueSeq;
    if (!quiet && !listEl.children.length) {
        render(listEl, html`<div class="card fiscal-list"><div class="skeleton-stack fiscal-skeleton">${[1, 2, 3, 4, 5].map(() => html`<div class="skeleton skeleton-block"></div>`)}</div></div>`);
    }
    try {
        const data = await api.get('/api/nf/queue', {
            params: { filter: queueFilter, q: queueQuery() },
            signal: queueController.signal,
            errorMessage: 'Erro ao carregar a fila fiscal',
        });
        if (seq !== queueSeq) return;
        if (data.stats) state.set('nfStats', data.stats);
        const items = data.items || data.queue || [];
        if (animate) await animateRemoved(items);
        queueItems = items;
        queueLoaded = true;
        renderFilters();
        renderQueue();
    } catch (err) {
        if (isAbort(err)) return;
        render(listEl, html`<div class="callout callout-danger">${icon('circle-alert', 16)}<div><div class="callout-title">Não foi possível carregar a fila fiscal</div>${err.message}<div class="fiscal-retry"><button type="button" class="btn btn-secondary btn-sm" data-action="retry">${icon('refresh-cw', 14)} Tentar de novo</button></div></div></div>`);
    }
}

/** Faz sumirem (com animação discreta) as linhas que saíram da fila e espera o fim. */
async function animateRemoved(nextItems) {
    const keep = new Set(nextItems.map(itemKey));
    const leaving = $$('.fiscal-row[data-key]', root).filter((row) => !keep.has(row.dataset.key));
    if (!leaving.length) return;
    for (const row of leaving) setVar(row, 'height', `${row.offsetHeight}px`);
    void root.offsetWidth;
    for (const row of leaving) row.classList.add('is-leaving');
    await new Promise((resolve) => setTimeout(resolve, LEAVE_MS));
}

function visibleItems() {
    const list = onlyIssues ? queueItems.filter((i) => queueIssues(i).length) : queueItems.slice();
    return list.sort(SORTS[sortMode].cmp);
}

function noteCell(status, number, value) {
    if (status === 'emitida') {
        return html`<span class="tag tag-success">${icon('circle-check', 12)} Emitida${number ? html` <span class="num">nº ${number}</span>` : ''}</span><span class="num fiscal-value">${formatMoney(value)}</span>`;
    }
    if (status === 'pendente') {
        return html`<span class="tag tag-warning">Pendente</span><span class="num fiscal-value">${formatMoney(value)}</span>`;
    }
    return html`<span class="text-subtle text-sm">Não se aplica</span>`;
}

function renderQueue() {
    if (!root) return;
    const listEl = $('[data-field="queue"]', root);
    const items = visibleItems();
    listEl._items = items;
    if (!items.length) {
        const allDone = queueFilter === 'pending' && !queueQuery() && !onlyIssues;
        render(listEl, html`<div class="card"><div class="empty-state${allDone ? ' empty-state-success' : ''}">
            <span class="empty-state-icon">${icon(allDone ? 'circle-check' : 'inbox', 20)}</span>
            <div class="empty-state-title">${allDone ? 'Nenhuma nota pendente' : 'Nenhuma nota neste filtro'}</div>
            <div class="empty-state-text">${allDone ? 'Todas as visitas já têm as notas registradas como emitidas.' : 'Mude o filtro ou limpe a busca para ver outras visitas.'}</div>
        </div></div>`);
        return;
    }
    render(listEl, html`<div class="card fiscal-list" role="list">
        <div class="fiscal-row fiscal-row-head" aria-hidden="true">
            <span>Entrada</span><span>Veículo e cliente</span><span>NFS-e · mão de obra</span><span>NF-e · peças</span><span>Avisos</span><span></span>
        </div>
        ${items.map((item, i) => {
            const issues = queueIssues(item);
            return html`<div class="fiscal-row" role="listitem" tabindex="0" data-index="${i}" data-key="${itemKey(item)}" aria-label="Abrir ${formatPlate(item.plate_display || item.plate)}, ${item.client_name || 'cliente'}">
                <span class="fiscal-cell-date num">${displayDate(item.entry_date) || '-'}</span>
                <div class="fiscal-cell-vehicle">
                    <div class="row">
                        <span class="plate-chip">${formatPlate(item.plate_display || item.plate)}</span>
                        <span class="fw-medium truncate">${item.car_model || 'Veículo'}</span>
                    </div>
                    <div class="text-sm text-muted truncate">${item.client_name || 'Cliente não informado'}${item.visit_num ? html` · <span class="num">visita nº ${item.visit_num}</span>` : ''}</div>
                </div>
                <div class="fiscal-cell-note">${noteCell(item.status_servico, item.nf_servico_num, item.valor_servico)}</div>
                <div class="fiscal-cell-note">${noteCell(item.status_pecas, item.nf_pecas_num, item.valor_pecas)}</div>
                <div class="fiscal-cell-issues">${issues.map((x) => html`<span class="tag tag-${x.tone}">${icon('triangle-alert', 12)} ${x.label}</span>`)}</div>
                <span class="fiscal-cell-go">${icon('chevron-right', 16)}</span>
            </div>`;
        })}
    </div>
    <p class="fiscal-count text-sm text-subtle">${plural(items.length, 'visita')} · ${SORTS[sortMode].label.toLowerCase()}</p>`);
}

function openFromQueue(index) {
    const item = $('[data-field="queue"]', root)._items?.[index];
    if (!item) return;
    openFiscalVisit({ filePath: item.file_path, plate: item.plate, visitNum: item.visit_num, fromQueue: true });
}

/* ================================================================== */
/* Modal: Copiloto de uma visita                                      */
/* ================================================================== */

let modal = null;
let fiscal = { filePath: '', plate: '', visitNum: null, data: null, fromQueue: false, key: '', lastIndex: 0 };
let flow = { copy: {}, steps: [], cursor: 0 };
let loadSeq = 0;

/** O backend devolve o tomador com chaves em inglês; versões antigas usavam português. Aceita ambas. */
function normalizeTomador(data) {
    const t = data.tomador || {};
    const number = t.address_num ? `, ${t.address_num}` : '';
    const compl = t.address_compl ? ` (${t.address_compl})` : '';
    const street = t.address ? `${t.address}${number}${compl}` : '';
    const cpfRaw = digits(t.cpf_raw || t.cpf_cnpj || t.cpf);
    const cepRaw = digits(t.cep_raw || t.cep);
    return {
        nome: (t.nome || t.name || data.client_name || '').trim(),
        cpf: (t.cpf_formatado || t.cpf || t.cpf_cnpj || '').trim(),
        cpfRaw,
        telefone: (t.telefone || t.phone || '').trim(),
        email: (t.email || '').trim(),
        endereco: (t.logradouro_numero || street).trim(),
        bairro: (t.bairro || t.neighborhood || '').trim(),
        cidade: `${t.municipio || t.city || 'Santos'} / ${t.uf || 'SP'}`,
        cep: (t.cep || '').trim(),
        cepRaw,
        resumo: t.resumo || t.text || (typeof data.dados_tomador === 'string' ? data.dados_tomador : ''),
    };
}

function tomadorFields(t) {
    const cpfProb = cpfProblem(t.cpfRaw);
    const cepProb = t.cepRaw && t.cepRaw.length !== 8 ? 'incomplete' : null;
    return [
        { id: 'cpf', label: 'CPF / CNPJ', value: t.cpf || t.cpfRaw, required: true, mono: true, problem: cpfProb === 'incomplete' ? 'Confira os dígitos' : null, alt: { id: 'cpf-raw', label: 'Só números', value: t.cpfRaw } },
        { id: 'nome', label: 'Nome / razão social', value: t.nome, required: true },
        { id: 'endereco', label: 'Endereço (rua e número)', value: t.endereco, required: true },
        { id: 'bairro', label: 'Bairro', value: t.bairro, required: true },
        { id: 'cep', label: 'CEP', value: t.cep, required: true, mono: true, problem: cepProb ? 'Confira os dígitos' : null, alt: { id: 'cep-raw', label: 'Sem traço', value: t.cepRaw } },
        { id: 'email', label: 'E-mail', value: t.email },
        { id: 'cidade', label: 'Município / UF', value: t.cidade },
        { id: 'telefone', label: 'Telefone', value: t.telefone, mono: true },
    ];
}

/** Transforma a resposta da API no que a tela mostra e no que cada botão copia. */
function buildModel(data) {
    const t = normalizeTomador(data);
    const fields = tomadorFields(t);
    const nf = data.nf_control || {};
    const nfse = data.nfse || {};
    const nfe = data.nfe || {};
    const services = nfse.itens_servico || [];
    const parts = nfe.itens_pecas || data.pecas_nfe || [];
    const nfseTotal = Number(nfse.valor_servicos ?? data.valor_servicos) || 0;
    const nfeTotal = Number(nfe.valor_pecas ?? data.valor_pecas) || 0;
    const nfseStatus = nfse.status || nf.status_servico || 'pendente';
    const nfeStatus = nfe.status || nf.status_pecas || 'pendente';
    return {
        t,
        fields,
        missing: fields.filter((f) => f.required && !f.value),
        doubtful: fields.filter((f) => f.value && f.problem),
        nfse: {
            status: nfseStatus,
            applicable: nfseStatus !== 'nao_se_aplica' || services.length > 0 || nfseTotal > 0,
            number: nfse.numero_nfse || nf.nf_servico_num || '',
            date: nfse.data_emissao && nfseStatus === 'emitida' ? nfse.data_emissao : '',
            total: nfseTotal,
            text: nfse.discriminacao_completa || data.discriminacao_nfse || '',
            items: services,
        },
        nfe: {
            status: nfeStatus,
            applicable: nfeStatus !== 'nao_se_aplica' || parts.length > 0 || nfeTotal > 0,
            number: nfe.numero_nfe || nf.nf_pecas_num || '',
            date: nfe.data_emissao && nfeStatus === 'emitida' ? nfe.data_emissao : '',
            total: nfeTotal,
            summary: nfe.resumo_texto || '',
            tsv: nfe.tabela_tsv || '',
            items: parts,
        },
    };
}

/** Tudo que pode ser copiado (id -> texto e rótulo) e a ordem em que a secretária digita. */
function buildFlow(model) {
    const copy = {};
    const steps = [];
    for (const f of model.fields) {
        copy[f.id] = { label: f.label, text: f.value };
        if (f.alt) copy[f.alt.id] = { label: `${f.label} (${f.alt.label.toLowerCase()})`, text: f.alt.value };
        if (f.value && ['cpf', 'nome', 'endereco', 'bairro', 'cep', 'email'].includes(f.id)) steps.push(f.id);
    }
    copy['all-tomador'] = { label: 'Dados do tomador', text: model.t.resumo };
    if (model.nfse.applicable) {
        copy['nfse-desc'] = { label: 'Discriminação da NFS-e', text: model.nfse.text };
        copy['nfse-total'] = { label: 'Total da mão de obra', text: moneyPlain(model.nfse.total) };
        copy['all-nfse'] = { label: 'NFS-e completa', text: model.nfse.text };
        if (model.nfse.text) steps.push('nfse-desc');
        if (model.nfse.total > 0) steps.push('nfse-total');
    }
    if (model.nfe.applicable) {
        copy['nfe-tsv'] = { label: 'Tabela de peças', text: model.nfe.tsv };
        copy['nfe-total'] = { label: 'Total das peças', text: moneyPlain(model.nfe.total) };
        copy['all-nfe'] = { label: 'NF-e completa', text: model.nfe.summary };
        if (model.nfe.items.length) steps.push('nfe-tsv');
        if (model.nfe.total > 0) steps.push('nfe-total');
    }
    return { copy, steps, cursor: 0 };
}

function fieldRow(f) {
    const empty = !f.value;
    return html`<div class="copy-field${empty ? (f.required ? ' is-missing' : ' is-empty') : ''}" data-step="${f.id}">
        <button type="button" class="copy-field-main" data-copy="${f.id}"${empty ? ' disabled' : ''}>
            <span class="copy-field-label">${f.label}
                ${empty && f.required ? html`<span class="tag tag-danger">${icon('triangle-alert', 12)} Faltando</span>` : ''}
                ${!empty && f.problem ? html`<span class="tag tag-warning">${icon('triangle-alert', 12)} ${f.problem}</span>` : ''}
            </span>
            <span class="copy-field-value${f.mono ? ' num' : ''}">${empty ? 'Não informado' : f.value}</span>
            <span class="copy-field-icon">${icon('copy', 16)}<span class="copy-field-done">${icon('check', 16)} Copiado</span></span>
        </button>
        ${f.alt && f.alt.value ? html`<button type="button" class="btn btn-ghost btn-sm" data-copy="${f.alt.id}">${f.alt.label}</button>` : ''}
    </div>`;
}

function statusTag(block, kind) {
    const label = kind === 'nfse' ? 'NFS-e' : 'NF-e';
    if (block.status === 'emitida') return html`<span class="tag tag-success tag-lg">${icon('circle-check', 14)} ${label} emitida${block.number ? html` · nº ${block.number}` : ''}</span>`;
    if (!block.applicable) return html`<span class="tag tag-lg">Não se aplica</span>`;
    return html`<span class="tag tag-warning tag-lg">${label} pendente</span>`;
}

function emitBar(block, kind) {
    const isNfse = kind === 'nfse';
    const label = isNfse ? 'NFS-e' : 'NF-e';
    if (block.status === 'emitida') {
        return html`<div class="fiscal-emit is-done">
            <span class="fiscal-emit-text">${icon('circle-check', 18)} <span>${label} ${block.number ? html`nº <strong class="num">${block.number}</strong> ` : ''}registrada como emitida${block.date ? html` em <span class="num">${displayDate(block.date)}</span>` : ''}.</span></span>
            <button type="button" class="btn btn-secondary btn-sm" data-action="unmark" data-kind="${kind}">${icon('undo-2', 14)} Desfazer</button>
        </div>`;
    }
    return html`<form class="fiscal-emit" data-action="mark-form" data-kind="${kind}" novalidate>
        <span class="fiscal-emit-text">${icon('receipt-text', 18)} <span>Depois de emitir no ${isNfse ? 'portal da Prefeitura' : 'emissor de NF-e'}, registre aqui:</span></span>
        <label class="field fiscal-emit-field"><span class="field-label">Nº da ${label}</span>
            <input class="input input-mono" name="number" inputmode="numeric" autocomplete="off" placeholder="Ex.: 1234" data-field="${kind}-number"></label>
        <label class="field fiscal-emit-field"><span class="field-label">Data da emissão</span>
            <input class="input" type="date" name="date" value="${todayIso()}" data-field="${kind}-date"></label>
        <button type="submit" class="btn btn-secondary" data-action="mark" data-kind="${kind}">${icon('circle-check', 16)} Marcar como emitida</button>
    </form>`;
}

function emptyBlock(text) {
    return html`<div class="fiscal-block-empty text-muted">${icon('minus', 16)} ${text}</div>`;
}

function renderFlow(model) {
    const { nfse, nfe } = model;
    const tomadorOk = !model.missing.length && !model.doubtful.length;
    const jump = (id, num, label, tag) => html`<button type="button" class="fiscal-jump" data-jump="${id}"><span class="fiscal-jump-num">${num}</span><span class="fiscal-jump-label">${label}</span>${tag}</button>`;
    const stepTag = (block) => (block.status === 'emitida'
        ? html`<span class="tag tag-success">${icon('check', 12)} Emitida</span>`
        : block.applicable ? html`<span class="tag tag-warning">Pendente</span>` : html`<span class="tag">Não se aplica</span>`);

    return html`
        <nav class="fiscal-jumps" aria-label="Etapas da nota">
            ${jump('tomador', 1, 'Tomador', tomadorOk
                ? html`<span class="tag tag-success">${icon('check', 12)} Completo</span>`
                : html`<span class="tag tag-${model.missing.length ? 'danger' : 'warning'}">${icon('triangle-alert', 12)} ${model.missing.length ? `${model.missing.length} faltando` : 'Conferir'}</span>`)}
            ${jump('nfse', 2, 'NFS-e · serviços', stepTag(nfse))}
            ${jump('nfe', 3, 'NF-e · peças', stepTag(nfe))}
        </nav>

        <div class="fiscal-flow">
            <section class="fiscal-block" id="fiscal-tomador" data-block="tomador" aria-labelledby="fiscal-tomador-title">
                <header class="fiscal-block-head">
                    <span class="fiscal-block-num">1</span>
                    <div class="fiscal-block-heading">
                        <h3 class="fiscal-block-title" id="fiscal-tomador-title">Tomador do serviço</h3>
                        <p class="fiscal-block-sub">Dados do cliente, na ordem do emissor. Clique no campo para copiar.</p>
                    </div>
                    <button type="button" class="btn btn-secondary btn-sm" data-copy="all-tomador">${icon('copy', 14)} Copiar tudo</button>
                </header>
                ${model.missing.length ? html`<div class="callout callout-danger">${icon('triangle-alert', 16)}<div><div class="callout-title">Faltam dados do cliente: ${model.missing.map((f) => f.label).join(', ')}</div>Peça ao cliente e complete na ficha (Editar OS). Os demais campos continuam disponíveis para copiar.</div></div>` : ''}
                <div class="copy-grid">${model.fields.map(fieldRow)}</div>
            </section>

            <section class="fiscal-block" id="fiscal-nfse" data-block="nfse" aria-labelledby="fiscal-nfse-title">
                <header class="fiscal-block-head">
                    <span class="fiscal-block-num">2</span>
                    <div class="fiscal-block-heading">
                        <h3 class="fiscal-block-title" id="fiscal-nfse-title">NFS-e · serviços (mão de obra)</h3>
                        <p class="fiscal-block-sub">Prefeitura de Santos · LC 116/03 item 14.01 · CNAE 4520-0/01</p>
                    </div>
                    ${statusTag(nfse, 'nfse')}
                    ${nfse.applicable ? html`<button type="button" class="btn btn-secondary btn-sm" data-copy="all-nfse">${icon('copy', 14)} Copiar tudo</button>` : ''}
                </header>
                ${nfse.applicable ? html`
                    <div class="fiscal-split">
                        <div class="copy-block" data-step="nfse-desc">
                            <div class="row row-between">
                                <span class="field-label">Discriminação dos serviços</span>
                                <button type="button" class="btn btn-ghost btn-sm" data-copy="nfse-desc">${icon('copy', 14)} Copiar discriminação</button>
                            </div>
                            <textarea class="textarea fiscal-textarea" readonly rows="9" aria-label="Discriminação dos serviços">${nfse.text}</textarea>
                        </div>
                        <div class="stack stack-4">
                            <div class="fiscal-total" data-step="nfse-total">
                                <div class="fiscal-total-info"><span class="fiscal-total-label">Total de mão de obra</span><span class="fiscal-total-value num">${formatMoney(nfse.total)}</span></div>
                                <button type="button" class="btn btn-secondary btn-sm" data-copy="nfse-total">${icon('copy', 14)} Copiar valor</button>
                            </div>
                            ${nfse.total > 0 ? '' : html`<div class="callout callout-warning">${icon('triangle-alert', 16)}<div>O valor de mão de obra está zerado. Confira a planilha antes de emitir.</div></div>`}
                            ${nfse.items.length ? html`<div class="table-wrap"><table class="table table-compact">
                                <thead><tr><th>Serviço</th><th class="num">Valor</th></tr></thead>
                                <tbody>${nfse.items.map((s) => html`<tr><td>${s.desc}${Number(s.qty) > 1 ? ` (${s.qty}x)` : ''}</td><td class="num">${formatMoney(s.total || s.unit_price || 0)}</td></tr>`)}</tbody>
                            </table></div>` : ''}
                        </div>
                    </div>
                    ${emitBar(nfse, 'nfse')}` : emptyBlock('Esta visita não tem mão de obra a faturar.')}
            </section>

            <section class="fiscal-block" id="fiscal-nfe" data-block="nfe" aria-labelledby="fiscal-nfe-title">
                <header class="fiscal-block-head">
                    <span class="fiscal-block-num">3</span>
                    <div class="fiscal-block-heading">
                        <h3 class="fiscal-block-title" id="fiscal-nfe-title">NF-e · peças (modelo 55)</h3>
                        <p class="fiscal-block-sub">Comércio varejista de autopeças · CFOP padrão 5.405 (ICMS-ST) · CSOSN 500</p>
                    </div>
                    ${statusTag(nfe, 'nfe')}
                    ${nfe.applicable ? html`<button type="button" class="btn btn-secondary btn-sm" data-copy="all-nfe">${icon('copy', 14)} Copiar tudo</button>` : ''}
                </header>
                ${nfe.applicable ? html`
                    <div class="table-wrap" data-step="nfe-tsv">
                        <table class="table fiscal-parts-table">
                            <thead><tr><th class="num">#</th><th>Descrição da peça</th><th class="num">Qtd</th><th class="num">Unitário</th><th class="num">Total</th><th>NCM sugerido</th><th>CFOP</th></tr></thead>
                            <tbody>${nfe.items.length ? nfe.items.map((p, i) => html`<tr>
                                <td class="num text-subtle">${i + 1}</td>
                                <td class="fw-medium">${p.desc}</td>
                                <td class="num">${p.qty || 1}</td>
                                <td class="num">${formatMoney(p.unit_price || 0)}</td>
                                <td class="num fw-semibold">${formatMoney(p.total || 0)}</td>
                                <td><span class="tag mono" title="${p.ncm_desc || ''}">${p.ncm_sugerido || '8708.29.99'}</span></td>
                                <td><span class="tag num">${p.cfop_display || p.cfop || '5.405'}</span></td>
                            </tr>`) : html`<tr><td colspan="7" class="text-center text-muted">Nenhuma peça detalhada nesta visita.</td></tr>`}</tbody>
                            <tfoot><tr><td colspan="4" class="text-right fw-medium">Total de peças</td><td class="num fw-semibold">${formatMoney(nfe.total)}</td><td colspan="2"></td></tr></tfoot>
                        </table>
                    </div>
                    <div class="fiscal-nfe-actions">
                        <p class="text-sm text-muted fiscal-hint">${icon('info', 14)} NCM e CFOP são sugestões automáticas por palavra-chave. Confira antes de emitir.</p>
                        <div class="row">
                            <button type="button" class="btn btn-ghost btn-sm" data-copy="nfe-tsv">${icon('table', 14)} Copiar tabela</button>
                            <div class="fiscal-total fiscal-total-inline" data-step="nfe-total">
                                <span class="fiscal-total-label">Total</span><span class="fiscal-total-value num">${formatMoney(nfe.total)}</span>
                                <button type="button" class="btn btn-secondary btn-sm" data-copy="nfe-total">${icon('copy', 14)} Copiar valor</button>
                            </div>
                        </div>
                    </div>
                    ${nfe.total > 0 ? '' : html`<div class="callout callout-warning">${icon('triangle-alert', 16)}<div>O total de peças está zerado. Confira a planilha antes de emitir.</div></div>`}
                    ${emitBar(nfe, 'nfe')}` : emptyBlock('Esta visita não tem peças a faturar.')}
            </section>
        </div>`;
}

function footerMarkup() {
    return html`
        <span class="fiscal-hints text-xs text-subtle push">
            <span data-field="next-hint"></span>
            <span class="fiscal-keys"><span class="kbd">N</span> copia o próximo campo <span class="kbd">P</span> volta <span class="kbd">Esc</span> fecha</span>
        </span>
        <button type="button" class="btn btn-secondary" data-action="next-visit" hidden>Próxima da fila ${icon('arrow-right', 16)}</button>
        <button type="button" class="btn btn-secondary" data-modal-close>Fechar</button>`;
}

function buildModal() {
    modal = createModal({
        id: 'fiscal-visit',
        title: 'Copiloto fiscal',
        icon: 'receipt-text',
        size: 'xl',
        bodyClass: 'modal-body-flush fiscal-modal-body',
        body: '',
        footer: footerMarkup(),
        onClose: () => {
            if (!queueDirty) return;
            queueDirty = false;
            setTimeout(() => loadQueue({ animate: true, quiet: true }), 120);
        },
    });

    on(modal.el, 'click', '[data-copy]', (e, btn) => copyStep(btn.dataset.copy, btn));
    on(modal.el, 'click', '[data-jump]', (e, btn) => {
        const section = $(`#fiscal-${btn.dataset.jump}`, modal.el);
        section?.scrollIntoView({ block: 'start', behavior: motionOk() ? 'smooth' : 'auto' });
    });
    on(modal.el, 'click', '[data-action="unmark"]', (e, btn) => saveStatus(btn.dataset.kind, false, btn));
    on(modal.el, 'click', '[data-action="retry"]', () => loadVisit());
    on(modal.el, 'click', '[data-action="next-visit"]', () => openNext());
    on(modal.el, 'submit', '[data-action="mark-form"]', (e, form) => {
        e.preventDefault();
        saveStatus(form.dataset.kind, true, $('button[type="submit"]', form), form);
    });

    document.addEventListener('keydown', (event) => {
        if (!modal?.isOpen() || event.ctrlKey || event.altKey || event.metaKey || event.defaultPrevented) return;
        if (event.target instanceof Element && event.target.closest('input, textarea, select, [contenteditable]')) return;
        const key = event.key.toLowerCase();
        if (key === 'n') {
            event.preventDefault();
            copyStep(flow.steps[flow.cursor]);
        } else if (key === 'p') {
            event.preventDefault();
            setCursor(flow.cursor - 1);
        }
    });
}

function motionOk() {
    return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** Realça o próximo campo a copiar e avisa no rodapé. */
function setCursor(index) {
    if (!modal) return;
    flow.cursor = Math.max(0, Math.min(index, flow.steps.length));
    for (const el of $$('.is-next', modal.el)) el.classList.remove('is-next');
    const id = flow.steps[flow.cursor];
    const hint = $('[data-field="next-hint"]', modal.el);
    if (!id) {
        hint.textContent = flow.steps.length ? 'Todos os campos copiados.' : '';
        return;
    }
    const target = $(`[data-step="${id}"]`, modal.el);
    target?.classList.add('is-next');
    target?.scrollIntoView({ block: 'nearest', behavior: motionOk() ? 'smooth' : 'auto' });
    hint.textContent = `Próximo: ${flow.copy[id]?.label || ''}`;
}

const copiedTimers = new WeakMap();

function flashCopied(btn) {
    if (!btn || !btn.isConnected) return;
    clearTimeout(copiedTimers.get(btn));
    btn.classList.add('is-copied');
    let original = null;
    if (btn.classList.contains('btn')) {
        original = [...btn.childNodes];
        render(btn, html`${icon('check', 14)} Copiado`);
    }
    copiedTimers.set(btn, setTimeout(() => {
        btn.classList.remove('is-copied');
        if (original !== null && btn.isConnected) btn.replaceChildren(...original);
    }, 1600));
}

async function copyStep(id, trigger = null) {
    const entry = flow.copy[id];
    if (!entry) return;
    if (!entry.text) {
        toast(`${entry.label}: não há nada para copiar.`, 'error');
        return;
    }
    const ok = await copyText(entry.text, `${entry.label} copiado.`);
    if (!ok) return;
    const buttons = trigger ? [trigger] : $$(`[data-copy="${id}"]`, modal.el);
    buttons.forEach(flashCopied);
    const index = flow.steps.indexOf(id);
    if (index >= 0) setCursor(index + 1);
}

function setLoading() {
    modal.setBody(html`<div class="fiscal-flow"><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-block"></div><div class="skeleton skeleton-block"></div></div>`);
}

async function loadVisit({ keepScroll = false } = {}) {
    const seq = ++loadSeq;
    const scrollTop = modal.body.scrollTop;
    try {
        const data = await api.get('/api/nf/data', {
            params: { file_path: fiscal.filePath, plate: fiscal.plate, visit_num: fiscal.visitNum },
            errorMessage: 'Erro ao carregar dados fiscais',
        });
        if (seq !== loadSeq) return;
        fiscal.data = data;
        fiscal.plate = data.plate || fiscal.plate;
        fiscal.filePath = data.copilot?.file_path || data.file_path || fiscal.filePath;
        fiscal.visitNum = data.visit_num || fiscal.visitNum;
        fiscal.key = itemKey({ file_path: fiscal.filePath, plate: fiscal.plate, visit_num: fiscal.visitNum });
        renderVisit(data, keepScroll ? scrollTop : 0, keepScroll);
    } catch (err) {
        if (seq !== loadSeq) return;
        modal.setBody(html`<div class="fiscal-flow"><div class="callout callout-danger">${icon('circle-alert', 16)}<div><div class="callout-title">Não foi possível abrir o copiloto desta visita</div>${err.message}<div class="fiscal-retry"><button type="button" class="btn btn-secondary btn-sm" data-action="retry">${icon('refresh-cw', 14)} Tentar de novo</button></div></div></div></div>`);
    }
}

function renderVisit(data, scrollTop = 0, keepCursor = false) {
    const model = buildModel(data);
    const previousCursor = flow.cursor;
    flow = buildFlow(model);
    if (keepCursor) flow.cursor = Math.min(previousCursor, flow.steps.length);
    modal.setTitle(`${formatPlate(data.plate_display || data.plate || 'Oficina')} · ${data.car_model || 'Veículo'}`);
    modal.setSubtitle(`${data.visit_num ? `Visita nº ${data.visit_num}` : 'OS'} · entrada ${displayDate(data.entry_date) || '-'} · ${model.t.nome || 'Cliente não informado'}`);
    modal.setBody(renderFlow(model));
    modal.body.scrollTop = scrollTop;
    updateNextButton();
    setCursor(keepCursor ? flow.cursor : 0);
}

function nextQueueItem() {
    if (!fiscal.fromQueue) return null;
    const items = $('[data-field="queue"]', root)?._items || [];
    const index = items.findIndex((i) => itemKey(i) === fiscal.key);
    if (index >= 0) {
        fiscal.lastIndex = index;
        return items[index + 1] || null;
    }
    return items[fiscal.lastIndex] || null;
}

function updateNextButton() {
    const btn = $('[data-action="next-visit"]', modal.el);
    const next = nextQueueItem();
    btn.hidden = !next;
}

function openNext() {
    const next = nextQueueItem();
    if (!next) return;
    openFiscalVisit({ filePath: next.file_path, plate: next.plate, visitNum: next.visit_num, fromQueue: true });
}

/** Marca (ou desfaz) a emissão de um dos blocos e atualiza fila, selo da barra lateral e modal. */
async function saveStatus(kind, emitted, button, form = null) {
    const isNfse = kind === 'nfse';
    const label = isNfse ? 'NFS-e' : 'NF-e';
    const data = fiscal.data || {};
    let number = '';
    let date = '';
    if (emitted) {
        number = ($('input[name="number"]', form)?.value || '').trim();
        date = ($('input[name="date"]', form)?.value || '').trim() || todayIso();
        if (!number) {
            toast(`Informe o número da ${label} para registrar a emissão.`, 'error');
            $('input[name="number"]', form)?.focus();
            return;
        }
    }
    const body = { file_path: fiscal.filePath, plate: fiscal.plate, visit_num: fiscal.visitNum };
    if (isNfse) {
        Object.assign(body, {
            status_servico: emitted ? 'emitida' : 'pendente',
            nf_servico_num: number,
            data_emissao_servico: emitted ? date : '',
            valor_servico: Number(data.nfse?.valor_servicos ?? data.valor_servicos) || 0,
        });
    } else {
        Object.assign(body, {
            status_pecas: emitted ? 'emitida' : 'pendente',
            nf_pecas_num: number,
            data_emissao_pecas: emitted ? date : '',
            valor_pecas: Number(data.nfe?.valor_pecas ?? data.valor_pecas) || 0,
        });
    }
    const restore = busy(button, emitted ? 'Salvando...' : 'Desfazendo...');
    try {
        await api.post('/api/nf/status', body, { errorMessage: 'Erro ao salvar o status' });
        toast(emitted ? `${label} nº ${number} registrada como emitida.` : `Registro da ${label} desfeito: voltou para pendente.`, 'success');
        queueDirty = true;
        await Promise.all([loadVisit({ keepScroll: true }), refresh('nfStats')]);
        emit('fiscal:changed', { plate: fiscal.plate });
    } catch (err) {
        restore();
        toast(`Não foi possível salvar: ${err.message}`, 'error');
    }
}

/**
 * Abre o Copiloto de uma visita. Sem arquivo nem placa, vai para a fila (#/fiscal).
 * `tab` (nfse|nfe|tomador) é aceito só por compatibilidade: o fluxo agora é um só, vertical.
 */
export function openFiscalVisit({ filePath = '', plate = '', visitNum = null, tab = '', fromQueue = false } = {}) {
    if (!filePath && !plate) {
        navigate('/fiscal');
        return;
    }
    if (!modal) buildModal();
    fiscal = { filePath: filePath || '', plate: plate || '', visitNum: visitNum || null, data: null, fromQueue, key: itemKey({ file_path: filePath, plate, visit_num: visitNum }), lastIndex: fiscal.lastIndex || 0 };
    modal.setTitle('Carregando copiloto...');
    modal.setSubtitle('Buscando dados da OS e do cliente');
    $('[data-action="next-visit"]', modal.el).hidden = true;
    $('[data-field="next-hint"]', modal.el).textContent = '';
    setLoading();
    modal.open({ focus: false });
    if (tab === 'nfse' || tab === 'nfe') {
        const wanted = tab;
        loadVisit().then(() => $(`#fiscal-${wanted}`, modal.el)?.scrollIntoView({ block: 'start' }));
    } else {
        loadVisit();
    }
}

/* ================================================================== */
/* Modal: exportação em lote para a contabilidade                      */
/* ================================================================== */

let exportModal = null;
let exportFormat = 'csv';
let exportSeq = 0;

function exportBody() {
    return html`
        <div class="stack stack-4">
            <p class="text-sm text-muted">Gera uma planilha (ou texto) com placa, cliente, CPF, valores e número das notas, para enviar à contabilidade.</p>
            <label class="field"><span class="field-label">Quais notas</span>
                <select class="select" data-field="export-scope">
                    ${QUEUE_FILTERS.map((f) => html`<option value="${f.value}"${f.value === queueFilter ? ' selected' : ''}>${f.label}</option>`)}
                </select></label>
            <div class="field"><span class="field-label">Formato</span>
                <div class="segmented" role="group" aria-label="Formato do arquivo">
                    <button type="button" class="segmented-item${exportFormat === 'csv' ? ' is-active' : ''}" data-format="csv" aria-pressed="${exportFormat === 'csv'}">${icon('file-spreadsheet', 14)} Planilha (CSV para Excel)</button>
                    <button type="button" class="segmented-item${exportFormat === 'txt' ? ' is-active' : ''}" data-format="txt" aria-pressed="${exportFormat === 'txt'}">${icon('file-text', 14)} Texto (TXT)</button>
                </div>
            </div>
            <div class="fiscal-export-summary" data-field="export-summary" aria-live="polite"></div>
            <div data-field="export-result" aria-live="polite"></div>
        </div>`;
}

function buildExportModal() {
    exportModal = createModal({
        id: 'fiscal-export',
        title: 'Exportar lote para a contabilidade',
        icon: 'file-down',
        size: 'md',
        body: exportBody(),
        footer: html`
            <button type="button" class="btn btn-secondary" data-modal-close>Fechar</button>
            <button type="button" class="btn btn-primary" data-action="export-download">${icon('download', 16)} Baixar arquivo</button>`,
    });
    on(exportModal.el, 'change', '[data-field="export-scope"]', () => {
        render($('[data-field="export-result"]', exportModal.el), '');
        loadExportSummary();
    });
    on(exportModal.el, 'click', '[data-format]', (e, btn) => {
        exportFormat = btn.dataset.format;
        $$('[data-format]', exportModal.el).forEach((b) => {
            b.classList.toggle('is-active', b === btn);
            b.setAttribute('aria-pressed', String(b === btn));
        });
        render($('[data-field="export-result"]', exportModal.el), '');
    });
    on(exportModal.el, 'click', '[data-action="export-download"]', (e, btn) => downloadExport(btn));
}

function exportScope() {
    return $('[data-field="export-scope"]', exportModal.el).value;
}

async function loadExportSummary() {
    const box = $('[data-field="export-summary"]', exportModal.el);
    const seq = ++exportSeq;
    render(box, html`<div class="skeleton skeleton-block"></div>`);
    try {
        const data = await api.get('/api/nf/queue', { params: { filter: exportScope() }, errorMessage: 'Erro ao calcular o lote' });
        if (seq !== exportSeq) return;
        const items = data.items || data.queue || [];
        const noCpf = items.filter((i) => cpfProblem(i.cpf)).length;
        const services = items.filter((i) => i.status_servico !== 'nao_se_aplica').reduce((s, i) => s + (i.valor_servico || 0), 0);
        const parts = items.filter((i) => i.status_pecas !== 'nao_se_aplica').reduce((s, i) => s + (i.valor_pecas || 0), 0);
        render(box, html`
            <div class="fiscal-export-stats">
                <div class="stat"><span class="stat-label">Visitas</span><span class="stat-value stat-value-sm num">${items.length}</span></div>
                <div class="stat"><span class="stat-label">Mão de obra</span><span class="stat-value stat-value-sm num">${formatMoney(services)}</span></div>
                <div class="stat"><span class="stat-label">Peças</span><span class="stat-value stat-value-sm num">${formatMoney(parts)}</span></div>
            </div>
            ${items.length === 0 ? html`<div class="callout callout-warning">${icon('triangle-alert', 16)}<div>Não há notas neste filtro. O arquivo sairia vazio.</div></div>` : ''}
            ${noCpf ? html`<div class="callout callout-warning">${icon('triangle-alert', 16)}<div>${plural(noCpf, 'visita')} sem CPF/CNPJ completo. A contabilidade vai precisar desses dados.</div></div>` : ''}`);
    } catch (err) {
        if (seq !== exportSeq) return;
        render(box, html`<div class="callout callout-danger">${icon('circle-alert', 16)}<div>${err.message}</div></div>`);
    }
}

async function downloadExport(button) {
    const scope = exportScope();
    const scopeLabel = QUEUE_FILTERS.find((f) => f.value === scope)?.label || scope;
    const result = $('[data-field="export-result"]', exportModal.el);
    const restore = busy(button, 'Gerando...');
    try {
        const res = await fetch(apiUrl('/api/nf/export_batch', { filter: scope, format: exportFormat }), { cache: 'no-store' });
        if (!res.ok) throw new Error(`O servidor retornou erro ${res.status}.`);
        const text = await res.text();
        const bom = exportFormat === 'csv' && !text.startsWith('﻿') ? '﻿' : '';
        const mime = exportFormat === 'csv' ? 'text/csv;charset=utf-8' : 'text/plain;charset=utf-8';
        const slug = { pending: 'pendentes', pending_servico: 'nfse-a-emitir', pending_pecas: 'nfe-a-emitir', emitidas: 'emitidas', all: 'todas' }[scope] || scope;
        const filename = `MecatroniCar_Notas_${slug}_${todayIso()}.${exportFormat}`;
        const url = URL.createObjectURL(new Blob([bom + text], { type: mime }));
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.hidden = true;
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 10000);
        const count = exportFormat === 'csv'
            ? Math.max(0, text.split(/\r?\n/).filter((line) => line.trim()).length - 1)
            : (text.match(/^\d+\. /gm) || []).length;
        render(result, html`<div class="callout callout-success">${icon('circle-check', 16)}<div><div class="callout-title">Arquivo gerado: ${plural(count, 'visita')} (${scopeLabel.toLowerCase()})</div><span class="mono">${filename}</span><br>O Edge salvou o arquivo na pasta de downloads. ${exportFormat === 'csv' ? 'Abra no Excel: os campos são separados por ponto e vírgula.' : ''}</div></div>`);
        toast(`Exportação pronta: ${plural(count, 'visita')} em ${filename}.`, 'success');
    } catch (err) {
        render(result, html`<div class="callout callout-danger">${icon('circle-alert', 16)}<div><div class="callout-title">Não foi possível exportar</div>${err.message}</div></div>`);
        toast(`Falha na exportação: ${err.message}`, 'error');
    } finally {
        restore();
    }
}

function openExport() {
    if (!exportModal) buildExportModal();
    const select = $('[data-field="export-scope"]', exportModal.el);
    select.value = queueFilter;
    render($('[data-field="export-result"]', exportModal.el), '');
    exportModal.open();
    loadExportSummary();
}

export default {
    id: 'fiscal',
    title: 'Copiloto Fiscal',
    mount,
    enter() {
        loadQueue({ quiet: queueLoaded });
    },
    leave() {
        queueController?.abort();
    },
};
