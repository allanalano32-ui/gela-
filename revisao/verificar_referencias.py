"""
Verificação de referências citadas em um documento contra o OpenAlex.

Regra de ouro: isto NÃO é um verificador que "confirma" ou "desmente" uma
referência com certeza absoluta. É uma busca de correspondência: o sistema
procura o candidato mais parecido na base real do OpenAlex e mostra a
similaridade textual encontrada. A decisão final é sempre do usuário -
o sistema nunca declara "esta referência é falsa", só "não encontrei
correspondência confiável, verifique manualmente".
"""

import re
from difflib import SequenceMatcher

from clients import openalex

LIMIAR_CORRESPONDENCIA_BOA = 0.72
LIMIAR_CORRESPONDENCIA_POSSIVEL = 0.5


def _normalizar(texto):
    texto = texto.lower()
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _similaridade(a, b):
    return SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def verificar_referencia(texto_referencia):
    """
    Verifica uma referência individual. Retorna um dict com:
    - texto_original: a referência como veio do documento
    - status: 'confirmada' | 'possivel' | 'nao_encontrada' | 'erro'
    - melhor_candidato: dict do OpenAlex (título, ano, autores, doi, url) ou None
    - similaridade: score de 0 a 1 entre o texto da referência e o título do candidato
    - mensagem: explicação legível do resultado
    """
    try:
        candidatos = openalex.buscar_melhor_correspondencia(texto_referencia, top_n=3)
    except RuntimeError as e:
        return {
            "texto_original": texto_referencia,
            "status": "erro",
            "melhor_candidato": None,
            "similaridade": None,
            "mensagem": f"Erro ao consultar o OpenAlex: {e}",
        }

    if not candidatos:
        return {
            "texto_original": texto_referencia,
            "status": "nao_encontrada",
            "melhor_candidato": None,
            "similaridade": None,
            "mensagem": "Nenhum artigo parecido foi encontrado no OpenAlex. "
                        "Isso não confirma que a referência é inválida - pode ser um "
                        "livro, capítulo, site ou documento fora da cobertura do OpenAlex. "
                        "Verifique manualmente.",
        }

    melhor = max(candidatos, key=lambda c: _similaridade(texto_referencia, c["titulo"]))
    score = _similaridade(texto_referencia, melhor["titulo"])

    if score >= LIMIAR_CORRESPONDENCIA_BOA:
        status = "confirmada"
        mensagem = ("Encontrada uma correspondência com alta similaridade textual "
                    "no OpenAlex. Confira se os dados batem (ano, autores) antes de "
                    "considerar validada.")
    elif score >= LIMIAR_CORRESPONDENCIA_POSSIVEL:
        status = "possivel"
        mensagem = ("Encontrado um candidato parecido, mas a similaridade é "
                    "moderada - pode ser a referência certa ou pode ser outro "
                    "trabalho parecido. Verifique manualmente.")
    else:
        status = "nao_encontrada"
        mensagem = ("O candidato mais próximo encontrado tem baixa similaridade "
                    "com o texto da referência. Provavelmente não é a mesma obra, "
                    "ou a referência não está no OpenAlex (pode ser livro, capítulo, "
                    "site, etc). Verifique manualmente.")

    return {
        "texto_original": texto_referencia,
        "status": status,
        "melhor_candidato": melhor,
        "similaridade": round(score, 2),
        "mensagem": mensagem,
    }


def verificar_lista_referencias(lista_referencias):
    return [verificar_referencia(ref) for ref in lista_referencias]
