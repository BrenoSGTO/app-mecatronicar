# Repaginação v3 — Plano mestre

Documento de referência para TODAS as threads que trabalham na repaginação.
Leia inteiro antes de começar sua tarefa.

## 1. Regras invioláveis

1. **Nunca** commitar, mergear ou dar push no branch `main`. A secretária usa o
   programa em produção e o botão "Verificar Atualizações" (updater.py) lê
   `https://raw.githubusercontent.com/BrenoSGTO/app-mecatronicar/main/version.json`
   e, como fallback, a última GitHub Release.
2. **Nunca** alterar `version.json`, `CURRENT_VERSION` em `updater.py`, nem criar
   tags ou GitHub Releases.
3. Branch de integração: `v3-repaginacao` (local). Cada tarefa trabalha no seu
   próprio branch `v3/<tarefa>` criado a partir dele, faz commits pequenos e no
   final deixa o branch pronto para merge (rebaseado em `v3-repaginacao` se ela
   tiver andado). Não fazer push a menos que o dono peça.
4. **Contratos da API são estáveis**: rotas `/api/*`, formatos JSON e o formato
   das planilhas `.xlsx` (excel_writer.py / templates/template_os.xlsx) não mudam
   sem necessidade. Se mudar, manter compatibilidade e anotar no relatório final.
5. **100% offline**: o programa roda na oficina sem garantia de internet.
   Nada de CDN, Google Fonts ou bibliotecas remotas. Tudo que for usado vai
   vendorizado em `static/vendor/` (com a licença ao lado).
6. Sem dependências novas pesadas. Python continua (Flask). Nada de framework
   JS com build step (sem React/Vite/npm). JS moderno nativo (ES modules) roda no
   Edge/Chrome que abre o app (`--app=`), então pode usar à vontade.
7. Rodar os testes existentes (`python -m pytest -q`) antes de entregar. Se um
   teste quebrar por causa de mudança visual legítima (ex.: teste que procura um
   emoji ou um id antigo), atualizar o teste e explicar.
8. Validar visualmente: subir o servidor (`python server.py` ou `python app.py`,
   porta 54321, pasta de planilhas = `planilhas_exemplo/`) e conferir as telas
   em 1366×768, 1920×1080 e (para a TV) 3840×2160. Anexar prints no relatório.
9. Português do Brasil em toda a interface. Código e commits podem ser em PT-BR.

## 2. Diagnóstico (estado atual do v2)

- Flask + HTML/JS/CSS puros, aberto numa janela do Edge em modo app.
- `static/app.js` (5,4 mil linhas), `static/style.css` (4,7 mil), `static/index.html`
  (1,7 mil) — monolíticos, com ~220 `style=""` inline, emojis como ícones,
  muito `innerHTML` reconstruindo telas inteiras.
- Dois `tv.html` (static/ e templates/) — duplicação.
- Repositório com lixo versionado: `.patch`, `.zip`, `.exe`, prints, html de teste.
- Visual "genérico de IA": amarelo em excesso, emojis, sombras e bordas
  inconsistentes, hierarquia fraca, botões de tamanhos variados.
- Rust não é necessário: o gargalo é I/O de planilhas e renderização do front,
  não CPU do Python. Os ganhos vêm de cache, servidor WSGI de verdade e um
  front que atualiza só o que mudou.

## 3. Direção visual (design system)

Inspiração: ferramentas profissionais sóbrias (Linear, Vercel dashboard, Stripe).
Interface calma, densa na medida certa, legível para quem passa o dia inteiro nela.

- **Marca**: amarelo MecatroniCar `#F9CC01` e carvão `#111827`. O amarelo é
  **acento**, não fundo: botão primário, foco, item ativo da navegação, destaques
  pontuais. Nunca grandes áreas amarelas.
- **Neutros**: escala de cinzas frios (estilo zinc/slate) para fundos, bordas e
  texto. Fundo do app levemente acinzentado, superfícies brancas.
- **Tema claro e escuro**, ambos de primeira classe, via tokens CSS
  (`data-theme="light|dark"` no `<html>`). TV é sempre escura.
- **Tipografia**: pilha do sistema — `"Segoe UI Variable Text", "Segoe UI",
  system-ui, sans-serif` (Windows já tem; zero download). Números com
  `font-variant-numeric: tabular-nums` (valores, placas, horas).
  Escala: 12 / 13 / 14 (base) / 16 / 20 / 24 / 32. Pesos 400/500/600.
