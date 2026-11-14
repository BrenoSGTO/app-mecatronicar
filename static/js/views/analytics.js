/**
 * Analytics (#/analytics): volume de carros, tempo de permanência,
 * médias financeiras, evolução mensal e últimas OS (GET /api/analytics?period=).
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

let root = null;
let period = '30';
let controller = null;

function mount(el) {
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Analytics</h1>
                <p class="page-subtitle">Volume de atendimentos, tempo de permanência e médias financeiras da oficina</p>
            </div>
            <div class="page-actions">
                <div class="segmented" role="group" aria-label="Período">
                    ${PERIODS.map(([value, label]) => html`<button type="button" class="segmented-item${value === period ? ' is-active' : ''}" data-period="${value}">${label}</button>`)}
                </div>
                <button type="button" class="btn btn-secondary btn-icon" data-action="refresh" aria-label="Atualizar" data-tooltip="Atualizar">${icon('refresh-cw', 16)}</button>
                <button type="button" class="btn btn-secondary" data-action="print">${icon('printer', 16)} Imprimir</button>
            </div>
        </header>

        <section class="analytics-section">
            <h2 class="section-title">${icon('car-front', 18)} Volume de carros atendidos</h2>
            <div class="stat-grid">
                <div class="stat"><span class="stat-label">Carros atendidos</span><span class="stat-value" data-v="total-cars">—</span><span class="stat-sub" data-v="total-orders"></span></div>
                <div class="stat"><span class="stat-label">Média por dia</span><span class="stat-value" data-v="cars-day">—</span><span class="stat-sub" data-v="orders-day"></span></div>
                <div class="stat"><span class="stat-label">Média por semana</span><span class="stat-value" data-v="cars-week">—</span><span class="stat-sub" data-v="orders-week"></span></div>
                <div class="stat"><span class="stat-label">Média por mês</span><span class="stat-value" data-v="cars-month">—</span><span class="stat-sub" data-v="orders-month"></span></div>
            </div>
        </section>

        <section class="analytics-section">
            <h2 class="section-title">${icon('timer', 18)} Tempo de permanência na oficina</h2>
            <div class="analytics-two-col">
                <div class="stat">
                    <span class="stat-label">Permanência média (da entrada à entrega)</span>
                    <span class="stat-value" data-v="stay-avg">—</span>
                    <span class="stat-sub" data-v="stay-range"></span>
                    <span class="stat-sub" data-v="stay-count"></span>
                </div>
                <div class="card card-body stack stack-2">
                    <span class="stat-label">Distribuição por faixa</span>
                    <div class="analytics-dist" data-field="distribution"></div>
                </div>
            </div>
        </section>

        <section class="analytics-section">
            <h2 class="section-title">${icon('coins', 18)} Métricas financeiras médias</h2>
            <div class="stat-grid">
                <div class="stat analytics-stat-pecas"><span class="stat-label"><span class="analytics-swatch is-pecas"></span> Autopeças por OS</span><span class="stat-value stat-value-sm" data-v="avg-parts">—</span><span class="stat-sub" data-v="total-parts"></span><span class="stat-sub" data-v="parts-note"></span></div>
                <div class="stat analytics-stat-servicos"><span class="stat-label"><span class="analytics-swatch is-servicos"></span> Mão de obra por OS</span><span class="stat-value stat-value-sm" data-v="avg-labor">—</span><span class="stat-sub" data-v="total-labor"></span><span class="stat-sub" data-v="labor-note"></span></div>
                <div class="stat"><span class="stat-label">Ticket médio por OS</span><span class="stat-value stat-value-sm" data-v="avg-ticket">—</span><span class="stat-sub" data-v="billed-count"></span><span class="stat-sub" data-v="ticket-note"></span></div>
                <div class="stat"><span class="stat-label">Faturamento no período</span><span class="stat-value stat-value-sm" data-v="revenue">—</span><span class="stat-sub" data-v="revenue-ratio"></span><span class="stat-sub" data-v="days-span"></span></div>
            </div>
            <div class="card card-body stack stack-2">
                <div class="row row-between row-wrap">
                    <span class="fw-semibold">Divisão do faturamento: autopeças × mão de obra</span>
                    <span class="analytics-legend">
                        <span><span class="analytics-swatch is-pecas"></span> Autopeças <strong class="num" data-v="ratio-parts">—</strong></span>
                        <span><span class="analytics-swatch is-servicos"></span> Mão de obra <strong class="num" data-v="ratio-labor">—</strong></span>
                    </span>
                </div>
                <div class="analytics-ratio" role="img" data-field="ratio" aria-label="Divisão do faturamento">
                    <span class="analytics-ratio-pecas" data-field="ratio-pecas"></span>
                    <span class="analytics-ratio-servicos" data-field="ratio-servicos"></span>
                </div>
            </div>
        </section>

        <section class="analytics-section">
            <h2 class="section-title">${icon('chart-column', 18)} Faturamento por mês</h2>
            <div class="card card-body">
                <div class="analytics-chart" data-field="chart"></div>
            </div>
        </section>

        <section class="analytics-section">
            <div class="section-header">
                <h2 class="section-title">${icon('list-checks', 18)} Últimos atendimentos no período <span class="badge" data-v="recent-count">0</span></h2>
            </div>
            <div class="table-wrap analytics-table-wrap">
                <table class="table">
                    <thead><tr>
                        <th>Placa</th><th>Cliente</th><th>Modelo</th><th class="num">Entrada</th><th class="num">Saída</th><th>Permanência</th>
                        <th class="num">Autopeças</th><th class="num">Mão de obra</th><th class="num">Total</th>
                    </tr></thead>
                    <tbody data-field="recent"></tbody>
                </table>
            </div>
        </section>`);

    on(root, 'click', '[data-period]', (e, btn) => {
        period = btn.dataset.period;
        $$('[data-period]', root).forEach((b) => b.classList.toggle('is-active', b === btn));
        load();
    });
    on(root, 'click', '[data-action]', (e, btn) => {
        if (btn.dataset.action === 'refresh') load({ announce: true });
        else if (btn.dataset.action === 'print') window.print();
    });
}

function setV(name, text) {
    const el = $(`[data-v="${name}"]`, root);
    if (el) el.textContent = text;
}

function renderData(data) {
    const vol = data.volume || {};
    const stay = data.stay_time || {};
    const fin = data.financials || {};

    setV('total-cars', String(vol.total_cars || 0));
    setV('total-orders', `${plural(vol.total_orders || 0, 'ordem de serviço', 'ordens de serviço')} · ${vol.active_days_count || 0} dias ativos`);
    setV('cars-day', formatDecimal(vol.avg_cars_per_day, 2));
    setV('orders-day', `${formatDecimal(vol.avg_orders_per_day, 2)} OS / dia`);
    setV('cars-week', formatDecimal(vol.avg_cars_per_week, 2));
    setV('orders-week', `${formatDecimal(vol.avg_orders_per_week, 2)} OS / semana`);
    setV('cars-month', formatDecimal(vol.avg_cars_per_month, 2));
    setV('orders-month', `${formatDecimal(vol.avg_orders_per_month, 2)} OS / mês`);

    const measured = stay.stays_measured_count || 0;
    setV('stay-avg', stay.avg_stay_text || `${formatDecimal(stay.avg_stay_days, 1)} dias`);
    setV('stay-range', measured > 0 ? `Mínimo ${stay.min_stay_days === 0 ? '0 dia (mesmo dia)' : `${stay.min_stay_days} d`} · máximo ${stay.max_stay_days} d` : 'Mínimo — · máximo —');
    setV('stay-count', `Medido em ${plural(measured, 'veículo finalizado', 'veículos finalizados')}`);

    const dist = stay.distribution || {};
    const pct = (n) => (measured > 0 ? Math.round((n / measured) * 100) : 0);
    const buckets = [
        ['Mesmo dia', dist.same_day || 0],
        ['1 a 3 dias', dist.days_1_to_3 || 0],
        ['4 a 7 dias (peças / serviço complexo)', dist.days_4_to_7 || 0],
        ['Mais de 7 dias (reparo pesado)', dist.days_over_7 || 0],
    ];
    const distEl = $('[data-field="distribution"]', root);
    render(distEl, html`${buckets.map(([label, n]) => html`<div class="analytics-dist-row">
        <div class="row row-between text-sm"><span>${label}</span><span class="num text-muted">${plural(n, 'carro')} · ${pct(n)}%</span></div>
        <div class="progress"><div class="progress-bar" data-pct="${pct(n)}"></div></div>
    </div>`)}`);
    $$('[data-pct]', distEl).forEach((bar) => setVar(bar, '--value', `${bar.dataset.pct}%`));

    setV('avg-parts', formatMoney(fin.avg_parts_per_order));
    setV('total-parts', `Total em peças: ${formatMoney(fin.total_parts)}`);
    setV('parts-note', `Média por OS com peças: ${formatMoney(fin.avg_parts_per_billed_order)} (${fin.orders_with_parts_count || 0} OS)`);
    setV('avg-labor', formatMoney(fin.avg_labor_per_order));
    setV('total-labor', `Total em serviços: ${formatMoney(fin.total_labor)}`);
    setV('labor-note', `Média por OS com serviço: ${formatMoney(fin.avg_labor_per_billed_order)} (${fin.orders_with_labor_count || 0} OS)`);
    setV('avg-ticket', formatMoney(fin.avg_ticket_order));
    setV('billed-count', `${fin.orders_billed_count || 0} de ${vol.total_orders || 0} OS faturadas`);
    setV('ticket-note', `Ticket médio faturado: ${formatMoney(fin.avg_ticket_billed_order)}`);
    setV('revenue', formatMoney(fin.total_revenue));
    setV('revenue-ratio', `Peças ${formatDecimal(fin.parts_percentage, 1)}% · mão de obra ${formatDecimal(fin.labor_percentage, 1)}%`);
    setV('days-span', `Base: ${data.days_span || 30} dias analisados`);

    const partsPct = fin.parts_percentage || 0;
    const laborPct = fin.labor_percentage || 0;
    setV('ratio-parts', `${formatMoney(fin.total_parts)} (${formatDecimal(partsPct, 1)}%)`);
    setV('ratio-labor', `${formatMoney(fin.total_labor)} (${formatDecimal(laborPct, 1)}%)`);
    setVar($('[data-field="ratio-pecas"]', root), '--value', `${partsPct}%`);
    setVar($('[data-field="ratio-servicos"]', root), '--value', `${laborPct}%`);
    $('[data-field="ratio"]', root).setAttribute('aria-label', `Autopeças ${formatDecimal(partsPct, 1)}%, mão de obra ${formatDecimal(laborPct, 1)}%`);

    renderChart(data.monthly_trend || []);
    renderRecent(data.recent_orders || []);
}

/** Barras simples (uma série): altura proporcional ao faturamento do mês. */
function renderChart(trend) {
    const chart = $('[data-field="chart"]', root);
    if (!trend.length) {
        render(chart, html`<div class="empty-state empty-state-compact"><div class="empty-state-text">Sem histórico mensal para o período selecionado.</div></div>`);
        return;
    }
    const max = Math.max(...trend.map((t) => t.total || 0), 1);
    render(chart, html`<div class="analytics-bars" role="list">${trend.map((t) => {
        const h = Math.max(2, Math.round(((t.total || 0) / max) * 100));
        const tip = `${t.label}: ${plural(t.cars || 0, 'carro')}, ${t.orders || 0} OS · peças ${formatMoney(t.parts)} · mão de obra ${formatMoney(t.labor)} · total ${formatMoney(t.total)}`;
        return html`<div class="analytics-bar" role="listitem" title="${tip}" aria-label="${tip}" data-h="${h}">
            <span class="analytics-bar-value num">${t.total > 0 ? formatMoney(t.total) : '—'}</span>
            <span class="analytics-bar-track"><span class="analytics-bar-fill"></span></span>
            <span class="analytics-bar-label">${t.label}</span>
            <span class="analytics-bar-sub num">${plural(t.cars || 0, 'carro')}</span>
        </div>`;
    })}</div>`);
    $$('[data-h]', chart).forEach((bar) => setVar(bar, '--h', `${bar.dataset.h}%`));
}

