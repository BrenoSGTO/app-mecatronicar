# Front-end MecatroniCar v3 — guia de arquitetura

Documento de referência para todas as threads que mexem no front (Fase 2: T7–T11).
Siga à risca. Direção visual: `docs/REPAGINACAO_V3.md`, seção 3.

## 1. Visão geral

- HTML/CSS/JS puros, **ES modules nativos**, sem build, sem npm, sem CDN (100% offline).
- O Flask serve a pasta `static/` na raiz: `static/js/main.js` → `/js/main.js`,
  `static/brands/x.svg` → `/brands/x.svg` (**não** `/static/brands/...`).
- `index.html` é só a **casca** (sidebar, barra superior, área de telas). Cada tela
  monta a própria marcação a partir do seu módulo JS.

```
static/
  index.html               casca do app
  css/
    tokens.css             design tokens (cores, tipografia, espaço, raios, sombras, movimento, status)
    base.css               reset, tipografia, foco, utilitários mínimos
    components.css         biblioteca de componentes (seção 5)
    layout.css             casca: sidebar, topbar, área principal, menu de configurações
    print.css              impressão (media="print")
    views/<tela>.css       uma folha por tela: inicio, veiculo, os, fiscal, agenda, analytics
  js/
    theme-boot.js          script clássico no <head>: tema/zoom/sidebar antes da 1ª pintura
    main.js                bootstrap: ícones → casca → config → rotas → polling
    api.js                 fetch com timeout, JSON, erros em PT-BR, cancelamento
    state.js               estado global (notifica só se mudou) + eventos
    router.js              rotas por hash
    scheduler.js           polling central (pausa com a janela oculta)
    data.js                loaders compartilhados (patio, agenda, carros, fiscal) + refresh()
    ui/                    dom.js (html com escape), icon.js, toast.js, modal.js, menu.js,
                           clipboard.js, vehicle.js (placa, logo, silhueta, status)
    lib/                   format.js (pt-BR), patio.js (status), catalog.js, documents.js (PDF/Excel)
    shell/                 layout.js (nav/badges/sidebar), search.js (busca global e atalhos),
                           settings.js (pasta, tema, zoom), updates.js
    views/                 uma por tela (seção 3)
  vendor/icons.svg         sprite Lucide (ISC) + LICENSE-lucide.txt
  car_catalog.js           catálogo de marcas/modelos (script clássico compartilhado com a TV)
```

## 2. Rotas e donos (Fase 2)

| Rota | Módulo | CSS | Dono |
|---|---|---|---|
| `#/inicio` | `views/inicio.js` + `views/patio.js` (modal "Gerenciar pátio") | `views/inicio.css` | T7 |
| `#/busca?q=` e `#/veiculo/:placa` | `views/busca.js`, `views/veiculo.js`, `views/impressao.js` | `views/veiculo.css` | T8 |
| modal Nova visita / Editar OS, Checklist | `views/os.js`, `views/checklist.js` | `views/os.css` | T9 |
| `#/fiscal` + modal do copiloto | `views/fiscal.js` | `views/fiscal.css` | T10 |
| `#/agenda`, `#/analytics` | `views/agenda.js`, `views/analytics.js` | `views/agenda.css`, `views/analytics.css` | T11 |

Mexa só nos seus arquivos. Mudança em `tokens/base/components/layout`, `ui/`, `lib/`,
`shell/`, `api/state/router/scheduler/data` ou `index.html` = mudança de fundação:
faça o mínimo, justifique no relatório (o T12 consolida).

## 3. Contrato de uma tela (view)

