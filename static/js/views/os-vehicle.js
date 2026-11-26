/**
 * Ficha da OS: Marca -> Ano -> Modelo com listas da Tabela FIPE (static/vehicle_catalog.js).
 *
 * - Marca: todas as montadoras vendidas no Brasil, com logo; as mais comuns primeiro.
 * - Ano: só os anos-modelo que a marca teve (o ano encolhe a lista de modelos).
 * - Modelo: "Strada 1.4", "Strada 1.8"... um item por litragem oferecida naquele ano,
 *   sem versão/acabamento. Sem marca, busca o modelo em todas as marcas e preenche a marca.
 * - Tudo continua aceitando texto livre para o carro que não está na tabela.
 */
import { attachCombobox } from '../ui/combobox.js';
import { matchesSearchTokens, normalizeText } from '../lib/format.js';
import { brandLogoUrl, catalogBrands, catalogModels, catalogYears, findBrandKey } from '../lib/catalog.js';

const BODY_LABEL = { hatch: 'Hatch', sedan: 'Sedã', suv: 'SUV', pickup: 'Picape', van: 'Utilitário' };
const FIRST_YEAR = 1950;

let form = null;
let logoEl = null;
let combos = {};
let allModelsCache = new Map(); // ano -> opções de todas as marcas (busca sem marca)

function brandKey() {
    return findBrandKey(form.elements.car_brand.value);
}

function yearValue() {
    const y = Number(form.elements.car_year.value);
    return /^\d{4}$/.test(form.elements.car_year.value.trim()) && y >= FIRST_YEAR ? y : 0;
}

function yearsText(opt) {
    if (!opt.from) return '';
    return opt.from === opt.to ? String(opt.from) : `${opt.from}–${opt.to}`;
}

function modelHint(opt, { withBrand = false, brandName = '' } = {}) {
    const parts = [];
    if (withBrand) parts.push(brandName);
    if (BODY_LABEL[opt.body]) parts.push(BODY_LABEL[opt.body]);
    if (opt.fuels.length) parts.push(opt.fuels.join(' / '));
    if (!yearValue()) parts.push(yearsText(opt));
    return parts.filter(Boolean).join(' · ');
}

/** Mostra o logo da marca dentro do campo Marca. */
export function syncBrandLogo() {
    if (!form || !logoEl) return;
    const key = brandKey();
    const url = key ? brandLogoUrl(key) : '';
    logoEl.hidden = !url;
    if (url && logoEl.getAttribute('src') !== url) logoEl.src = url;
    form.elements.car_brand.closest('.input-group').classList.toggle('has-logo', Boolean(url));
}

function brandOptions(query) {
    const list = catalogBrands();
    const filtered = query ? list.filter((b) => matchesSearchTokens(`${b.name} ${b.aliases.join(' ')}`, query)) : list;
    return filtered.map((b) => ({
        value: b.name,
        label: b.name,
        logo: b.logo,
        group: query ? '' : (b.popular ? 'Mais comuns' : 'Todas as marcas'),
        key: b.key,
    }));
}

function yearOptions(query) {
    const key = brandKey();
    let years = key ? catalogYears(key) : [];
    if (!years.length) {
        const top = new Date().getFullYear() + 1;
        years = Array.from({ length: top - 1979 }, (_, i) => top - i);
    }
    const q = query.replace(/\D/g, '');
    return years
        .filter((y) => !q || String(y).startsWith(q) || String(y).slice(2).startsWith(q))
        .map((y) => ({ value: String(y), label: String(y) }));
}

function allBrandsModels(year) {
    if (!allModelsCache.has(year)) {
        const out = [];
        for (const b of catalogBrands()) {
            for (const opt of catalogModels(b.key, year)) out.push({ ...opt, brandName: b.name, logo: b.logo });
        }
        allModelsCache.set(year, out);
    }
    return allModelsCache.get(year);
}

function modelOptions(query) {
    const key = brandKey();
    const year = yearValue();
    if (key) {
        const list = catalogModels(key, year);
        const filtered = query ? list.filter((o) => matchesSearchTokens(o.label, query)) : list;
        return filtered.map((o) => ({ value: o.label, label: o.label, hint: modelHint(o), opt: o }));
    }
    // Sem marca: procura em todas (só depois de digitar algo, senão a lista seria enorme).
    if (normalizeText(query).length < 2) return [];
    const q = normalizeText(query);
    return allBrandsModels(year)
        .filter((o) => matchesSearchTokens(`${o.label} ${o.brandName}`, query))
        .sort((a, b) => (normalizeText(a.label).startsWith(q) ? 0 : 1) - (normalizeText(b.label).startsWith(q) ? 0 : 1))
        .map((o) => ({
            value: o.label, label: o.label, logo: o.logo,
            hint: modelHint(o, { withBrand: true, brandName: o.brandName }), opt: o,
        }));
}

function focusNext(name) {
    const el = form.elements[name];
    if (el) setTimeout(() => el.focus(), 0);
}

function setField(name, value, src = 'user') {
    const el = form.elements[name];
    if (!el) return;
    el.value = value;
    el.dataset.src = src;
    el.classList.remove('is-invalid');
    el.dispatchEvent(new Event('change', { bubbles: true }));
}

/**
 * Liga os três campos. Chamar uma vez depois de montar o formulário.
 *   onChange(): avisa o formulário que o usuário alterou algo (marca "não salvo").
 */
export function initVehiclePicker(formEl, host, { onChange } = {}) {
    form = formEl;
    logoEl = form.querySelector('[data-field="brand-logo"]');
    const f = form.elements;

    combos.brand = attachCombobox(f.car_brand, {
        host,
        getOptions: brandOptions,
        emptyText: (q) => (q ? `“${q}” não está na tabela FIPE: pode deixar assim mesmo.` : ''),
        onPick: () => {
            syncBrandLogo();
            onChange?.();
            focusNext('car_year');
        },
    });
    combos.year = attachCombobox(f.car_year, {
        host,
        getOptions: yearOptions,
        onPick: () => {
            onChange?.();
            focusNext('car_model');
        },
    });
    combos.model = attachCombobox(f.car_model, {
        host,
        getOptions: modelOptions,
        emptyText: (q) => {
            const key = brandKey();
            if (!key && normalizeText(q).length < 2) return 'Escolha a marca ou digite o nome do modelo.';
            if (key && yearValue() && !q) return `Nenhum modelo dessa marca em ${yearValue()} na tabela FIPE. Digite o modelo.`;
            return q ? `Nenhum modelo com “${q}” na tabela: pode digitar o nome assim mesmo.` : '';
        },
        onPick: ({ opt }) => {
            if (opt && !brandKey()) {
                setField('car_brand', opt.brandName);
                syncBrandLogo();
            }
            // Combustível: só preenche se o modelo teve um único tipo e o campo está vazio.
            if (opt && opt.fuels.length === 1 && !f.car_fuel.value.trim()) setField('car_fuel', opt.fuels[0], 'auto');
            onChange?.();
            focusNext('car_color');
        },
    });

    f.car_brand.addEventListener('input', syncBrandLogo);
    f.car_brand.addEventListener('change', syncBrandLogo);
    f.car_year.addEventListener('input', (e) => { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 4); });
}

export function closeVehiclePicker() {
    Object.values(combos).forEach((c) => c.close());
}
