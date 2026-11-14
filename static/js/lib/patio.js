/**
 * Domínio do pátio: status oficiais (mesmos valores de exibição do backend,
 * cache.PATIO_STATUSES_DISPLAY) e a chave de cor usada em data-status.
 * As cores ficam em css/tokens.css (--status-<chave>) — iguais na TV.
 */
import { normalizeText } from './format.js';

export const PATIO_STATUSES = [
    { value: 'Em Diagnóstico', label: 'Diagnóstico', key: 'diagnostico' },
    { value: 'Esperando Orçamento', label: 'Orçamento', key: 'orcamento' },
    { value: 'Esperando Aprovação', label: 'Aprovação', key: 'aprovacao' },
    { value: 'Esperando Peças', label: 'Aguardando peças', key: 'pecas' },
    { value: 'Em Execução', label: 'Em execução', key: 'execucao' },
    { value: 'Esperando Cliente Buscar', label: 'Pronto p/ retirada', key: 'pronto' },
    { value: 'Liberado p/ Retirada por Terceiro', label: 'Retirada por terceiro', key: 'terceiro' },
];

export const DELIVERED_STATUS = 'Entregue';
export const THIRD_PARTY_STATUS = 'Liberado p/ Retirada por Terceiro';

/** Status (qualquer grafia, com ou sem acento) → chave de cor. */
export function statusKey(status) {
    const s = normalizeText(status);
    if (!s) return 'diagnostico';
    if (s.includes('entregue')) return 'entregue';
    if (s.includes('terceiro')) return 'terceiro';
    if (s.includes('diagnost')) return 'diagnostico';
    if (s.includes('orcament')) return 'orcamento';
    if (s.includes('aprova')) return 'aprovacao';
    if (s.includes('peca')) return 'pecas';
    if (s.includes('execu')) return 'execucao';
    if (s.includes('cliente') || s.includes('pronto') || s.includes('retirada')) return 'pronto';
    return 'diagnostico';
}

/** Rótulo curto para um status. */
export function statusLabel(status) {
    const key = statusKey(status);
    if (key === 'entregue') return 'Entregue';
    const found = PATIO_STATUSES.find((s) => s.key === key);
    return found ? found.label : String(status || 'Em Diagnóstico');
}

/** Valor oficial (para selects) a partir de qualquer grafia. */
export function statusValue(status) {
    const key = statusKey(status);
    if (key === 'entregue') return DELIVERED_STATUS;
    const found = PATIO_STATUSES.find((s) => s.key === key);
    return found ? found.value : PATIO_STATUSES[0].value;
}