```js
// static/js/views/exemplo.js
import { html, render, on, $ } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { state } from '../state.js';
import { refresh } from '../data.js';

let root = null;

function mount(el) {               // 1ª vez: el = <section class="view view-exemplo">
    root = el;
    render(el, html`
        <header class="page-header">
            <div class="page-heading">
                <h1 class="page-title">Exemplo</h1>
                <p class="page-subtitle">Descrição curta</p>
            </div>
            <div class="page-actions">
                <button type="button" class="btn btn-secondary" data-action="refresh">${icon('refresh-cw')} Atualizar</button>
            </div>
        </header>
        <div data-field="list"></div>`);

    on(root, 'click', '[data-action]', (e, btn) => {          // delegação de eventos
        if (btn.dataset.action === 'refresh') refresh('patio');
    });
    state.watch('patio', renderList);                         // re-render só quando o dado muda
}

function renderList(patio) { /* ... render($('[data-field="list"]', root), html`...`) */ }

export default {
    id: 'exemplo',          // vira data-view e a classe .view-exemplo
    title: 'Exemplo',       // título da janela
    mount,
    enter(params, query) {},  // toda vez que a rota fica ativa (inclui troca de parâmetro)
    leave() {},               // ao ir para outra tela (cancele requisições aqui)
};
```

Registrar: importe em `main.js` e adicione em `defineRoutes([...])`; se for item do menu,
adicione o `<a class="nav-item" data-nav="exemplo">` no `index.html` (fundação).
A `<section>` é criada uma vez e só fica `hidden` entre visitas (filtros/rolagem persistem).

Navegar: `navigate('/veiculo/' + encodeURIComponent(placa))` (de `router.js`) ou `<a href="#/agenda">`.

## 4. Dados, estado e polling

- **API**: `api.get/post/put/del(path, ...)` de `api.js`. Lança `ApiError` (mensagem em PT-BR)
  em erro de rede, timeout (20s padrão, `timeout:` para mais), HTTP != 2xx, resposta não-JSON
  ou `{success:false}` (use `allowFailure: true` para tratar você mesmo).
  Cancelamento: passe `signal` e ignore `isAbort(err)`.
  PDFs/downloads: `openInNewTab(path, params)` e `postToNewTab(path, fields)`.
- **Estado** (`state.js`): `state.set(chave, valor)` só notifica se o valor mudou (JSON);
  `state.watch(chave, fn)` chama já e a cada mudança. Chaves: `config`, `appInfo`, `cars`,
  `patio` (`{all, active, delivered}`), `agendaEvents`, `agendamentos`, `nfStats`.
- **Eventos** (`on/emit`): `route:changed`, `os:saved {plate}`, `fiscal:changed {plate}`,
  `vehicle:reload {plate}`, `data:reindexed`.
- **Polling**: só em `data.js`, via `scheduler.js` (um agendador, pausa com a janela oculta).
  Intervalos: patio 15s, agendamentos 10s, agenda 30s, fiscal 60s, carros 120s.
  **Telas não criam `setInterval`.** Depois de uma ação: `await refresh('patio', 'nfStats')`.
  Tarefa nova: adicione um loader em `data.js` que grava no `state`.

## 5. Componentes (HTML)

Todos usam tokens; nenhum precisa de CSS extra na tela.

