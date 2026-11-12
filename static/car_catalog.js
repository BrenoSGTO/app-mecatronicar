/**
 * MecatroniCar - Catálogo de Veículos, Identidade Visual & Componentes Oficiais
 * - 100 modelos mais populares do Brasil mapeados (10 marcas x 10 modelos)
 * - Logos oficiais de montadoras em SVG
 * - Silhuetas de perfil em alta definição
 * - Placas Mercosul oficiais padronizadas
 * - Biblioteca de ícones vetoriais SVG (eliminação total de emojis)
 */

(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.CarCatalog = factory();
    }
}(typeof self !== 'undefined' ? self : this, function () {

    // 1. Catálogo das 10 Montadoras Principais + Marcas Comuns
    const BRANDS = {
        fiat: { name: 'Fiat', logo: '/static/brands/fiat.svg' },
        volkswagen: { name: 'Volkswagen', logo: '/static/brands/volkswagen.svg' },
        chevrolet: { name: 'Chevrolet', logo: '/static/brands/chevrolet.svg' },
        toyota: { name: 'Toyota', logo: '/static/brands/toyota.svg' },
        hyundai: { name: 'Hyundai', logo: '/static/brands/hyundai.svg' },
        renault: { name: 'Renault', logo: '/static/brands/renault.svg' },
        jeep: { name: 'Jeep', logo: '/static/brands/jeep.svg' },
        nissan: { name: 'Nissan', logo: '/static/brands/nissan.svg' },
        honda: { name: 'Honda', logo: '/static/brands/honda.svg' },
        ford: { name: 'Ford', logo: '/static/brands/ford.svg' },
        peugeot: { name: 'Peugeot', logo: '/static/brands/peugeot.svg' },
        citroen: { name: 'Citroën', logo: '/static/brands/citroen.svg' },
        mitsubishi: { name: 'Mitsubishi', logo: '/static/brands/mitsubishi.svg' },
        chery: { name: 'Caoa Chery', logo: '/static/brands/chery.svg' },
        bmw: { name: 'BMW', logo: '/static/brands/bmw.svg' },
        mercedes: { name: 'Mercedes-Benz', logo: '/static/brands/mercedes.svg' },
        audi: { name: 'Audi', logo: '/static/brands/audi.svg' },
        kia: { name: 'Kia', logo: '/static/brands/kia.svg' },
        byd: { name: 'BYD', logo: '/static/brands/byd.svg' },
        generic: { name: 'MecatroniCar', logo: '/static/brands/generic.svg' }
    };

    // 2. Mapeamento dos 100 Modelos Mais Populares
    const POPULAR_MODELS = [
        // Fiat (10)
        { brand: 'fiat', key: 'fiat-strada', name: 'Strada', body: 'pickup', patterns: ['strada'] },
        { brand: 'fiat', key: 'fiat-argo', name: 'Argo', body: 'hatch', patterns: ['argo'] },
        { brand: 'fiat', key: 'fiat-mobi', name: 'Mobi', body: 'hatch', patterns: ['mobi'] },
        { brand: 'fiat', key: 'fiat-toro', name: 'Toro', body: 'pickup', patterns: ['toro'] },
        { brand: 'fiat', key: 'fiat-cronos', name: 'Cronos', body: 'sedan', patterns: ['cronos'] },
        { brand: 'fiat', key: 'fiat-pulse', name: 'Pulse', body: 'suv', patterns: ['pulse'] },
        { brand: 'fiat', key: 'fiat-fastback', name: 'Fastback', body: 'suv', patterns: ['fastback'] },
        { brand: 'fiat', key: 'fiat-fiorino', name: 'Fiorino', body: 'van', patterns: ['fiorino'] },
        { brand: 'fiat', key: 'fiat-uno', name: 'Uno', body: 'hatch', patterns: ['uno', 'mille'] },
        { brand: 'fiat', key: 'fiat-palio', name: 'Palio', body: 'hatch', patterns: ['palio', 'siena', 'weekend'] },

        // Volkswagen (10)
        { brand: 'volkswagen', key: 'vw-gol', name: 'Gol', body: 'hatch', patterns: ['gol'] },
        { brand: 'volkswagen', key: 'vw-polo', name: 'Polo', body: 'hatch', patterns: ['polo'] },
        { brand: 'volkswagen', key: 'vw-tcross', name: 'T-Cross', body: 'suv', patterns: ['t-cross', 'tcross', 't cross'] },
        { brand: 'volkswagen', key: 'vw-nivus', name: 'Nivus', body: 'suv', patterns: ['nivus'] },
        { brand: 'volkswagen', key: 'vw-saveiro', name: 'Saveiro', body: 'pickup', patterns: ['saveiro'] },
        { brand: 'volkswagen', key: 'vw-virtus', name: 'Virtus', body: 'sedan', patterns: ['virtus'] },
        { brand: 'volkswagen', key: 'vw-voyage', name: 'Voyage', body: 'sedan', patterns: ['voyage'] },
        { brand: 'volkswagen', key: 'vw-fox', name: 'Fox', body: 'hatch', patterns: ['fox', 'crossfox', 'spacefox'] },
        { brand: 'volkswagen', key: 'vw-taos', name: 'Taos', body: 'suv', patterns: ['taos'] },
        { brand: 'volkswagen', key: 'vw-up', name: 'Up', body: 'hatch', patterns: ['up!', 'up'] },

        // Chevrolet (10)
        { brand: 'chevrolet', key: 'chevrolet-onix', name: 'Onix', body: 'hatch', patterns: ['onix'] },
        { brand: 'chevrolet', key: 'chevrolet-onix-plus', name: 'Onix Plus', body: 'sedan', patterns: ['onix plus', 'onix sedan'] },
        { brand: 'chevrolet', key: 'chevrolet-tracker', name: 'Tracker', body: 'suv', patterns: ['tracker'] },
        { brand: 'chevrolet', key: 'chevrolet-s10', name: 'S10', body: 'pickup', patterns: ['s10', 's-10'] },
        { brand: 'chevrolet', key: 'chevrolet-spin', name: 'Spin', body: 'suv', patterns: ['spin'] },
        { brand: 'chevrolet', key: 'chevrolet-montana', name: 'Montana', body: 'pickup', patterns: ['montana'] },
        { brand: 'chevrolet', key: 'chevrolet-celta', name: 'Celta', body: 'hatch', patterns: ['celta'] },
        { brand: 'chevrolet', key: 'chevrolet-prisma', name: 'Prisma', body: 'sedan', patterns: ['prisma'] },
        { brand: 'chevrolet', key: 'chevrolet-corsa', name: 'Corsa', body: 'hatch', patterns: ['corsa'] },
        { brand: 'chevrolet', key: 'chevrolet-cruze', name: 'Cruze', body: 'sedan', patterns: ['cruze'] },

        // Toyota (10)
        { brand: 'toyota', key: 'toyota-hilux', name: 'Hilux', body: 'pickup', patterns: ['hilux'] },
        { brand: 'toyota', key: 'toyota-corolla', name: 'Corolla', body: 'sedan', patterns: ['corolla'] },
        { brand: 'toyota', key: 'toyota-corolla-cross', name: 'Corolla Cross', body: 'suv', patterns: ['corolla cross'] },
        { brand: 'toyota', key: 'toyota-yaris-hatch', name: 'Yaris Hatch', body: 'hatch', patterns: ['yaris hatch', 'yaris'] },
        { brand: 'toyota', key: 'toyota-yaris-sedan', name: 'Yaris Sedan', body: 'sedan', patterns: ['yaris sedan'] },
        { brand: 'toyota', key: 'toyota-etios', name: 'Etios', body: 'hatch', patterns: ['etios'] },
        { brand: 'toyota', key: 'toyota-sw4', name: 'SW4', body: 'suv', patterns: ['sw4', 'hilux sw4'] },
        { brand: 'toyota', key: 'toyota-rav4', name: 'RAV4', body: 'suv', patterns: ['rav4', 'rav 4'] },
        { brand: 'toyota', key: 'toyota-bandeirante', name: 'Bandeirante', body: 'suv', patterns: ['bandeirante'] },
        { brand: 'toyota', key: 'toyota-prius', name: 'Prius', body: 'sedan', patterns: ['prius'] },

        // Hyundai (10)
        { brand: 'hyundai', key: 'hyundai-hb20', name: 'HB20', body: 'hatch', patterns: ['hb20', 'hb-20', 'hb20x'] },
        { brand: 'hyundai', key: 'hyundai-hb20s', name: 'HB20S', body: 'sedan', patterns: ['hb20s', 'hb-20s', 'hb20 sedan'] },
        { brand: 'hyundai', key: 'hyundai-creta', name: 'Creta', body: 'suv', patterns: ['creta'] },
        { brand: 'hyundai', key: 'hyundai-tucson', name: 'Tucson', body: 'suv', patterns: ['tucson'] },
        { brand: 'hyundai', key: 'hyundai-santafe', name: 'Santa Fe', body: 'suv', patterns: ['santa fe', 'santafe', 'santa fé'] },
        { brand: 'hyundai', key: 'hyundai-i30', name: 'i30', body: 'hatch', patterns: ['i30', 'i-30'] },
        { brand: 'hyundai', key: 'hyundai-ix35', name: 'ix35', body: 'suv', patterns: ['ix35', 'ix-35'] },
        { brand: 'hyundai', key: 'hyundai-hr', name: 'HR', body: 'van', patterns: ['hr', 'h100'] },
        { brand: 'hyundai', key: 'hyundai-azera', name: 'Azera', body: 'sedan', patterns: ['azera'] },
        { brand: 'hyundai', key: 'hyundai-elantra', name: 'Elantra', body: 'sedan', patterns: ['elantra'] },

        // Renault (10)
        { brand: 'renault', key: 'renault-kwid', name: 'Kwid', body: 'hatch', patterns: ['kwid'] },
        { brand: 'renault', key: 'renault-sandero', name: 'Sandero', body: 'hatch', patterns: ['sandero', 'stepway'] },
        { brand: 'renault', key: 'renault-logan', name: 'Logan', body: 'sedan', patterns: ['logan'] },
        { brand: 'renault', key: 'renault-duster', name: 'Duster', body: 'suv', patterns: ['duster'] },
        { brand: 'renault', key: 'renault-oroch', name: 'Oroch', body: 'pickup', patterns: ['oroch', 'duster oroch'] },
        { brand: 'renault', key: 'renault-captur', name: 'Captur', body: 'suv', patterns: ['captur'] },
        { brand: 'renault', key: 'renault-master', name: 'Master', body: 'van', patterns: ['master'] },
        { brand: 'renault', key: 'renault-kangoo', name: 'Kangoo', body: 'van', patterns: ['kangoo'] },
        { brand: 'renault', key: 'renault-megane', name: 'Megane', body: 'sedan', patterns: ['megane', 'mégane'] },
        { brand: 'renault', key: 'renault-clio', name: 'Clio', body: 'hatch', patterns: ['clio'] },

        // Jeep (10)
        { brand: 'jeep', key: 'jeep-renegade', name: 'Renegade', body: 'suv', patterns: ['renegade'] },
        { brand: 'jeep', key: 'jeep-compass', name: 'Compass', body: 'suv', patterns: ['compass'] },
        { brand: 'jeep', key: 'jeep-commander', name: 'Commander', body: 'suv', patterns: ['commander'] },
        { brand: 'jeep', key: 'jeep-cherokee', name: 'Cherokee', body: 'suv', patterns: ['cherokee'] },
        { brand: 'jeep', key: 'jeep-grandcherokee', name: 'Grand Cherokee', body: 'suv', patterns: ['grand cherokee'] },
        { brand: 'jeep', key: 'jeep-wrangler', name: 'Wrangler', body: 'suv', patterns: ['wrangler'] },
        { brand: 'jeep', key: 'jeep-gladiator', name: 'Gladiator', body: 'pickup', patterns: ['gladiator'] },
        { brand: 'jeep', key: 'jeep-compass-4xe', name: 'Compass 4xe', body: 'suv', patterns: ['compass 4xe'] },
        { brand: 'jeep', key: 'jeep-renegade-4xe', name: 'Renegade 4xe', body: 'suv', patterns: ['renegade 4xe'] },
        { brand: 'jeep', key: 'jeep-commander-blackhawk', name: 'Commander Blackhawk', body: 'suv', patterns: ['blackhawk'] },

        // Nissan (10)
        { brand: 'nissan', key: 'nissan-kicks', name: 'Kicks', body: 'suv', patterns: ['kicks'] },
        { brand: 'nissan', key: 'nissan-versa', name: 'Versa', body: 'sedan', patterns: ['versa'] },
        { brand: 'nissan', key: 'nissan-sentra', name: 'Sentra', body: 'sedan', patterns: ['sentra'] },
        { brand: 'nissan', key: 'nissan-frontier', name: 'Frontier', body: 'pickup', patterns: ['frontier'] },
        { brand: 'nissan', key: 'nissan-march', name: 'March', body: 'hatch', patterns: ['march'] },
        { brand: 'nissan', key: 'nissan-tiida', name: 'Tiida', body: 'hatch', patterns: ['tiida'] },
        { brand: 'nissan', key: 'nissan-livina', name: 'Livina', body: 'suv', patterns: ['livina'] },
        { brand: 'nissan', key: 'nissan-grandlivina', name: 'Grand Livina', body: 'suv', patterns: ['grand livina'] },
        { brand: 'nissan', key: 'nissan-xtrail', name: 'X-Trail', body: 'suv', patterns: ['x-trail', 'xtrail'] },
        { brand: 'nissan', key: 'nissan-vdrive', name: 'V-Drive', body: 'sedan', patterns: ['v-drive', 'vdrive'] },

        // Honda (10)
        { brand: 'honda', key: 'honda-civic', name: 'Civic', body: 'sedan', patterns: ['civic'] },
        { brand: 'honda', key: 'honda-hrv', name: 'HR-V', body: 'suv', patterns: ['hr-v', 'hrv', 'hr v'] },
        { brand: 'honda', key: 'honda-city', name: 'City', body: 'sedan', patterns: ['city'] },
        { brand: 'honda', key: 'honda-fit', name: 'Fit', body: 'hatch', patterns: ['fit'] },
        { brand: 'honda', key: 'honda-wrv', name: 'WR-V', body: 'suv', patterns: ['wr-v', 'wrv', 'wr v'] },
        { brand: 'honda', key: 'honda-crv', name: 'CR-V', body: 'suv', patterns: ['cr-v', 'crv', 'cr v'] },
        { brand: 'honda', key: 'honda-accord', name: 'Accord', body: 'sedan', patterns: ['accord'] },
        { brand: 'honda', key: 'honda-zrv', name: 'ZR-V', body: 'suv', patterns: ['zr-v', 'zrv', 'zr v'] },
        { brand: 'honda', key: 'honda-city-hatchback', name: 'City Hatchback', body: 'hatch', patterns: ['city hatch'] },
        { brand: 'honda', key: 'honda-prelude', name: 'Prelude', body: 'sedan', patterns: ['prelude'] },

        // Ford (10)
        { brand: 'ford', key: 'ford-ka', name: 'Ka', body: 'hatch', patterns: ['ka', 'ka+'] },
        { brand: 'ford', key: 'ford-ka-sedan', name: 'Ka Sedan', body: 'sedan', patterns: ['ka sedan', 'ka+ sedan'] },
        { brand: 'ford', key: 'ford-ecosport', name: 'EcoSport', body: 'suv', patterns: ['ecosport', 'eco sport'] },
        { brand: 'ford', key: 'ford-ranger', name: 'Ranger', body: 'pickup', patterns: ['ranger'] },
        { brand: 'ford', key: 'ford-fiesta', name: 'Fiesta', body: 'hatch', patterns: ['fiesta'] },
        { brand: 'ford', key: 'ford-focus', name: 'Focus', body: 'hatch', patterns: ['focus'] },
        { brand: 'ford', key: 'ford-fusion', name: 'Fusion', body: 'sedan', patterns: ['fusion'] },
        { brand: 'ford', key: 'ford-territory', name: 'Territory', body: 'suv', patterns: ['territory'] },
        { brand: 'ford', key: 'ford-maverick', name: 'Maverick', body: 'pickup', patterns: ['maverick'] },
        { brand: 'ford', key: 'ford-bronco-sport', name: 'Bronco Sport', body: 'suv', patterns: ['bronco'] },

        // Outros populares comuns
        { brand: 'peugeot', key: 'peugeot-partner', name: 'Partner', body: 'van', patterns: ['partner'] },
        { brand: 'peugeot', key: 'peugeot-208', name: '208', body: 'hatch', patterns: ['208', '207', '206'] },
        { brand: 'citroen', key: 'citroen-c3', name: 'C3', body: 'hatch', patterns: ['c3', 'aircross', 'c4'] },
        { brand: 'mitsubishi', key: 'mitsubishi-l200', name: 'L200', body: 'pickup', patterns: ['l200', 'pajero', 'asx'] }
    ];

    // Helper de limpeza de texto
    function normalizeText(str) {
        if (!str) return '';
        return String(str)
            .toLowerCase()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-z0-9\s-]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
    }

    /**
     * Identifica montadora, modelo e silhueta correspondente a partir de uma string
     */
    function identifyCar(modelStr) {
        const norm = normalizeText(modelStr);
        if (!norm) {
            return {
                brandKey: 'generic',
                brandName: 'MecatroniCar',
                brandLogo: BRANDS.generic.logo,
                modelKey: 'car-generic',
                modelName: 'Veículo',
                silhouette: '/static/models/car-generic.svg',
                bodyType: 'hatch'
            };
        }

        // 1. Tenta identificar por modelo específico mais longo primeiro (ex: "onix plus" antes de "onix")
        // Ordena por tamanho do padrão decrescente
        const sortedModels = [...POPULAR_MODELS].sort((a, b) => {
            const maxA = Math.max(...a.patterns.map(p => p.length));
            const maxB = Math.max(...b.patterns.map(p => p.length));
            return maxB - maxA;
        });

        for (const item of sortedModels) {
            for (const pat of item.patterns) {
                // Regex de palavra inteira ou limite
                const regex = new RegExp(`(^|\\s)${pat}(\\s|$)`, 'i');
                if (regex.test(norm) || norm.includes(pat)) {
                    const brandObj = BRANDS[item.brand] || BRANDS.generic;
                    return {
                        brandKey: item.brand,
                        brandName: brandObj.name,
                        brandLogo: brandObj.logo,
                        modelKey: item.key,
                        modelName: item.name,
                        silhouette: `/static/models/${item.key}.svg`,
                        bodyType: item.body
                    };
                }
            }
        }

        // 2. Tenta identificar montadora isoladamente
        let foundBrand = 'generic';
        if (norm.includes('fiat')) foundBrand = 'fiat';
        else if (norm.includes('vw') || norm.includes('volks') || norm.includes('volkswagen')) foundBrand = 'volkswagen';
        else if (norm.includes('chev') || norm.includes('gm') || norm.includes('corsa') || norm.includes('celta')) foundBrand = 'chevrolet';
        else if (norm.includes('toyo') || norm.includes('toyota')) foundBrand = 'toyota';
        else if (norm.includes('hyundai')) foundBrand = 'hyundai';
        else if (norm.includes('renault')) foundBrand = 'renault';
        else if (norm.includes('jeep')) foundBrand = 'jeep';
        else if (norm.includes('nissan')) foundBrand = 'nissan';
        else if (norm.includes('honda')) foundBrand = 'honda';
        else if (norm.includes('ford')) foundBrand = 'ford';
        else if (norm.includes('peugeot')) foundBrand = 'peugeot';
        else if (norm.includes('citroen')) foundBrand = 'citroen';
        else if (norm.includes('mitsu')) foundBrand = 'mitsubishi';
        else if (norm.includes('chery')) foundBrand = 'chery';
        else if (norm.includes('bmw')) foundBrand = 'bmw';
        else if (norm.includes('mercedes')) foundBrand = 'mercedes';
        else if (norm.includes('audi')) foundBrand = 'audi';
        else if (norm.includes('kia')) foundBrand = 'kia';
        else if (norm.includes('byd')) foundBrand = 'byd';

        // 3. Tenta identificar tipo de carroceria genérica
        let genericSilhouette = 'car-generic';
        let bodyType = 'hatch';
        if (norm.includes('sedan') || norm.includes('sed')) {
            genericSilhouette = 'sedan-generic';
            bodyType = 'sedan';
        } else if (norm.includes('suv') || norm.includes('cross') || norm.includes('jeep')) {
            genericSilhouette = 'suv-generic';
            bodyType = 'suv';
        } else if (norm.includes('picape') || norm.includes('pickup') || norm.includes('cabine') || norm.includes('strada') || norm.includes('toro')) {
            genericSilhouette = 'pickup-generic';
            bodyType = 'pickup';
        } else if (norm.includes('furg') || norm.includes('van') || norm.includes('utilitario') || norm.includes('partner') || norm.includes('fiorino')) {
            genericSilhouette = 'van-generic';
            bodyType = 'van';
        } else if (norm.includes('hatch')) {
            genericSilhouette = 'hatch-generic';
            bodyType = 'hatch';
        }

        const brandObj = BRANDS[foundBrand] || BRANDS.generic;
        return {
            brandKey: foundBrand,
            brandName: brandObj.name,
            brandLogo: brandObj.logo,
            modelKey: genericSilhouette,
            modelName: modelStr || 'Veículo',
            silhouette: `/static/models/${genericSilhouette}.svg`,
            bodyType: bodyType
        };
    }

    /**
     * Formata placa Mercosul oficial
     * Baseado na referência oficial:
     * - Topo azul #003399 com BRASIL e BR com mini bandeira
     * - Corpo branco com texto preto negrito destacado
     */
    function renderMercosulPlateHtml(plateText, size = 'md') {
        const raw = String(plateText || 'SEM PLACA').trim().toUpperCase();
        const clean = raw.replace(/[^A-Z0-9]/g, '');
        let formatted = raw;
        if (clean.length === 7) {
            // Se for padrão antigo LLLNNNN (ex ABC1234) formata com hífen ABC-1234
            if (/^[A-Z]{3}[0-9]{4}$/.test(clean)) {
                formatted = clean.slice(0, 3) + '-' + clean.slice(3);
            } else {
                formatted = clean; // Mercosul ABC1D23
            }
        }

        return `
            <div class="mercosul-plate mercosul-plate-${size}" title="Placa do Veículo: ${formatted}">
                <div class="mercosul-top-bar">
                    <span class="mercosul-country">BRASIL</span>
                    <span class="mercosul-br-box">
                        <span class="mercosul-br-text">BR</span>
                        <svg class="mercosul-mini-flag" viewBox="0 0 20 14" width="13" height="9">
                            <rect width="20" height="14" fill="#009b3a" rx="1"/>
                            <polygon points="10,1.5 18.5,7 10,12.5 1.5,7" fill="#fedf00"/>
                            <circle cx="10" cy="7" r="3" fill="#002776"/>
                        </svg>
                    </span>
                </div>
                <div class="mercosul-body-area">
                    <span class="mercosul-number">${escapeHtml(formatted)}</span>
                </div>
            </div>
        `;
    }

    /**
     * Retorna HTML do logo da montadora
     */
    function renderBrandLogoHtml(brandKey, size = 32) {
        const brand = BRANDS[brandKey] || BRANDS.generic;
        return `
            <div class="brand-logo-container" title="Montadora: ${brand.name}" style="width: ${size}px; height: ${size}px;">
                <img src="${brand.logo}" alt="${brand.name}" class="brand-logo-img" loading="lazy" />
            </div>
        `;
    }

    /**
     * Retorna HTML da silhueta do carro
     */
    function renderCarSilhouetteHtml(carInfo, height = 48) {
        return `
            <div class="car-silhouette-container" style="height: ${height}px;">
                <img src="${carInfo.silhouette}" alt="${carInfo.modelName}" class="car-silhouette-img" loading="lazy" />
            </div>
        `;
    }

    function escapeHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Biblioteca de Ícones Vetoriais SVG (Substituição Completa de Emojis)
     * Sistema consistente e profissional alinhado à identidade visual da MecatroniCar.
     */
    const SVG_ICONS = {
        car: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg>`,
        calendar: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
        user: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`,
        gauge: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/></svg>`,
        phone: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/></svg>`,
        fileText: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
        clipboard: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>`,
        receipt: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-8"/><path d="M16 12h-8"/><path d="M12 16h-4"/></svg>`,
        wrench: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
        edit: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>`,
        folder: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`,
        search: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
        tv: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"/><polyline points="17 2 12 7 7 2"/></svg>`,
        plus: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
        sparkles: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/></svg>`,
        refresh: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>`,
        close: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
        mapPin: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`,
        printer: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>`,
        check: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
        checkCircle: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
        key: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 2-2 2m-1.5 1.5L14 9M9 14l-4 4-2-2 2-2-2-2 4-4a6 6 0 1 1 8.5 8.5Z"/></svg>`,
        trash: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`,
        save: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>`,
        package: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>`,
        clock: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
        alert: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
        volume: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`,
        volumeX: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>`,
        maximize: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>`,
        building: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"/><line x1="9" y1="22" x2="9" y2="2"/><line x1="8" y1="6" x2="10" y2="6"/><line x1="14" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="10" y2="10"/><line x1="14" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="10" y2="14"/><line x1="14" y1="14" x2="16" y2="14"/><line x1="8" y1="18" x2="10" y2="18"/><line x1="14" y1="18" x2="16" y2="18"/></svg>`,
        coins: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/></svg>`,
        table: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M12 3v18"/></svg>`,
        download: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
        zoomIn: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`,
        zoomOut: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`,
        zap: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
        bell: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
        bellOff: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.73 21a2 2 0 0 1-3.46 0"/><path d="M18.63 13A17.89 17.89 0 0 1 18 8"/><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"/><path d="M18 8a6 6 0 0 0-9.33-5"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`,
        hash: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/><line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/></svg>`
    };

    function getIcon(name, size = 16, className = '') {
        const svg = SVG_ICONS[name] || SVG_ICONS.car;
        if (size !== 16 || className) {
            return svg.replace(
                /<svg /i,
                `<svg width="${size}" height="${size}" class="app-icon ${className}" `
            );
        }
        return svg.replace(/<svg /i, `<svg class="app-icon" `);
    }

    return {
        BRANDS,
        POPULAR_MODELS,
        identifyCar,
        renderMercosulPlateHtml,
        renderBrandLogoHtml,
        renderCarSilhouetteHtml,
        getIcon,
        icons: SVG_ICONS
    };
}));
