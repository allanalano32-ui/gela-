"""
Cliente para a API pública do DOAJ (Directory of Open Access Journals).

Documentação oficial: https://doaj.org/api/v4/docs

Confirmado na documentação oficial:
- Não precisa de chave de API para busca (só para submissão de dados como editor).
- Limite de taxa: 2 requisições/segundo (rajadas de até 5 são permitidas).
- Busca limitada a 1000 resultados por consulta (usar filtros mais específicos
  se um tema tiver mais que isso).
- Sintaxe de busca: query string no estilo Elasticsearch, com AND/OR e busca
  por campo (ex: "title:biomecânica AND abstract:corrida").
- Nomes curtos de campo para artigos: title, doi, issn, publisher, abstract.

NÃO VERIFICADO EM CHAMADA REAL: a paginação exata (nomes dos parâmetros
page/pageSize) - a documentação descreve o formato mas não testei contra uma
resposta real. Se o formato não bater, o erro será reportado de forma clara.
"""

import requests

BASE_URL = "https://doaj.org/api/search/articles/"


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    """
    Monta a query no formato aceito pela DOAJ (sintaxe Elasticsearch/Lucene).
    Termos com espaço são colocados entre aspas para busca de frase exata.
    """
    def formatar(termo):
        return f'"{termo}"' if " " in termo else termo

    partes = [formatar(t) for t in termos_obrigatorios]
    query = " AND ".join(partes)
    if termos_qualquer:
        alternativas = " OR ".join(formatar(t) for t in termos_qualquer)
        query += f" AND ({alternativas})"
    return query


def buscar(query_string, ano_inicio=None, ano_fim=None, page_size=25, max_resultados=200):
    """
    Busca artigos no DOAJ. Retorna (lista_normalizada, total_disponivel) ou
    levanta RuntimeError com mensagem clara em caso de erro.

    Nota: a API não documenta um filtro de intervalo de anos diretamente na
    query de forma simples e testada - se ano_inicio/ano_fim forem informados,
    adicionamos ao texto da busca como aproximação (ex: "bibjson.year:[2020 TO 2024]"),
    mas isso NÃO foi testado contra uma resposta real - se não funcionar como
    esperado, me tragam o resultado real para eu ajustar.
    """
    query = query_string
    if ano_inicio and ano_fim:
        query += f' AND bibjson.year:[{ano_inicio} TO {ano_fim}]'

    resultados = []
    pagina = 1
    total = None

    while len(resultados) < max_resultados:
        url = f"{BASE_URL}{query}"
        params = {"page": pagina, "pageSize": min(page_size, 100)}
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Erro na API do DOAJ ({resp.status_code}). Isso pode indicar "
                f"que a query ou os parâmetros de paginação usados aqui estão "
                f"incorretos - resposta: {resp.text[:300]}"
            )

        data = resp.json()
        total = data.get("total", 0)
        registros = data.get("results", [])
        if not registros:
            break

        for r in registros:
            bibjson = r.get("bibjson", {})
            titulo = bibjson.get("title", "(sem título)")

            autores = "; ".join(
                a.get("name", "") for a in bibjson.get("author", []) if a.get("name")
            )

            doi = None
            for ident in bibjson.get("identifier", []):
                if ident.get("type", "").lower() == "doi":
                    doi = ident.get("id", "").lower()

            issn = None
            for ident in bibjson.get("identifier", []):
                if ident.get("type", "").lower() in ("issn", "eissn", "pissn"):
                    issn = ident.get("id")
                    break

            url_artigo = None
            for link in bibjson.get("link", []):
                if link.get("type") == "fulltext":
                    url_artigo = link.get("url")
                    break

            resultados.append({
                "id": f"doaj:{r.get('id')}",
                "id_nativo": r.get("id"),
                "fonte": "doaj",
                "titulo": titulo,
                "ano": bibjson.get("year"),
                "revista": (bibjson.get("journal") or {}).get("title"),
                "autores": autores or None,
                "resumo": bibjson.get("abstract"),  # texto original da fonte, sem reescrita
                "doi": doi,
                "url": url_artigo or doi,
            })
            if len(resultados) >= max_resultados:
                break

        if len(registros) < params["pageSize"]:
            break
        pagina += 1

    return resultados, total
