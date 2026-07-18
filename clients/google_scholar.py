"""
Cliente para o Google Scholar - DESATIVADO em produção (ver diagnóstico abaixo).

HISTÓRICO: esta integração usava raspagem não-oficial via biblioteca `scholarly`.
Foi testada ao vivo em produção (Vercel) e confirmou exatamente o risco que já
era esperado: o Google bloqueia o IP de datacenter do Vercel com HTTP 403
imediatamente. Pior, a lib `scholarly` reage a esse bloqueio entrando em retry
interno com backoff de ~95 segundos, e esse retry NÃO é interrompido por
`scholarly.set_timeout()` (que só limita cada request HTTP individual) nem por
um timeout de `ThreadPoolExecutor.result(timeout=...)` no código chamador -
esse timeout só abandona a ESPERA pelo resultado, não mata a thread nem a
requisição de rede presa dentro da lib. Ou seja, a chamada real trava muito
além do timeout de 10s do Vercel (plano free), o que já chegou a estourar o
tempo da função inteira em produção.

Por isso esta função foi desativada (retorna lista vazia, PENDENTE=True),
seguindo o mesmo padrão do SciELO/PhilPapers, em vez de arriscar travar
`/api/buscar` de novo.

PRÓXIMO PASSO REAL, se quiserem reativar:
1. Um proxy de IP residencial (não datacenter) reduziria a taxa de bloqueio,
   mas tem custo próprio e ainda não é garantia contra o 403.
2. Trocar a execução para um processo separado (`multiprocessing`, que pode
   ser efetivamente terminado, ao contrário de uma thread) permitiria cortar
   o timeout de verdade - mas isso não resolve o bloqueio do Google em si,
   só evita que ele trave a rota.
3. Sem uma dessas duas mudanças, reativar esta fonte arrisca voltar a travar
   a busca inteira em produção.

Biblioteca usada (mantida instalada para quando for reativada): scholarly
https://github.com/scholarly-python-package/scholarly
"""


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


def buscar(query_string, ano_inicio=None, ano_fim=None, max_resultados=30):
    """
    Retorna (lista_vazia, 0) e sinaliza que a integração está desativada.
    Ver docstring do módulo para o diagnóstico real observado em produção.
    """
    return [], 0


PENDENTE = True  # usado pela interface para mostrar um aviso em vez de "0 artigos encontrados"
