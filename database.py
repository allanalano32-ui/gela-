"""
Camada de banco de dados do GELA (Postgres/Supabase).

Regra de ouro do projeto: nenhum dado de artigo (título, resumo, autores, etc.)
é gerado ou alterado por IA. Tudo que é salvo aqui vem literalmente das APIs
das fontes (OpenAlex, SciELO, PhilPapers).

A conexão é lida de DATABASE_URL (formato padrão do Supabase/Postgres).
A criação das tabelas roda separadamente via init_db.py, não no import deste módulo.
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL")

SCHEMA = """
CREATE TABLE IF NOT EXISTS buscas (
    id SERIAL PRIMARY KEY,
    termo_busca TEXT NOT NULL,
    ano_inicio INTEGER,
    ano_fim INTEGER,
    string_openalex TEXT,
    string_scielo TEXT,
    string_philpapers TEXT,
    string_bvs TEXT,
    string_google_scholar TEXT,
    string_doaj TEXT,
    string_semantic_scholar TEXT,
    data_execucao TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE buscas ADD COLUMN IF NOT EXISTS string_bvs TEXT;
ALTER TABLE buscas ADD COLUMN IF NOT EXISTS string_google_scholar TEXT;
ALTER TABLE buscas ADD COLUMN IF NOT EXISTS string_doaj TEXT;
ALTER TABLE buscas ADD COLUMN IF NOT EXISTS string_semantic_scholar TEXT;

CREATE TABLE IF NOT EXISTS artigos (
    id TEXT PRIMARY KEY,           -- identificador único: doi normalizado OU id nativo da fonte
    busca_id INTEGER NOT NULL REFERENCES buscas(id),
    fonte TEXT NOT NULL,           -- 'openalex' | 'scielo' | 'philpapers'
    id_nativo TEXT,                -- id original na fonte (ex: OpenAlex work id, PID SciELO)
    titulo TEXT NOT NULL,
    ano INTEGER,
    revista TEXT,
    autores TEXT,                  -- lista separada por "; ", como veio da fonte
    resumo TEXT,                   -- resumo original reconstruído, ou NULL se indisponível
    resumo_disponivel INTEGER NOT NULL DEFAULT 0,  -- 0/1 - deixa explícito quando não há resumo
    doi TEXT,
    url TEXT,
    duplicata_de TEXT,             -- aponta para o id de outro artigo já visto, se for duplicata
    status_triagem TEXT NOT NULL DEFAULT 'pendente',  -- 'pendente' | 'incluido' | 'excluido'
    motivo_exclusao TEXT
);

CREATE INDEX IF NOT EXISTS idx_artigos_busca ON artigos(busca_id);
CREATE INDEX IF NOT EXISTS idx_artigos_doi ON artigos(doi);
CREATE INDEX IF NOT EXISTS idx_artigos_status ON artigos(status_triagem);
"""

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL não está configurada no ambiente.")
        _pool = SimpleConnectionPool(1, 5, dsn=DATABASE_URL)
    return _pool


def init_db():
    """Cria as tabelas se não existirem. Deve ser chamado por um script separado
    (init_db.py), não a cada import deste módulo."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def _cursor(conn):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()


def criar_busca(termo_busca, ano_inicio, ano_fim, string_openalex, string_scielo, string_philpapers,
                 string_bvs=None, string_google_scholar=None,
                 string_doaj=None, string_semantic_scholar=None):
    with get_conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                """INSERT INTO buscas (termo_busca, ano_inicio, ano_fim, string_openalex, string_scielo,
                                        string_philpapers, string_bvs, string_google_scholar,
                                        string_doaj, string_semantic_scholar)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (termo_busca, ano_inicio, ano_fim, string_openalex, string_scielo,
                 string_philpapers, string_bvs, string_google_scholar,
                 string_doaj, string_semantic_scholar),
            )
            return cur.fetchone()["id"]


def salvar_artigos(busca_id, artigos):
    """
    Salva uma lista de artigos (dicts já normalizados pelos clients) e aplica
    deduplicação por DOI contra o que já existe na mesma busca.
    Retorna um resumo: {fonte: {"total": N, "novos": N, "duplicatas": N}}
    """
    resumo = {}
    with get_conn() as conn:
        with _cursor(conn) as cur:
            for art in artigos:
                fonte = art["fonte"]
                resumo.setdefault(fonte, {"total": 0, "novos": 0, "duplicatas": 0})
                resumo[fonte]["total"] += 1

                duplicata_de = None
                if art.get("doi"):
                    cur.execute(
                        "SELECT id FROM artigos WHERE busca_id = %s AND doi = %s AND doi IS NOT NULL",
                        (busca_id, art["doi"]),
                    )
                    existente = cur.fetchone()
                    if existente:
                        duplicata_de = existente["id"]
                        resumo[fonte]["duplicatas"] += 1
                    else:
                        resumo[fonte]["novos"] += 1
                else:
                    resumo[fonte]["novos"] += 1

                cur.execute(
                    """INSERT INTO artigos
                       (id, busca_id, fonte, id_nativo, titulo, ano, revista, autores,
                        resumo, resumo_disponivel, doi, url, duplicata_de)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO NOTHING""",
                    (
                        art["id"], busca_id, fonte, art.get("id_nativo"), art["titulo"],
                        art.get("ano"), art.get("revista"), art.get("autores"),
                        art.get("resumo"), 1 if art.get("resumo") else 0,
                        art.get("doi"), art.get("url"), duplicata_de,
                    ),
                )
    return resumo


def marcar_duplicatas_adicionais(pares_duplicatas):
    """
    Recebe uma lista de pares (id_artigo_1, id_artigo_2) encontrados pela
    deduplicação avançada (bib-dedupe) e marca duplicata_de para os artigos
    que ainda não tinham sido marcados como duplicata pela dedup simples por
    DOI. Nunca desfaz uma marcação já existente - só preenche o que estava
    NULL. Retorna o número de artigos marcados como duplicata adicional.
    """
    if not pares_duplicatas:
        return 0

    marcados = 0
    with get_conn() as conn:
        with _cursor(conn) as cur:
            for id_1, id_2 in pares_duplicatas:
                cur.execute(
                    "SELECT id, duplicata_de FROM artigos WHERE id IN (%s, %s)",
                    (id_1, id_2),
                )
                linhas = {r["id"]: r["duplicata_de"] for r in cur.fetchall()}
                if id_1 not in linhas or id_2 not in linhas:
                    continue

                if linhas[id_1] is not None or linhas[id_2] is not None:
                    continue

                cur.execute(
                    "UPDATE artigos SET duplicata_de = %s WHERE id = %s AND duplicata_de IS NULL",
                    (id_1, id_2),
                )
                if cur.rowcount:
                    marcados += cur.rowcount

    return marcados


def listar_artigos_por_busca(busca_id):
    with get_conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "SELECT * FROM artigos WHERE busca_id = %s ORDER BY fonte, ano DESC", (busca_id,)
            )
            return [dict(r) for r in cur.fetchall()]


def atualizar_triagem(artigo_id, status, motivo_exclusao=None):
    assert status in ("pendente", "incluido", "excluido")
    with get_conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                "UPDATE artigos SET status_triagem = %s, motivo_exclusao = %s WHERE id = %s",
                (status, motivo_exclusao if status == "excluido" else None, artigo_id),
            )


def obter_busca(busca_id):
    with get_conn() as conn:
        with _cursor(conn) as cur:
            cur.execute("SELECT * FROM buscas WHERE id = %s", (busca_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def relatorio_prisma(busca_id):
    """
    Monta os números do fluxo estilo PRISMA para uma busca:
    identificados por fonte, duplicatas removidas, triados, excluídos (com motivos), incluídos.
    """
    with get_conn() as conn:
        with _cursor(conn) as cur:
            cur.execute(
                """SELECT fonte, COUNT(*) as total,
                          SUM(CASE WHEN duplicata_de IS NOT NULL THEN 1 ELSE 0 END) as duplicatas
                   FROM artigos WHERE busca_id = %s GROUP BY fonte""",
                (busca_id,),
            )
            por_fonte = cur.fetchall()

            cur.execute(
                "SELECT COUNT(*) as n FROM artigos WHERE busca_id = %s AND duplicata_de IS NULL",
                (busca_id,),
            )
            unicos = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) as n FROM artigos WHERE busca_id = %s AND duplicata_de IS NULL AND status_triagem = 'pendente'",
                (busca_id,),
            )
            pendentes = cur.fetchone()["n"]

            cur.execute(
                """SELECT motivo_exclusao, COUNT(*) as n FROM artigos
                   WHERE busca_id = %s AND status_triagem = 'excluido'
                   GROUP BY motivo_exclusao""",
                (busca_id,),
            )
            excluidos = cur.fetchall()

            cur.execute(
                "SELECT COUNT(*) as n FROM artigos WHERE busca_id = %s AND status_triagem = 'incluido'",
                (busca_id,),
            )
            incluidos = cur.fetchone()["n"]

            return {
                "por_fonte": [dict(r) for r in por_fonte],
                "total_identificado": sum(r["total"] for r in por_fonte),
                "unicos_apos_duplicatas": unicos,
                "pendentes_triagem": pendentes,
                "excluidos_por_motivo": [dict(r) for r in excluidos],
                "total_excluidos": sum(r["n"] for r in excluidos),
                "total_incluidos": incluidos,
            }
