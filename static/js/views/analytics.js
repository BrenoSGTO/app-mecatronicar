/**
 * Analytics (#/analytics): indicadores, tendência mensal, divisão peças x mão de
 * obra, permanência e últimas OS (GET /api/analytics?period=).
 * Gráficos em SVG próprio (sem biblioteca), cores dos tokens --color-data-*.
 * Dono na Fase 2: T11.
 */
import { api, isAbort } from '../api.js';
import { html, render, on, $, $$, setVar } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { toast } from '../ui/toast.js';
import { formatDecimal, formatMoney, formatPlate, plural } from '../lib/format.js';

const PERIODS = [
    ['30', 'Últimos 30 dias'],
    ['90', 'Últimos 90 dias'],
    ['all', 'Histórico completo'],
];

const CHART_HEIGHT = 280;
const CHART_MARGIN = { top: 14, right: 26, bottom: 34, left: 68 };

let root = null;
let period = '30';
let chartMode = 'bars';   // 'bars' | 'lines'
let data = null;          // resposta da API do período atual
let controller = null;
let resizeObserver = null;
let drawnWidth = 0;

/* ------------------------------------------------------------------ */
/* Formatação                                                          */
/* ------------------------------------------------------------------ */

/** Valor curto para eixos: R$ 850, R$ 12,5 mil, R$ 1,2 mi. */
function moneyShort(value) {
    const n = Math.abs(value);
    const fmt = (v) => v.toLocaleString('pt-BR', { maximumFractionDigits: 1 });
    if (n >= 1_000_000) return `R$ ${fmt(value / 1_000_000)} mi`;
    if (n >= 1_000) return `R$ ${fmt(value / 1_000)} mil`;
    return `R$ ${fmt(value)}`;
}

/** Máximo "redondo" do eixo e o passo entre as linhas de grade. */
function niceScale(maxValue, steps = 4) {
    const raw = Math.max(maxValue, 1) / steps;
    const magnitude = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map((f) => f * magnitude).find((s) => s >= raw) || raw;
    return { step, max: step * Math.ceil(Math.max(maxValue, 1) / step) };
}

