import os
from functools import wraps

from flask import Flask, request, session, redirect, url_for, render_template, jsonify, Response
from dotenv import load_dotenv

import database as db
import export as exp
from clients import openalex, scielo, philpapers, bvs, google_scholar
from revisao.extrair_texto import extrair_texto, separar_corpo_e_referencias, extrair_paragrafos_com_formatacao
from revisao.verificar_referencias import verificar_lista_referencias
from correcao.abnt import verificar_lista_referencias_abnt

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "chave-insegura-troque-no-env")


def login_obrigatorio(f):
    @wraps(f)
    def decorado(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorado


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None
    if request.method == "POST":
        senha_correta = os.environ.get("GELA_PASSWORD", "")
        if not senha_correta:
            erro = "GELA_PASSWORD não está configurada no arquivo .env. Configure antes de usar o sistema."
        elif request.form.get("senha") == senha_correta:
            session["autenticado"] = True
            return redirect(url_for("index"))
        else:
            erro = "Senha incorreta."
    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_obrigatorio
def index():
    return render_template("index.html")


@app.route("/api/buscar", methods=["POST"])
@login_obrigatorio
def api_buscar():
    dados = request.get_json(force=True)
    termos_obrigatorios = [t.strip() for t in dados.get("termos_obrigatorios", []) if t.strip()]
    termos_qualquer = [t.strip() for t in dados.get("termos_qualquer", []) if t.strip()]
    ano_inicio = dados.get("ano_inicio")
    ano_fim = dados.get("ano_fim")

    if not termos_obrigatorios:
        return jsonify({"erro": "Informe ao menos um termo de busca."}), 400

    query_oa = openalex.montar_query_booleana(termos_obrigatorios, termos_qualquer)
    query_sc = scielo.montar_query_booleana(termos_obrigatorios, termos_qualquer)
    query_pp = philpapers.montar_query_booleana(termos_obrigatorios, termos_qualquer)
    query_bvs = bvs.montar_query_booleana(termos_obrigatorios, termos_qualquer)
    query_gs = google_scholar.montar_query_booleana(termos_obrigatorios, termos_qualquer)

    busca_id = db.criar_busca(
        termo_busca=" ".join(termos_obrigatorios),
        ano_inicio=ano_inicio, ano_fim=ano_fim,
        string_openalex=query_oa, string_scielo=query_sc, string_philpapers=query_pp,
        string_bvs=query_bvs, string_google_scholar=query_gs,
    )

    avisos = []
    todos_artigos = []

    try:
        res_oa, total_oa = openalex.buscar(query_oa, ano_inicio, ano_fim)
        todos_artigos += res_oa
    except RuntimeError as e:
        avisos.append(f"OpenAlex: {e}")
        total_oa = 0

    res_sc, total_sc = scielo.buscar(query_sc, ano_inicio, ano_fim)
    todos_artigos += res_sc
    if getattr(scielo, "PENDENTE", False):
        avisos.append(
            "SciELO: busca por palavra-chave livre não é possível via API oficial "
            "(ver clients/scielo.py para os detalhes e as opções de próximo passo)."
        )

    res_pp, total_pp = philpapers.buscar(query_pp, ano_inicio, ano_fim)
    if getattr(philpapers, "PENDENTE", False):
        avisos.append(
            "PhilPapers: integração ainda não implementada (requer contato prévio com a "
            "equipe do PhilPapers conforme os termos deles - ver clients/philpapers.py)."
        )

    try:
        res_bvs, total_bvs = bvs.buscar(query_bvs, ano_inicio, ano_fim)
        todos_artigos += res_bvs
    except RuntimeError as e:
        avisos.append(f"BVS: {e}")
        total_bvs = 0

    try:
        res_gs, total_gs = google_scholar.buscar(query_gs, ano_inicio, ano_fim)
        todos_artigos += res_gs
    except RuntimeError as e:
        avisos.append(f"Google Scholar: {e}")
        total_gs = 0

    resumo_dedup = db.salvar_artigos(busca_id, todos_artigos)

    return jsonify({
        "busca_id": busca_id,
        "contadores": {
            "openalex": total_oa,
            "scielo": total_sc,
            "philpapers": total_pp,
            "bvs": total_bvs,
            "google_scholar": total_gs,
        },
        "strings_busca": {
            "openalex": query_oa,
            "scielo": query_sc,
            "philpapers": query_pp,
            "bvs": query_bvs,
            "google_scholar": query_gs,
        },
        "resumo_dedup": resumo_dedup,
        "avisos": avisos,
    })


@app.route("/api/busca/<int:busca_id>/artigos")
@login_obrigatorio
def api_listar_artigos(busca_id):
    artigos = db.listar_artigos_por_busca(busca_id)
    return jsonify(artigos)


@app.route("/api/artigo/<path:artigo_id>/triagem", methods=["POST"])
@login_obrigatorio
def api_triagem(artigo_id):
    dados = request.get_json(force=True)
    status = dados.get("status")
    motivo = dados.get("motivo")
    if status not in ("pendente", "incluido", "excluido"):
        return jsonify({"erro": "status inválido"}), 400
    db.atualizar_triagem(artigo_id, status, motivo)
    return jsonify({"ok": True})


@app.route("/api/busca/<int:busca_id>/relatorio-prisma")
@login_obrigatorio
def api_relatorio_prisma(busca_id):
    return jsonify(db.relatorio_prisma(busca_id))


@app.route("/busca/<int:busca_id>/exportar/prisma.md")
@login_obrigatorio
def exportar_prisma(busca_id):
    conteudo = exp.gerar_relatorio_prisma_md(busca_id)
    return Response(conteudo, mimetype="text/markdown",
                     headers={"Content-Disposition": f"attachment; filename=relatorio-prisma-{busca_id}.md"})


@app.route("/busca/<int:busca_id>/exportar/obsidian.zip")
@login_obrigatorio
def exportar_obsidian(busca_id):
    conteudo = exp.gerar_pacote_obsidian(busca_id)
    return Response(conteudo, mimetype="application/zip",
                     headers={"Content-Disposition": f"attachment; filename=obsidian-{busca_id}.zip"})


@app.route("/busca/<int:busca_id>/exportar/notebooklm.md")
@login_obrigatorio
def exportar_notebooklm(busca_id):
    conteudo = exp.gerar_consolidado_notebooklm(busca_id)
    return Response(conteudo, mimetype="text/markdown",
                     headers={"Content-Disposition": f"attachment; filename=notebooklm-{busca_id}.md"})


@app.route("/revisao")
@login_obrigatorio
def revisao():
    return render_template("revisao.html")


@app.route("/api/revisao/upload", methods=["POST"])
@login_obrigatorio
def api_revisao_upload():
    if "arquivo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    arquivo = request.files["arquivo"]
    if not arquivo.filename:
        return jsonify({"erro": "Nenhum arquivo selecionado."}), 400

    try:
        conteudo_bytes = arquivo.read()
        linhas = extrair_texto(arquivo.filename, conteudo_bytes)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400

    corpo, lista_referencias, encontrou_cabecalho = separar_corpo_e_referencias(
        linhas, linhas_sao_paragrafos=arquivo.filename.lower().endswith(".docx")
    )

    resposta = {
        "nome_arquivo": arquivo.filename,
        "total_linhas_corpo": len(corpo),
        "cabecalho_referencias_encontrado": encontrou_cabecalho,
        "total_referencias_detectadas": len(lista_referencias),
    }

    if not encontrou_cabecalho:
        resposta["aviso"] = (
            "Não foi possível localizar uma seção de referências reconhecível "
            "(procurei por um cabeçalho como 'REFERÊNCIAS' ou 'REFERÊNCIAS BIBLIOGRÁFICAS'). "
            "Nenhuma referência foi verificada."
        )
        resposta["referencias_verificadas"] = []
        return jsonify(resposta)

    resposta["referencias_verificadas"] = verificar_lista_referencias(lista_referencias)
    return jsonify(resposta)


@app.route("/api/correcao/abnt", methods=["POST"])
@login_obrigatorio
def api_correcao_abnt():
    """
    Verifica a lista de referências de um arquivo contra o padrão estrutural
    da ABNT NBR 6023. Checagem heurística (não é reescrita automática).
    """
    if "arquivo" not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400

    arquivo = request.files["arquivo"]
    if not arquivo.filename:
        return jsonify({"erro": "Nenhum arquivo selecionado."}), 400

    eh_docx = arquivo.filename.lower().endswith(".docx")
    try:
        conteudo_bytes = arquivo.read()
        paragrafos = extrair_paragrafos_com_formatacao(arquivo.filename, conteudo_bytes)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400

    linhas = [p["texto"] for p in paragrafos]
    corpo, referencias_texto, encontrou_cabecalho = separar_corpo_e_referencias(
        linhas, linhas_sao_paragrafos=eh_docx
    )

    if not encontrou_cabecalho:
        return jsonify({
            "aviso": "Não foi possível localizar uma seção de referências reconhecível.",
            "resultado": [],
        })

    # localizar os parágrafos com formatação correspondentes à seção de referências:
    # o corpo tem N linhas, seguido do cabeçalho (1 linha), seguido das referências
    paragrafos_referencias = paragrafos[len(corpo) + 1:]

    resultado = verificar_lista_referencias_abnt(paragrafos_referencias)

    avisos_gerais = []
    if not eh_docx:
        avisos_gerais.append(
            "Este arquivo é um PDF: não foi possível verificar negrito/itálico dos títulos "
            "(essa informação não é preservada na extração de PDF). Recomendo enviar o .docx "
            "original se quiser essa checagem completa."
        )

    return jsonify({
        "nome_arquivo": arquivo.filename,
        "avisos_gerais": avisos_gerais,
        "resultado": resultado,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
