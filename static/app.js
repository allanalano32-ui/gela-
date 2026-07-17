const NOMES_FONTE = { openalex: "OpenAlex", scielo: "SciELO", philpapers: "PhilPapers" };

document.getElementById("btn-buscar").addEventListener("click", buscar);

async function buscar() {
  const obrig = document.getElementById("termos-obrigatorios").value
    .split("\n").map(s => s.trim()).filter(Boolean);
  const qualquer = document.getElementById("termos-qualquer").value
    .split("\n").map(s => s.trim()).filter(Boolean);
  const anoInicio = document.getElementById("ano-inicio").value || null;
  const anoFim = document.getElementById("ano-fim").value || null;

  const status = document.getElementById("status-busca");
  if (obrig.length === 0) {
    status.textContent = "Informe ao menos um termo obrigatório.";
    return;
  }
  status.textContent = "Buscando nas fontes...";
  document.getElementById("resultados").innerHTML = "";

  const resp = await fetch("/api/buscar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      termos_obrigatorios: obrig, termos_qualquer: qualquer,
      ano_inicio: anoInicio, ano_fim: anoFim,
    }),
  });
  const dados = await resp.json();

  if (!resp.ok) {
    status.textContent = "Erro: " + (dados.erro || "falha na busca");
    return;
  }

  status.textContent = "";
  mostrarStringsBusca(dados);
  if (dados.avisos && dados.avisos.length) {
    status.innerHTML = dados.avisos.map(a => `<div class="aviso-fonte">${a}</div>`).join("");
  }

  await carregarArtigos(dados.busca_id);
  mostrarExportacoes(dados.busca_id);
}

function mostrarStringsBusca(dados) {
  const bloco = document.getElementById("strings-busca");
  bloco.hidden = false;
  document.getElementById("str-oa").textContent = dados.strings_busca.openalex;
  document.getElementById("str-sc").textContent = dados.strings_busca.scielo;
  document.getElementById("str-pp").textContent = dados.strings_busca.philpapers;
}

function mostrarExportacoes(buscaId) {
  const painel = document.getElementById("exportacoes");
  painel.hidden = false;
  document.getElementById("links-export").innerHTML = `
    <a href="/busca/${buscaId}/exportar/prisma.md" target="_blank">Relatório PRISMA (.md)</a>
    <a href="/busca/${buscaId}/exportar/obsidian.zip">Pacote Obsidian (.zip)</a>
    <a href="/busca/${buscaId}/exportar/notebooklm.md" target="_blank">Consolidado NotebookLM (.md)</a>
  `;
}

async function carregarArtigos(buscaId) {
  const resp = await fetch(`/api/busca/${buscaId}/artigos`);
  const artigos = await resp.json();

  const porFonte = {};
  for (const art of artigos) {
    porFonte[art.fonte] = porFonte[art.fonte] || [];
    porFonte[art.fonte].push(art);
  }

  const container = document.getElementById("resultados");
  container.innerHTML = "";

  for (const fonte of ["openalex", "scielo", "philpapers"]) {
    const lista = porFonte[fonte] || [];
    const bloco = document.createElement("div");
    bloco.className = "fonte-bloco";

    const header = document.createElement("div");
    header.className = "fonte-header";
    header.innerHTML = `<h3>${NOMES_FONTE[fonte]}</h3><span class="fonte-contador">${lista.length} artigos encontrados</span>`;
    bloco.appendChild(header);

    const listaEl = document.createElement("div");
    listaEl.hidden = false;
    header.addEventListener("click", () => { listaEl.hidden = !listaEl.hidden; });

    if (lista.length === 0 && fonte === "philpapers") {
      listaEl.innerHTML = `<p class="aviso-fonte">Integração com PhilPapers ainda pendente (ver clients/philpapers.py).</p>`;
    } else if (lista.length === 0) {
      listaEl.innerHTML = `<p class="artigo-meta">Nenhum resultado nesta fonte para os termos usados.</p>`;
    } else {
      for (const art of lista) {
        listaEl.appendChild(renderArtigo(art));
      }
    }
    bloco.appendChild(listaEl);
    container.appendChild(bloco);
  }
}

function renderArtigo(art) {
  const div = document.createElement("div");
  div.className = "artigo" + (art.duplicata_de ? " duplicata" : "");

  const resumoClasse = art.resumo_disponivel ? "artigo-resumo" : "artigo-resumo indisponivel";
  const resumoTexto = art.resumo_disponivel ? art.resumo : "Resumo não disponível na fonte.";

  div.innerHTML = `
    <p class="artigo-titulo">${escapeHtml(art.titulo)} ${art.duplicata_de ? '<span class="badge-duplicata">(duplicata)</span>' : ""}</p>
    <p class="artigo-meta">${art.ano || "ano não informado"} · ${escapeHtml(art.revista || "revista não informada")} ${art.url ? `· <a href="${art.url}" target="_blank">link</a>` : ""}</p>
    <p class="${resumoClasse}">${escapeHtml(resumoTexto)}</p>
    <div class="artigo-acoes">
      <button data-status="incluido" class="${art.status_triagem === 'incluido' ? 'ativo-incluido' : ''}">Relevante</button>
      <button data-status="excluido" class="${art.status_triagem === 'excluido' ? 'ativo-excluido' : ''}">Descartar</button>
    </div>
  `;

  div.querySelectorAll("[data-status]").forEach(btn => {
    btn.addEventListener("click", async () => {
      let motivo = null;
      if (btn.dataset.status === "excluido") {
        motivo = prompt("Motivo da exclusão (opcional, ajuda no relatório PRISMA):", "") || null;
      }
      await fetch(`/api/artigo/${encodeURIComponent(art.id)}/triagem`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: btn.dataset.status, motivo }),
      });
      btn.parentElement.querySelectorAll("button").forEach(b => b.className = "");
      btn.className = btn.dataset.status === "incluido" ? "ativo-incluido" : "ativo-excluido";
    });
  });

  return div;
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}
