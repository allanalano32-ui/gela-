import os
from functools import wraps

from flask import Flask, request, session, redirect, url_for, render_template, jsonify, Response
from dotenv import load_dotenv

import database as db
import export as exp
from clients import openalex, scielo, philpapers

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

    busca_id = db.criar_busca(
        termo_busca=" ".join(termos_obrigatorios),
        ano_inicio=ano_inicio, ano_fim=ano_fim,
        string_openalex=query_oa, string_scielo=query_sc, string_philpapers=query_pp,
    )

    avisos = []
    todos_artigos = []

    try:
        res_oa, total_oa = openalex.buscar(query_oa, ano_inicio, ano_fim)
        todos_artigos += res_oa
    except RuntimeError as e:
        avisos.append(f"OpenAlex: {e}")
        total_oa = 0

    try:
        res_sc, total_sc = scielo.buscar(query_sc, ano_inicio, ano_fim)
        todos_artigos += res_sc
    except RuntimeError as e:
        avisos.append(f"SciELO: {e}")
        total_sc = 0

    res_pp, total_pp = philpapers.buscar(query_pp, ano_inicio, ano_fim)
    if getattr(philpapers, "PENDENTE", False):
        avisos.append(
            "PhilPapers: integração ainda não implementada (requer contato prévio com a "
            "equipe do PhilPapers conforme os termos deles - ver clients/philpapers.py)."
        )

    resumo_dedup = db.salvar_artigos(busca_id, todos_artigos)

    return jsonify({
        "busca_id": busca_id,
        "contadores": {
            "openalex": total_oa,
            "scielo": total_sc,
            "philpapers": total_pp,
        },
        "strings_busca": {
            "openalex": query_oa,
            "scielo": query_sc,
            "philpapers": query_pp,
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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
