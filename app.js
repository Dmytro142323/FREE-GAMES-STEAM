const state = { data: null, category: "All", query: "", sort: "popular", page: 1, pageSize: 40, featured: 0 };
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[c]));

function selectGames() {
  let games = state.data.games;
  if (state.category === "Online") games = games.filter(g => g.online);
  else if (state.category !== "All") games = games.filter(g => g.tags.includes(state.category));
  if (state.query) {
    const q = state.query.toLowerCase();
    games = games.filter(g => g.name.toLowerCase().includes(q) || g.tags.some(t => t.toLowerCase().includes(q)));
  }
  games = [...games];
  if (state.sort === "reviews") games.sort((a, b) => b.reviewPercent - a.reviewPercent);
  if (state.sort === "newest") games.sort((a, b) => (b.releaseTimestamp || 0) - (a.releaseTimestamp || 0));
  if (state.sort === "name") games.sort((a, b) => a.name.localeCompare(b.name));
  return games;
}

function renderFeatured() {
  const games = state.data.featured;
  if (!games.length) return;
  const g = games[state.featured % games.length];
  const shots = [g.header, g.capsule, ...g.screenshots].filter(Boolean).slice(0, 4);
  $("#featured-card").innerHTML = `<a class="featured-art" href="${g.url}" target="_blank" rel="noopener" style="background-image:url('${g.header}')"></a>
    <div class="featured-info"><h2>${esc(g.name)}</h2>
      <div class="featured-thumbs">${shots.map(src => `<img src="${src}" alt="" loading="lazy">`).join("")}</div>
      <div class="now-free">Play for free</div>
      <div class="tags">${g.tags.slice(0, 3).map(t => `<span>${esc(t)}</span>`).join(" ")}</div>
      <a class="price-free" href="${g.url}" target="_blank" rel="noopener">Free To Play</a>
    </div>`;
  $("#featured-dots").innerHTML = games.map((_, i) => `<button class="${i === state.featured ? "active" : ""}" data-feature="${i}" aria-label="Featured game ${i + 1}"></button>`).join("");
  $$("#featured-dots button").forEach(btn => btn.onclick = () => { state.featured = Number(btn.dataset.feature); renderFeatured(); });
}

function renderCategories() {
  const categories = state.data.categories.slice(0, 18);
  const quick = ["Online", "Action", "RPG", "Strategy", "Simulation", "Adventure", "Casual", "Sports"];
  $("#quick-category-list").innerHTML = quick.map(c => `<button class="quick-cat ${c === "Online" ? "online" : ""}" data-category="${c}">${c}</button>`).join("");
  $("#sidebar-categories").innerHTML = categories.map(c => `<button class="side-filter" data-category="${esc(c.name)}"><span>${esc(c.name)}</span><b>${c.count.toLocaleString()}</b></button>`).join("");
  $("#all-count").textContent = state.data.total.toLocaleString();
  $("#online-count").textContent = state.data.onlineCount.toLocaleString();
  $$("[data-category]").forEach(btn => btn.onclick = () => setCategory(btn.dataset.category));
}

function setCategory(category) {
  state.category = category; state.page = 1;
  $$(".side-filter").forEach(b => b.classList.toggle("active", b.dataset.category === category));
  $("#catalog-title").textContent = category === "All" ? "ALL FREE GAMES" : category.toUpperCase();
  $("#active-filter").innerHTML = category === "All" ? "" : `<span>${esc(category)} ×</span>`;
  renderGames();
  $("#catalog").scrollIntoView({ behavior: "smooth" });
}

function platformIcons(platforms) {
  return [platforms.windows && "▣ WIN", platforms.mac && "◆ MAC", platforms.linux && "● LINUX"].filter(Boolean).join(" ");
}

function renderGames() {
  const games = selectGames();
  const pages = Math.max(1, Math.ceil(games.length / state.pageSize));
  if (state.page > pages) state.page = pages;
  const start = (state.page - 1) * state.pageSize;
  const visible = games.slice(start, start + state.pageSize);
  $("#result-count").textContent = games.length.toLocaleString();
  $("#game-list").innerHTML = visible.length ? visible.map(g => `<a class="game-row" href="${g.url}" target="_blank" rel="noopener">
    <img class="game-capsule" src="${g.capsule}" alt="${esc(g.name)}" loading="lazy">
    <div class="game-info"><h3>${esc(g.name)} ${g.online ? `<span class="online-pill">ONLINE</span>` : ""}</h3>
      <span class="platforms">${platformIcons(g.platforms)}</span><span class="release">${esc(g.release || "Release date unavailable")}</span>
      <div class="tag-line">${g.tags.map(esc).join(", ")}</div>
    </div>
    <div class="game-price"><span class="free-label">Free</span><span class="review">${esc(g.reviewText || "No reviews yet")}${g.reviewPercent ? ` · ${g.reviewPercent}%` : ""}</span></div>
  </a>`).join("") : `<div class="empty">No free games match these filters.</div>`;
  $("#page-status").textContent = `Page ${state.page.toLocaleString()} of ${pages.toLocaleString()}`;
  $("#prev-page").disabled = state.page === 1;
  $("#next-page").disabled = state.page === pages;
}

function bind() {
  $("#game-search").oninput = e => { state.query = e.target.value.trim(); state.page = 1; renderGames(); };
  $("#nav-search").oninput = e => { $("#game-search").value = e.target.value; state.query = e.target.value.trim(); state.page = 1; renderGames(); };
  $("#clear-search").onclick = () => { state.query = ""; $("#game-search").value = ""; $("#nav-search").value = ""; renderGames(); };
  $("#sort-select").onchange = e => { state.sort = e.target.value; state.page = 1; renderGames(); };
  $("#prev-page").onclick = () => { if (state.page > 1) { state.page--; renderGames(); $("#catalog").scrollIntoView(); } };
  $("#next-page").onclick = () => { state.page++; renderGames(); $("#catalog").scrollIntoView(); };
  $(".menu-button").onclick = () => { const open = $(".menu-button").getAttribute("aria-expanded") === "true"; $(".menu-button").setAttribute("aria-expanded", String(!open)); $("#mobile-menu").classList.toggle("open", !open); };
  setInterval(() => { if (state.data?.featured?.length) { state.featured = (state.featured + 1) % state.data.featured.length; renderFeatured(); } }, 8000);
}

async function init() {
  try {
    const response = await fetch(`data/games.json?v=${Date.now()}`);
    if (!response.ok) throw new Error("catalog");
    state.data = await response.json();
    $("#updated-at").textContent = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(state.data.updatedAt));
    renderFeatured(); renderCategories(); renderGames(); bind();
  } catch {
    $("#game-list").innerHTML = `<div class="empty">The Steam catalog could not be loaded. Please refresh this page later.</div>`;
  }
}
init();
