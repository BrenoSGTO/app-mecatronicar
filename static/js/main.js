/**
 * MecatroniCar v3 — bootstrap do front-end (ES modules nativos, sem build).
 *
 * Ordem: ícones → casca (layout, busca, configurações) → config do servidor
 * → rotas → polling central. Arquitetura completa: docs/FRONTEND.md
 */
import { api } from './api.js';
import { state, on } from './state.js';
import { defineRoutes, start as startRouter, navigate } from './router.js';
import { startDataPolling } from './data.js';
import { loadIconSprite } from './ui/icon.js';
import { installImageFallback } from './ui/vehicle.js';
import { toast } from './ui/toast.js';
import { $ } from './ui/dom.js';
import { initLayout } from './shell/layout.js';
import { initSearch } from './shell/search.js';
import { initSettings, applyServerConfig } from './shell/settings.js';

import inicioView from './views/inicio.js';
import buscaView from './views/busca.js';
import veiculoView from './views/veiculo.js';
import agendaView from './views/agenda.js';
import fiscalView from './views/fiscal.js';
import analyticsView from './views/analytics.js';
import { openNewOs } from './views/os.js';

async function loadConfig() {
    try {
        const data = await api.get('/api/config', { errorMessage: 'Erro ao ler configurações' });
        state.set('config', data.config || {});
        state.set('appInfo', {
            version: data.version || '',
            localIp: data.local_ip || '',
            tvUrl: data.tv_url || '',
            stats: data.stats || {},
        });
        applyServerConfig(data.config);
    } catch (err) {
        console.error('Erro carregando configuração inicial:', err);
        toast('Não foi possível conectar ao servidor local do MecatroniCar.', 'error');
    }
}

async function boot() {
    await loadIconSprite();
    installImageFallback();

    initLayout();
    initSearch();
    initSettings();

    $('#btn-nova-visita')?.addEventListener('click', () => openNewOs());

    // Depois de salvar uma OS, abre a ficha do veículo atualizada.
    on('os:saved', ({ plate }) => {
        if (plate) navigate(`/veiculo/${encodeURIComponent(plate)}`);
    });

    defineRoutes([
        { path: '/inicio', view: inicioView },
        { path: '/busca', view: buscaView },
        { path: '/veiculo/:placa', view: veiculoView },
        { path: '/agenda', view: agendaView },
        { path: '/fiscal', view: fiscalView },
        { path: '/analytics', view: analyticsView },
    ], { host: $('#view-host'), fallback: '/inicio' });

    await loadConfig();
    startRouter();
    startDataPolling();
}

boot();
