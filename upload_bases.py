"""
Etapa 2 - Upload das bases para um Volume do Databricks (Unity Catalog).

O que este script faz:
1. Confere se o login no Databricks já foi feito (perfil salvo no computador).
2. Conecta no workspace usando esse perfil.
3. Confere se o catálogo e o schema já existem e cria o volume, se ainda não existir.
4. Envia todos os arquivos .csv, .json e .txt da pasta local para o volume.
5. Lista o conteúdo do volume no final para conferir os tamanhos.

Pré-requisitos:
- pip install databricks-sdk
- databricks auth login --host <endereço do workspace> --profile fintrans

Observação: este script só copia os arquivos. As tabelas são criadas na etapa 3,
no notebook 01_ingestao_bronze, lendo esses arquivos a partir do volume.
"""

# ----------------------------------------------------------------------
# Bibliotecas
# ----------------------------------------------------------------------
import configparser  # lê o arquivo de configuração do login (.databrickscfg)
import time          # mede quanto tempo cada arquivo leva para subir
from pathlib import Path  # trabalha com caminhos de pastas e arquivos no Windows

from databricks.sdk import WorkspaceClient            # cliente oficial para falar com o Databricks
from databricks.sdk.service.catalog import VolumeType  # tipos de volume (gerenciado ou externo)

# ----------------------------------------------------------------------
# Configurações - os únicos valores que você precisa ajustar
# ----------------------------------------------------------------------
# Endereço do workspace, o mesmo usado no "databricks auth login".
HOST = "https://dbc-e2340fd8-5109.cloud.databricks.com"

# Nome do perfil de login salvo no computador. O perfil guarda o endereço do
# workspace; a senha/token fica no Gerenciador de Credenciais do Windows, não no código.
PERFIL = "fintrans"

# Pasta do computador onde estão os arquivos baixados do Kaggle.
# O "r" antes das aspas faz o Python ler as barras invertidas do Windows corretamente.
PASTA_LOCAL = Path(
    r"C:\Users\Emill\OneDrive\Documentos\GitHub Projects\Financial Transactions Dataset"
)

# Destino no Databricks: catalogo.schema.volume
# O catálogo e o schema já precisam existir; o volume o script cria se faltar.
CATALOGO = "financial_transactions"
SCHEMA = "bronze"
VOLUME = "arquivos"

# Só estes tipos de arquivo são enviados (evita subir o script, o .gitignore etc.).
# O .txt é a tabela de cidades do Censo dos EUA, separada por tabulação.
EXTENSOES = {".csv", ".json", ".txt"}


# ----------------------------------------------------------------------
# Passo 1 - Conferir o login
# ----------------------------------------------------------------------
def conferir_perfil() -> None:
    """Confere se o login com o perfil PERFIL já foi feito para o HOST.

    O comando `databricks auth login` grava os perfis no arquivo .databrickscfg,
    dentro da pasta do usuário (C:\\Users\\Emill). Aqui lemos esse arquivo para
    avisar com uma mensagem clara caso o login ainda não tenha sido feito,
    em vez de deixar o script quebrar com um erro difícil de entender.
    """
    # Comando que será sugerido se algo estiver errado.
    comando = f"databricks auth login --host {HOST} --profile {PERFIL}"

    # Caminho do arquivo de configuração: C:\Users\<usuário>\.databrickscfg
    arquivo = Path.home() / ".databrickscfg"

    # Lê o arquivo (formato parecido com .ini: [nome_do_perfil] e linhas chave = valor).
    config = configparser.ConfigParser()
    if arquivo.exists():
        config.read(arquivo, encoding="utf-8")

    # O perfil precisa existir...
    if PERFIL not in config.sections():
        raise SystemExit(f"Perfil '{PERFIL}' não encontrado. Rode antes:\n  {comando}")

    # ...e apontar para o mesmo workspace configurado em HOST.
    if config[PERFIL].get("host", "").rstrip("/") != HOST.rstrip("/"):
        raise SystemExit(f"O perfil '{PERFIL}' aponta para outro endereço. Rode de novo:\n  {comando}")


