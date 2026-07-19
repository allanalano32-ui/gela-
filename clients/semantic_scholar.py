"""
Cliente para o Semantic Scholar, usando a biblioteca `semanticscholar`
(danielnsilva/semanticscholar, MIT, wrapper da API oficial do Semantic Scholar).

Sem chave de API o limite de requisições é compartilhado e mais baixo; com uma
chave gratuita (obtida em semanticscholar.org/product/api), o limite é maior.
"""

from semanticscholar import SemanticScholar

_cliente = None


def _obter_cliente(api_key=None):
    global _cliente
    if _cliente is None:
        _cliente = SemanticScholar(api_key=api_key)
    return _cliente


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    """
    A busca do Semantic Scholar não documenta operadores booleanos formais
    (AND/OR) da mesma forma que OpenAlex/DOAJ - ela faz busca por relevância
    sobre os termos fornecidos. Aqui concatenamos os termos obrigatórios e
    registramos os alternativos como uma nota, para manter a reprodutibilidade
    documentada mesmo sabendo que a busca em si é por relevância, não booleana
    estrita.
    """
    partes = list(termos_obrigatorios)
    if termos_qualquer:
        partes.append("(" + " OR ".join(termos_qualquer) + ")")
    return " ".join(partes)


def buscar(query_string, ano_inicio=None, ano_fim=None, api_key=None, limite=25):
    """
    Busca artigos no Semantic Scholar. Retorna (lista_normalizada, total_disponivel)
    ou levanta RuntimeError com mensagem clara em caso de erro.
    """
    sch = _obter_cliente(api_key)

    kwargs = {"limit": min(limite, 100)}
    if ano_inicio and ano_fim:
        kwargs["year"] = f"{ano_inicio}-{ano_fim}"

    try:
        resultados_busca = sch.search_paper(query_string, **kwargs)
    except Exception as e:
        raise RuntimeError(f"Erro ao consultar o Semantic Scholar: {e}")

    resultados = []
    try:
        for paper in resultados_busca:
            if len(resultados) >= limite:
                break
            autores = "; ".join(a.name for a in (paper.authors or []) if a.name)
            resultados.append({
                "id": f"semanticscholar:{paper.paperId}",
                "id_nativo": paper.paperId,
                "fonte": "semantic_scholar",
                "titulo": paper.title or "(sem título)",
                "ano": paper.year,
                "revista": (paper.venue or None),
                "autores": autores or None,
                "resumo": paper.abstract,  # texto original da fonte, sem reescrita
                "doi": (paper.externalIds or {}).get("DOI", "").lower() or None
                       if paper.externalIds else None,
                "url": paper.url,
            })
    except Exception as e:
        if resultados:
            return resultados, len(resultados)
        raise RuntimeError(f"Erro ao percorrer os resultados do Semantic Scholar: {e}")

    total = getattr(resultados_busca, "total", len(resultados))
    return resultados, total
