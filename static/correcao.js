document.getElementById("btn-corrigir-abnt").addEventListener("click", corrigirAbnt);

async function corrigirAbnt() {
  const input = document.getElementById("arquivo-correcao");
  const status = document.getElementById("status-correcao");
  const container = document.getElementById("resultado-correcao");
  container.innerHTML = "";

  if (!input.files.length) {
    status.textContent = "Selecione um arquivo primeiro.";
    return;
  }

  status.textContent = "Verificando referências contra o padrão ABNT...";

  const formData = new FormData();
  formData.append("arquivo", input.files[0]);

  const resp = await fetch("/api/correcao/abnt", { method: "POST", body: formData });
  const dados = await resp.json();

  if (!resp.ok) {
    status.textContent = "Erro: " + (dados.erro || "falha ao processar o arquivo");
    return;
  }
  status.textContent = "";

  if (dados.aviso) {
    container.innerHTML = `<div class="aviso-fonte">${escapeHtmlCorrecao(dados.aviso)}</div>`;
    return;
  }

  (dados.avisos_gerais || []).forEach(a => {
    container.innerHTML += `<div class="aviso-fonte">${escapeHtmlCorrecao(a)}</div>`;
  });

  for (const item of dados.resultado) {
    const div = document.createElement("div");
    div.className = "fonte-bloco";
    const corIndicador = item.total_avisos === 0 ? "status-confirmada" : "status-possivel";
    div.innerHTML = `
      <p class="artigo-titulo">${escapeHtmlCorrecao(item.texto_original)}</p>
      <p class="${corIndicador}">${item.total_avisos === 0 ? "Sem observações estruturais" : item.total_avisos + " ponto(s) para conferir"}</p>
      <ul>
        ${item.achados.map(a => `<li class="artigo-meta">${a.nivel === "ok" ? "✓" : "⚠"} ${escapeHtmlCorrecao(a.mensagem)}</li>`).join("")}
      </ul>
    `;
    container.appendChild(div);
  }
}

function escapeHtmlCorrecao(str) {
  const d = document.createElement("div");
  d.textContent = str || "";
  return d.innerHTML;
}
