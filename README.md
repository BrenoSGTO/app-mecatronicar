# 🔧 MecatroniCar - Histórico de Veículos e Serviços da Oficina

Sistema moderno e intuitivo desenvolvido sob medida para a oficina mecânica consultar o histórico completo de visitas, serviços realizados, peças trocadas e laudos de diagnóstico de qualquer veículo a partir das planilhas em Excel (`.xlsx` e `.xls`).

---

## 📥 Como Baixar e Instalar

Para usar no computador do escritório da oficina:

1. [**Clique aqui para Baixar o MecatroniCar (Versão 1.0.0)**](https://github.com/BrenoSGTO/app-mecatronicar/releases/latest/download/MecatroniCar-v1.0.0.zip)
2. Extraia o arquivo `.zip` na pasta de sua preferência (ex: em `Documentos\Projetos\APP Oficina`).
3. Dê dois cliques em **`iniciar_app.bat`** (ou dê dois cliques em **`criar_atalho_desktop.py`** para criar o atalho direto na Área de Trabalho).

---

## ✨ Principais Funcionalidades

- **🔍 Busca Instantânea:** Digite a placa (ex: `FNB 1A77` ou `FNB1A77`) ou o nome do cliente (ex: `Danilo`, `Natanael`). O sistema filtra e exibe o histórico na hora!
- **🎨 Cores Originais do Excel Preservadas:** Se uma linha de peça ou serviço foi destacada em amarelo, roxo, rosa ou verde na planilha, a mesma cor aparece no aplicativo com contraste ideal de leitura.
- **🚩 Visualização dos Triângulos Vermelhos (Comentários e Notas):** Qualquer célula com comentários (como os relatórios completos do scanner OBD2 / CodeScan ou observações do mecânico) ganha o triângulo vermelho e o botão **"Ver nota"**, com opção de copiar o texto para o WhatsApp do cliente com 1 clique.
- **📂 Abrir no Excel com 1 Clique:** Cada visita possui um botão verde **"Abrir no Excel"**, que abre imediatamente a planilha original no computador.
- **🚀 Atualização Automática para a Secretária:** Basta clicar em **"✨ Verificar Atualizações"** dentro do próprio aplicativo. Se houver uma nova versão no GitHub, um único clique em **"Atualizar Agora"** baixa e instala a atualização automaticamente sem complicação!
- **⚡ Super Rápido e Offline:** Usa um banco de dados local que indexa centenas de planilhas em frações de segundo e funciona perfeitamente sem internet na oficina.
- **📑 Suporte Completo:** Lê tanto planilhas modernas `.xlsx` quanto planilhas legadas `.xls`.

---

## 🖥️ Como Atualizar o Programa pelo Próprio App

Criado pensando na facilidade para a secretária do escritório:

1. No topo da tela do programa, clique no botão azul **"✨ Verificar Atualizações"**.
2. O programa verificará se há novidades no GitHub.
3. Se houver uma nova versão, clique em **"Atualizar Agora Automaticamente"**.
4. O aplicativo baixará os arquivos, atualizará o sistema e reiniciará sozinho!

---

## 🛠️ Tecnologias Utilizadas

- **Python 3** (Backend local, indexador e analisador de planilhas)
- **openpyxl** (Análise completa de arquivos `.xlsx`, cores e comentários)
- **xlrd** (Análise completa de arquivos legados `.xls` com formatação e notas)
- **Flask** (Servidor HTTP local leve e seguro)
- **HTML5, CSS3 Moderno e JavaScript Vanilla** (Interface sem dependência de internet externa)
- **CustomTkinter** (Interface desktop nativa opcional inclusa em `gui_desktop.py`)
- **SQLite** (Cache ultraveloz de busca e indexação)

---

## 👨‍💻 Autor

Desenvolvido por [BrenoSGTO](https://github.com/BrenoSGTO) para a oficina mecânica do seu pai.