/* ------------------------------------------------------------------ */
/* Casca                                                               */
/* ------------------------------------------------------------------ */

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Analytics</h1>
                <p class="page-subtitle">Atendimentos, permanência e faturamento da oficina</p>
            </div>
            <div class="page-actions">
                <div class="segmented" role="group" aria-label="Período">
                    ${PERIODS.map(([value, label]) => html`<button type="button" class="segmented-item${value === period ? ' is-active' : ''}" aria-pressed="${value === period}" data-period="${value}">${label}</button>`)}
                </div>
                <button type="button" class="btn btn-secondary btn-icon" data-action="refresh" aria-label="Atualizar" data-tooltip="Atualizar">${icon('refresh-cw', 16)}</button>
                <button type="button" class="btn btn-secondary" data-action="print">${icon('printer', 16)} Imprimir</button>
            </div>
        </header>
        <div class="analytics-body" data-field="body" aria-live="polite"></div>`);

    on(root, 'click', '[data-period]', (e, btn) => {
        if (btn.dataset.period === period) return;
        period = btn.dataset.period;
        data = null;
        $$('[data-period]', root).forEach((b) => {
            b.classList.toggle('is-active', b === btn);
            b.setAttribute('aria-pressed', String(b === btn));
        });
        load();
    });
    on(root, 'click', '[data-action]', (e, btn) => {
        const action = btn.dataset.action;
        if (action === 'refresh') load({ announce: true });
        else if (action === 'print') window.print();
        else if (action === 'full-history') setPeriod('all');
    });
    on(root, 'click', '[data-chart-mode]', (e, btn) => {
        chartMode = btn.dataset.chartMode;
        $$('[data-chart-mode]', root).forEach((b) => {
            b.classList.toggle('is-active', b === btn);
            b.setAttribute('aria-pressed', String(b === btn));
        });
        drawTrend();
    });
    wireChartHover();
}

function setPeriod(value) {
    const btn = $(`[data-period="${value}"]`, root);
    if (btn) btn.click();
}

/* ------------------------------------------------------------------ */
/* Estados: carregando, vazio, erro                                    */
/* ------------------------------------------------------------------ */

function body() {
    return $('[data-field="body"]', root);
}

function renderSkeleton() {
    render(body(), html`
        <div class="analytics-kpis" aria-hidden="true">${[1, 2, 3, 4, 5, 6].map(() => html`<div class="skeleton skeleton-block analytics-skeleton-kpi"></div>`)}</div>
        <div class="analytics-grid" aria-hidden="true">
            <div class="skeleton skeleton-block analytics-skeleton-chart"></div>
            <div class="skeleton skeleton-block analytics-skeleton-chart"></div>
        </div>
        <div class="skeleton skeleton-block analytics-skeleton-table" aria-hidden="true"></div>
        <span class="sr-only">Carregando indicadores…</span>`);
}

function renderEmpty() {
    const label = PERIODS.find(([value]) => value === period)?.[1]?.toLowerCase() || 'período';
    render(body(), html`<div class="card"><div class="empty-state">
        <span class="empty-state-icon">${icon('chart-column', 20)}</span>
        <div class="empty-state-title">Sem atendimentos no período</div>
        <div class="empty-state-text">Não há ordens de serviço nos ${label}. Escolha um período maior para ver os indicadores.</div>
        ${period !== 'all' ? html`<div class="empty-state-actions"><button type="button" class="btn btn-secondary btn-sm" data-action="full-history">${icon('history', 15)} Ver histórico completo</button></div>` : ''}
    </div></div>`);
}

function renderError(message) {
    render(body(), html`<div class="card"><div class="empty-state">
        <span class="empty-state-icon">${icon('triangle-alert', 20)}</span>
        <div class="empty-state-title">Não foi possível carregar os indicadores</div>
        <div class="empty-state-text">${message}</div>
        <div class="empty-state-actions"><button type="button" class="btn btn-secondary btn-sm" data-action="refresh">${icon('refresh-cw', 15)} Tentar de novo</button></div>
    </div></div>`);
}

/* ------------------------------------------------------------------ */
/* Dados                                                               */
/* ------------------------------------------------------------------ */

function kpi({ label, value, sub, swatch = '' }) {
    return html`<div class="stat">
        <span class="stat-label">${swatch ? html`<span class="analytics-swatch ${swatch}"></span>` : ''}${label}</span>
        <span class="stat-value num">${value}</span>
        <span class="stat-sub">${sub}</span>
    </div>`;
}

function renderData() {
    const vol = data.volume || {};
    const stay = data.stay_time || {};
    const fin = data.financials || {};
    const measured = stay.stays_measured_count || 0;
    const recent = data.recent_orders || [];

    render(body(), html`
        <section class="analytics-kpis" aria-label="Indicadores do período">
            ${kpi({ label: 'Carros atendidos', value: String(vol.total_cars || 0), sub: plural(vol.total_orders || 0, 'ordem de serviço', 'ordens de serviço') })}
            ${kpi({ label: 'Média por mês', value: formatDecimal(vol.avg_cars_per_month, 1), sub: 'carros por mês' })}
            ${kpi({ label: 'Tempo médio no pátio', value: stay.avg_stay_text || `${formatDecimal(stay.avg_stay_days, 1)} dias`, sub: measured > 0 ? `Medido em ${plural(measured, 'veículo')}` : 'Sem entregas medidas' })}
            ${kpi({ label: 'Peças', value: formatMoney(fin.total_parts), sub: `${formatDecimal(fin.parts_percentage, 1)}% do faturamento`, swatch: 'is-pecas' })}
            ${kpi({ label: 'Mão de obra', value: formatMoney(fin.total_labor), sub: `${formatDecimal(fin.labor_percentage, 1)}% do faturamento`, swatch: 'is-servicos' })}
            ${kpi({ label: 'Ticket médio por OS', value: formatMoney(fin.avg_ticket_order), sub: `${fin.orders_billed_count || 0} de ${vol.total_orders || 0} OS faturadas` })}
        </section>

        <div class="analytics-grid">
            <section class="card analytics-card analytics-card-trend">
                <div class="card-header">
                    <span class="card-title">Faturamento por mês</span>
                    <div class="segmented" role="group" aria-label="Tipo de gráfico">
                        <button type="button" class="segmented-item${chartMode === 'bars' ? ' is-active' : ''}" aria-pressed="${chartMode === 'bars'}" data-chart-mode="bars">Barras</button>
                        <button type="button" class="segmented-item${chartMode === 'lines' ? ' is-active' : ''}" aria-pressed="${chartMode === 'lines'}" data-chart-mode="lines">Linhas</button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="analytics-legend">
                        <span><span class="analytics-swatch is-pecas"></span> Peças</span>
                        <span><span class="analytics-swatch is-servicos"></span> Mão de obra</span>
                        <span class="analytics-legend-total">Total no período <strong class="num">${formatMoney(fin.total_revenue)}</strong></span>
                    </div>
                    <div class="analytics-chart" data-field="chart"></div>
                </div>
            </section>

            <section class="card analytics-card">
                <div class="card-header"><span class="card-title">Peças × mão de obra</span></div>
                <div class="card-body analytics-split" data-field="split"></div>
            </section>
        </div>

        <section class="card analytics-card">
            <div class="card-header">
                <span class="card-title">Tempo no pátio</span>
                <span class="text-sm text-muted">${measured > 0 ? `Mínimo ${stay.min_stay_days === 0 ? 'mesmo dia' : `${stay.min_stay_days} d`} · máximo ${stay.max_stay_days} d` : 'Sem entregas no período'}</span>
            </div>
            <div class="card-body analytics-dist" data-field="distribution"></div>
        </section>

        <section class="analytics-recent">
            <div class="section-header">
                <h2 class="section-title">Ordens recentes <span class="badge">${recent.length}</span></h2>
            </div>
            <div class="table-wrap analytics-table-wrap">
                <table class="table">
                    <thead><tr>
                        <th>Placa</th><th>Cliente</th><th>Modelo</th><th class="num">Entrada</th><th class="num">Saída</th><th>Permanência</th>
                        <th class="num">Peças</th><th class="num">Mão de obra</th><th class="num">Total</th>
                    </tr></thead>
                    <tbody data-field="recent"></tbody>
                </table>
            </div>
        </section>`);

    renderSplit(fin);
    renderDistribution(stay, measured);
    renderRecent(recent);
    drawTrend();
}

/* ------------------------------------------------------------------ */
/* Rosca: peças x mão de obra                                          */
/* ------------------------------------------------------------------ */

function renderSplit(fin) {
    const parts = fin.total_parts || 0;
    const labor = fin.total_labor || 0;
    const total = parts + labor;
    const size = 168;
    const c = size / 2;
    const r = 66;
    const circ = 2 * Math.PI * r;
    const gap = total > 0 && parts > 0 && labor > 0 ? 3 : 0;
    const partsLen = total > 0 ? Math.max(0, (parts / total) * circ - gap) : 0;
    const laborLen = total > 0 ? Math.max(0, (labor / total) * circ - gap) : 0;
    const partsPct = total > 0 ? (parts / total) * 100 : 0;
    const laborPct = total > 0 ? (labor / total) * 100 : 0;

    render($('[data-field="split"]', root), html`
        <div class="analytics-donut">
            <svg class="analytics-donut-svg" viewBox="0 0 ${size} ${size}" role="img" aria-label="Peças ${formatDecimal(partsPct, 1)}%, mão de obra ${formatDecimal(laborPct, 1)}%">
                <circle class="donut-track" cx="${c}" cy="${c}" r="${r}"></circle>
                ${partsLen > 0 ? html`<circle class="donut-seg is-pecas" cx="${c}" cy="${c}" r="${r}" stroke-dasharray="${partsLen} ${circ - partsLen}" stroke-dashoffset="${-gap / 2}" transform="rotate(-90 ${c} ${c})"></circle>` : ''}
                ${laborLen > 0 ? html`<circle class="donut-seg is-servicos" cx="${c}" cy="${c}" r="${r}" stroke-dasharray="${laborLen} ${circ - laborLen}" stroke-dashoffset="${-(partsLen + gap * 1.5)}" transform="rotate(-90 ${c} ${c})"></circle>` : ''}
                <text class="donut-value" x="${c}" y="${c - 2}" text-anchor="middle">${moneyShort(total)}</text>
                <text class="donut-caption" x="${c}" y="${c + 16}" text-anchor="middle">faturamento</text>
            </svg>
            <ul class="analytics-split-list">
                <li><span class="analytics-swatch is-pecas"></span><span class="analytics-split-name">Peças</span><span class="num analytics-split-pct">${formatDecimal(partsPct, 1)}%</span><span class="num text-muted analytics-split-val">${formatMoney(parts)}</span></li>
                <li><span class="analytics-swatch is-servicos"></span><span class="analytics-split-name">Mão de obra</span><span class="num analytics-split-pct">${formatDecimal(laborPct, 1)}%</span><span class="num text-muted analytics-split-val">${formatMoney(labor)}</span></li>
            </ul>
        </div>`);
}

/* ------------------------------------------------------------------ */
/* Permanência                                                         */
/* ------------------------------------------------------------------ */

function renderDistribution(stay, measured) {
    const dist = stay.distribution || {};
    const pct = (n) => (measured > 0 ? Math.round((n / measured) * 100) : 0);
    const buckets = [
        ['Mesmo dia', dist.same_day || 0],
        ['1 a 3 dias', dist.days_1_to_3 || 0],
        ['4 a 7 dias', dist.days_4_to_7 || 0],
        ['Mais de 7 dias', dist.days_over_7 || 0],
    ];
    const el = $('[data-field="distribution"]', root);
    render(el, html`${buckets.map(([label, n]) => html`<div class="analytics-dist-item" data-pct="${pct(n)}">
        <div class="analytics-dist-head"><span>${label}</span><span class="num text-muted">${plural(n, 'carro')} · ${pct(n)}%</span></div>
        <div class="progress" role="img" aria-label="${label}: ${pct(n)}%"><div class="progress-bar"></div></div>
    </div>`)}`);
    $$('[data-pct]', el).forEach((item) => setVar($('.progress-bar', item), '--value', `${item.dataset.pct}%`));
}

/* ------------------------------------------------------------------ */
/* Tendência mensal (SVG)                                              */
/* ------------------------------------------------------------------ */

function drawTrend() {
    const chart = $('[data-field="chart"]', root);
    if (!chart || !data) return;
    const trend = data.monthly_trend || [];
    if (!trend.length) {
        render(chart, html`<div class="empty-state empty-state-compact"><div class="empty-state-text">Sem histórico mensal para o período selecionado.</div></div>`);
        return;
    }
    const width = Math.floor(chart.clientWidth);
    if (width < 80) return;   // tela oculta: redesenha quando ficar visível
    drawnWidth = width;

    const m = CHART_MARGIN;
    const iw = width - m.left - m.right;
    const ih = CHART_HEIGHT - m.top - m.bottom;
    const n = trend.length;
    const band = iw / n;
    const peak = Math.max(...trend.map((t) => Math.max(t.total || 0, t.parts || 0, t.labor || 0)), 0);
    const { step, max } = niceScale(peak);
    const ticks = [];
    for (let v = 0; v <= max + step / 2; v += step) ticks.push(v);
    const y = (v) => m.top + ih - (v / max) * ih;
    const cx = (i) => m.left + band * (i + 0.5);
    const barW = Math.min(64, band * 0.52);
    const labelEvery = Math.ceil(n / Math.max(1, Math.floor(iw / 72)));

    const grid = ticks.map((v) => html`<g>
        <line class="chart-grid${v === 0 ? ' is-base' : ''}" x1="${m.left}" x2="${width - m.right}" y1="${y(v)}" y2="${y(v)}"></line>
        <text class="chart-tick" x="${m.left - 10}" y="${y(v)}" text-anchor="end" dominant-baseline="middle">${moneyShort(v)}</text>
    </g>`);

    const bands = trend.map((t, i) => html`<rect class="chart-band" data-band="${i}" x="${m.left + band * i}" y="${m.top}" width="${band}" height="${ih}" rx="6"></rect>`);

    let marks;
    if (chartMode === 'bars') {
        marks = trend.map((t, i) => {
            const parts = t.parts || 0;
            const labor = t.labor || 0;
            const hParts = (parts / max) * ih;
            const hLabor = (labor / max) * ih;
            return html`<g class="chart-marks">
                ${hParts > 0 ? html`<rect class="chart-bar is-pecas" x="${cx(i) - barW / 2}" y="${y(0) - hParts}" width="${barW}" height="${hParts}"></rect>` : ''}
                ${hLabor > 0 ? html`<rect class="chart-bar is-servicos" x="${cx(i) - barW / 2}" y="${y(0) - hParts - hLabor}" width="${barW}" height="${hLabor}" rx="3"></rect>` : ''}
            </g>`;
        });
    } else {
        const path = (key) => trend.map((t, i) => `${i === 0 ? 'M' : 'L'}${cx(i).toFixed(1)} ${y(t[key] || 0).toFixed(1)}`).join(' ');
        marks = [
            html`<path class="chart-line is-pecas" d="${path('parts')}"></path>`,
            html`<path class="chart-line is-servicos" d="${path('labor')}"></path>`,
            ...trend.map((t, i) => html`<g class="chart-marks">
                <circle class="chart-dot is-pecas" cx="${cx(i)}" cy="${y(t.parts || 0)}" r="4"></circle>
                <circle class="chart-dot is-servicos" cx="${cx(i)}" cy="${y(t.labor || 0)}" r="4"></circle>
            </g>`),
        ];
    }

    const labels = trend.map((t, i) => (i % labelEvery === 0
        ? html`<text class="chart-label" x="${cx(i)}" y="${CHART_HEIGHT - 12}" text-anchor="middle">${t.label}</text>` : ''));

    const hits = trend.map((t, i) => html`<rect class="chart-hit" data-i="${i}" tabindex="0" role="img" aria-label="${tipLabel(t)}" x="${m.left + band * i}" y="${m.top}" width="${band}" height="${ih + m.bottom - 6}"></rect>`);

    render(chart, html`
        <svg class="analytics-trend-svg" width="${width}" height="${CHART_HEIGHT}" viewBox="0 0 ${width} ${CHART_HEIGHT}" role="group" aria-label="Faturamento mensal: peças e mão de obra">
            ${grid}${bands}${marks}${labels}${hits}
        </svg>
        <div class="chart-tip" data-field="tip" role="status" hidden></div>`);
}

function tipLabel(t) {
    return `${t.label}: peças ${formatMoney(t.parts)}, mão de obra ${formatMoney(t.labor)}, total ${formatMoney(t.total)}, ${plural(t.cars || 0, 'carro')}`;
}

function wireChartHover() {
    const show = (e, hit) => {
        const chart = $('[data-field="chart"]', root);
        const tip = $('[data-field="tip"]', chart);
        const t = (data?.monthly_trend || [])[Number(hit.dataset.i)];
        if (!tip || !t) return;
        $$('.chart-band', chart).forEach((b) => b.classList.toggle('is-active', b.dataset.band === hit.dataset.i));
        render(tip, html`
            <div class="chart-tip-title">${t.label}</div>
            <div class="chart-tip-row"><span class="analytics-swatch is-pecas"></span><span>Peças</span><span class="num">${formatMoney(t.parts)}</span></div>
            <div class="chart-tip-row"><span class="analytics-swatch is-servicos"></span><span>Mão de obra</span><span class="num">${formatMoney(t.labor)}</span></div>
            <div class="chart-tip-row is-total"><span></span><span>Total</span><span class="num">${formatMoney(t.total)}</span></div>
            <div class="chart-tip-foot">${plural(t.cars || 0, 'carro')} · ${plural(t.orders || 0, 'OS', 'OS')}</div>`);
        tip.hidden = false;
        const bandW = (chart.clientWidth - CHART_MARGIN.left - CHART_MARGIN.right) / data.monthly_trend.length;
        const center = CHART_MARGIN.left + bandW * (Number(hit.dataset.i) + 0.5);
        // Ao lado da coluna (nunca por cima das barras/linhas): à direita na metade esquerda do gráfico
        const gap = Math.min(64, bandW * 0.52) / 2 + 14;
        const onRight = center < chart.clientWidth / 2;
        tip.dataset.side = onRight ? 'right' : 'left';
        setVar(tip, '--x', `${onRight ? center + gap : center - gap}px`);
        setVar(tip, '--y', `${CHART_MARGIN.top + 8}px`);
    };
    const hideTip = () => {
        const chart = $('[data-field="chart"]', root);
        const tip = chart && $('[data-field="tip"]', chart);
        if (tip) tip.hidden = true;
        $$('.chart-band', chart || root).forEach((b) => b.classList.remove('is-active'));
    };
    on(root, 'mouseover', '.chart-hit', show);
    on(root, 'focusin', '.chart-hit', show);
    on(root, 'mouseout', '.chart-hit', hideTip);
    on(root, 'focusout', '.chart-hit', hideTip);
}

/* ------------------------------------------------------------------ */
/* Ordens recentes                                                     */
/* ------------------------------------------------------------------ */

function stayTag(order) {
    if (order.stay_days !== null && order.stay_days !== undefined) {
        if (order.stay_days === 0) return html`<span class="tag tag-success">mesmo dia</span>`;
        if (order.stay_days <= 3) return html`<span class="tag tag-info num">${order.stay_days} d</span>`;
        return html`<span class="tag tag-warning num">${order.stay_days} d</span>`;
    }
    return order.exit_date ? html`<span class="tag">Finalizado</span>` : html`<span class="tag">Em aberto</span>`;
}

function renderRecent(orders) {
    const tbody = $('[data-field="recent"]', root);
    if (!orders.length) {
        render(tbody, html`<tr><td colspan="9" class="text-center text-muted">Nenhuma ordem de serviço no período.</td></tr>`);
        return;
    }
    render(tbody, html`${orders.map((o) => html`<tr>
        <td><a class="plate-chip" href="#/veiculo/${encodeURIComponent(o.plate_clean || o.plate || '')}">${formatPlate(o.plate_display || o.plate || '—')}</a></td>
        <td class="fw-medium">${o.client_name || '—'}</td>
        <td class="truncate">${o.car_model || '—'}</td>
        <td class="num">${o.entry_date || '—'}</td>
        <td class="num">${o.exit_date || '—'}</td>
        <td>${stayTag(o)}</td>
        <td class="num">${o.parts_val > 0 ? formatMoney(o.parts_val) : '—'}</td>
        <td class="num">${o.labor_val > 0 ? formatMoney(o.labor_val) : '—'}</td>
        <td class="num fw-semibold">${o.total_val > 0 ? formatMoney(o.total_val) : '—'}</td>
    </tr>`)}`);
}

/* ------------------------------------------------------------------ */
/* Carregamento                                                        */
/* ------------------------------------------------------------------ */

async function load({ announce = false } = {}) {
    controller?.abort();
    controller = new AbortController();
    const mine = controller;
    if (!data) renderSkeleton();
    root.classList.add('is-loading');
    try {
        const resp = await api.get('/api/analytics', { params: { period }, signal: mine.signal, errorMessage: 'Erro ao carregar analytics' });
        if (!resp.data) throw new Error('Resposta sem dados');
        data = resp.data;
        if (!(data.volume?.total_orders > 0)) renderEmpty();
        else renderData();
        if (announce) toast('Métricas atualizadas.', 'success');
    } catch (err) {
        if (isAbort(err)) return;
        if (!data) renderError(err.message);
        toast(`Erro ao carregar analytics: ${err.message}`, 'error');
    } finally {
        if (controller === mine) root.classList.remove('is-loading');
    }
}

function watchResize() {
    if (resizeObserver || typeof ResizeObserver === 'undefined') return;
    resizeObserver = new ResizeObserver(() => {
        const chart = $('[data-field="chart"]', root);
        if (chart && Math.floor(chart.clientWidth) !== drawnWidth) drawTrend();
    });
    resizeObserver.observe(root);
}

export default {
    id: 'analytics',
    title: 'Analytics',
    mount,
    enter() {
        watchResize();
        load();
    },
    leave() {
        controller?.abort();
    },
};
