## Descrição
Criar uma base de dados realista com aproximadamente 200 planilhas de Excel (`.xlsx`) simulando clientes, veículos e visitas na oficina MecatroniCar para fins de testes e homologação completa da aplicação.

## Requisitos
1. **Geração de 200 Planilhas Excel (.xlsx):**
   - Criar um script dedicado (ex: `gerar_massa_dados.py` ou comando de seed) gerando 200 planilhas no padrão oficial aceito pelo `parser.py` e gerado por `excel_writer.py`.
   - Variação rica de dados:
     - Diferentes clientes fictícios com nomes completos brasileiros realistas.
     - Quantidades variadas de visitas por cliente/veículo (clientes novos com 1 visita até clientes fiéis com 10 a 50 visitas).
     - Alguns clientes com múltiplos carros (ex: 2 a 4 veículos).
     - Alguns veículos transferidos que já pertenceram a mais de um cliente (histórico cruzado com mudança de proprietário).
     - Peças automotivas reais (pastilhas, discos, amortecedores, filtros, óleo 5W30, correias, velas, etc.) com valores de mercado coerentes.
     - Serviços de mão de obra reais (alinhamento, troca de óleo, diagnóstico eletrônico, revisão preventiva, suspensão, etc.).
     - Status de pátio distribuídos: 'Orçamento', 'Aguardando Peças', 'Em Execução', 'Aguardando Retirada', 'Entregue'.
     - Datas e horas distribuídas ao longo dos últimos meses/anos para alimentar o histórico e os analytics.
2. **Indexação e Carga:**
   - Salvar as planilhas na pasta `planilhas_exemplo/` ou pasta de dados configurada.
   - Executar a indexação e verificar a integridade da base `oficina_cache.db` com queries de teste.
