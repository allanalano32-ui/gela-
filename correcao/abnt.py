"""
Verificador estrutural de referências bibliográficas no padrão ABNT (NBR 6023:2025).

O QUE ISSO FAZ: verifica se cada referência segue o PADRÃO ESTRUTURAL geral da
norma (presença de elementos essenciais, ordem, pontuação básica) usando
heurísticas de texto (expressões regulares). NÃO é uma reescrita automática -
o sistema aponta o que parece faltar ou estar fora do padrão, e quem decide a
correção final são vocês.

O QUE ISSO NÃO FAZ: não cobre os ~20 tipos de documento distintos da norma
(monografia, evento, patente, documento jurídico etc.) com suas regras
específicas - isso exigiria uma árvore de regras muito maior. Por enquanto,
a checagem cobre o padrão mais comum (monografia/livro: autor, título, edição,
local, editora, data), que é o tipo mais frequente em bibliografias.

NÃO cobre citação no texto (autor, ano no meio do parágrafo) - isso é outra
norma (NBR 10520), que ainda não foi enviada.

As regras abaixo foram escritas com base na estrutura da norma, mas em texto
próprio - nenhum trecho da NBR 6023 é reproduzido aqui.
"""

import re

REGEX_AUTOR = re.compile(r"^[A-ZÀ-Ú][A-ZÀ-Ú\.\s]+,\s*[A-ZÀ-Úa-zà-ú]")
REGEX_ANO_FINAL = re.compile(r"\b(19|20)\d{2}\b\s*\.?\s*$")
REGEX_LOCAL_EDITORA = re.compile(r"[A-ZÀ-Úa-zà-ú\.\s]+:\s*[A-ZÀ-Úa-zà-ú].*,")


def verificar_referencia_abnt(texto, trechos_destacados=None, formatacao_disponivel=True):
    """
    Verifica uma referência (string) contra o padrão estrutural geral da ABNT
    para monografias/livros. Retorna uma lista de "achados", cada um com
    nível ('ok' | 'aviso') e uma explicação.

    trechos_destacados: lista de substrings em negrito/itálico encontradas no
    parágrafo original (vem da extração com formatação). Se None ou lista
    vazia E formatacao_disponivel=True, isso é um problema real (falta destaque).
    Se formatacao_disponivel=False (ex: veio de PDF), a checagem de destaque
    é pulada com um aviso claro de que não foi possível verificar.
    """
    achados = []
    trechos_destacados = trechos_destacados or []

    # 1. Autor no formato SOBRENOME, Nome
    if REGEX_AUTOR.match(texto.strip()):
        achados.append({"nivel": "ok", "mensagem": "Autor parece estar no formato SOBRENOME, Nome."})
    else:
        achados.append({
            "nivel": "aviso",
            "mensagem": "Não identifiquei o padrão 'SOBRENOME, Nome' no início da referência. "
                        "Pode ser uma obra sem autoria pessoal (entrada pelo título), ou pode "
                        "estar fora do padrão - confira manualmente.",
        })

    # 2. Destaque tipográfico do título (negrito/itálico)
    if not formatacao_disponivel:
        achados.append({
            "nivel": "aviso",
            "mensagem": "Não foi possível verificar se o título está em negrito/itálico "
                        "(essa informação não é preservada na extração de PDF). Confira "
                        "manualmente se o título da obra está destacado.",
        })
    elif trechos_destacados:
        achados.append({
            "nivel": "ok",
            "mensagem": f"Encontrei texto em negrito/itálico nesta referência "
                        f"(ex: \"{trechos_destacados[0][:60]}\"), o que é esperado para o título.",
        })
    else:
        achados.append({
            "nivel": "aviso",
            "mensagem": "Não encontrei nenhum trecho em negrito ou itálico nesta referência. "
                        "A norma exige que o título da obra apareça com destaque tipográfico "
                        "(negrito ou itálico, de forma uniforme em todas as referências).",
        })

    # 3. Padrão Local: Editora,
    if REGEX_LOCAL_EDITORA.search(texto):
        achados.append({"nivel": "ok", "mensagem": "Encontrei um padrão \"Local: Editora,\" na referência."})
    else:
        achados.append({
            "nivel": "aviso",
            "mensagem": "Não identifiquei o padrão \"Local: Editora,\" (dois pontos entre local "
                        "e editora, vírgula antes do ano). Confira se local e editora estão "
                        "presentes e pontuados corretamente.",
        })

    # 4. Ano ao final
    if REGEX_ANO_FINAL.search(texto):
        achados.append({"nivel": "ok", "mensagem": "A referência termina com um ano de 4 dígitos, como esperado."})
    else:
        achados.append({
            "nivel": "aviso",
            "mensagem": "Não encontrei um ano de publicação (4 dígitos) ao final da referência.",
        })

    return achados


def verificar_lista_referencias_abnt(paragrafos_com_formatacao):
    """
    Recebe a lista de parágrafos já filtrada como sendo a seção de referências
    (cada item: {"texto", "trechos_destacados", "formatacao_disponivel"}) e
    devolve a checagem estrutural de cada uma.
    """
    resultado = []
    for par in paragrafos_com_formatacao:
        achados = verificar_referencia_abnt(
            par["texto"], par.get("trechos_destacados"), par.get("formatacao_disponivel", True)
        )
        resultado.append({
            "texto_original": par["texto"],
            "achados": achados,
            "total_avisos": sum(1 for a in achados if a["nivel"] == "aviso"),
        })
    return resultado
