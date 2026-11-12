## Descrição
Ao tentar criar ou salvar uma ficha manualmente no sistema através do modal de Nova Visita / OS, ocorre o seguinte erro no navegador:
`Erro de conexão ao salvar: Unexpected token '<', "<!doctype "... is not valid JSON`

## Objetivos e Requisitos
1. **Tratamento Robusto na API (`server.py`):**
   - Garantir que todas as rotas `/api/*` (especialmente `/api/save_order`) sempre retornem payload JSON válido, inclusive em casos de erro 400, 404, 422 ou 500, impedindo o retorno das páginas HTML padrão de erro do Flask.
   - Tratar exceções internas do `excel_writer.save_order_to_excel` e `cache.index_single_file` retornando `{ "success": false, "error": "mensagem legível" }`.
2. **Tratamento no Frontend (`static/app.js`):**
   - Verificar `res.ok` e o cabeçalho `Content-Type` antes de executar `res.json()`.
   - Se o servidor responder com status diferente de 200 ou com HTML, capturar o erro e exibir um alerta amigável e explicativo para o usuário.
3. **Validação do Fluxo de Criação Manual:**
   - Testar o fluxo completo de cadastro de nova visita manual com novo cliente, novo carro e serviços/peças, confirmando a criação da planilha `.xlsx` e a correta indexação no banco de dados.
