"""
Cliente para o PhilPapers - INTEGRAÇÃO AINDA NÃO IMPLEMENTADA.

Por quê: a documentação oficial (philpapers.org/help/api) afirma que o uso
da API está sujeito a termos que restringem a redistribuição dos dados, e
pede explicitamente para que o desenvolvedor entre em contato com a equipe
do PhilPapers ANTES de construir uma aplicação sobre ela. Eu não tenho como
fazer esse contato por vocês, e não encontrei documentação pública da sintaxe
exata de busca por palavra-chave da API JSON deles.

O que existe confirmado e documentado publicamente é o protocolo OAI-PMH
(https://philpapers.org/help/oai.html), mas ele serve para "colher" registros
por data/coleção (harvesting), não para busca por palavra-chave livre -
então não substitui uma busca de tema como "análise biomecânica da corrida".

PRÓXIMO PASSO REAL (não um código que finge funcionar):
1. Acessem https://philpapers.org/help/api e leiam os termos.
2. Criem uma conta e uma chave de API em https://philpapers.org/utils/create_api_user.html
3. Entrem em contato com a equipe do PhilPapers conforme pedido na documentação,
   informando o uso pretendido (pesquisa acadêmica pessoal).
4. Com a resposta deles, me tragam a documentação exata do endpoint de busca
   que eles liberarem, e eu implemento a função `buscar()` de verdade.

Até lá, esta função retorna uma lista vazia e avisa isso claramente no
resultado, em vez de simular dados.
"""


def montar_query_booleana(termos_obrigatorios, termos_qualquer=None):
    partes = list(termos_obrigatorios)
    if termos_qualquer:
        partes.append("(" + " OR ".join(termos_qualquer) + ")")
    return " AND ".join(partes)


def buscar(query_string, ano_inicio=None, ano_fim=None):
    """
    Retorna (lista_vazia, 0) e sinaliza que a integração está pendente.
    Ver docstring do módulo para o que precisa ser feito antes de implementar de verdade.
    """
    return [], 0


PENDENTE = True  # usado pela interface para mostrar um aviso em vez de "0 artigos encontrados"
