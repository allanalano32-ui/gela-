"""
Cliente para o SciELO - BUSCA POR PALAVRA-CHAVE LIVRE NÃO É POSSÍVEL VIA API OFICIAL.

Por quê: o endpoint usado anteriormente aqui (https://search.scielo.org/) é o
backend interno do site de busca (SOLR), não uma API pública documentada -
por isso retorna 403 mesmo em requisições idênticas às do navegador (não é
bloqueio de user-agent, é acesso não autorizado a um endpoint não destinado
a clientes externos).

A API pública e documentada é a ArticleMeta
(https://github.com/scieloorg/articles_meta, doc em scielo.readthedocs.io),
mas ela não tem parâmetro de busca textual (`q`). Os endpoints reais permitem
apenas:
- /api/v1/article/identifiers/?collection=...&issn=...&from=...&until=...
  (lista PIDs filtrados por periódico/coleção/intervalo de datas)
- /api/v1/article/?code=PID (metadados completos de UM artigo, formato legado)

Ou seja: dá para listar artigos de um periódico (por ISSN) num período, mas
não para buscar por termo livre em todo o SciELO como esta função promete.
Existe também o protocolo OAI-PMH (github.com/scieloorg/oai-pmh), que serve
para harvest de metadados por data/set, também sem busca textual.

PRÓXIMO PASSO REAL (não um código que finge funcionar):
1. Se a busca puder ser restrita a periódicos específicos (com ISSN conhecido),
   me tragam a lista de ISSNs relevantes para o GELA e eu implemento a busca
   via /article/identifiers/ + /article/ com filtro de termo feito no cliente
   sobre título/resumo.
2. Se a busca precisar cobrir o SciELO inteiro por palavra-chave, a única forma
   documentada é baixar o dump batch mensal
   (http://static.scielo.org/articlemeta/articles.json.zip) e indexar localmente
   (ex: Elasticsearch/Whoosh) - isso é um projeto à parte, não um simples client
   HTTP.

Até uma dessas decisões ser tomada, esta função retorna uma lista vazia e
avisa isso claramente no resultado, em vez de tentar um endpoint que não é
uma API pública.
"""


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    partes = list(termos_obrigatorios)
    if termos_qualquer:
        partes.append("(" + " OR ".join(termos_qualquer) + ")")
    return " AND ".join(partes)


def buscar(query_string, ano_inicio=None, ano_fim=None, count=50):
    """
    Retorna (lista_vazia, 0) e sinaliza que a integração está pendente.
    Ver docstring do módulo para o que precisa ser decidido antes de implementar de verdade.
    """
    return [], 0


PENDENTE = True  # usado pela interface para mostrar um aviso em vez de "0 artigos encontrados"
