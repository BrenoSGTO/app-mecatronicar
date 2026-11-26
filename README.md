# 🔧 MecatroniCar - Histórico de Veículos e Serviços da Oficina

<p align="center">
  <img src="static/logo.png" alt="MecatroniCar Logo" width="160" />
</p>

Sistema moderno e intuitivo desenvolvido sob medida para a oficina mecânica **MecatroniCar** consultar o histórico completo de visitas, serviços realizados, peças trocadas e laudos de diagnóstico de qualquer veículo a partir das planilhas em Excel (`.xlsx` e `.xls`).

---

## 📥 Como Baixar e Instalar (Super Simples para a Secretária)

Criado para ser 100% automático, sem necessidade de descompactar pastas ou rodar comandos:

1. [**👉 Clique aqui para Baixar o Instalador (Instalar-MecatroniCar.exe)**](https://github.com/BrenoSGTO/app-mecatronicar/releases/latest/download/Instalar-MecatroniCar.exe)
2. Abra o arquivo **`Instalar-MecatroniCar.exe`**.
3. Na janela do instalador, confirme a opção de adicionar o atalho na Área de Trabalho e clique em **"Instalar e Abrir"**.
4. O programa será instalado automaticamente na pasta de programas do computador e abrirá na hora com o atalho oficial na Área de Trabalho!

---

## ✨ Principais Funcionalidades

- **🔍 Busca Instantânea:** Digite a placa (ex: `FNB 1A77` ou `FNB1A77`) ou o nome do cliente (ex: `Danilo`, `Natanael`). O sistema filtra e exibe o histórico na hora!
- **🎨 Cores Originais do Excel Preservadas:** Se uma linha de peça ou serviço foi destacada em amarelo, roxo, rosa ou verde na planilha, a mesma cor aparece no aplicativo com contraste ideal de leitura.
- **🚩 Visualização dos Triângulos Vermelhos (Comentários e Notas):** Qualquer célula com comentários (como os relatórios completos do scanner OBD2 / CodeScan ou observações do mecânico) ganha o triângulo vermelho e o botão **"Ver nota"**, com opção de copiar o texto para o WhatsApp do cliente com 1 clique.
- **📂 Abrir no Excel com 1 Clique:** Cada visita possui um botão verde **"Abrir no Excel"**, que abre imediatamente a planilha original no computador.
- **📄 Impressão com ou sem Valores:** 
  - **`🖨️ Imprimir`**: Imprime a ficha completa com preços e totais.
  - **`📄 Imprimir sem Valores`**: Imprime uma via limpa para o cliente ou para a oficina sem exibir as colunas de preços, valores unitários e totais.
- **🚀 Atualização Automática para a Secretária:** Basta clicar em **"✨ Verificar Atualizações"** dentro do próprio aplicativo. Se houver uma nova versão no GitHub, um único clique em **"Atualizar Agora"** baixa e instala a atualização automaticamente sem complicação!
- **⚡ Super Rápido e Offline:** Usa um banco de dados local que indexa centenas de planilhas em frações de segundo e funciona perfeitamente sem internet na oficina.
- **📑 Suporte Completo:** Lê tanto planilhas modernas `.xlsx` quanto planilhas legadas `.xls`.

---

## 🖥️ Como Atualizar o Programa pelo Próprio App

1. No topo da tela do programa, clique no botão **"✨ Verificar Atualizações"**.
2. O programa verificará se há novidades no GitHub.
3. Se houver uma nova versão, clique em **"Atualizar Agora Automaticamente"**.
4. O aplicativo atualizará os arquivos e reiniciará sozinho, mantendo todas as planilhas e histórico salvos!

---

## 🗺️ Mapa da pasta (para quem mexe no código)

| Onde | O que é |
|---|---|
| `app.py` | **Ponto de partida.** Sobe o servidor e abre a janela do app (`python app.py`). |
| `server.py` | Servidor Flask: todas as rotas `/api/...` que a tela usa. |
| `parser.py` | Lê as planilhas `.xlsx`/`.xls` (peças, serviços, cores, notas). |
| `cache.py` | Banco local SQLite que indexa as planilhas para a busca ser instantânea. |
| `excel_writer.py` | Grava uma OS nova/editada na planilha (mantém o formato do Excel). |
| `pdf_generator.py` | Gera Orçamento e Checklist em PDF. |
| `nf_copilot.py` | Copiloto Fiscal: separa NFS-e (serviços) e NF-e (peças). |
| `calendar_sync.py` | Agendamentos. |
| `updater.py` + `version.json` | Botão "Verificar atualizações" (lê o `version.json` da `main`). |
| `config.py` / `config.json` | Configuração local (pasta das planilhas). `config.json` não vai para o Git. Agenda, Copiloto Fiscal e Analytics só aparecem com `"modulos_em_teste": true` nele. |
| `static/` | A interface: `index.html`, `js/` (telas em `js/views/`), `css/` (telas em `css/views/`), logos das marcas (`brands/`), silhuetas (`models/`), catálogo FIPE de marcas/modelos (`vehicle_catalog.js`) e a TV (`tv.*`). |
| `templates/` | Modelo de planilha usado para OS novas e página da TV. |
| `planilhas_exemplo/` | Planilhas fictícias para testar sem tocar nas reais. |
| `tests/` | Testes automáticos (`python -m pytest -q`). |
| `docs/` | Planos, roadmap, notas de release, prints e issues antigas. |
| `scripts/` | Ferramentas de desenvolvimento (gerar release, benchmark, gerar ícones, baixar logos e a tabela FIPE: `vehicle_brands.py`, `fetch_fipe_catalog.py`, `build_vehicle_catalog.py`). |
| `packaging/` | Código do instalador e do atalho `.exe`. |
| `gerar_massa_dados.py` | Gera planilhas fictícias em massa para testes. |
| `gui_desktop.py`, `criar_atalho_desktop.py`, `iniciar_app*.bat/.vbs`, `Instalar-MecatroniCar.bat` | Atalhos e alternativas de inicialização no Windows. |

---

## 👨‍💻 Autor

Desenvolvido por [BrenoSGTO](https://github.com/BrenoSGTO) para a oficina mecânica do seu pai.
