# Financial Transactions: qualidade de dados e risco de fraude no Databricks

> *Data quality and fraud risk pipeline on Databricks (Medallion Architecture) for 13.3 million card transactions, with governed ingestion, data quality rules and Power BI dashboards.*

**Ferramentas:** Python · Databricks SDK · Databricks (Unity Catalog, Delta Lake, PySpark, SQL) · Power BI
**Status:** 🚧 em andamento

---

## Contexto

Uma fintech americana emissora de cartões contratou uma consultoria porque **não confia nos próprios dados**: os relatórios de fraude e de perdas não batem entre as áreas, e ninguém sabe dizer quais registros estão corretos.

O projeto estrutura uma base confiável e rastreável, mede a qualidade dos dados e entrega painéis de risco e de qualidade para as áreas de negócio.

## Etapas

| # | Etapa | O que envolve | Camada | Status |
|---|---|---|---|---|
| 1 | Ingestão | Ambiente no Unity Catalog, upload dos arquivos via Python e criação das tabelas brutas | Bronze | ✅ |
| 2 | Qualidade e tratamento | Perfil dos dados, padronização, proteção de dados sensíveis, regras de qualidade e quarentena | Silver | 🚧 |
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
- **Licença:** [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0), conforme a página do dataset no Kaggle.

| Arquivo | Tamanho | Conteúdo |
|---|---|---|
| `transactions_data.csv` | 1,2 GB | 13.305.915 transações de cartão |
| `train_fraud_labels.json` | 152 MB | Rótulo de fraude ("Yes"/"No") de 8.914.963 transações |
| `cards_data.csv` | 498 KB | 6.146 cartões: bandeira, tipo, limite, chip |
| `users_data.csv` | 161 KB | 2.000 clientes: idade, renda, dívida, score |
| `mcc_codes.json` | 5 KB | 109 códigos de categoria de comércio (MCC) |

**Fonte complementar:** [Gazetteer Files 2020 do Censo dos EUA](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html) (arquivo *Places*), com cerca de 32 mil cidades americanas e suas coordenadas. É um dado público do governo americano, usado para descobrir a cidade e o estado de cada cliente.

Os dados são dos **Estados Unidos**: valores em dólar, estados e CEPs americanos.

---

## Etapa 1: Ingestão

### 1.1 Ambiente

Criação do catálogo `financial_transactions` no Unity Catalog, com um schema para cada camada:

| Schema | Uso |
|---|---|
| `bronze` | Volume com os arquivos originais e tabelas com os dados brutos |
| `silver` | Dados tratados e padronizados |
| `gold` | Modelo estrela e tabelas agregadas para o Power BI |
| `quality` | Regras de qualidade, quarentena e placar de qualidade |

### 1.2 Upload dos arquivos via Python

Script: [`upload_bases.py`](upload_bases.py)

Em vez de enviar os arquivos pela interface, o upload foi feito com o **Databricks SDK para Python**, para que possa ser repetido sempre com o mesmo resultado. O script:

1. Confere o login no Databricks, feito pela CLI com autenticação OAuth. Nenhuma senha ou token fica no código.
2. Confere o catálogo e o schema e cria o volume `arquivos`, se ainda não existir.
3. Envia os arquivos `.csv` e `.json`, mostrando tamanho e tempo de cada um.
4. Lista o conteúdo do volume ao final, para comparar os tamanhos com os originais.

Os arquivos ficam guardados no volume sem alteração, o que permite recriar qualquer tabela sem baixar os dados de novo.

### 1.3 Tabelas na Bronze

Notebook: [`Ingest bronze.ipynb`](Ingest%20bronze.ipynb)

| Tabela | Origem | Linhas |
|---|---|---|
| `bronze.users` | users_data.csv | 2.000 |
| `bronze.cards` | cards_data.csv | 6.146 |
| `bronze.transactions` | transactions_data.csv | 13.305.915 |
| `bronze.mcc_codes` | mcc_codes.json | 109 |
| `bronze.fraud_labels` | train_fraud_labels.json | 8.914.963 |

**Decisões**
- **Colunas dos CSVs lidas como texto.** A Bronze guarda o dado exatamente como chegou; conversões e correções ficam na Silver, onde cada uma é documentada.
- **Rastreabilidade:** todas as tabelas têm `_arquivo_origem` e `_data_ingestao`.
- **JSONs reestruturados:** os dois arquivos são um único objeto `{"chave": "valor"}`. Foram transformados em tabelas de duas colunas, com uma linha por chave.

### 1.4 Primeiras observações de qualidade

Pontos encontrados numa análise inicial, que serão tratados na Etapa 2:

- **Valores monetários como texto**, com "$" (limite de crédito, renda e dívida).
- **Dados sensíveis expostos:** número do cartão e CVV; endereço e coordenadas dos clientes.
- **Coluna sem informação:** `card_on_dark_web` é "No" em todos os cartões.
- **Padrões diferentes de sim/não:** "YES/NO" em `has_chip` e "No" em `card_on_dark_web`

---

## Etapa 2: Qualidade e tratamento

### 2.1 Tabelas na Silver

Notebook: [`processing silver.ipynb`](processing%20silver.ipynb)