function stayTag(order) {
    if (order.stay_days !== null && order.stay_days !== undefined) {
        if (order.stay_days === 0) return html`<span class="tag tag-success">mesmo dia</span>`;
        if (order.stay_days <= 3) return html`<span class="tag tag-info num">${order.stay_days} d</span>`;
        return html`<span class="tag tag-warning num">${order.stay_days} d</span>`;
    }
    return order.exit_date ? html`<span class="tag">Finalizado</span>` : html`<span class="tag">Em aberto</span>`;
}

function renderRecent(orders) {
    setV('recent-count', String(orders.length));
    const tbody = $('[data-field="recent"]', root);
    if (!orders.length) {
        render(tbody, html`<tr><td colspan="9" class="text-center text-muted">Nenhuma ordem de serviço no período.</td></tr>`);
        return;
    }
    render(tbody, html`${orders.map((o) => html`<tr>
        <td><a class="plate-chip" href="#/veiculo/${encodeURIComponent(o.plate || o.plate_display || '')}">${formatPlate(o.plate_display || o.plate || '—')}</a></td>
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

async function load({ announce = false } = {}) {
    controller?.abort();
    controller = new AbortController();
    root.classList.add('is-loading');
    try {
        const resp = await api.get('/api/analytics', { params: { period }, signal: controller.signal, errorMessage: 'Erro ao carregar analytics' });
        if (!resp.data) throw new Error('Resposta sem dados');
        renderData(resp.data);
        if (announce) toast('Métricas atualizadas.', 'success');
    } catch (err) {
        if (isAbort(err)) return;
        toast(`Erro ao carregar analytics: ${err.message}`, 'error');
    } finally {
        root.classList.remove('is-loading');
    }
}

export default {
    id: 'analytics',
    title: 'Analytics',
    mount,
    enter() {
        load();
    },
    leave() {
        controller?.abort();
    },
};
