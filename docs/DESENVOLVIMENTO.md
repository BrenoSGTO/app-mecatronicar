# Desenvolvimento

## Rodar em desenvolvimento

```powershell
pip install -r requirements.txt
python app.py        # abre o app numa janela do Edge/Chrome (--app), porta 54321
python server.py     # apenas o servidor Flask, sem janela
```

Na primeira execução o app cria sozinho `config.json` e `oficina_cache.db`
(ambos ignorados pelo git). Para testar use a pasta `planilhas_exemplo/`.
O painel da TV fica em `http://localhost:54321/tv`.

## Testes

```powershell
python -m pytest -q
```

Os `test_*.py` ficam por enquanto na raiz (mover para `tests/` está previsto
para a Fase 3, depois dos merges das outras tarefas).

## Estrutura de pastas

| Caminho | Conteúdo |
|---|---|
| `app.py`, `server.py` | Janela/launcher e API Flask (`/api/*`) |
| `parser.py`, `cache.py`, `excel_writer.py` | Leitura das planilhas, cache SQLite, gravação `.xlsx` |
| `pdf_generator.py`, `nf_copilot.py`, `calendar_sync.py` | PDFs, Copiloto Fiscal, agenda |
| `updater.py`, `version.json` | Atualização automática |
| `static/` | Front-end (HTML/JS/CSS puros, 100% offline) |
| `templates/` | `template_os.xlsx` e páginas servidas pelo Flask |
| `planilhas_exemplo/` | Planilhas de exemplo para desenvolvimento |
| `packaging/` | Fontes C# do launcher (`MecatroniCar.exe`) e do instalador |
| `scripts/` | Utilitários (`build_release.ps1`, geração de assets) |
| `docs/` | Documentação, plano da repaginação, `screenshots/`, `issues/` |

## Branches

- `main`: **produção congelada**. A secretária usa esta versão; não se faz
  commit nem push nela durante a v3.
- `v3-repaginacao`: integração da repaginação v3.
- `v3/<tarefa>`: um branch por tarefa, criado a partir de `v3-repaginacao`,
  com commits pequenos e rebase antes do merge.

## Build de release (artefatos não versionados)

`MecatroniCar.exe`, `Instalar-MecatroniCar.exe` e `*.zip` não ficam no git:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
```

Usa o `csc.exe` do .NET Framework que já vem no Windows e gera em `dist\`:
`MecatroniCar.exe` (launcher), `MecatroniCar-v<versão>.zip` (app + exe, layout
plano) e `Instalar-MecatroniCar.exe` (instalador com o zip embutido).
O script não altera `version.json`, não cria tag nem release.

## Atualização automática

O botão "Verificar Atualizações" (`updater.py`) lê
`https://raw.githubusercontent.com/BrenoSGTO/app-mecatronicar/main/version.json`
e compara com `CURRENT_VERSION`; se houver versão maior, baixa o `download_url`
(zip do release), extrai, e um `.bat` copia os arquivos por cima preservando
`config.json` e `oficina_cache.db`, depois reabre o app. Se o `version.json`
falhar, usa a última GitHub Release como alternativa.
Por isso o `version.json` na `main` e o `CURRENT_VERSION` só mudam em um
release oficial.
