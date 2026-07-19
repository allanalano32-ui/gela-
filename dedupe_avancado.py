"""
Deduplicação avançada de artigos usando a biblioteca `bib-dedupe`
(CoLRev-Environment/bib-dedupe, MIT), feita especificamente para revisões de
literatura.

Isso é COMPLEMENTAR à deduplicação simples por DOI que já existe em
database.py - aquela continua sendo a primeira linha (mais rápida e 100%
confiável quando o DOI bate). Este módulo entra para pegar duplicatas que o
DOI exato não pega: erros de digitação no DOI, mesma obra indexada com DOIs
diferentes por fontes diferentes, ou artigos sem DOI.

Regra de ouro mantida: isso não decide sozinho - marca pares como "possível
duplicata" para revisão, usando um algoritmo transparente e reproduzível
(mesmo algoritmo usado por ferramentas de revisão sistemática como o CoLRev).
"""

import pandas as pd
from bib_dedupe.bib_dedupe import prep, block, match


def encontrar_duplicatas_avancadas(artigos):
    """
    Recebe uma lista de artigos (dicts no formato usado pelo GELA: id, titulo,
    ano, autores, revista, doi) e devolve uma lista de pares
    (id_artigo_1, id_artigo_2) que o bib-dedupe considera prováveis duplicatas,
    mesmo que os DOIs sejam diferentes ou ausentes.

    Retorna lista vazia se houver menos de 2 artigos (não há o que comparar).
    """
    if len(artigos) < 2:
        return []

    linhas = []
    for art in artigos:
        linhas.append({
            "ID": art["id"],
            "title": art.get("titulo") or "",
            "author": art.get("autores") or "",
            "year": str(art.get("ano") or ""),
            "journal": art.get("revista") or "",
            "doi": art.get("doi") or "",
            "abstract": art.get("resumo") or "",
        })

    df = pd.DataFrame(linhas)

    try:
        preparado = prep(df)
        blocado = block(preparado)
        se_encontrou_pares = len(blocado) > 0
        if not se_encontrou_pares:
            return []
        combinado = match(blocado)
    except Exception as e:
        raise RuntimeError(f"Erro ao rodar a deduplicação avançada (bib-dedupe): {e}")

    if "duplicate_label" not in combinado.columns:
        return []

    duplicatas = combinado[combinado["duplicate_label"] == "duplicate"]
    return list(zip(duplicatas["ID_1"], duplicatas["ID_2"]))
