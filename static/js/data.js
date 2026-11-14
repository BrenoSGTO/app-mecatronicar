/**
 * Dados compartilhados entre telas + polling central.
 *
 * Cada loader busca na API e grava no `state` (que só notifica se mudou).
 * As telas NÃO fazem polling por conta própria: elas observam o state
 * (state.watch) e, depois de uma ação, chamam refresh('<nome>').
 *
 *   import { refresh } from '../data.js';
 *   await api.post('/api/patio/status', {...});
 *   await refresh('patio');
 */
import { api } from './api.js';
import { state } from './state.js';
import { every, runNow } from './scheduler.js';

const loaders = {
    async cars() {
        const data = await api.get('/api/cars', { errorMessage: 'Erro ao carregar veículos' });
        state.set('cars', data.cars || []);
    },

    async patio() {
        const data = await api.get('/api/patio', { errorMessage: 'Erro ao carregar o pátio' });
        const all = data.cars || [];
        const isDelivered = (c) => (c.status || '') === 'Entregue' || (c.status_display || '') === 'Entregue';
        state.set('patio', {
            all,
            active: data.active_cars || all.filter((c) => !isDelivered(c)),
            delivered: data.delivered_cars || all.filter(isDelivered),
            tvUrl: data.tv_url || '',
        });
    },

    async agendaEvents() {
        const data = await api.get('/api/agenda', { errorMessage: 'Erro ao carregar a agenda' });
        state.set('agendaEvents', data.events || []);
    },

    async agendamentos() {
        const data = await api.get('/api/agendamentos', { errorMessage: 'Erro ao carregar agendamentos' });
        state.set('agendamentos', data.agendamentos || []);
    },

    async nfStats() {
        const data = await api.get('/api/nf/pending', { errorMessage: 'Erro ao carregar pendências fiscais' });
        state.set('nfStats', data.stats || {});
    },
};

/** Intervalos de polling (ms). A janela oculta pausa tudo. */
const INTERVALS = {
    cars: 120000,
    patio: 15000,
    agendaEvents: 30000,
    agendamentos: 10000,
    nfStats: 60000,
};

/** Atualiza já um conjunto de dados (após uma ação do usuário). */
export function refresh(...names) {
    return Promise.all(names.map((name) => runNow(`data:${name}`)));
}

export function startDataPolling() {
    for (const [name, loader] of Object.entries(loaders)) {
        every(`data:${name}`, INTERVALS[name], loader);
    }
}
