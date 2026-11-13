## Descrição
Reformular a tela do Painel de TV da Oficina (`/tv`, `templates/tv.html` e `static/tv.js`) substituindo o formato de colunas kanban por uma grade moderna e dinâmica que preenche a tela inteira sem deixar sensação de oficina vazia.

## Requisitos
1. **Layout em Grade Ordenada por Fase:**
   - Não separar a tela por colunas verticais fixas.
   - Organizar todos os carros em formato de grade (grid CSS dinâmico).
   - Ordenar os cards pela fase operacional do veículo (ex: Diagnóstico -> Orçamento -> Aguardando Peças -> Em Execução -> Aguardando Retirada -> Finalizado), garantindo que veículos na mesma fase fiquem automaticamente agrupados lado a lado.
2. **Indicador Visual de Fase:**
   - Cada card de veículo deve ter um indicador/badge de destaque nítido indicando em qual fase o carro se encontra, com cores semânticas bem contrastantes para visualização a distância em TVs.
3. **Ajuste Automático de Tamanho (Auto-Fit / Tela Cheia):**
   - O tamanho dos cards deve se ajustar dinamicamente em proporção à quantidade total de carros no pátio.
   - Quer haja 2 carros, 8 carros ou 25 carros, os cards devem expandir para preencher toda a tela da TV de forma proporcional e elegante, eliminando grandes áreas pretas vazias.
4. **Atualização em Tempo Real:**
   - Manter a atualização automática via polling/intervalo suave sem recarregar a página inteira.
