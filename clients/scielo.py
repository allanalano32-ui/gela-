"""
Cliente para a API do SciELO.

ATENÇÃO — DIFERENÇA IMPORTANTE EM RELAÇÃO AO CLIENTE DO OPENALEX:
Não encontrei documentação OFICIAL da SciELO (scielo.readthedocs.io ou
github.com/scieloorg) que confirme com certeza um parâmetro de busca por
palavra-chave livre nesta API. A implementação abaixo segue um formato visto
em uma listagem de terceiros (não-oficial), então deve ser tratada como
NÃO VERIFICADA até ser testada ao vivo.

Antes de confiar nos resultados desta integração:
1. Rode uma busca de teste com um termo que vocês sabem que tem artigos no SciELO.
2. Confiram manualmente no navegador (search.scielo.org) se os resultados batem.
3. Se o endpoint abaixo não funcionar como esperado, ajustem a função `buscar()`
   com base no comportamento real observado - não vou adivinhar um comportamento
   que não pude confirmar na documentação oficial.
"""

import requests

SEARCH_URL = "https://search.scielo.org/"


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    partes = list(termos_obrigatorios)
    if termos_qualquer:
        partes.append("(" + " OR ".join(termos_qualquer) + ")")
    return " AND ".join(partes)


def buscar(query_string, ano_inicio=None, ano_fim=None, count=50):
    """
    Busca artigos no SciELO. INTEGRAÇÃO NÃO VERIFICADA (ver aviso no topo do arquivo).
    Retorna (lista_normalizada, total_estimado) ou levanta RuntimeError com uma
    mensagem clara se a resposta não vier no formato esperado.
    """
    params = {"q": query_string, "format": "json", "count": count}
    if ano_inicio and ano_fim:
        params["filter[year_cluster]"] = f"{ano_inicio}-{ano_fim}"

    resp = requests.get(SEARCH_URL, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Erro na API do SciELO ({resp.status_code}). Isso pode indicar que o "
            f"endpoint/parâmetros usados aqui estão incorretos - essa integração "
            f"ainda não foi validada com uma resposta real. Resposta: {resp.text[:300]}"
        )

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(
            "A resposta do SciELO não veio em JSON como esperado. "
            "A integração precisa ser revisada com base no formato real retornado."
        )

    docs = data.get("docs", data.get("results", []))
    resultados = []
    for doc in docs:
        titulo = doc.get("title")
        if isinstance(titulo, dict):
            titulo = titulo.get("en") or next(iter(titulo.values()), None)

        doi = doc.get("doi")
        if doi:
            doi = doi.strip().lower()

        pid = doc.get("pid", "")
        resultados.append({
            "id": f"scielo:{pid or doi or titulo}",  # chave única do registro (fonte + id nativo)
            "id_nativo": pid,
            "fonte": "scielo",
            "titulo": titulo or "(sem título)",
            "ano": doc.get("publication_year"),
            "revista": doc.get("journal_title"),
            "autores": "; ".join(doc.get("authors", [])) if doc.get("authors") else None,
            "resumo": doc.get("abstract"),  # campo do próprio SciELO, sem reescrita
            "doi": doi,
            "url": f"https://search.scielo.org/?q={pid}" if pid else None,
        })

    total = data.get("total", len(resultados))
    return resultados, total