```html
<!-- Botões: 1 primário por tela (o "Nova visita" da barra já é o primário global;
     nas telas use secondary/ghost; primário só em modal de salvar) -->
<button class="btn btn-primary">Salvar</button>
<button class="btn btn-secondary btn-sm">Secundário pequeno</button>
<button class="btn btn-ghost">Discreto</button>
<button class="btn btn-danger">Excluir</button>
<button class="btn btn-danger-ghost">Remover</button>
<button class="btn btn-secondary btn-icon" aria-label="Atualizar" data-tooltip="Atualizar">…ícone…</button>

<!-- Campos -->
<label class="field col-6">
  <span class="field-label">Placa <span class="req">*</span></span>
  <input class="input input-upper input-mono" name="plate">
  <span class="field-hint">Dica</span>
</label>
<select class="select">…</select>   <textarea class="textarea"></textarea>
<div class="input-group"><svg class="icon input-icon">…</svg><input class="input"></div>
<div class="form-grid">  <!-- grade de 12 colunas: .col-2 … .col-12 --> </div>
<label class="check"><input type="checkbox"> <span class="check-text">Texto<span class="check-desc">ajuda</span></span></label>

<!-- Etiquetas -->
<span class="badge">3</span> <span class="badge badge-accent">3</span>
<span class="tag">Neutra</span> <span class="tag tag-success">Ok</span> <span class="tag tag-warning">Pendente</span>
<span class="tag tag-danger">Erro</span> <span class="tag tag-info">Info</span> <span class="tag tag-accent">Destaque</span>
<span class="status-tag" data-status="execucao">Em execução</span>   <!-- ou statusTag(status) -->
<span class="plate-chip">BRA2E19</span>                              <!-- placa compacta -->
<span class="kbd">Ctrl K</span>   <button class="chip">+ Sugestão</button>

<!-- Card, estatística, tabela -->
<section class="card"><div class="card-header"><span class="card-title">Título</span></div><div class="card-body">…</div></section>
<div class="stat-grid"><div class="stat"><span class="stat-label">Visitas</span><span class="stat-value">24</span><span class="stat-sub">texto</span></div></div>
<div class="table-wrap"><table class="table"><thead><tr><th>Nome</th><th class="num">Valor</th></tr></thead><tbody>…</tbody></table></div>

<!-- Abas, segmentado, filtros -->
<div class="tabs" role="tablist"><button class="tab" role="tab" aria-selected="true">Aba <span class="badge">2</span></button></div>
<div class="segmented"><button class="segmented-item is-active">Hoje</button><button class="segmented-item">Todos</button></div>
<div class="filter-pills"><button class="filter-pill is-active">Todos <span class="count">4</span></button></div>

<!-- Feedback -->
<div class="callout callout-warning">…ícone… <div><div class="callout-title">Título</div>texto</div></div>
<div class="empty-state"><span class="empty-state-icon">…ícone…</span><div class="empty-state-title">Nada aqui</div><div class="empty-state-text">…</div></div>
<div class="skeleton skeleton-block"></div>  <div class="skeleton skeleton-text"></div>
<div class="progress"><div class="progress-bar"></div></div>   <!-- largura: setVar(el, '--value', '40%') -->
<td class="has-excel-note">…</td>                               <!-- triângulo vermelho de nota do Excel -->
```

JS de componentes:

```js
import { createModal, confirmDialog } from '../ui/modal.js';   // tamanhos sm|md|lg|xl; [data-modal-close] fecha; Esc fecha o de cima
const m = createModal({ id: 'x', title: 'Título', icon: 'wrench', size: 'md', body: html`…`, footer: html`…` });
m.open(); m.close(); m.setTitle('…'); m.setSubtitle('…'); m.body; m.footer;
if (await confirmDialog({ title: 'Excluir?', message: '…', confirmLabel: 'Excluir', danger: true })) { … }

import { createMenu } from '../ui/menu.js';                    // dropdown ancorado; [data-action] + onAction
import { toast } from '../ui/toast.js';  toast('Salvo.', 'success');   // 'info' | 'success' | 'error'
import { copyText } from '../ui/clipboard.js';
import { plate, brandLogo, silhouette, statusTag } from '../ui/vehicle.js';  // plate(v, 'sm'|'md'|'lg')
import { icon } from '../ui/icon.js';  icon('printer', 16)       // tamanhos 12/14/16/18/20/24/32/40
```

