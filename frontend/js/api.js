
const API = "";
let selectedMode = "MANAGER";
let currentCareerId = null;
let busy = false;
let activeCareer = null;
let dashboardVersion = 0;

const $ = (selector) => document.querySelector(selector);

function notify(message, success = false) {
  const el = $("#message");
  el.textContent = message;
  el.className = success ? "message success" : "message";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function clearNotice() {
  $("#message").classList.add("hidden");
}

async function request(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });

  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : null; }
  catch { data = text; }

  if (!response.ok) {
    let detail = data?.detail || `Erro HTTP ${response.status}`;
    if (Array.isArray(detail)) {
      detail = detail.map(e => e.msg || "Dados inválidos").join("; ");
    }
    throw new Error(String(detail));
  }
  return data;
}

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;"
  })[c]);
}

function showPage(page) {
  document.querySelectorAll(".page").forEach(el => el.classList.add("hidden"));
  $("#" + page).classList.remove("hidden");
  document.querySelectorAll(".nav-btn").forEach(el =>
    el.classList.toggle("active", el.dataset.page === page)
  );
  clearNotice();

  const titles = {
    home: "Sua história começa aqui.",
    new: "Crie seu legado.",
    continue: "Continue sua história.",
    dashboard: "Central da carreira."
  };
  $("#page-title").textContent = titles[page];

  if (page === "new") loadClubs();
  if (page === "continue") loadCareers();
}

function setMode(mode) {
  selectedMode = mode;
  document.querySelectorAll("[data-select]").forEach(btn =>
    btn.classList.toggle("selected", btn.dataset.select === mode)
  );
  $("#manager-fields").classList.toggle("hidden", mode !== "MANAGER");
  $("#player-fields").classList.toggle("hidden", mode !== "PLAYER");
}

async function loadClubs() {
  const select = $("#club");
  select.replaceChildren(new Option("Carregando clubes...", ""));

  try {
    const clubs = await request("/clubs");
    select.replaceChildren(new Option("Selecione um clube", ""));
    clubs.forEach(club =>
      select.add(new Option(
        `${club.name} — Força ${club.strength}`, club.name
      ))
    );
  } catch (err) {
    select.replaceChildren(new Option("Erro ao carregar clubes", ""));
    notify(err.message);
  }
}

async function createCareer(event) {
  event.preventDefault();
  if (busy) return;

  const name = $("#career-name").value.trim();
  if (name.length < 2) return notify("Informe um nome válido para a carreira.");

  const body = { name, mode: selectedMode };

  if (selectedMode === "MANAGER") {
    body.club = $("#club").value;
    if (!body.club) return notify("Escolha um clube.");
  } else {
    const playerName = $("#player-name").value.trim();
    if (playerName.length < 2) return notify("Informe o nome do jogador.");
    body.player = {
      name: playerName,
      position: $("#position").value,
      age: Number($("#age").value)
    };
    if (!Number.isInteger(body.player.age) ||
        body.player.age < 16 || body.player.age > 21) {
      return notify("A idade deve estar entre 16 e 21 anos.");
    }
  }

  busy = true;
  $("#create-btn").disabled = true;
  $("#create-btn").textContent = "CRIANDO CARREIRA...";

  try {
    const career = await request("/careers", {
      method: "POST",
      body: JSON.stringify(body)
    });
    await openCareer(career.id);
    notify("Carreira criada com sucesso!", true);
  } catch (err) {
    notify(err.message);
  } finally {
    busy = false;
    $("#create-btn").disabled = false;
    $("#create-btn").textContent = "CRIAR CARREIRA ↗";
  }
}

async function loadCareers() {
  const list = $("#career-list");
  list.textContent = "Carregando...";

  try {
    const careers = await request("/careers");
    list.replaceChildren();

    if (!careers.length) {
      list.textContent = "Nenhuma carreira encontrada. Crie a sua primeira!";
      return;
    }

    careers.forEach(c => {
      const card = document.createElement("div");
      card.className = "career-entry";
      card.innerHTML = `
        <div>
          <h3>${escapeHTML(c.name)}</h3>
          <p>${c.mode === "MANAGER" ? "TÉCNICO" : "JOGADOR"}
            · TEMPORADA ${c.season} · RODADA ${c.round}
            · ${escapeHTML(c.status)}</p>
        </div>
        <button class="small-btn">CONTINUAR ↗</button>
      `;
      card.querySelector("button").addEventListener("click", () => openCareer(c.id));
      list.append(card);
    });
  } catch (err) {
    list.textContent = "";
    notify(err.message);
  }
}

function stat(label, value) {
  return `<div class="stat-card"><small>${escapeHTML(label)}</small>
    <strong>${escapeHTML(value)}</strong></div>`;
}

