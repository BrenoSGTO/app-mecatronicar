## Descrição
Reformular a tela inicial da aplicação (`static/index.html` e `static/app.js`) para torná-la um painel de comando central com foco na operação diária da oficina, conforme esboço fornecido pelo cliente.

## Requisitos
1. **Área Central - Carros Ativos no Pátio:**
   - Exibir todos os carros que estão com algum estado ativo na oficina (ex: 'Diagnóstico', 'Orçamento', 'Aguardando Peças', 'Em Execução', 'Aguardando Retirada').
   - Cada carro deve ter um card grande de fácil visualização contendo:
     - Placa no estilo oficial Mercosul da MecatroniCar (com faixa azul superior 'BRASIL', badge e texto destacado).
     - Modelo do veículo.
     - Os 2 primeiros nomes do dono do carro (ex: "Danilo Pereira").
     - Status atual com cor semântica e tempo na oficina.
2. **Aba "Entregues Recentemente":**
   - Ao marcar um carro como 'Entregue', ele deve sair da visualização central ativa e ir para a aba "Entregues Recentemente".
   - Os carros entregues ficam acessíveis nessa aba por 2 dias para consultas rápidas sem poluir a tela principal. Após 2 dias, ficam acessíveis via busca global.
3. **Sidebar Esquerda - Histórico Recente:**
   - Exibir uma lista rápida com os últimos veículos acessados/atendidos na oficina recentemente para navegação ágil.
4. **Sidebar Direita - Agendamentos e Calendário:**
   - Exibir os agendamentos futuros vindos da agenda da oficina (integrando com o módulo de calendário).
5. **Acesso Direto:**
   - Clicar em qualquer card abre instantaneamente os detalhes e histórico do veículo.
