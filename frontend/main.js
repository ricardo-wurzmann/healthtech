const apiUrl = "http://127.0.0.1:8000/pipeline/debug";

const inputText = document.getElementById("inputText");
const runBtn = document.getElementById("runBtn");
const statusEl = document.getElementById("status");

const rawTextEl = document.getElementById("rawText");
const preprocessedTextEl = document.getElementById("preprocessedText");
const sentencesEl = document.getElementById("sentences");
const entitiesBeforeEl = document.getElementById("entitiesBefore");
const entitiesAfterEl = document.getElementById("entitiesAfter");
const filterLogEl = document.getElementById("filterLog");
const finalOutputEl = document.getElementById("finalOutput");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.className = isError ? "status error" : "status";
}

function renderJson(el, value) {
  if (typeof value === "string") {
    el.textContent = value;
    return;
  }
  el.textContent = JSON.stringify(value, null, 2);
}

async function runPipeline() {
  const text = inputText.value || "";
  if (!text.trim()) {
    setStatus("Insira um texto clínico para executar.", true);
    return;
  }

  runBtn.disabled = true;
  setStatus("Executando pipeline...");

  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(errText || "Erro ao executar o pipeline.");
    }

    const data = await response.json();
    renderJson(rawTextEl, data.raw_text);
    renderJson(preprocessedTextEl, data.preprocessed_text);
    renderJson(sentencesEl, data.sentences);
    renderJson(entitiesBeforeEl, data.entities_before_filter);
    renderJson(entitiesAfterEl, data.entities_after_filter);
    renderJson(filterLogEl, data.filter_log);
    renderJson(finalOutputEl, data.final_output);

    setStatus("Concluído.");
  } catch (err) {
    setStatus(`Erro: ${err.message}`, true);
  } finally {
    runBtn.disabled = false;
  }
}

runBtn.addEventListener("click", runPipeline);