async function openCareer(id) {
  const version = ++dashboardVersion;
  try {
    const career = await request(`/careers/${id}`);
    if (version !== dashboardVersion) return;
    activeCareer = career;
    currentCareerId = career.id;
    $("#player-section").classList.add("hidden");
    $("#squad-section").classList.add("hidden");
    showPage("dashboard");

    $("#career-mode-label").textContent =
      career.mode === "MANAGER" ? "MODO TÉCNICO" : "MODO JOGADOR";

    let html = "";

    if (career.mode === "MANAGER") {
      html = `
        <h2>${escapeHTML(career.team?.name)}</h2>
        <div class="stats-grid">
          ${stat("TEMPORADA", career.season)}
          ${stat("RODADA", career.round)}
          ${stat("ORÇAMENTO (MILHÕES)", career.team?.budget_millions ?? "-")}
          ${stat("CONFIANÇA DA DIRETORIA", career.board_confidence)}
        </div>
        <p>Próximo confronto:
          ${escapeHTML(career.next_fixture?.home || "A definir")}
          × ${escapeHTML(career.next_fixture?.away || "A definir")}
        </p>`;
    } else {
      const p = career.player || {};
      html = `
        <h2>${escapeHTML(p.name)}</h2>
        <div class="stats-grid">
          ${stat("OVERALL", p.rating ?? "-")}
          ${stat("POTENCIAL", p.potential ?? "-")}
          ${stat("POSIÇÃO", p.position ?? "-")}
          ${stat("TEMPORADA", career.season)}
        </div>
        <p>Clube: ${escapeHTML(career.team?.name)}
          · Idade: ${escapeHTML(p.age)}
          · Rodada: ${escapeHTML(career.round)}</p>`;
    }

    $("#dashboard-content").innerHTML = html;
    $("#advance-btn").disabled =
      career.status !== "ACTIVE";
    $("#advance-btn").textContent = career.season_finished ? "INICIAR PRÓXIMA TEMPORADA ↗" : "SIMULAR PRÓXIMA RODADA ⚽";

    await loadStandings(id, career.team?.id);
    if (version !== dashboardVersion) return;
    if (career.mode === "MANAGER") {
      await loadSquad(id);
      setRosterEnabled(career.status === "ACTIVE");
    } else {
      $("#squad-section").classList.add("hidden");
      await loadPlayerCareer(career);
    }
    if (version !== dashboardVersion) return;
    await loadFixtures(id);
  } catch (err) {
    notify(err.message);
  }
}

async function loadStandings(id, teamId) {
  try {
    const rows = await request(`/careers/${id}/standings`);
    if (id !== currentCareerId) return;
    const table = document.createElement("table");
    table.innerHTML = `
      <thead><tr>
        <th>POS</th><th>CLUBE</th><th>J</th>
        <th>V</th><th>E</th><th>D</th><th>SG</th><th>PTS</th>
      </tr></thead><tbody></tbody>`;

    const tbody = table.querySelector("tbody");

    rows.forEach(r => {
      const tr = document.createElement("tr");
      if (r.team_id === teamId) tr.className = "highlight";
      [r.position, r.name, r.played, r.wins, r.draws,
       r.losses, r.goal_diff, r.points].forEach(value => {
        const td = document.createElement("td");
        td.textContent = value;
        tr.append(td);
      });
      tbody.append(tr);
    });

    $("#standings").replaceChildren(table);
  } catch (err) {
    $("#standings").textContent = "Não foi possível carregar a classificação.";
  }
}

async function advanceRound() {
  if (busy || currentCareerId === null) return;
  if (!confirm(activeCareer?.season_finished ? "Encerrar esta temporada e iniciar a próxima?" : "Simular a próxima rodada? Esta ação altera a carreira.")) return;

  busy = true;
  $("#advance-btn").disabled = true;

  try {
    const result = await request(
      activeCareer?.season_finished ? `/careers/${currentCareerId}/next-season` : `/careers/${currentCareerId}/advance?rounds=1`,
      { method: "POST" }
    );
    await openCareer(currentCareerId);
    notify(result.message || `Carreira atualizada! Temporada ${result.next_season || result.season}.`, true);
  } catch (err) {
    notify(err.message);
  } finally {
    busy = false;
    $("#advance-btn").disabled = activeCareer?.status !== "ACTIVE";
  }
}

document.querySelectorAll("[data-page]").forEach(btn =>
  btn.addEventListener("click", () => showPage(btn.dataset.page))
);

document.querySelectorAll("[data-mode]").forEach(btn =>
  btn.addEventListener("click", () => {
    setMode(btn.dataset.mode);
    showPage("new");
  })
);

document.querySelectorAll("[data-select]").forEach(btn =>
  btn.addEventListener("click", () => setMode(btn.dataset.select))
);

$("#career-form").addEventListener("submit", createCareer);
$("#refresh-careers").addEventListener("click", loadCareers);
$("#advance-btn").addEventListener("click", advanceRound);
$("#back-careers").addEventListener("click", () => showPage("continue"));

async function checkAPI() {
  try {
    await request("/health");
    $("#api-status").textContent = "API conectada";
    $(".status-dot").classList.add("online");
  } catch {
    $("#api-status").textContent = "API indisponível";
  }
}

checkAPI();
