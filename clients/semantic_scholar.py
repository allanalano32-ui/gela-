"""
Cliente para o Semantic Scholar, usando a biblioteca `semanticscholar`
(danielnsilva/semanticscholar, MIT, wrapper da API oficial do Semantic Scholar).

Sem chave de API o limite de requisições é compartilhado e mais baixo; com uma
chave gratuita (obtida em semanticscholar.org/product/api), o limite é maior.

Testado ao vivo em produção: sem chave, a segunda página de paginação retornou
HTTP 429 (rate limit) já na primeira busca real. A lib `semanticscholar` tem
`retry=True` por padrão (via tenacity), o que significa que iterar o objeto de
busca além da primeira página pode disparar retries internos com backoff que
o código chamador não controla - o mesmo tipo de problema estrutural já visto
no cliente do Google Scholar. Por isso aqui: `retry=False` explícito, timeout
curto, e o limite é sempre travado a no máximo o tamanho de uma página (100,
limite da própria API) para nunca precisar de uma segunda chamada HTTP.
"""

import os

from semanticscholar import SemanticScholar
from tenacity import RetryError

TIMEOUT_SEGUNDOS = 10


def _obter_cliente(api_key=None):
    return SemanticScholar(api_key=api_key, timeout=TIMEOUT_SEGUNDOS, retry=False)


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

    Nunca itera além da primeira página de resultados (ver aviso no topo do
    módulo sobre o retry interno da lib e o rate limit sem chave de API).
    """
    if api_key is None:
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None

    sch = _obter_cliente(api_key)
    limite_pagina = min(limite, 100)

    kwargs = {"limit": limite_pagina}
    if ano_inicio and ano_fim:
        kwargs["year"] = f"{ano_inicio}-{ano_fim}"

    try:
        resultados_busca = sch.search_paper(query_string, **kwargs)
    except RetryError as e:
        causa_original = e.last_attempt.exception() if e.last_attempt else None
        if isinstance(causa_original, ConnectionRefusedError):
            raise RuntimeError(
                "Erro ao consultar o Semantic Scholar: limite de taxa (HTTP 429) "
                "atingido. Sem uma chave de API dedicada, isso é esperado com "
                "frequência - configure SEMANTIC_SCHOLAR_API_KEY para reduzir."
            )
        raise RuntimeError(f"Erro ao consultar o Semantic Scholar: {causa_original or e}")
    except Exception as e:
        raise RuntimeError(f"Erro ao consultar o Semantic Scholar: {e}")

    resultados = []
    try:
        for paper in resultados_busca.items[:limite_pagina]:
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