Ícones disponíveis (Lucide, `icon('nome')`): arrow-left arrow-right ban banknote building-2 calendar
calendar-check calendar-clock calendar-days calendar-plus car car-front chart-column chart-no-axes-column
check chevron-down chevron-left chevron-right chevron-up circle-alert circle-check circle-dollar-sign
circle-gauge circle-help circle-x clipboard-check clipboard-list clock cog coins copy download ellipsis
external-link eye eye-off file-down file-spreadsheet file-text filter folder folder-open gauge hammer hash
history house inbox info keyboard list-checks list-filter loader-circle log-in map-pin menu
message-square-text minus monitor moon package package-check panel-left-close panel-left-open pencil phone
plus printer receipt receipt-text refresh-cw rotate-cw save scan-line search settings sparkles sticky-note
sun table timer trash-2 triangle-alert tv undo-2 user user-check users warehouse wrench x zoom-in zoom-out.
Precisa de outro: baixe o SVG do `lucide-static@0.460.0`, acrescente um `<symbol id="i-nome">` em
`vendor/icons.svg` (mesmo formato) e registre no relatório.

## 6. Convenções (obrigatórias)

1. **Escape de HTML**: só monte marcação com o template `html\`...\`` de `ui/dom.js` e aplique
   com `render(el, ...)`. Interpolações são escapadas. `raw()` só para marcação escrita no código,
   **nunca** para dado de planilha/usuário/servidor. Nada de `innerHTML = \`${dado}\``.
2. **Sem `style=""` inline** no HTML/templates. Mostrar/ocultar: atributo `hidden` (`el.hidden = true`).
   Valor dinâmico (largura de barra, cor vinda do Excel): custom property via `setVar(el, '--value', '40%')`.
3. **Sem emoji** na interface, código e comentários (o `test_visual_cards.py` reprova).
   Use ícones (`icon()`); sem caracteres decorativos dos blocos U+2300–U+27BF.
4. **Só tokens**: nada de cor/raio/sombra crua nas folhas de tela. Se faltar um token, peça na fundação.
   Status do pátio sempre por `data-status="<chave>"` (`lib/patio.js` → `statusKey()`).
   Amarelo é acento (primário, foco, item ativo) — nunca fundo de área grande.
5. **Não use `vh`/`vw`**: o zoom da UI (`zoom` no `<html>`) faz `100vh` estourar a janela.
   Use `%`, `inset: 0` e deixe a área rolar.
6. **Eventos por delegação** com `data-action` (`on(root, 'click', '[data-action]', fn)`); nada de
   `onclick=""`.
7. **Textos em português do Brasil**, frases curtas, sentence case ("Nova visita", não "NOVA VISITA").
8. Números/valores/placas/horas: classe `.num` (tabular-nums). Moeda/km/data: `lib/format.js`.
9. Erros ao usuário com `toast(msg, 'error')`; nunca `alert()`/`confirm()` (use `confirmDialog`).
10. Acessibilidade: alvos ≥ 32px, `aria-label` em botão só-ícone, foco visível (já vem do base.css).
11. Contratos da API não mudam. Se precisar de rota nova, anote no relatório (T4 implementa).

## 7. Tema, zoom e atalhos

- `data-theme="light|dark"` no `<html>`; a preferência (`light|dark|auto`) fica no config do servidor
  (`theme`) e em `localStorage` (`mc.theme`). "Automático" segue o Windows (`prefers-color-scheme`).
- Zoom: config `ui_zoom` (50–150) → `--ui-zoom` no `<html>`; atalhos Ctrl+ / Ctrl- / Ctrl 0.
- Sidebar: recolhe sozinha abaixo de 1440px (preferência manual em `mc.sidebar`).
- Atalhos: `/` ou `Ctrl+K` foca a busca, `Esc` fecha modal/menu/limpa a busca.
- TV: pode reaproveitar `css/tokens.css` com `data-theme="dark"` (cores de status idênticas).

## 8. Checklist antes de entregar uma tela

- [ ] Funciona em 1366×768 (sidebar recolhida) e 1920×1080, nos dois temas.
- [ ] Sem erro no console; sem `style=""`; sem emoji; só tokens.
- [ ] Dados do usuário passam pelo `html\`\`` (teste com um nome contendo `<b>`).
- [ ] Ações recarregam dados com `refresh(...)`, não com polling próprio.
- [ ] `python -m pytest -q` passa.
