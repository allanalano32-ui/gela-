"""
Geração de exportações do GELA. Tudo aqui usa apenas dados já salvos no banco
(vindos literalmente das APIs) - nenhum texto é gerado por IA nesta etapa.
"""

import re
import zipfile
import io

import database as db


def _slug(texto, max_len=80):
    texto = re.sub(r"[^\w\s-]", "", texto or "sem-titulo").strip().lower()
    texto = re.sub(r"[\s_-]+", "-", texto)
    return texto[:max_len] or "sem-titulo"


def gerar_relatorio_prisma_md(busca_id):
    """Gera o relatório de fluxo estilo PRISMA em Markdown, com os números reais da busca."""
    busca = db.obter_busca(busca_id)
    rel = db.relatorio_prisma(busca_id)

    linhas = [
        f"# Relatório de busca - {busca['termo_busca']}",
        "",
        f"- Data da execução: {busca['data_execucao']}",
        f"- Período: {busca['ano_inicio']}–{busca['ano_fim']}" if busca["ano_inicio"] else "- Período: não especificado",
        "",
        "## Strings de busca utilizadas (para reprodutibilidade)",
        "",
        f"- **OpenAlex:** `{busca['string_openalex']}`",
        f"- **SciELO:** `{busca['string_scielo']}`" if busca["string_scielo"] else "- **SciELO:** não executado",
        f"- **PhilPapers:** `{busca['string_philpapers']}`" if busca["string_philpapers"] else "- **PhilPapers:** integração pendente (ver clients/philpapers.py)",
        "",
        "## Identificação por fonte",
        "",
        "| Fonte | Registros identificados | Duplicatas (já vistas nesta busca) |",
        "|---|---|---|",
    ]
    for f in rel["por_fonte"]:
        linhas.append(f"| {f['fonte']} | {f['total']} | {f['duplicatas']} |")

    linhas += [
        "",
        f"**Total identificado (todas as fontes):** {rel['total_identificado']}",
        f"**Registros únicos após remoção de duplicatas:** {rel['unicos_apos_duplicatas']}",
        "",
        "## Triagem",
        "",
        f"- Ainda pendentes de decisão: {rel['pendentes_triagem']}",
        f"- Excluídos: {rel['total_excluidos']}",
    ]
    if rel["excluidos_por_motivo"]:
        linhas.append("")
        linhas.append("### Motivos de exclusão")
        linhas.append("")
        linhas.append("| Motivo | Quantidade |")
        linhas.append("|---|---|")
        for m in rel["excluidos_por_motivo"]:
            motivo = m["motivo_exclusao"] or "(sem motivo registrado)"
            linhas.append(f"| {motivo} | {m['n']} |")

    linhas += [
        "",
        f"## Incluídos na síntese final: {rel['total_incluidos']}",
        "",
        "_Este relatório reflete exclusivamente decisões e dados registrados no GELA. "
        "Nenhum número aqui foi estimado ou gerado por IA._",
    ]
    return "\n".join(linhas)


def gerar_pacote_obsidian(busca_id, apenas_incluidos=True):
    """
    Gera um .zip com uma nota Markdown por artigo + uma nota-mestra do tema,
    no formato esperado pelo Obsidian (links [[duplo colchete]]).
    Retorna os bytes do zip.
    """
    busca = db.obter_busca(busca_id)
    artigos = db.listar_artigos_por_busca(busca_id)
    if apenas_incluidos:
        artigos = [a for a in artigos if a["status_triagem"] == "incluido"]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        links = []
        for art in artigos:
            nome_arquivo = f"{_slug(art['titulo'])}.md"
            links.append(f"[[{_slug(art['titulo'])}]]")

            frontmatter = [
                "---",
                f"fonte: {art['fonte']}",
                f"ano: {art['ano'] or ''}",
                f"revista: \"{(art['revista'] or '').replace(chr(34), chr(39))}\"",
                f"doi: {art['doi'] or ''}",
                "---",
                "",
                f"# {art['titulo']}",
                "",
                f"**Autores:** {art['autores'] or 'não informado pela fonte'}",
                "",
                f"**Link:** {art['url'] or 'não disponível'}",
                "",
                "## Resumo",
                "",
                art["resumo"] if art["resumo_disponivel"] else "_Resumo não disponível na fonte._",
            ]
            zf.writestr(nome_arquivo, "\n".join(frontmatter))

        nota_mestra = [
            f"# {busca['termo_busca']}",
            "",
            f"Busca executada em {busca['data_execucao']}, período {busca['ano_inicio']}–{busca['ano_fim']}.",
            "",
            "## Artigos incluídos",
            "",
        ] + [f"- {link}" for link in links]
        zf.writestr(f"{_slug(busca['termo_busca'])}.md", "\n".join(nota_mestra))

    buffer.seek(0)
    return buffer.read()


def gerar_consolidado_notebooklm(busca_id, apenas_incluidos=True):
    """
    Gera um único Markdown consolidado (título, ano, fonte, URL, resumo integral
    de cada artigo) pronto para upload como fonte no NotebookLM.
    """
    busca = db.obter_busca(busca_id)
    artigos = db.listar_artigos_por_busca(busca_id)
    if apenas_incluidos:
        artigos = [a for a in artigos if a["status_triagem"] == "incluido"]

    partes = [f"# Compilado de artigos - {busca['termo_busca']}", ""]
    for art in artigos:
        partes += [
            f"## {art['titulo']}",
            f"- Fonte: {art['fonte']}",
            f"- Ano: {art['ano'] or 'não informado'}",
            f"- Revista: {art['revista'] or 'não informado'}",
            f"- DOI/URL: {art['url'] or art['doi'] or 'não disponível'}",
            "",
            art["resumo"] if art["resumo_disponivel"] else "_Resumo não disponível na fonte._",
            "",
            "---",
            "",
        ]
    return "\n".join(partes)
