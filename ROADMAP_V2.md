# 🛠️ Plano Diretor & Roadmap: MecatroniCar v2.0 (Gestão Central da Oficina)

Este documento define o planejamento estratégico, arquitetural e os **Checkpoints de Desenvolvimento** para a evolução do **MecatroniCar** — saindo de um consultor de histórico (`v1.0.7`) para um **Sistema de Organização Central da Oficina (`v2.0`)**, sem jamais abandonar a segurança e compatibilidade total com as planilhas Excel (`.xlsx` / `.xls`) que os proprietários já conhecem e confiam.

---

## 🛡️ 1. Como funciona a proteção do programa atual (`Branches`, `Merge` e `Issues`)

Para garantir **risco zero** ao sistema que já está rodando na oficina hoje:

1. **Branch Principal (`main`):**
   - É onde mora a versão oficial atual (`v1.0.7`).
   - O botão **"✨ Verificar Atualizações"** no computador da secretária olha apenas para o arquivo [`version.json`](version.json) na branch `main`.
   - Enquanto não mexermos na `main`, o computador da oficina **não sofrerá nenhuma alteração acidental**.

2. **Branch de Desenvolvimento (`v2-gestao-central`):**
   - Criamos uma "linha do tempo paralela" chamada `v2-gestao-central`.
   - Todo o código novo (criação de OS, PDFs, Checklist, Painel de TV e NFs) será construído e testado aqui.

3. **Issues e Milestones (Checkpoints no GitHub):**
   - **Milestones (Marcos):** São as grandes fases do projeto (Fase 1 a Fase 6).
   - **Issues (Tarefas / Checkpoints):** São cartões numerados no GitHub para cada funcionalidade. Conforme formos programando e validando cada etapa, vamos marcando como concluída até atingir 100% da versão 2.0.

4. **Lançamento (`Merge`):**
   - Somente quando você testar a `v2.0` por completo e tiver certeza absoluta de que está pronta para o dia a dia, faremos o **Merge** (união da `v2-gestao-central` para a `main`) e subiremos o número no `version.json` para `2.0.0`. Nesse momento, bastará 1 clique em "Atualizar" na oficina.

---

## 🏗️ 2. Arquitetura dos 5 Pilares da Evolução

```
+-----------------------------------------------------------------------------------+
|                        MECATRONICAR v2.0 - GESTÃO CENTRAL                         |
+-----------------------------------------------------------------------------------+
         |                        |                        |                   |
         v                        v                        v                   v
+-----------------+    +--------------------+    +------------------+   +---------------+
| 1. MOTOR EXCEL  |    | 2. PDFs & IMPRESSÃO|    | 3. PAINEL DE TV  |   | 4. COPILOTO   |
|  BIDIRECIONAL   |    |    PROFISSIONAL    |    |  (PÁTIO AO VIVO) |   |  FISCAL (NF)  |
+-----------------+    +--------------------+    +------------------+   +---------------+
| - Cria/Edita OS |    | - Orçamento c/ Logo|    | - Rota /tv na LAN|   | - NFS-e Santos|
|   pela tela web |    |   MecatroniCar     |    | - Colunas/Cards  |   |   (Serviços)  |
| - Salva .xlsx   |    | - Checklist de     |    |   por status     |   | - NF-e 55     |
|   idêntico ao   |    |   Para-brisa (sem  |    | - Atualização    |   |   (Peças)     |
|   modelo legado |    |   preços, c/ [ ])  |    |   automática     |   | - 1 Clique    |
+-----------------+    +--------------------+    +------------------+   +---------------+
```

### Pilar 1: Motor Excel Bidirecional ("Segurança Total para os Pais")
- **Como funciona:** Quando a secretária abrir uma **Nova Visita** para um carro que já veio antes, o sistema puxa automaticamente todos os dados cadastrais da última visita (Nome, CPF, Endereço, Telefone, Marca, Modelo, Ano, Placa, Cor, Combustível, Chassi) e incrementa o número da visita automaticamente (`Visita N + 1`).
- **Espelhamento Fiel no Excel (`excel_writer.py`):** Ao clicar em **"Salvar Ficha"**, o sistema gera/atualiza imediatamente o arquivo `.xlsx` na pasta oficial da oficina, seguindo **exatamente a mesma estrutura de células e fórmulas** do modelo tradicional:
  - Nome do arquivo padronizado: `PLACA - Nº_VISITA - Nome Cliente - Modelo - Cor.xlsx`
  - Cabeçalho do Cliente nas linhas `R7..R14`, Dados do Carro em `R15..R19`, Ordem de Serviço em `R20..R24`
  - Tabela de Peças (`R28..R44`) com fórmulas `=G30*H30` e `=SUM(I30:I43)`
  - Tabela de Serviços (`R45..R50`) e Totais (`R51..R53`) com `=I44+I51`
