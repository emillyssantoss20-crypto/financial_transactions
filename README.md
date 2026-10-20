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
| `silver.transactions` | 13.295.276 linhas nas duas, 0 datas, valores e MCC vazios e 1.652.706 CEPs vazios (o mesmo número da Bronze) |
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

#### 2.3.1. Unicidade
Verifica se cada tabela tem um id diferente por linha. Se o total de linhas for diferente do total de ids distintos, há ids repetidos.

**Ideal:** linhas e ids iguais em todas as bases.

<img width="1145" height="298" alt="image" src="https://github.com/user-attachments/assets/35d7f17d-4fbb-4d51-bc6d-5bab33ee64b0" />

**Conclusão:** Nenhum id repetido e mesma quantidade de linhas da Bronze nas 5 tabelas (nenhum registro perdido no tratamento)

> **Ajuste após a validação:** as transações passam a ter 13.295.276 linhas por causa da quarentena (10.639 transações de valor zero). Os ids continuam únicos em todas as bases.

#### 2.3.2. Completude
Conta quantos campos estão vazios em cada coluna das tabelas da Silver.

**Ideal:** 0 vazios, com exceção dos já conhecidos da Bronze nas transações (merchant_state, zip e errors).

<img width="1153" height="297" alt="image" src="https://github.com/user-attachments/assets/bd1aa35b-7328-4e98-83f3-6c1d40295df1" />

**Conclusão:** só as transações têm vazios, em `merchant_state`, `zip` e `errors`. Os mesmos vazios já existiam na Bronze, então o tratamento não criou nenhum.

> **Ajuste após a validação:** os vazios de estado e CEP são compras online e no exterior, que agora estão identificadas nas colunas `channel` e `merchant_country`. O campo `errors` vazio passou a ser "Nenhum".

#### 2.3.3. Formato
Verifica se cada coluna da Silver ficou com o tipo esperado (número, data, verdadeiro/falso) e se alguma conversão falhou, comparando os vazios da Silver com os da Bronze.

**Ideal:** 0 colunas com tipo errado e 0 falhas de conversão em todas as bases.

<img width="1145" height="312" alt="image" src="https://github.com/user-attachments/assets/f7aeee93-b0a1-463b-ad18-a25f2900d4ca" />

**Conclusão:** todas as colunas estão com o tipo esperado e nenhuma conversão falhou.

> **Ajuste após a validação:** na primeira execução, `transaction_id` e `is_fraud` estavam como texto na `fraud_labels`. A tabela foi recriada com os tipos corretos. As novas colunas das transações também entraram na verificação.

#### 2.3.4. Valores possíveis
Verifica se os valores de cada coluna estão dentro de faixas reais (idade, score, renda, limite, valor da transação) e se as categorias são as conhecidas (gênero, bandeira, tipo de cartão e de transação).

**Ideal:** 0 valores fora das regras em todas as bases.

<img width="1146" height="285" alt="image" src="https://github.com/user-attachments/assets/d564f14f-c967-4023-877f-0d03ea9f127b" />

**Conclusão:** 1 cliente com 101 anos, 15 clientes com renda per capita zero, 31 cartões com limite zero e 10.639 transações com valor zero. As demais regras estão dentro do esperado.

> **Ajuste após a validação:** as transações de valor zero foram para a quarentena. Uma nova regra encontrou 5.788 compras de chip com cidade "ONLINE", que ficam com alerta.

#### 2.3.5. Coerência
Cruza colunas relacionadas para ver se elas se contradizem: idade e ano de nascimento, renda per capita e renda anual, idade e aposentadoria, abertura e vencimento do cartão, troca do PIN e abertura da conta, e data das transações.

**Ideal:** 0 registros incoerentes.

<img width="1152" height="286" alt="image" src="https://github.com/user-attachments/assets/568d7dd3-b7ed-4208-93b2-72ac593a3d39" />

**Conclusão:** 34 clientes com renda per capita maior que a anual, 277 clientes com idade acima da aposentadoria (provavelmente já aposentados) e 248 cartões abertos no mês do vencimento. Esses casos seguem na Silver com alerta.

#### 2.3.6. Integridade
Verifica se as tabelas se ligam corretamente: se todo cartão tem um cliente, se a quantidade de cartões do cliente bate com a tabela de cartões, se toda transação tem cliente, cartão e código MCC cadastrados, se o cartão usado pertence ao cliente da transação e se todo rótulo de fraude tem uma transação.

**Ideal:** 0 registros sem correspondência em todas as ligações.

<img width="1147" height="342" alt="image" src="https://github.com/user-attachments/assets/15702578-a68f-4cd2-b472-3b1ab3cc9532" />

**Conclusão:** as 7 ligações estão íntegras. As tabelas podem ser relacionadas com segurança na camada Gold.

> **Ajuste após a validação:** depois da quarentena, 7.193 rótulos de fraude ficaram sem transação na Silver, porque pertencem às transações de valor zero que foram para a quarentena.

### Resumo da validação

**Pontos validados:** as tabelas da Silver não têm ids repetidos nem perda de linhas, todas as colunas estão com o tipo correto e todas as ligações entre as tabelas estão íntegras.

**Alertas:** clientes com idade, renda ou aposentadoria fora do esperado, cartões com limite zero ou abertos no mês do vencimento e transações sem estado e CEP do comércio. Esses registros seguem na Silver, marcados para análise.

**Quarentena:** transações com valor zero, que ficam separadas das análises de risco.

#### 2.4 Decisões

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
