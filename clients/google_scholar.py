"""
Cliente EXPERIMENTAL para o Google Scholar, via raspagem não-oficial (biblioteca `scholarly`).

AVISO IMPORTANTE, JÁ DISCUTIDO E ACEITO PELO USUÁRIO:
- O Google Scholar NÃO tem API oficial pública.
- Esta integração usa raspagem não-oficial, que VIOLA os termos de uso do Google.
- Pode parar de funcionar a qualquer momento sem aviso (bloqueio por IP, captcha).
- Em ambientes serverless (Vercel), o IP muda a cada execução/instância, o que
  tende a aumentar a chance de bloqueio (o Google detecta padrões de tráfego
  automatizado mais facilmente vindo de datacenters conhecidos, como os da AWS/
  Vercel, do que de IPs residenciais).
- Por isso, este cliente SEMPRE falha de forma explícita (RuntimeError com
  mensagem clara) em vez de silenciosamente devolver zero resultados quando
  bloqueado - para não ser confundido com "não há artigos sobre esse tema".

Timeout: `scholarly.set_timeout()` só limita cada requisição HTTP individual
da lib, não o tempo total da busca (search_pubs devolve um iterador que pode
disparar várias páginas em sequência, cada uma com seu próprio timeout - uma
busca com várias páginas lentas ainda poderia estourar bem além do timeout
configurado). Por isso a chamada inteira roda numa thread separada com um
timeout agregado explícito, para nunca travar a rota /api/buscar além do
limite do Vercel independente do que a lib fizer internamente.

Biblioteca usada: https://github.com/scholarly-python-package/scholarly
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from scholarly import scholarly

TIMEOUT_TOTAL_SEGUNDOS = 8  # margem para não estourar o timeout de 10s do Vercel (plano free)

scholarly.set_timeout(TIMEOUT_TOTAL_SEGUNDOS)


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    """
    O Google Scholar não documenta suporte formal a operadores booleanos como
    AND/OR da mesma forma que APIs estruturadas (OpenAlex, SciELO, BVS). Ele
    aceita frases entre aspas e o operador OR em maiúsculas de forma informal.
    Aqui montamos a melhor aproximação possível, mas ela é MENOS reprodutível
    que nas outras fontes - vale registrar isso no método de vocês, se usarem
    este resultado numa revisão sistemática formal.
    """
    partes = [f'"{t}"' if " " in t else t for t in termos_obrigatorios]
    if termos_qualquer:
        alternativas = " OR ".join(termos_qualquer)
        partes.append(f"({alternativas})")
    return " ".join(partes)


def _buscar_sincrono(query_string, ano_inicio, ano_fim, max_resultados):
    query = scholarly.search_pubs(query_string, year_low=ano_inicio, year_high=ano_fim)

    resultados = []
    for i, pub in enumerate(query):
        if i >= max_resultados:
            break
        bib = pub.get("bib", {})
        titulo = bib.get("title", "(sem título)")
        resultados.append({
            "id": f"scholar:{pub.get('pub_url') or pub.get('author_id') or titulo}",
            "id_nativo": pub.get("pub_url"),
            "fonte": "google_scholar",
            "titulo": titulo,
            "ano": int(bib["pub_year"]) if bib.get("pub_year", "").isdigit() else None,
            "revista": bib.get("venue"),
            "autores": "; ".join(bib.get("author", [])) if bib.get("author") else None,
            "resumo": bib.get("abstract"),  # quando o Scholar expõe, sem reescrita
            "doi": None,  # Google Scholar geralmente não expõe DOI estruturado
            "url": pub.get("pub_url"),
        })
    return resultados


def buscar(query_string, ano_inicio=None, ano_fim=None, max_resultados=30):
    """
    Busca no Google Scholar via scraping não-oficial. Retorna (lista, total_estimado)
    ou levanta RuntimeError com mensagem clara em caso de bloqueio/captcha/erro/timeout.

    total_estimado aqui é aproximado (o Google Scholar não expõe uma contagem
    exata e confiável de resultados totais da mesma forma que APIs estruturadas).

    A busca roda com um timeout total agregado (ver TIMEOUT_TOTAL_SEGUNDOS) para
    que um travamento nesta fonte nunca impeça a resposta das outras fontes.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_buscar_sincrono, query_string, ano_inicio, ano_fim, max_resultados)
        try:
            resultados = future.result(timeout=TIMEOUT_TOTAL_SEGUNDOS)
        except FutureTimeoutError:
            raise RuntimeError(
                f"O Google Scholar não respondeu dentro do timeout de "
                f"{TIMEOUT_TOTAL_SEGUNDOS}s (comum em raspagem não-oficial - "
                f"geralmente captcha ou limite de taxa). Não significa necessariamente "
                f"zero resultados - tente novamente mais tarde."
            )
        except Exception as e:
            raise RuntimeError(
                f"Falha ao consultar o Google Scholar (raspagem não-oficial). "
                f"Isso pode ser um bloqueio temporário do Google (comum neste tipo "
                f"de integração) - não significa necessariamente zero resultados. "
                f"Erro original: {e}"
            )

    return resultados, len(resultados)