- **Garantia Reversível:** Se seus pais abrirem a pasta pelo Windows Explorer ou clicarem em "Abrir no Excel", a planilha estará lá, 100% igual ao método antigo. Se alguém editar direto no Excel, o sistema detecta a mudança (`mtime`) e sincroniza de volta!

### Pilar 2: Orçamentos e OS em PDF de Nível Profissional
- **Fim da impressão crua de planilha:** Criação de um layout dedicado de Ordem de Serviço / Orçamento com a identidade visual oficial da **MecatroniCar** (`#f9cc01` Amarelo MecatroniCar e `#111827` Preto Carvão, com fundo branco econômico em toner para impressão).
- **Elementos do Documento:**
  - Cabeçalho com Logotipo Oficial, Razão Social (*Mecatroni Car - Serviços e Autopeças Ltda*), CNPJ `05.961.672/0001-87`, endereço e telefone.
  - Quadro estruturado de Cliente + Veículo (Placa em destaque Mercosul, Hodômetro, Data/Hora de Entrada, Defeito/Reclamação relatada).
  - Tabela separada de **Peças** e **Mão de Obra / Serviços** com subtotais claros, descontos, total geral e forma de pagamento.
  - Campo de observações técnicas / laudo do scanner e linha de assinatura do cliente.
  - Opção de **Baixar PDF** (pronto para anexar no WhatsApp do cliente com nome padronizado `Orcamento_FNB1A77_MecatroniCar.pdf`) ou **Imprimir Direto**.

### Pilar 3: Checklist de Para-brisa para os Mecânicos (Sem Valores)
- **Botão dedicado em cada carro/visita:** `📋 Imprimir Checklist (Vidro)`.
- **Conteúdo pensado para o chão de oficina:**
  - Letras grandes e de alto contraste no topo: **PLACA**, **MODELO/COR**, **CLIENTE**, **HODÔMETRO** e **QUEIXA PRINCIPAL / SINTOMA**.
  - Lista de **Peças Aprovadas** (apenas Quantidade + Descrição + Caixa `[  ] Instalado`).
  - Lista de **Serviços Aprovados** (apenas Descrição + Caixa `[  ] Executado`).
  - **Zero valores financeiros:** Nenhum preço unitário, subtotal ou total aparece nesta folha.
  - Espaço inferior para **"Observações do Mecânico / Peças Adicionais Descobertas na Desmontagem"**, **"Mecânico Responsável"** e **"Conferência Final / Teste de Rodagem"**.

### Pilar 4: Painel de TV da Oficina (Monitoramento de Pátio em Tempo Real)
- **Como a TV acessa sem precisar de servidor na nuvem:**
  - O servidor do MecatroniCar (`server.py`) no PC da secretária passará a escutar na rede local (`0.0.0.0:54321`).
  - Qualquer Smart TV, TV Box ou computador conectado ao mesmo Wi-Fi/rede da oficina poderá abrir o endereço local (ex: `http://192.168.X.X:54321/tv`) em tela cheia (`F11`).
- **Fluxo de Status dos Veículos:**
  1. 🔍 **Em Diagnóstico** (Recém-chegado / aguardando avaliação ou scanner)
  2. 📝 **Esperando Orçamento** (Mecânico já passou a lista, secretária cotando peças)
  3. ⏳ **Esperando Aprovação** (Orçamento enviado ao cliente no WhatsApp)
  4. 📦 **Esperando Peças** (Aprovado, aguardando entrega da autopeças)
  5. 🔧 **Em Execução** (Mecânico trabalhando no elevador/box)
  6. ✅ **Pronto / Esperando Cliente** (Serviço finalizado, aguardando retirada)
  7. 🔑 **Liberado p/ Retirada por Terceiro** (Destaque especial com o **nome/documento de quem está autorizado** a buscar o carro!)
