/**
 * Ponte para o catálogo de veículos (static/car_catalog.js, script clássico
 * compartilhado com o painel de TV, que define window.CarCatalog).
 *
 * Corrige os caminhos dos assets: o catálogo aponta para "/static/brands/..."
 * e "/static/models/...", mas o Flask serve a pasta static na raiz
 * ("/brands/...", "/models/..."), então as imagens davam 404.
 */

const FALLBACK = {
    brandKey: 'generic',
    brandName: 'Veículo',
    brandLogo: '/brands/generic.svg',
    modelKey: 'car-generic',
    modelName: 'Veículo',
    silhouette: '/models/car-generic.svg',
    bodyType: 'hatch',
};

function fixAssetPath(path) {
    if (!path) return path;
    return String(path).replace(/^\/static\//, '/');
}

/** Identifica marca/modelo/silhueta a partir do texto do modelo. */
export function identifyCar(modelText) {
    const catalog = window.CarCatalog;
    if (!catalog || typeof catalog.identifyCar !== 'function') return { ...FALLBACK, modelName: modelText || 'Veículo' };
    try {
        const info = catalog.identifyCar(modelText || '');
        return {
            ...info,
            brandLogo: fixAssetPath(info.brandLogo),
            silhouette: fixAssetPath(info.silhouette),
        };
    } catch {
        return { ...FALLBACK, modelName: modelText || 'Veículo' };
    }
}

export const GENERIC_BRAND_LOGO = FALLBACK.brandLogo;
export const GENERIC_SILHOUETTE = FALLBACK.silhouette;
