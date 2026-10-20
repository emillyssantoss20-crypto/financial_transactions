# Financial Transactions: qualidade de dados e risco de fraude no Databricks

> *Data quality and fraud risk pipeline on Databricks (Medallion Architecture) for millions of card transactions, with governed ingestion, data quality rules and Power BI dashboards.*

**Ferramentas:** Python · Databricks SDK · Databricks (Unity Catalog, Delta Lake, PySpark, SQL) · Power BI
**Status:** 🚧 em andamento

---

## Contexto

Uma fintech emissora de cartões contratou uma consultoria porque **não confia nos próprios dados**: os relatórios de fraude e de perdas não batem entre as áreas, e ninguém sabe dizer quais registros estão corretos.

O projeto estrutura uma base confiável e rastreável, mede a qualidade dos dados e entrega painéis de risco e de qualidade para as áreas de negócio.

## Etapas

| # | Etapa | O que envolve | Camada | Status |
|---|---|---|---|---|
| 1 | Ingestão | Ambiente no Unity Catalog, upload dos arquivos via Python e criação das tabelas brutas | Bronze | 🔄 |
| 2 | Qualidade e tratamento | Perfil dos dados, regras de qualidade, padronização, proteção de dados sensíveis e quarentena | Silver | ⬜ |
| 3 | Modelagem | Modelo estrela, indicadores de risco e tabelas agregadas | Gold | ⬜ |
| 4 | Visualização | Painéis de risco e de qualidade de dados | Power BI | ⬜ |

## Arquitetura

```
Kaggle ──► Volume ──────────► BRONZE ──────► SILVER ───────────► GOLD ────────────► Power BI
           arquivos           dados brutos   dados tratados      modelo estrela     risco e
           originais                         e quarentena        e agregados        qualidade
```

## Dados

- **Fonte:** [Financial Transactions Dataset: Analytics (Kaggle)](https://www.kaggle.com/datasets/computingvictor/transactions-fraud-datasets)
- **Natureza:** dados **sintéticos**, gerados para simular transações bancárias reais.
- **Licença:** Apache 2.0

| Arquivo | Tamanho | Conteúdo |
|---|---|---|
| `transactions_data.csv` | 1,2 GB | Transações de cartão |
| `train_fraud_labels.json` | 152 MB | Rótulo de fraude ("Yes"/"No") de 8.914.963 transações |
| `cards_data.csv` | 498 KB | 6.146 cartões: bandeira, tipo, limite, chip |
| `users_data.csv` | 161 KB | 2.000 clientes: idade, renda, dívida, score |
| `mcc_codes.json` | 5 KB | 109 códigos de categoria de comércio (MCC) |

Os arquivos não estão neste repositório por causa do tamanho e por conterem dados sensíveis simulados (número de cartão e CVV). Para reproduzir, baixe-os pelo link acima.

---

## Etapa 1: Ingestão

### 1.1 Ambiente

Criação do catálogo `financial_transactions` e dos schemas de cada camada no Unity Catalog.

| Schema | Uso |
|---|---|
| `bronze` | Arquivos originais e tabelas com os dados brutos |
| `silver` | Dados tratados e padronizados |
| `gold` | Modelo estrela e tabelas agregadas para o Power BI |
| `quality` | Regras de qualidade, quarentena e placar de qualidade |

### 1.2 Upload dos arquivos via Python

Script: 
Em vez de enviar os arquivos pela interface, o upload foi feito com o **Databricks SDK para Python**, para que possa ser repetido sempre com o mesmo resultado. O script:

1. Confere o login no Databricks, feito pela CLI com autenticação OAuth. Nenhuma senha ou token fica no código.
2. Confere o catálogo e o schema e cria o volume `arquivos`, se ainda não existir.
3. Envia os arquivos `.csv` e `.json`, mostrando tamanho e tempo de cada um.
4. Lista o conteúdo do volume ao final, para comparar os tamanhos com os originais.

Os arquivos ficam guardados no volume sem alteração, o que permite recriar qualquer tabela sem baixar os dados de novo.

### 1.3 Tabelas na Bronze

Notebook:

| Tabela | Origem | Linhas |
|---|---|---|
| `bronze.users` | users_data.csv | <!-- PREENCHER --> |
| `bronze.cards` | cards_data.csv | <!-- PREENCHER --> |
| `bronze.transactions` | transactions_data.csv | <!-- PREENCHER --> |
| `bronze.mcc_codes` | mcc_codes.json | <!-- PREENCHER --> |
| `bronze.fraud_labels` | train_fraud_labels.json | <!-- PREENCHER --> |

**Decisões**
- **Colunas dos CSVs lidas como texto.** A Bronze guarda o dado exatamente como chegou; conversões e correções ficam na Silver, onde cada uma é documentada.
- **Rastreabilidade:** todas as tabelas têm `_arquivo_origem` e `_data_ingestao`.
- **JSONs reestruturados:** os dois arquivos são um único objeto `{"chave": "valor"}`. Foram transformados em tabelas de duas colunas, com uma linha por chave.

## Como reproduzir

```powershell
# 1. Baixe os arquivos do Kaggle para uma pasta local

# 2. Crie o ambiente e instale a biblioteca
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install databricks-sdk

# 3. Instale a CLI do Databricks e faça o login
winget install Databricks.DatabricksCLI
databricks auth login --host https://<seu-workspace>.cloud.databricks.com --profile fintrans

# 4. Ajuste HOST, PASTA_LOCAL, CATALOGO e SCHEMA no upload_bases.py e rode
python upload_bases.py
```

Depois, importe o notebook `01_ingestao_bronze.py` no Databricks e execute.

**Ambiente:** Databricks Free Edition (computação serverless).

---

**Autora:** Emilly Santos · [LinkedIn](https://www.linkedin.com/in/emilly-silva-santos-b14b18177)