- **Experiência Visual na TV:**
  - Tema escuro automotivo (`#111827`) com cabeçalho amarelo `#f9cc01`, fontes grandes legíveis a 5 metros de distância, relógio em tempo real, atualização automática a cada 5 segundos sem precisar tocar na TV, e alerta sonoro/visual opcional quando um carro muda de fase.

### Pilar 5: Acelerador de Notas Fiscais para a Secretária
- **Por que a secretária acaba deixando para depois?** Porque ela precisa copiar manualmente da planilha o CPF, Nome, Endereço, CEP, separar o que é Peça (NF-e Modelo 55 - ICMS/Autopeças) do que é Mão de Obra (NFS-e Prefeitura de Santos - ISS Item 14.01), somar cada parte e digitar tudo de novo no emissor.
- **Solução "Painel Fiscal 1-Clique" dentro da Ficha do Carro:**
  - **Separação Automática Inteligente:** O programa já divide automaticamente os itens da ficha em duas abas prontas:
    - 🟦 **Bloco 1: Nota de Serviço (NFS-e Santos - Item 14.01):** Gera automaticamente o texto discriminado completo dos serviços executados + placa/modelo/km + valor total de mão de obra + dados do tomador (CPF/CNPJ, Nome, Endereço, Bairro, CEP, Email) com botões **"Copiar Discriminação"** e **"Copiar CPF/Dados"** em 1 clique, além de exportação de lote/rascunho.
    - 🟨 **Bloco 2: Nota de Peças (NF-e Consumidor / Autopeças):** Lista enxuta das peças aplicadas com Quantidade, Descrição, Valor Unitário, Total de Peças e sugestão de classificação fiscal (NCM / CFOP padrão de revenda de autopeças / ICMS-ST), mais controle de status (`[ ] Pendente NF` -> `[x] NF Emitida nº ___`).
  - **Fila de "Notas Pendentes do Dia/Semana":** Uma aba no sistema que mostra todos os carros finalizados cuja nota fiscal ainda não foi marcada como emitida, impedindo que qualquer serviço fique esquecido!

---

## 📍 3. Checkpoints do Projeto (Milestones & Issues)

Abaixo estão os checkpoints estruturados no repositório para guiar nosso desenvolvimento passo a passo:

| Checkpoint | Fase / Milestone | Entregáveis Principais | Status |
| :--- | :--- | :--- | :--- |
| **CP-01** | **Fundação & Banco de Dados v2** | Criação de tabelas operacionais no SQLite (`patio_status`, `nf_control`, `templates`) preservando 100% do `oficina_cache.db` atual. | ⏳ Planejado |
| **CP-02** | **Motor Excel Bidirecional (`excel_writer.py`)** | Gerador e editor de planilhas `.xlsx` fiéis ao layout legado (`Plan1`), auto-preenchimento de clientes recorrentes e cálculo automático do nº da visita. | ⏳ Planejado |
| **CP-03** | **Interface de Criação e Edição de OS no App** | Modal/Tela de "Nova Visita / Editar OS" com autocompletar de clientes, veículos, catálogo rápido de peças/serviços mais usados na oficina e sincronização imediata com o Excel. | ⏳ Planejado |
| **CP-04** | **Checklist de Para-brisa (PDF sem Valores)** | Botão `📋 Checklist Mecânico` em cada visita gerando documento limpo com placa gigante, sintomas, checkboxes `[ ]` de peças e serviços aprovados e campo de anotações. | ⏳ Planejado |
| **CP-05** | **Orçamento & OS Profissional em PDF** | Novo gerador de Orçamento/OS com logotipo MecatroniCar, dados fiscais da empresa, tabelas estilizadas de Peças e Serviços, termos de garantia e botão de compartilhamento rápido. | ⏳ Planejado |
| **CP-06** | **Painel de TV da Oficina (`/tv`)** | Servidor acessível na rede local (LAN), painel Kanban/Grid para TV em tela cheia com os 7 status de pátio, aviso de "Retirada por Terceiro" e controle rápido pela secretária. | ⏳ Planejado |
| **CP-07** | **Copiloto de Notas Fiscais (Peças + Serviços)** | Painel de emissão rápida com separação automática NFS-e (Serviços) vs NF-e (Peças), copiador inteligente em 1 clique, fila de notas pendentes e marcação de NFs emitidas. | ⏳ Planejado |
| **CP-08** | **Testes, Empacotamento e Release `v2.0.0`** | Validação completa com planilhas reais, geração do novo instalador Windows e merge seguro para a branch `main`. | ⏳ Planejado |