# ----------------------------------------------------------------------
# Passo 2 - Conferir o destino e criar o volume
# ----------------------------------------------------------------------
def garantir_estrutura(w: WorkspaceClient) -> None:
    """Confere se o catálogo e o schema existem e cria o volume, se necessário.

    No Unity Catalog a organização é: catálogo > schema > volume (para arquivos)
    ou tabela (para dados estruturados). O volume funciona como uma pasta
    gerenciada pelo Databricks, onde guardamos os arquivos originais.
    """
    # Lista os catálogos que você tem acesso e verifica se o nosso está entre eles.
    if CATALOGO not in {c.name for c in w.catalogs.list()}:
        raise SystemExit(f"Catálogo '{CATALOGO}' não encontrado. Confira o nome em CATALOGO.")

    # Lista os schemas dentro do catálogo e verifica se o nosso existe.
    if SCHEMA not in {s.name for s in w.schemas.list(catalog_name=CATALOGO)}:
        raise SystemExit(f"Schema '{CATALOGO}.{SCHEMA}' não encontrado. Confira o nome em SCHEMA.")

    # Lista os volumes do schema; se o nosso ainda não existe, cria.
    # MANAGED = o próprio Databricks cuida do armazenamento (não precisa configurar nuvem).
    volumes = {v.name for v in w.volumes.list(catalog_name=CATALOGO, schema_name=SCHEMA)}
    if VOLUME not in volumes:
        print(f"Criando volume {CATALOGO}.{SCHEMA}.{VOLUME}...")
        w.volumes.create(
            catalog_name=CATALOGO,
            schema_name=SCHEMA,
            name=VOLUME,
            volume_type=VolumeType.MANAGED,
            comment="CSVs e JSONs originais do Kaggle",
        )


# ----------------------------------------------------------------------
# Passo 3 - Enviar os arquivos
# ----------------------------------------------------------------------
def enviar_arquivos(w: WorkspaceClient) -> None:
    """Envia cada arquivo .csv/.json/.txt da pasta local para o volume."""
    # Pega só os arquivos (não pastas) com as extensões permitidas,
    # em ordem alfabética para o progresso ficar previsível.
    arquivos = sorted(
        p for p in PASTA_LOCAL.iterdir() if p.is_file() and p.suffix.lower() in EXTENSOES
    )
    if not arquivos:
        raise SystemExit(f"Nenhum arquivo .csv/.json/.txt encontrado em {PASTA_LOCAL}")

    # Todo volume do Unity Catalog é acessado pelo caminho /Volumes/catalogo/schema/volume.
    destino_base = f"/Volumes/{CATALOGO}/{SCHEMA}/{VOLUME}"

    # Arquivos que já estão no volume, com o tamanho de cada um.
    # Se o arquivo local tiver o mesmo tamanho, ele já foi enviado e é pulado
    # (evita reenviar o arquivo de 1,2 GB toda vez que um arquivo novo for incluído).
    ja_enviados = {
        item.name: item.file_size for item in w.files.list_directory_contents(destino_base)
    }

    for arquivo in arquivos:
        if ja_enviados.get(arquivo.name) == arquivo.stat().st_size:
            print(f"Pulando {arquivo.name}: já está no volume")
            continue

        # Mostra o nome e o tamanho antes de começar (útil no arquivo de 1,2 GB).
        tamanho_mb = arquivo.stat().st_size / 1024 / 1024
        print(f"Enviando {arquivo.name} ({tamanho_mb:,.1f} MB)...", end=" ", flush=True)
        inicio = time.time()

        # Abre o arquivo em modo binário ("rb") e envia o conteúdo.
        # overwrite=True substitui o arquivo se ele já existir, então dá para rodar
        # o script de novo sem erro (por exemplo, se um upload for interrompido).
        with arquivo.open("rb") as conteudo:
            w.files.upload(f"{destino_base}/{arquivo.name}", conteudo, overwrite=True)

        print(f"ok em {time.time() - inicio:,.0f}s")


# ----------------------------------------------------------------------
# Passo 4 - Conferir o resultado
# ----------------------------------------------------------------------
def conferir_volume(w: WorkspaceClient) -> None:
    """Lista o que ficou no volume, com tamanho, para comparar com a pasta local.

    Se o tamanho de algum arquivo estiver diferente do original, o upload
    não terminou corretamente e vale rodar o script de novo.
    """
    print("\nConteúdo do volume:")
    for item in w.files.list_directory_contents(f"/Volumes/{CATALOGO}/{SCHEMA}/{VOLUME}"):
        tamanho_mb = (item.file_size or 0) / 1024 / 1024
        print(f"  {item.name:<28} {tamanho_mb:>10,.1f} MB")


# ----------------------------------------------------------------------
# Execução - roda os passos na ordem quando o arquivo é executado
# (python upload_bases.py). Se o arquivo for importado por outro script,
# este bloco não roda.
# ----------------------------------------------------------------------
if __name__ == "__main__":
    conferir_perfil()

    # Cria a conexão com o Databricks usando o perfil de login.
    w = WorkspaceClient(profile=PERFIL)

    # Mostra com qual usuário conectou, para confirmar que é a conta certa.
    print(f"Perfil: {PERFIL} | Conectada como: {w.current_user.me().user_name}\n")

    garantir_estrutura(w)
    enviar_arquivos(w)
    conferir_volume(w)
