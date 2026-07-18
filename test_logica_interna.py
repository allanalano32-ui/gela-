"""
Teste com dados FALSOS/simulados só para validar a MECÂNICA do sistema
(banco, deduplicação, decodificação de resumo, exportação) - não representa
resultados reais de nenhuma API. Isso é diferente de "inventar referências":
aqui estamos testando código, não apresentando estes dados como achados de pesquisa.

Requer DATABASE_URL apontando para um Postgres/Supabase real (pode ser o mesmo
projeto de produção: este teste usa um schema isolado "gela_test", criado e
apagado neste próprio script, então não toca nas tabelas de produção).

Rodar:
    DATABASE_URL=postgresql://... python test_logica_interna.py
"""
import os

if not os.environ.get("DATABASE_URL"):
    raise SystemExit(
        "DATABASE_URL não configurada. Defina a connection string do Postgres/Supabase "
        "(Project Settings -> Database -> Connection string -> URI) antes de rodar este teste.\n"
        "Exemplo: DATABASE_URL=postgresql://usuario:senha@host:porta/postgres python test_logica_interna.py"
    )

os.environ["GELA_PASSWORD"] = "teste"
os.environ["FLASK_SECRET_KEY"] = "teste"

import psycopg2

import database as db
from clients.openalex import _decodificar_abstract
import export as exp

TEST_SCHEMA = "gela_test"

# Isola os testes num schema próprio, para não misturar com dados reais de produção.
with psycopg2.connect(db.DATABASE_URL) as _conn:
    with _conn.cursor() as _cur:
        _cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
        _cur.execute(f"CREATE SCHEMA {TEST_SCHEMA}")
    _conn.commit()

os.environ["DATABASE_URL"] = db.DATABASE_URL + f"?options=-csearch_path%3D{TEST_SCHEMA}"
db.DATABASE_URL = os.environ["DATABASE_URL"]
db._pool = None  # força recriar o pool apontando para o novo search_path

try:
    # 1. Testar decodificação do abstract_inverted_index (formato real do OpenAlex)
    inverted = {"Running": [0], "biomechanics": [1], "is": [2], "complex": [3]}
    resultado = _decodificar_abstract(inverted)
    assert resultado == "Running biomechanics is complex", f"Falhou: {resultado}"
    print("[OK] Decodificação de abstract_inverted_index funciona.")

    # 2. Testar banco de dados + deduplicação
    db.init_db()

    busca_id = db.criar_busca(
        termo_busca="teste biomecânica", ano_inicio=2020, ano_fim=2026,
        string_openalex="biomechanics AND running", string_scielo="biomechanics AND running",
        string_philpapers=None,
    )

    artigos_simulados = [
        {"id": "openalex:W1", "id_nativo": "W1", "fonte": "openalex", "titulo": "Artigo A (simulado)",
         "ano": 2022, "revista": "Revista X (simulado)", "autores": "Autor Um", "resumo": "Resumo simulado A.",
         "doi": "10.1234/abc", "url": "https://doi.org/10.1234/abc"},
        {"id": "scielo:S1", "id_nativo": "S1", "fonte": "scielo", "titulo": "Artigo A (simulado)",
         "ano": 2022, "revista": "Revista X (simulado)", "autores": "Autor Um", "resumo": None,
         "doi": "10.1234/abc", "url": "https://scielo.org/S1"},  # mesmo DOI = duplicata esperada
        {"id": "openalex:W2", "id_nativo": "W2", "fonte": "openalex", "titulo": "Artigo B (simulado)",
         "ano": 2023, "revista": "Revista Y (simulado)", "autores": "Autor Dois", "resumo": "Resumo simulado B.",
         "doi": "10.9999/xyz", "url": "https://doi.org/10.9999/xyz"},
    ]

    resumo_dedup = db.salvar_artigos(busca_id, artigos_simulados)
    print("[OK] Resumo de deduplicação:", resumo_dedup)

    artigos_salvos = db.listar_artigos_por_busca(busca_id)
    assert len(artigos_salvos) == 3, f"Esperava 3 registros salvos, veio {len(artigos_salvos)}"
    duplicatas = [a for a in artigos_salvos if a["duplicata_de"]]
    assert len(duplicatas) == 1, f"Esperava 1 duplicata detectada, veio {len(duplicatas)}"
    print("[OK] Deduplicação por DOI identificou corretamente 1 duplicata.")

    # 3. Testar triagem
    db.atualizar_triagem("openalex:W1", "incluido")
    db.atualizar_triagem("openalex:W2", "excluido", motivo_exclusao="fora do período")

    # 4. Testar relatório PRISMA
    rel = db.relatorio_prisma(busca_id)
    print("[OK] Relatório PRISMA:", rel)
    assert rel["total_identificado"] == 3
    assert rel["unicos_apos_duplicatas"] == 2
    assert rel["total_incluidos"] == 1
    assert rel["total_excluidos"] == 1

    # 5. Testar geração dos exports (sem apenas_incluidos, para ver o excluído também no md bruto)
    md_prisma = exp.gerar_relatorio_prisma_md(busca_id)
    assert "Total identificado" in md_prisma
    assert "fora do período" in md_prisma
    print("\n--- Relatório PRISMA gerado ---\n")
    print(md_prisma)

    zip_bytes = exp.gerar_pacote_obsidian(busca_id, apenas_incluidos=True)
    assert len(zip_bytes) > 0
    print("\n[OK] Pacote Obsidian gerado,", len(zip_bytes), "bytes.")

    consolidado = exp.gerar_consolidado_notebooklm(busca_id, apenas_incluidos=True)
    assert "Artigo A (simulado)" in consolidado
    print("[OK] Consolidado NotebookLM gerado.")

    print("\n=== TODOS OS TESTES DE LÓGICA INTERNA PASSARAM ===")
finally:
    db._pool = None
    with psycopg2.connect(db.DATABASE_URL.split("?")[0]) as _conn:
        with _conn.cursor() as _cur:
            _cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
        _conn.commit()