| Tabela | Principais tratamentos |
|---|---|
| `silver.users` | Tipos convertidos, "$" removido dos valores, **cidade e estado** adicionados; endereço e coordenadas removidos |
| `silver.cards` | Número do cartão **mascarado** (só os 4 últimos dígitos), **CVV removido**, datas "MM/AAAA" convertidas em data, sim/não convertido em verdadeiro/falso |
| `silver.transactions` | Data e hora convertidas, valor em número, CEP padronizado com 5 dígitos, `use_chip` renomeada para `transaction_type` |
| `silver.mcc_codes` | Código convertido em número |
| `silver.fraud_labels` | Id da transação em número e rótulo "Yes/No" em verdadeiro/falso |

Cada tabela segue o mesmo padrão: **formatação, tratamento** e **conferência**. A conferência é uma validação rápida feita logo após a criação. Ela compara as linhas da Bronze com as da Silver e verifica se alguma conversão deixou valores vazios.

| Tabela | Resultado ideal da conferência |
|---|---|
| `silver.users` | 2.000 linhas na Bronze e na Silver, 0 clientes sem cidade e quase todos a até 10 km da cidade encontrada |
| `silver.cards` | 6.146 linhas nas duas e 0 vazios em validade, abertura, limite, chip e dark web |
| `silver.transactions` | 13.305.915 linhas nas duas, 0 datas, valores e MCC vazios e 1.652.706 CEPs vazios (o mesmo número da Bronze) |
| `silver.mcc_codes` | 109 linhas nas duas e 0 códigos ou descrições vazias |
| `silver.fraud_labels` | 8.914.963 linhas nas duas, 0 vazios e 13.332 fraudes |

### 2.2 Cidade e estado dos clientes

A base de clientes traz só o endereço da rua e as coordenadas, sem cidade nem estado. Para permitir análises por região sem guardar dados pessoais:

1. A tabela de cidades do Censo foi carregada na Bronze (`bronze.place_2020`).
2. Para cada cliente, foi calculada a distância em km até todas as cidades (fórmula de Haversine) e escolhida a mais próxima.
3. Na Silver ficam só a cidade e o estado. O endereço e as coordenadas exatas não seguem adiante.

### 2.3 Validação da Silver

Notebook: [`validation silver.ipynb`](validation%20silver.ipynb)

Após o tratamento, as tabelas da Silver foram medidas em seis dimensões de qualidade. Cada verificação gera uma tabela com o **resultado** e a **ação** (prosseguir ou avaliar).

| Dimensão | O que verifica | Resultado na Bronze |
|---|---|---|
| Unicidade | Ids repetidos | Nenhum id repetido |
| Completude | Campos vazios | Vazios em `merchant_state` (1.563.700), `zip` (1.652.706) e `errors` (13.094.522) nas transações |
| Formato | Valores que não viram número ou data | Todos convertíveis |
| Valores possíveis | Valores fora de faixas reais | Idade 101 (1), renda per capita zero (15), limite zero (31), transações de valor zero (103.969) |
| Coerência | Colunas que se contradizem | Renda per capita maior que a anual (34), cartão aberto no mês do vencimento (248), idade acima da aposentadoria (277, alerta) |
| Integridade | Ligações entre tabelas | Nenhum registro sem correspondência |

| Verificação | O que verifica | Resultado ideal |
|---|---|---|
| Formato | Se cada coluna ficou com o tipo esperado e se alguma conversão deixou valores vazios (vazios da Silver × Bronze) | 0 colunas com tipo errado e 0 falhas de conversão |
| Valores possíveis | Se os valores estão dentro de faixas reais e se cidade e estado foram preenchidos | Os mesmos casos encontrados na Bronze, sem casos novos |
| Coerência | Se colunas relacionadas não se contradizem | Os mesmos casos encontrados na Bronze, sem casos novos |

Encontrar os mesmos casos da Bronze mostra que o tratamento não perdeu nem criou problemas. Esses casos viram as regras de alerta e quarentena da próxima etapa.

### 2.4 Decisões

- **Dados sensíveis ficam só na Bronze.** Número completo do cartão, CVV, endereço e coordenadas não chegam à Silver nem ao Power BI.
- **Valores suspeitos não são apagados.** Idade 101, limite zero e renda zero seguem na Silver e serão marcados por regras de qualidade (alerta). Só as transações de valor zero são candidatas à quarentena.
- **Datas "MM/AAAA":** a abertura da conta vira o primeiro dia do mês e a validade do cartão vira o último dia, porque o cartão vale até o fim do mês.

---

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

Depois, importe os notebooks no Databricks e execute nesta ordem: `Ingest bronze`, `processing silver` e `validation silver`. Para a cidade dos clientes, suba o arquivo de *Places* do Censo pela interface do Databricks como `bronze.place_2020`.

**Ambiente:** Databricks Free Edition (computação serverless).

## Estrutura do repositório

```
├── upload_bases.py          # Etapa 1: upload dos arquivos para o volume
├── Ingest bronze.ipynb      # Etapa 1: criação das tabelas Bronze
├── processing silver.ipynb  # Etapa 2: tratamento das tabelas Silver (com cidade e estado)
├── validation silver.ipynb  # Etapa 2: validação de qualidade da Silver
├── imagens/                 # prints usados neste README
├── .gitignore               # impede o envio das bases e de credenciais
└── README.md
```

---

**Autora:** Emilly Santos · [LinkedIn](https://www.linkedin.com/in/emilly-silva-santos-b14b18177)
