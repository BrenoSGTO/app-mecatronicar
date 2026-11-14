## Descrição
Criar um módulo de agendamento de atendimentos na oficina, permitindo registrar previsões de chegada de veículos pela TV/oficina e integrá-los diretamente na tela da secretária para entrada ágil na oficina sem gerar planilhas acidentais.

## Requisitos
1. **Aba de Calendário na Janela da TV:**
   - Adicionar uma aba/seção dedicada no painel da TV para visualização e cadastro de agendamentos.
   - Formulário de cadastro de agendamento contendo:
     - Nome do cliente
     - Telefone de contato
     - Carro (placa e/ou modelo)
     - Título do problema
     - Descrição do problema / sintomas relatados
     - Data e horário agendados
   - Armazenar esses agendamentos em tabela dedicada no banco de dados SQLite (`oficina_cache.db`).
   - (Nota: a integração com o Google Calendar fica preparada para etapa posterior).
2. **Exibição na Sidebar do Programa da Secretária:**
   - Exibir a lista de agendamentos futuros na Sidebar Direita da tela principal da secretária.
   - Destaque para agendamentos do dia atual e próximos dias.
3. **Conversão de Agendamento em Ficha de Entrada:**
   - Na sidebar da secretária, adicionar ação "Dar Entrada / Criar Ficha" ao lado do agendamento.
   - Ao clicar, abrir o modal de Nova Visita/OS com os campos pré-preenchidos (mesmo que com informações iniciais) para que a secretária refine os dados cadastrais e técnicos.
   - **Regra Importante:** Não gerar arquivo Excel (.xlsx) até que a secretária clique conscientemente em "Salvar", evitando planilhas vazias ou fantasmas de clientes que não compareceram.