- **Espaçamento**: escala de 4px (4, 8, 12, 16, 24, 32, 48).
- **Raio**: 6px (controles), 10px (cards), 14px (modais). Placa Mercosul mantém
  o visual próprio.
- **Elevação**: bordas de 1px sutis em vez de sombras pesadas; sombra só em
  modal/popover.
- **Ícones**: zero emojis na interface. Usar ícones SVG de traço (Lucide, licença
  ISC) vendorizados como sprite em `static/vendor/icons.svg`, 16/20px, stroke 1.75.
- **Cores de status do pátio** (mesmas na TV e no app, definidas em tokens):
  diagnóstico (azul), orçamento (âmbar), aprovação (laranja), peças (violeta),
  execução (ciano/teal), pronto (verde), retirada por terceiro (rosa/magenta).
  Usar como ponto/barra/etiqueta, não como fundo de card inteiro.
- **Movimento**: 120–180ms ease-out; respeitar `prefers-reduced-motion`.
- **Acessibilidade**: contraste AA, foco visível (anel amarelo), alvos ≥ 32px,
  tudo operável por teclado (atalhos: `/` ou `Ctrl+K` foca a busca, `Esc` fecha
  modal).

Os tokens oficiais ficam em `static/css/tokens.css` (criado pela tarefa T2).
Quem rodar em paralelo antes disso existir (TV, PDFs) deve seguir os valores
desta seção para que tudo bata depois.

## 4. Fases e tarefas

### Fase 1 — em paralelo (arquivos independentes)

| ID | Tarefa | Escopo de arquivos | Modelo |
|----|--------|--------------------|--------|
| T1 | Faxina do repositório e .gitignore | raiz (lixo versionado), `.gitignore`, `README` técnico | Claude Sonnet 5.5 (medium) |
| T2 | Fundação do front: design system, casca do app e modularização do JS/CSS | `static/index.html`, `static/app.js` → `static/js/*`, `static/style.css` → `static/css/*` | Claude Opus 5.5 (xhigh) |
| T3 | Painel de TV repaginado | `static/tv.*`, `templates/tv.html` (eliminar duplicata) | Claude Sonnet 5.5 (high) |
| T4 | Backend: desempenho e robustez | `server.py`, `cache.py`, `parser.py`, `app.py`, `calendar_sync.py` | Claude Opus 5.5 (high) |
| T5 | PDFs (Orçamento/OS, Checklist, Histórico) com visual profissional | `pdf_generator.py` | Claude Sonnet 5.5 (high) |
| T6 | Logos de montadoras e silhuetas de modelos | `static/brands/`, `static/models/`, `scripts/` (+ branch `wip/gemini-assets`) | Gemini 4 Argon via Antigravity (high) |

### Fase 2 — depois que T2 for mergeada em `v3-repaginacao`

Cada tela vira um módulo próprio em `static/js/views/` + `static/css/views/`,
então podem rodar em paralelo sem conflito.

| ID | Tarefa | Modelo |
|----|--------|--------|
| T7 | Início / Pátio (dashboard central, entregues recentemente, sidebars) | Claude Sonnet 5.5 (high) |
| T8 | Busca e Ficha do veículo (histórico, linha do tempo, notas, peças/serviços) | Claude Opus 5.5 (high) |
| T9 | Nova Visita / Editar OS (formulário, autocomplete, checklist, salvar no Excel) | Claude Opus 5.5 (high) |
| T10 | Copiloto Fiscal (NFS-e/NF-e, fila de pendentes) | Claude Sonnet 5.5 (high) |
| T11 | Agenda + Analytics (calendário, sidebar da secretária, painel de métricas) | Claude Sonnet 5.5 (high) |

### Fase 3 — integração

| ID | Tarefa | Modelo |
|----|--------|--------|
| T12 | Merge de todos os branches em `v3-repaginacao`, revisão de consistência visual, testes, prints finais e roteiro de release (sem tocar na `main`) | Claude Opus 5.5 (xhigh) |

## 5. Relatório final de cada tarefa

Ao terminar, responda com: branch e último commit, o que mudou, o que ficou de
fora, resultado dos testes, prints das telas e qualquer mudança de contrato.
