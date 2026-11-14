/**
 * Componentes visuais de veículo: placa Mercosul, logo da montadora,
 * silhueta do modelo e etiqueta de status do pátio.
 */
import { html } from './dom.js';
import { formatPlate } from '../lib/format.js';
import { identifyCar, GENERIC_BRAND_LOGO, GENERIC_SILHOUETTE } from '../lib/catalog.js';
import { statusKey } from '../lib/patio.js';

const FLAG = html`<svg class="mercosul-mini-flag" viewBox="0 0 20 14" aria-hidden="true"><rect width="20" height="14" fill="#009b3a" rx="1"/><polygon points="10,1.5 18.5,7 10,12.5 1.5,7" fill="#fedf00"/><circle cx="10" cy="7" r="3" fill="#002776"/></svg>`;

/**
 * Placa Mercosul.  size: 'sm' | 'md' | 'lg'
 *   html`${plate('BRA2E19', 'lg')}`
 */
export function plate(value, size = 'md') {
    const text = formatPlate(value);
    return html`<div class="mercosul-plate mercosul-plate-${size}" role="img" aria-label="Placa ${text}">
        <div class="mercosul-top-bar"><span class="mercosul-country">BRASIL</span><span class="mercosul-br-box"><span class="mercosul-br-text">BR</span>${FLAG}</span></div>
        <div class="mercosul-body-area"><span class="mercosul-number">${text}</span></div>
    </div>`;
}

/** Logo da montadora a partir do texto do modelo.  size: 'sm' | 'md' | 'lg' */
export function brandLogo(modelText, size = 'md') {
    const info = identifyCar(modelText);
    const cls = size === 'md' ? '' : ` is-${size}`;
    return html`<span class="brand-logo-container${cls}" title="Montadora: ${info.brandName}">
        <img class="brand-logo-img" src="${info.brandLogo}" alt="${info.brandName}" loading="lazy" data-fallback="${GENERIC_BRAND_LOGO}">
    </span>`;
}

/** Silhueta lateral do modelo. */
export function silhouette(modelText) {
    const info = identifyCar(modelText);
    return html`<span class="car-silhouette-container" title="Modelo: ${info.modelName}">
        <img class="car-silhouette-img" src="${info.silhouette}" alt="" loading="lazy" data-fallback="${GENERIC_SILHOUETTE}">
    </span>`;
}

/** Etiqueta colorida de status do pátio. */
export function statusTag(status, label) {
    return html`<span class="status-tag" data-status="${statusKey(status)}">${label || status || 'Em Diagnóstico'}</span>`;
}

/**
 * Troca imagens quebradas pelo fallback (data-fallback). Instalado uma vez
 * no documento pelo main.js (eventos de erro de <img> não borbulham; usamos captura).
 */
export function installImageFallback(root = document) {
    root.addEventListener('error', (event) => {
        const img = event.target;
        if (!(img instanceof HTMLImageElement)) return;
        const fallback = img.dataset.fallback;
        if (fallback && !img.src.endsWith(fallback)) {
            img.src = fallback;
        }
    }, true);
}
