"""
Cliente para a BVS (Biblioteca Virtual em Saúde) / base LILACS, via interface iAH/iAHx.

Documentação oficial dos parâmetros de busca (rede BVS):
https://red.bvsalud.org/en/search-parameters-for-iah-and-iahx-interfaces/

ATENÇÃO — assim como o SciELO, esta integração é MARCADA COMO NÃO VERIFICADA:
a documentação confirma os PARÂMETROS de busca (base, exprSearch, indexSearch,
conectSearch), mas essa é uma interface CGI mais antiga, e não confirmei com
certeza o formato de saída (parece que existe um parâmetro de formato de
registro, mas não testei ao vivo). Pode devolver HTML por padrão em vez de
algo facilmente parseável.

Antes de confiar nos resultados:
1. Rodem uma busca de teste com um termo que vocês sabem ter resultado no LILACS.
2. Confiram manualmente em https://pesquisa.bvsalud.org se os resultados batem.
3. Se a resposta não vier em um formato parseável, me tragam um exemplo real da
   resposta (não vou adivinhar a partir daqui sem ver o dado real).
"""

import re
import requests

BASE_URL = "http://bases.bireme.br/cgi-bin/wxislind.exe/iah/online/"


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    partes = list(termos_obrigatorios)
    if termos_qualquer:
        partes.append("(" + " OR ".join(termos_qualquer) + ")")
    return " AND ".join(partes)


def buscar(query_string, ano_inicio=None, ano_fim=None, base="LILACS"):
    """
    Busca na BVS/LILACS via interface iAH. INTEGRAÇÃO NÃO VERIFICADA
    (ver aviso no topo do arquivo). Levanta RuntimeError com uma mensagem
    clara se a resposta não vier em um formato que consigamos processar.
    """
    params = {
        "IsisScript": "iah/iah.xis",
        "lang": "p",
        "base": base,
        "nextAction": "lnk",
        "form": "A",
        "exprSearch": query_string,
        "indexSearch": "TW",  # busca por palavras (title/abstract/subject/author)
    }

    resp = requests.get(BASE_URL, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Erro na interface da BVS/LILACS ({resp.status_code}). "
            f"Essa integração ainda não foi validada com uma resposta real - "
            f"resposta: {resp.text[:300]}"
        )

    texto = resp.text
    if "<html" not in texto.lower() and "<?xml" not in texto.lower():
        raise RuntimeError(
            "A resposta da BVS não veio no formato esperado (nem HTML nem XML "
            "reconhecível). A integração precisa ser revisada com base no "
            "formato real retornado - não vou tentar adivinhar a estrutura."
        )

    # Extração best-effort de registros a partir do HTML retornado pela interface iAH.
    # NÃO TESTADO CONTRA UMA RESPOSTA REAL - ajustar assim que virmos o HTML de verdade.
    resultados = []
    blocos = re.findall(r'<td[^>]*class="resultsBibliographicDetails"[^>]*>(.*?)</td>', texto, re.S)
    if not blocos:
        # Formato não reconhecido - melhor falhar de forma clara do que devolver lista vazia
        # como se fosse "zero resultados".
        raise RuntimeError(
            "Não foi possível localizar registros na resposta da BVS com o padrão "
            "esperado. Isso não significa necessariamente 'zero resultados' - "
            "pode ser que o formato da página mudou. Precisa de revisão manual."
        )

    for i, bloco in enumerate(blocos):
        titulo_match = re.search(r'<b>(.*?)</b>', bloco)
        titulo = re.sub("<[^<]+?>", "", titulo_match.group(1)) if titulo_match else "(sem título)"
        resultados.append({
            "id": f"bvs:{base}:{i}:{hash(titulo) % 100000}",
            "id_nativo": None,
            "fonte": "bvs",
            "titulo": titulo,
            "ano": None,       # não extraído nesta versão - revisar com resposta real
            "revista": None,   # não extraído nesta versão - revisar com resposta real
            "autores": None,
            "resumo": None,    # não extraído nesta versão - revisar com resposta real
            "doi": None,
            "url": None,
        })

    return resultados, len(resultados)
