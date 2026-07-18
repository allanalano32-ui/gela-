"""
Cliente para a API do OpenAlex.

Documentação: https://docs.openalex.org/
Desde 13/02/2025 a API exige uma api_key para o limite completo (100.000 req/dia).
Sem chave, o limite é de apenas 100 req/dia (modo teste).

Regra de ouro: este módulo só LÊ e reorganiza campos que já vêm prontos da API.
Nenhum texto é gerado, resumido ou reescrito aqui.
"""

import os
import requests

BASE_URL = "https://api.openalex.org/works"


def _decodificar_abstract(abstract_inverted_index):
    """
    O OpenAlex não devolve o resumo como texto puro, por questões legais.
    Ele devolve um "índice invertido": um dicionário {palavra: [posições]}.
    Esta função reconstrói o texto original juntando as palavras nas posições certas.
    Isso é reconstrução determinística, não geração de texto.
    """
    if not abstract_inverted_index:
        return None
    posicoes = {}
    for palavra, posicoes_lista in abstract_inverted_index.items():
        for pos in posicoes_lista:
            posicoes[pos] = palavra
    if not posicoes:
        return None
    max_pos = max(posicoes.keys())
    palavras_ordenadas = [posicoes.get(i, "") for i in range(max_pos + 1)]
    return " ".join(p for p in palavras_ordenadas if p)


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    """
    Monta uma string de busca booleana simples e reproduzível, para poder
    ser documentada no método de uma revisão sistemática.
    termos_obrigatorios: lista de termos que devem aparecer (AND)
    termos_qualquer: lista de termos alternativos (OR), opcional
    """
    partes = list(termos_obrigatorios)
    if termos_qualquer:
        partes.append("(" + " OR ".join(termos_qualquer) + ")")
    return " AND ".join(partes)


def buscar(query_string, ano_inicio=None, ano_fim=None, per_page=25, max_resultados=200):
    """
    Busca artigos no OpenAlex. Retorna uma lista de dicts já normalizados
    no formato usado pelo banco de dados do GELA.

    Levanta RuntimeError com mensagem clara se a chave de API não estiver configurada
    e o limite de teste for excedido (isso é reportado pela própria API).
    """
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    email = os.environ.get("OPENALEX_EMAIL", "").strip()

    params = {
        "search": query_string,
        "per_page": min(per_page, 200),
    }
    if ano_inicio and ano_fim:
        params["filter"] = f"publication_year:{ano_inicio}-{ano_fim}"
    if api_key:
        params["api_key"] = api_key
    if email:
        params["mailto"] = email

    resultados = []
    cursor = "*"
    while len(resultados) < max_resultados:
        params["cursor"] = cursor
        resp = requests.get(BASE_URL, params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Erro na API do OpenAlex ({resp.status_code}): {resp.text[:300]}"
            )
        data = resp.json()
        works = data.get("results", [])
        if not works:
            break

        for w in works:
            autores = "; ".join(
                a.get("author", {}).get("display_name", "")
                for a in w.get("authorships", [])
                if a.get("author")
            )
            fonte_local = (w.get("primary_location") or {}).get("source") or {}
            resumo = _decodificar_abstract(w.get("abstract_inverted_index"))
            doi = w.get("doi")
            if doi:
                doi = doi.replace("https://doi.org/", "").lower()

            resultados.append({
                "id": f"openalex:{w['id']}",  # chave única do registro (fonte + id nativo)
                "id_nativo": w["id"],
                "fonte": "openalex",
                "titulo": w.get("title") or "(sem título)",
                "ano": w.get("publication_year"),
                "revista": fonte_local.get("display_name"),
                "autores": autores,
                "resumo": resumo,
                "doi": doi,
                "url": (w.get("open_access") or {}).get("oa_url") or w.get("id"),
            })
            if len(resultados) >= max_resultados:
                break

        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break

    total_disponivel = data.get("meta", {}).get("count", len(resultados))
    return resultados, total_disponivel


def buscar_melhor_correspondencia(texto_referencia, top_n=3):
    """
    Busca no OpenAlex os artigos mais prováveis de corresponder a uma referência
    específica (usado na verificação de referências, não na busca principal).
    Usa o texto da referência inteira como consulta de relevância (não booleana).

    Retorna uma lista de até `top_n` candidatos normalizados (mesmo formato de
    `buscar`), ordenados por relevância segundo o próprio OpenAlex.
    """
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    email = os.environ.get("OPENALEX_EMAIL", "").strip()

    params = {"search": texto_referencia, "per_page": top_n}
    if api_key:
        params["api_key"] = api_key
    if email:
        params["mailto"] = email

    resp = requests.get(BASE_URL, params=params, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Erro na API do OpenAlex ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    candidatos = []
    for w in data.get("results", []):
        autores = "; ".join(
            a.get("author", {}).get("display_name", "")
            for a in w.get("authorships", [])
            if a.get("author")
        )
        fonte_local = (w.get("primary_location") or {}).get("source") or {}
        doi = w.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "").lower()
        candidatos.append({
            "titulo": w.get("title") or "(sem título)",
            "ano": w.get("publication_year"),
            "revista": fonte_local.get("display_name"),
            "autores": autores,
            "doi": doi,
            "url": w.get("id"),
        })
    return candidatos
