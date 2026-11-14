# 🚀 Guia de Lançamento: MecatroniCar v2.0.0 (Gestão Central)

Documento oficial de homologação e guia para o **Merge Seguro** da branch `v2-gestao-central` para a branch `main`.

---

## 📋 Sumário Executivo

O **MecatroniCar v2.0.0** representa a maior evolução do sistema desde a sua concepção. O software transcendeu o papel de mero consultor de histórico (`v1.0.7`) para se tornar a **central operacional e de gestão da oficina mecânica**, mantendo como princípio inegociável a **segurança total das planilhas legadas em Excel (`.xlsx` e `.xls`)**.

Todos os 8 Checkpoints planejados no [ROADMAP_V2.md](ROADMAP_V2.md) foram integralmente implementados e aprovados com 100% de cobertura nos testes automatizados.

---

## 🌟 Os 5 Pilares Entregues na Versão 2.0.0

### 1. Motor Excel Bidirecional e Criação de OS (`excel_writer.py`)
- Criação e edição de Ordens de Serviço diretamente pela interface web.
- Gravação nativa no Excel (`.xlsx`) espelhando com precisão matemática o modelo legado da oficina (`Plan1`, células A1:I54, fórmulas `=G*H`, `=SUM(I30:I43)`, `=I44+I51-G52`).
- Injeção em nível OpenXML de valores calculados (`<v>`), permitindo que a visualização sem recálculo continue perfeita.
- Autocompletar inteligente de clientes e veículos cadastrados.
- Numeração automática sequencial de visitas (`Visita N + 1`).

### 2. Checklist Operacional de Para-brisa (PDF sem Valores)
- Rota dedicada `/api/checklist_pdf` e botão `📋 Checklist Para-brisa` na linha do tempo.
- Folha de chão de oficina focada na execução técnica: placa em destaque gigante, sintomas relatados, checkboxes `[ ]` para cada peça e serviço aprovado.
- **Zero valores financeiros** exibidos no papel, resguardando o sigilo comercial e a negociação da secretária.

### 3. Orçamento e OS Profissional em PDF
- Rota `/api/orcamento_pdf` e botão `📄 Imprimir Orçamento (PDF)`.
- Identidade visual oficial da **MecatroniCar**: Amarelo `#f9cc01` e Preto Carvão `#111827`, com fundo branco econômico em consumo de toner.
- Logotipo oficial, razão social (*Mecatroni Car - Serviços e Autopeças Ltda*), CNPJ `05.961.672/0001-87`, termos de garantia de 90 dias e linhas de assinatura.
- Pronto para impressão direta ou salvamento em PDF para envio via WhatsApp ao cliente.

### 4. Painel de TV da Oficina (`/tv` na Rede Local)
- Servidor ouvindo em rede local (`0.0.0.0:54321`) permitindo acesso por Smart TVs, TV Boxes, tablets ou celulares conectados ao Wi-Fi da oficina.
- Painel de 7 colunas cobrindo o fluxo de pátio:
  1. *Em Diagnóstico*
  2. *Esperando Orçamento*
  3. *Esperando Aprovação*
  4. *Esperando Peças*
  5. *Em Execução*
  6. *Pronto / Esperando Cliente*
  7. *Liberado p/ Retirada por Terceiro*
- Destaque em vermelho/alerta sonoro quando um veículo está autorizado para retirada por terceiro, exibindo nome e documento do retirante.
- Atualização em tempo real (polling a cada 5 segundos) e relógio digital integrado.

### 5. Copiloto Fiscal Inteligente (NFS-e Santos + NF-e Peças)
- Rota `/api/nf` e modal integrado `📑 Copiloto Fiscal`.
- Separação automatizada entre serviços (NFS-e Prefeitura de Santos Item 14.01) e peças (NF-e Modelo 55 - ICMS/Autopeças com CFOP 5405 / ST).
- Copiador 1-clique de dados do tomador e texto padrão de discriminação dos serviços.
- Fila e painel de controle de notas fiscais pendentes com indicadores de valor acumulado a emitir.
- Exportação em lote para contabilidade nos formatos CSV e TXT.

---

## 🧪 Validação dos Testes Integrados Automatizados

A suíte completa de testes unitários e de integração foi executada com 100% de sucesso:

```bash
python -m unittest test_cp01_database.py test_excel_writer.py test_v2_integration.py
```

**Resultado:**
- `Ran 15 tests in ~2.0s`
- **Status:** `OK` (0 falhas, 0 erros, 0 alertas de vazamento de recursos).
- `oficina_cache.db` preservado com suas 4 planilhas de referência intactas e isolamento garantido para gravações de teste.

---

## 🔒 Passo a Passo para o Merge Seguro na Branch `main`

> [!IMPORTANT]
> O procedimento abaixo só deve ser executado no momento em que você decidir homologar e disponibilizar a versão 2.0.0 para os computadores da oficina.

### Passo 1: Garantir que a branch de trabalho esteja limpa e commitada
```bash
git checkout v2-gestao-central
git status
```

### Passo 2: Ir para a branch `main` e atualizá-la
```bash
git checkout main
git pull origin main
```

### Passo 3: Executar o Merge da branch `v2-gestao-central`
```bash
git merge v2-gestao-central --no-ff -m "chore: merge v2-gestao-central (release v2.0.0)"
```

### Passo 4: Rodar a suíte de testes na branch `main`
```bash
python -m unittest test_cp01_database.py test_excel_writer.py test_v2_integration.py
```

### Passo 5: Criar a Tag de Versão `v2.0.0`
```bash
git tag -a v2.0.0 -m "MecatroniCar v2.0.0 - Gestão Central da Oficina"
```

### Passo 6: Publicar para o GitHub
```bash
git push origin main
git push origin v2.0.0
```

---

## 🛟 Procedimento de Rollback de Emergência (Se Necessário)

Caso qualquer imprevisto aconteça na oficina após o merge, você pode retornar a branch `main` para a versão `1.0.7` em segundos:

```bash
git checkout main
git reset --hard 522e6f2  # Commit estável da versão 1.0.7
git push origin main --force
```
