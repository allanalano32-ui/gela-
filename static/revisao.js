const NOMES_STATUS = {
  confirmada: { texto: "Correspondência encontrada", classe: "status-confirmada" },
  possivel: { texto: "Correspondência possível - conferir", classe: "status-possivel" },
  nao_encontrada: { texto: "Não encontrada - verificar manualmente", classe: "status-naoencontrada" },
  erro: { texto: "Erro na verificação", classe: "status-erro" },
};

document.getElementById("btn-enviar-revisao").addEventListener("click", enviarRevisao);

async function enviarRevisao() {
  const input = document.getElementById("arquivo-revisao");
  const status = document.getElementById("status-revisao");
  const resultado = document.getElementById("resultado-revisao");
  resultado.innerHTML = "";

  if (!input.files.length) {
    status.textContent = "Selecione um arquivo primeiro.";
    return;
  }

  status.textContent = "Extraindo texto e verificando referências (pode levar alguns segundos)...";

  const formData = new FormData();
  formData.append("arquivo", input.files[0]);

  const resp = await fetch("/api/revisao/upload", { method: "POST", body: formData });
  const dados = await resp.json();

  if (!resp.ok) {
    status.textContent = "Erro: " + (dados.erro || "falha ao processar o arquivo");
    return;
  }

  status.textContent = "";
  renderizarResultado(dados);
}

function renderizarResultado(dados) {
  const container = document.getElementById("resultado-revisao");

  const resumo = document.createElement("div");
  resumo.className = "painel-busca";
  resumo.innerHTML = `
    <h3>${escapeHtml(dados.nome_arquivo)}</h3>
    <p class="artigo-meta">${dados.total_linhas_corpo} linhas de corpo de texto ·
    ${dados.total_referencias_detectadas} referências detectadas</p>
  `;
  if (dados.aviso) {
    resumo.innerHTML += `<div class="aviso-fonte">${escapeHtml(dados.aviso)}</div>`;
  }
  container.appendChild(resumo);

  if (!dados.referencias_verificadas || dados.referencias_verificadas.length === 0) return;

  for (const ref of dados.referencias_verificadas) {
    container.appendChild(renderizarReferencia(ref));
  }
}

function renderizarReferencia(ref) {
  const div = document.createElement("div");
  div.className = "fonte-bloco";
  const statusInfo = NOMES_STATUS[ref.status] || { texto: ref.status, classe: "" };

  let candidatoHtml = "";
  if (ref.melhor_candidato) {
    const c = ref.melhor_candidato;
    candidatoHtml = `
      <div class="artigo" style="border-top:none;">
        <p class="artigo-meta">Candidato mais parecido encontrado no OpenAlex (similaridade: ${(ref.similaridade * 100).toFixed(0)}%):</p>
        <p class="artigo-titulo">${escapeHtml(c.titulo)}</p>
        <p class="artigo-meta">${c.ano || "ano não informado"} · ${escapeHtml(c.revista || "revista não informada")} · ${escapeHtml(c.autores || "autores não informados")}
        ${c.url ? ` · <a href="${c.url}" target="_blank">link</a>` : ""}</p>
      </div>
    `;
  }

  div.innerHTML = `
    <div class="fonte-header">
      <p class="artigo-titulo" style="margin:0;">${escapeHtml(ref.texto_original)}</p>
    </div>
    <p class="${statusInfo.classe}">${statusInfo.texto}</p>
    <p class="artigo-meta">${escapeHtml(ref.mensagem)}</p>
    ${candidatoHtml}
  `;
  return div;
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}
