## Descrição
Implementar personalização interativa para a emissão do Checklist de chão de oficina / vidro e adicionar uma janela seletora de visitas antes da impressão do histórico do veículo.

## Requisitos
1. **Customização Interativa do Checklist (`pdf_generator.py` e modal no frontend):**
   - Antes de imprimir o checklist, exibir um modal de configuração onde o operador possa:
     - Marcar/desmarcar quais itens e serviços da visita devem aparecer na folha impressa.
     - Adicionar itens manualmente sob demanda (ex: observação pontual do chefe de oficina).
     - Ativar/desativar a inclusão dos códigos de falha do scanner OBD2.
   - Remover permanentemente as seções desnecessárias da folha de checklist:
     - Observações longas e notas textuais.
     - Bloco de assinatura do mecânico responsável.
     - Seção de conferência final e teste de rodagem.
2. **Seleção Prévia de Visitas para Impressão:**
   - Ao solicitar a impressão do histórico de visitas de um veículo (que pode conter até 50 visitas), abrir um modal com a listagem de todas as visitas (data, número da visita, resumo dos serviços).
   - Permitir ao usuário marcar com checkboxes quais visitas deseja imprimir (ou opções rápidas: "Apenas última", "Últimas 3", "Todas").
   - Gerar o PDF/impressão consolidado contendo exclusivamente as visitas selecionadas, evitando impressão excessiva de páginas.
