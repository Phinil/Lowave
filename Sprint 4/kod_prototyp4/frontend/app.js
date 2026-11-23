import { api } from "./api.js";

const root = document.getElementById("app");

const numberFormatter = new Intl.NumberFormat("sv-SE");
const relativeFormatter = new Intl.RelativeTimeFormat("sv", { numeric: "auto" });

const navItems = [
  { key: "discover", label: "Upptäck", icon: "home" },
  { key: "suggest", label: "Föreslå", icon: "plus" },
  { key: "feed", label: "Flöde", icon: "radio" },
  { key: "search", label: "Sök", icon: "sparkles" },
  { key: "profile", label: "Profil", icon: "user" },
];

const state = {
  boot: null,
  view: "discover",
  isLoading: true,
  loadingMessage: "Laddar appen...",
  error: "",
  selectedGenres: [],
  discoverResults: [],
  discoverHasRun: false,
  searchResults: [],
  searchInterpretation: null,
  searchPrompt: "",
  searchHasRun: false,
  feed: {
    card: null,
    communityPosts: [],
    seenKeys: [],
  },
  profile: {
    saved_artists: [],
    custom_artists: [],
    saved_count: 0,
    custom_count: 0,
  },
  savedKeys: new Set(),
  suggestionDraft: {
    isrc: "",
    confirm: false,
    note: "",
  },
  suggestionStatus: "",
  itemIndex: new Map(),
  communityTipOpen: false,
};

function icon(name) {
  const common = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
  const icons = {
    note: `<svg ${common}><path d="M12 3v11.4a3.4 3.4 0 1 1-1.8-3V6.6l7-1.8V14a3.4 3.4 0 1 1-1.8-3V3.9z"/></svg>`,
    home: `<svg ${common}><path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10.5V20h13V10.5"/></svg>`,
    plus: `<svg ${common}><circle cx="12" cy="12" r="8.5"/><path d="M12 8v8"/><path d="M8 12h8"/></svg>`,
    radio: `<svg ${common}><path d="M12 12m-2.5 0a2.5 2.5 0 1 0 5 0 2.5 2.5 0 1 0-5 0"/><path d="M5.5 5.5a9 9 0 0 0 0 13"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/><path d="M8.5 8.5a5 5 0 0 0 0 7"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/></svg>`,
    sparkles: `<svg ${common}><path d="m12 3 1.8 4.8L18.5 9l-4.7 1.2L12 15l-1.8-4.8L5.5 9l4.7-1.2z"/><path d="m18 2 .6 1.6L20.2 4l-1.6.4L18 6l-.6-1.6L15.8 4l1.6-.4z"/></svg>`,
    user: `<svg ${common}><path d="M12 13.5a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>`,
    bookmark: `<svg ${common}><path d="M8 4.5h8a1 1 0 0 1 1 1V20l-5-3-5 3V5.5a1 1 0 0 1 1-1Z"/></svg>`,
    bookmarkFilled: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 4.5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1V20l-5-3-5 3z"/></svg>`,
    heart: `<svg ${common}><path d="M12 20s-6.5-4.35-8.2-8.25A4.9 4.9 0 0 1 12 6a4.9 4.9 0 0 1 8.2 5.75C18.5 15.65 12 20 12 20Z"/></svg>`,
    next: `<svg ${common}><path d="M8 7.5 16 12l-8 4.5z"/><path d="M18 7v10"/></svg>`,
    plane: `<svg ${common}><path d="M21 3 10 14"/><path d="m21 3-7 18-4-7-7-4z"/></svg>`,
    trash: `<svg ${common}><path d="M4.5 7h15"/><path d="M9 7V5.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V7"/><path d="M8.5 10.5V18"/><path d="M12 10.5V18"/><path d="M15.5 10.5V18"/><path d="M6.5 7 7.4 19a1 1 0 0 0 1 .9h7.2a1 1 0 0 0 1-.9L17.5 7"/></svg>`,
    refresh: `<svg ${common}><path d="M20 6v5h-5"/><path d="M19 11a7 7 0 1 1-2-5"/></svg>`,
  };

  return icons[name] || "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "saknas";
  }
  const number = Number(value);
  if (Number.isNaN(number)) {
    return "saknas";
  }
  if (number >= 1000000) {
    return `${(number / 1000000).toFixed(1).replace(".0", "")}M`;
  }
  if (number >= 1000) {
    return `${(number / 1000).toFixed(1).replace(".0", "")}k`;
  }
  return numberFormatter.format(Math.round(number));
}

function formatRelativeTime(value) {
  if (!value) {
    return "nyss";
  }

  const date = new Date(value);
  const diffMs = date.getTime() - Date.now();
  const diffMinutes = Math.round(diffMs / (1000 * 60));

  if (Math.abs(diffMinutes) < 60) {
    return relativeFormatter.format(diffMinutes, "minute");
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return relativeFormatter.format(diffHours, "hour");
  }

  const diffDays = Math.round(diffHours / 24);
  return relativeFormatter.format(diffDays, "day");
}

function rememberItems(items = []) {
  items.forEach((item) => {
    if (item?.artist_key) {
      state.itemIndex.set(item.artist_key, item);
    }
  });
}

function syncProfile(profilePayload) {
  state.profile = profilePayload;
  state.savedKeys = new Set(profilePayload.saved_artists.map((item) => item.artist_key));
  rememberItems(profilePayload.saved_artists);
  rememberItems(profilePayload.custom_artists);
}

function setLoading(isLoading, message = "Jobbar...") {
  state.isLoading = isLoading;
  state.loadingMessage = message;
  render();
}

function setError(message = "") {
  state.error = message;
  render();
}

function activeCardPayload(artistKey) {
  const item = state.itemIndex.get(artistKey);
  if (!item) {
    return null;
  }

  return {
    artist_key: item.artist_key,
    artist: item.artist,
    song: item.song,
    genre: item.genre,
    image: item.image,
    preview: item.preview,
    deezer_link: item.deezer_link,
    lastfm_link: item.lastfm_link,
    reason: item.reason,
    top_genres: item.top_genres || [],
    similar_artists: item.similar_artists || [],
    metrics: item.metrics || {},
    audio_signature: item.audio_signature || {},
    source: item.source || state.view,
    is_custom: Boolean(item.is_custom),
  };
}

async function initialize() {
  try {
    const [boot, profile, feed] = await Promise.all([
      api.bootstrap(),
      api.profile(),
      api.feed({ exclude_artist_keys: [] }),
    ]);

    state.boot = boot;
    state.feed.card = feed.card;
    state.feed.communityPosts = feed.community_posts || [];
    rememberItems(feed.card ? [feed.card] : []);
    syncProfile(profile);
  } catch (error) {
    state.error = error.message;
  } finally {
    state.isLoading = false;
    render();
  }
}

function render() {
  const boot = state.boot;
  const counts = boot?.stats;

  root.innerHTML = `
    <div class="app-shell">
      <div class="ambient ambient-one"></div>
      <div class="ambient ambient-two"></div>
      <div class="content-shell">
        ${state.error ? `<div class="banner error-banner">${escapeHtml(state.error)}</div>` : ""}
        <main class="screen">
          ${state.isLoading ? renderLoadingState() : renderCurrentView()}
        </main>
        <nav class="bottom-nav">
          ${navItems.map(renderNavItem).join("")}
        </nav>
      </div>
      ${counts ? `<div class="corner-badge">${counts.artist_count} artister indexerade</div>` : ""}
    </div>
  `;

  refreshActionStates();
}

function renderLoadingState() {
  return `
    <section class="hero-stack loading-state">
      <div class="hero-icon shimmer">${icon("note")}</div>
      <h1>${escapeHtml(state.loadingMessage)}</h1>
      <p>Vi kopplar ihop datasetet med Deezer och Last.fm.</p>
    </section>
  `;
}

function renderNavItem(item) {
  const activeClass = state.view === item.key ? "is-active" : "";
  return `
    <button class="nav-button ${activeClass}" data-view="${item.key}" type="button">
      <span class="nav-icon">${icon(item.icon)}</span>
      <span>${item.label}</span>
    </button>
  `;
}

function renderCurrentView() {
  switch (state.view) {
    case "discover":
      return renderDiscoverView();
    case "suggest":
      return renderSuggestView();
    case "feed":
      return renderFeedView();
    case "search":
      return renderSearchView();
    case "profile":
      return renderProfileView();
    default:
      return renderDiscoverView();
  }
}

function renderDiscoverView() {
  if (state.discoverResults.length > 0) {
    rememberItems(state.discoverResults);
    return `
      <section class="hero-stack compact-hero">
        <div class="hero-icon">${icon("note")}</div>
        <h1>Dina Perfekta Matchningar</h1>
        <p>Artister och låtar anpassade efter dina val.</p>
      </section>
      <section class="stack">
        ${state.discoverResults.map((item) => renderArtistCard(item)).join("")}
        <button class="secondary-button wide-button" type="button" data-action="discover-reset">Starta Ny Sökning</button>
      </section>
    `;
  }

  return `
    <section class="hero-stack">
      <div class="hero-icon">${icon("note")}</div>
      <h1>Upptäck Din Musik</h1>
      <p>Välj dina favoritgenrer för att komma igång.</p>
      <div class="chip-grid">
        ${(state.boot?.genres || [])
          .map(
            (genre) => `
              <button
                class="genre-chip ${state.selectedGenres.includes(genre.label) ? "is-active" : ""}"
                type="button"
                data-genre="${genre.label}"
              >
                ${escapeHtml(genre.label)}
              </button>
            `
          )
          .join("")}
      </div>
      <button
        class="primary-button wide-button"
        type="button"
        data-action="discover-submit"
        ${state.selectedGenres.length === 0 ? "disabled" : ""}
      >
        Hitta Min Musik
      </button>
    </section>
    ${
      state.discoverHasRun
        ? renderEmptyState(
            "Inga träffar just nu",
            "Testa en annan genreblandning eller sök igen så provar vi ett nytt urval av mindre artister."
          )
        : ""
    }
    <section class="support-card">
      <h2>${escapeHtml(state.boot?.small_artist_definition?.title || "Mindre artister")}</h2>
      <p>${escapeHtml(state.boot?.small_artist_definition?.text || "")}</p>
      <div class="metric-row">
        <span class="metric-pill">Spotify ≤ ${escapeHtml(state.boot?.small_artist_definition?.thresholds?.spotify_avg_popularity_max ?? "")}</span>
        <span class="metric-pill">Last.fm ≤ ${formatNumber(state.boot?.small_artist_definition?.thresholds?.lastfm_listeners_max)}</span>
        <span class="metric-pill">Deezer ≤ ${formatNumber(state.boot?.small_artist_definition?.thresholds?.deezer_fans_max)}</span>
      </div>
    </section>
  `;
}

function renderSuggestView() {
  const recentCustom = state.profile.custom_artists.slice(0, 2);
  rememberItems(recentCustom);

  return `
    <section class="hero-stack compact-hero">
      <div class="hero-icon">${icon("plane")}</div>
      <h1>Föreslå en Låt</h1>
      <p>Skicka in ditt musikförslag med en ISRC-kod.</p>
    </section>
    <section class="stack">
      <form class="card form-card" id="suggest-form" novalidate>
        <label class="field-label" for="isrc-input">ISRC-kod</label>
        <input
          id="isrc-input"
          name="isrc"
          class="text-input"
          type="text"
          value="${escapeHtml(state.suggestionDraft.isrc)}"
          placeholder="t.ex. USRC17607839"
          autocomplete="off"
        />
        <p class="microcopy">International Standard Recording Code (ISRC) är en unik identifierare för inspelningar.</p>
        <label class="checkbox-card">
          <input id="confirm-smaller" name="confirm" type="checkbox" ${state.suggestionDraft.confirm ? "checked" : ""} />
          <span>Jag bekräftar att det här är en mindre artist som jag vill lägga till i appen.</span>
        </label>
        <button class="primary-button wide-button" type="submit" id="suggest-submit">
          Skicka In Låt
        </button>
      </form>
      ${
        state.suggestionStatus
          ? `<div class="banner success-banner">${escapeHtml(state.suggestionStatus)}</div>`
          : ""
      }
      <section class="support-card">
        <h2>Hur hittar man ISRC-koder?</h2>
        <p>Du kan hitta ISRC-koder på musikplattformar som Spotify, Apple Music eller via musiktjänster och databaser som visar låtmetadata.</p>
      </section>
      ${
        recentCustom.length
          ? `
            <section class="stack">
              <h2 class="section-title">Senast tillagda</h2>
              ${recentCustom.map((item) => renderProfileCard(item, "custom")).join("")}
            </section>
          `
          : ""
      }
    </section>
  `;
}

function renderFeedView() {
  const card = state.feed.card;
  rememberItems(card ? [card] : []);
  const communityPosts = state.feed.communityPosts || [];

  return `
    <section class="stack">
      ${
        card
          ? `
            <article class="feed-hero">
              <div class="feed-hero-image">
                ${
                  card.image
                    ? `<img src="${escapeHtml(card.image)}" alt="${escapeHtml(card.artist)}" />`
                    : `<div class="image-fallback">${icon("note")}</div>`
                }
              </div>
              <div class="feed-detail card">
                <p class="eyebrow">Flödesval</p>
                <h1>${escapeHtml(card.song || card.artist)}</h1>
                <p class="feed-artist">${escapeHtml(card.artist)}</p>
                <div class="metric-row">
                  ${renderMetricPills(card.metrics)}
                </div>
                <p class="body-copy">${escapeHtml(card.bio || card.reason || "En ny mindre artist att utforska.")}</p>
                <div class="action-row">
                  <button type="button" class="icon-button" data-action="save-toggle" data-key="${escapeHtml(card.artist_key)}">${state.savedKeys.has(card.artist_key) ? icon("bookmarkFilled") : icon("heart")}</button>
                  ${
                    card.preview
                      ? `<audio class="audio-player" controls src="${escapeHtml(card.preview)}"></audio>`
                      : ""
                  }
                  <button type="button" class="primary-button mini-button" data-action="feed-next">
                    ${icon("next")} Byt
                  </button>
                </div>
              </div>
            </article>
          `
          : renderEmptyState("Flödet är tomt", "Lägg till en artist eller gör en ny upptäckt så fyller vi flödet.")
      }
      <section class="support-card community-divider">
        <h2>Community Flöde</h2>
        <form class="community-form" id="community-form">
          <textarea
            class="text-area"
            name="text"
            rows="4"
            placeholder="Dela dina tankar eller tipsa om en låt..."
          ></textarea>
          ${
            state.communityTipOpen
              ? `
                <div class="tip-grid">
                  <input class="text-input" type="text" name="tip_artist" placeholder="Artist (valfritt)" />
                  <input class="text-input" type="text" name="tip_song" placeholder="Låt (valfritt)" />
                </div>
              `
              : ""
          }
          <div class="composer-actions">
            <button type="button" class="ghost-button" data-action="toggle-tip">+ Låttips</button>
            <button type="submit" class="primary-button mini-button">${icon("plane")} Posta</button>
          </div>
        </form>
      </section>
      <section class="stack">
        ${communityPosts.map(renderCommunityPost).join("")}
      </section>
    </section>
  `;
}

function renderSearchView() {
  if (state.searchResults.length > 0) {
    rememberItems(state.searchResults);
  }

  return `
    <section class="hero-stack compact-hero">
      <div class="hero-icon">${icon("sparkles")}</div>
      <h1>Musiksökare</h1>
      <p>Beskriv musiken du vill upptäcka.</p>
      <form class="prompt-bar" id="search-form">
        <input
          id="prompt-input"
          name="prompt"
          type="text"
          class="text-input prompt-input"
          value="${escapeHtml(state.searchPrompt)}"
          placeholder="t.ex. låtar som känns som höst"
          autocomplete="off"
        />
        <button class="icon-submit" type="submit" aria-label="Sök">${icon("plane")}</button>
      </form>
    </section>
    ${
      state.searchResults.length > 0
        ? `
          <section class="stack">
            <h2 class="section-title">Rekommenderade mindre artister</h2>
            ${state.searchResults.map((item) => renderArtistCard(item, { compact: true })).join("")}
            <button class="secondary-button wide-button" type="button" data-action="search-reset">Ny Sökning</button>
          </section>
        `
        : state.searchHasRun
          ? `
            <section class="stack">
              ${renderEmptyState("Inga träffar", "Prova att vara lite bredare med prompten eller välj en annan stämning.")}
              <button class="secondary-button wide-button" type="button" data-action="search-reset">Ny Sökning</button>
            </section>
          `
        : `
          <section class="stack">
            <div class="feature-pill">Feature under utveckling</div>
            <div class="support-card">
              <p>Prova dessa förslag:</p>
            </div>
            ${(state.boot?.prompt_suggestions || [])
              .map(
                (prompt) => `
                  <button class="list-button" type="button" data-prompt="${escapeHtml(prompt)}">
                    ${escapeHtml(prompt)}
                  </button>
                `
              )
              .join("")}
          </section>
        `
    }
  `;
}

function renderProfileView() {
  const saved = state.profile.saved_artists || [];
  const custom = state.profile.custom_artists || [];
  rememberItems(saved);
  rememberItems(custom);

  return `
    <section class="hero-stack compact-hero">
      <div class="hero-icon">${icon("user")}</div>
      <h1>Min Profil</h1>
      <p>Dina sparade låtar och egna tillskott.</p>
      <div class="metric-row centered">
        <span class="metric-pill">${state.profile.saved_count} sparade</span>
        <span class="metric-pill">${state.profile.custom_count} egna tillskott</span>
      </div>
    </section>
    <section class="stack">
      <h2 class="section-title">Sparade artister</h2>
      ${
        saved.length
          ? saved.map((item) => renderProfileCard(item, "saved")).join("")
          : renderEmptyState("Inga sparade än", "Spara favoriter från Upptäck, Flöde eller Sök.")
      }
      <h2 class="section-title">Egna tillskott</h2>
      ${
        custom.length
          ? custom.map((item) => renderProfileCard(item, "custom")).join("")
          : renderEmptyState("Inga egna tillskott än", "Använd Föreslå-vyn för att lägga till en artist via ISRC.")
      }
    </section>
  `;
}

function renderArtistCard(item, options = {}) {
  const compact = options.compact === true;
  return `
    <article class="artist-card card ${compact ? "compact-card" : ""}">
      <div class="artist-card-top">
        <div class="artwork">
          ${
            item.image
              ? `<img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.artist)}" />`
              : `<div class="image-fallback">${icon("note")}</div>`
          }
        </div>
        <div class="artist-meta">
          <div class="card-heading-row">
            <div>
              <h2>${escapeHtml(item.artist)}</h2>
              <p class="muted-line">${escapeHtml(item.song || "Okänd låt")}</p>
            </div>
            <button
              class="save-button"
              type="button"
              data-action="save-toggle"
              data-key="${escapeHtml(item.artist_key)}"
              aria-label="Spara artist"
            >
              ${state.savedKeys.has(item.artist_key) ? icon("bookmarkFilled") : icon("bookmark")}
            </button>
          </div>
          ${
            item.secondary_tracks?.length
              ? `<p class="secondary-track">Även känd för: ${escapeHtml(item.secondary_tracks.join(" • "))}</p>`
              : ""
          }
          <p class="body-copy">${escapeHtml(item.reason || "")}</p>
          <div class="metric-row">
            ${renderMetricPills(item.metrics)}
            ${(item.top_genres || []).slice(0, 2).map((genre) => `<span class="metric-pill accent-pill">${escapeHtml(genre)}</span>`).join("")}
          </div>
        </div>
      </div>
      <div class="card-actions ${compact ? "compact-actions" : ""}">
        ${
          item.preview
            ? `<audio class="audio-player" controls src="${escapeHtml(item.preview)}"></audio>`
            : ""
        }
        <div class="link-row">
          ${
            item.deezer_link
              ? `<a class="link-button" href="${escapeHtml(item.deezer_link)}" target="_blank" rel="noreferrer">Öppna i Deezer</a>`
              : ""
          }
          ${
            item.lastfm_link
              ? `<a class="link-button ghost-link" href="${escapeHtml(item.lastfm_link)}" target="_blank" rel="noreferrer">Last.fm</a>`
              : ""
          }
        </div>
      </div>
    </article>
  `;
}

function renderMetricPills(metrics = {}) {
  const entries = [
    ["Spotify", metrics.spotify_popularity],
    ["Last.fm", metrics.lastfm_listeners],
    ["Deezer", metrics.deezer_fans],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "saknas");

  return entries
    .map(
      ([label, value]) => `<span class="metric-pill">${label}: ${formatNumber(value)}</span>`
    )
    .join("");
}

function renderCommunityPost(post) {
  const initial = escapeHtml((post.username || "d").slice(0, 1).toUpperCase());
  return `
    <article class="card post-card">
      <div class="post-header">
        <div class="avatar">${initial}</div>
        <div>
          <h3>${escapeHtml(post.username || "du")}</h3>
          <p>${formatRelativeTime(post.created_at)}</p>
        </div>
      </div>
      <p class="body-copy">${escapeHtml(post.text)}</p>
      ${
        post.tip_artist || post.tip_song
          ? `
            <div class="tip-card">
              <span class="tip-tag">Låttips</span>
              <strong>${escapeHtml(post.tip_song || "Okänd låt")}</strong>
              <span>${escapeHtml(post.tip_artist || "Okänd artist")}</span>
            </div>
          `
          : ""
      }
    </article>
  `;
}

function renderProfileCard(item, mode) {
  return `
    <article class="profile-card card">
      <div class="profile-artwork">
        ${
          item.image
            ? `<img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.artist)}" />`
            : `<div class="image-fallback">${icon("note")}</div>`
        }
      </div>
      <div class="profile-meta">
        <h3>${escapeHtml(item.song || item.artist)}</h3>
        <p>${escapeHtml(item.artist)}</p>
        <span class="tiny-label">${mode === "custom" ? "Eget tillskott" : "Sparad rekommendation"}</span>
      </div>
      <button class="icon-button quiet-button" type="button" data-action="remove-library" data-key="${escapeHtml(item.artist_key)}">
        ${icon("trash")}
      </button>
    </article>
  `;
}

function renderEmptyState(title, text) {
  return `
    <div class="empty-state card">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(text)}</p>
    </div>
  `;
}

function refreshActionStates() {
  const suggestButton = document.getElementById("suggest-submit");
  if (suggestButton) {
    suggestButton.disabled = !(state.suggestionDraft.isrc.trim() && state.suggestionDraft.confirm);
  }
}

function toggleGenre(label) {
  if (state.selectedGenres.includes(label)) {
    state.selectedGenres = state.selectedGenres.filter((item) => item !== label);
  } else {
    state.selectedGenres = [...state.selectedGenres, label];
  }
  render();
}

async function runDiscover() {
  if (state.selectedGenres.length === 0) {
    return;
  }

  state.error = "";
  state.isLoading = true;
  state.loadingMessage = "Vi letar upp mindre artister för dina genrer...";
  render();

  try {
    const payload = await api.discover({ genres: state.selectedGenres, limit: 6 });
    state.discoverResults = payload.results || [];
    state.discoverHasRun = true;
    rememberItems(state.discoverResults);
  } catch (error) {
    state.error = error.message;
  } finally {
    state.isLoading = false;
    render();
  }
}

async function runPromptSearch(prompt) {
  state.searchPrompt = prompt;
  state.error = "";
  state.isLoading = true;
  state.loadingMessage = "Tolkar din prompt och letar fram mindre artister...";
  render();

  try {
    const payload = await api.search({ prompt, limit: 6 });
    state.searchResults = payload.results || [];
    state.searchInterpretation = payload.interpretation || null;
    state.searchHasRun = true;
    rememberItems(state.searchResults);
  } catch (error) {
    state.error = error.message;
  } finally {
    state.isLoading = false;
    render();
  }
}

async function loadFeed() {
  state.error = "";
  state.isLoading = true;
  state.loadingMessage = "Bygger ditt flöde...";
  render();

  try {
    const payload = await api.feed({ exclude_artist_keys: state.feed.seenKeys });
    state.feed.card = payload.card || null;
    state.feed.communityPosts = payload.community_posts || [];
    if (state.feed.card?.artist_key) {
      rememberItems([state.feed.card]);
    }
  } catch (error) {
    state.error = error.message;
  } finally {
    state.isLoading = false;
    render();
  }
}

async function refreshProfile() {
  const profile = await api.profile();
  syncProfile(profile);
}

async function toggleSave(artistKey) {
  const payload = activeCardPayload(artistKey);
  if (!payload) {
    return;
  }

  try {
    await api.save(payload);
    await refreshProfile();
  } catch (error) {
    state.error = error.message;
  }

  render();
}

async function removeLibraryArtist(artistKey) {
  try {
    await api.removeArtist(artistKey);
    await refreshProfile();
    if (state.feed.card?.artist_key === artistKey) {
      state.feed.card = null;
    }
  } catch (error) {
    state.error = error.message;
  }

  render();
}

root.addEventListener("click", async (event) => {
  const navTarget = event.target.closest("[data-view]");
  if (navTarget) {
    state.view = navTarget.dataset.view;
    state.error = "";
    if (state.view === "feed" && !state.feed.card) {
      await loadFeed();
      return;
    }
    render();
    return;
  }

  const genreTarget = event.target.closest("[data-genre]");
  if (genreTarget) {
    toggleGenre(genreTarget.dataset.genre);
    return;
  }

  const promptTarget = event.target.closest("[data-prompt]");
  if (promptTarget) {
    const prompt = promptTarget.dataset.prompt;
    state.searchPrompt = prompt;
    await runPromptSearch(prompt);
    return;
  }

  const actionTarget = event.target.closest("[data-action]");
  if (!actionTarget) {
    return;
  }

  const { action, key } = actionTarget.dataset;

  switch (action) {
    case "discover-submit":
      await runDiscover();
      break;
    case "discover-reset":
      state.discoverResults = [];
      state.selectedGenres = [];
      state.discoverHasRun = false;
      render();
      break;
    case "save-toggle":
      await toggleSave(key);
      break;
    case "feed-next":
      if (state.feed.card?.artist_key) {
        state.feed.seenKeys = [...new Set([...state.feed.seenKeys, state.feed.card.artist_key])];
      }
      await loadFeed();
      break;
    case "toggle-tip":
      state.communityTipOpen = !state.communityTipOpen;
      render();
      break;
    case "search-reset":
      state.searchResults = [];
      state.searchInterpretation = null;
      state.searchPrompt = "";
      state.searchHasRun = false;
      render();
      break;
    case "remove-library":
      await removeLibraryArtist(key);
      break;
    default:
      break;
  }
});

root.addEventListener("input", (event) => {
  if (event.target.id === "isrc-input") {
    state.suggestionDraft.isrc = event.target.value.toUpperCase();
    refreshActionStates();
  }

  if (event.target.id === "prompt-input") {
    state.searchPrompt = event.target.value;
  }
});

root.addEventListener("change", (event) => {
  if (event.target.id === "confirm-smaller") {
    state.suggestionDraft.confirm = event.target.checked;
    refreshActionStates();
  }
});

root.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (event.target.id === "search-form") {
    const formData = new FormData(event.target);
    const prompt = String(formData.get("prompt") || "").trim();
    if (prompt) {
      await runPromptSearch(prompt);
    }
    return;
  }

  if (event.target.id === "suggest-form") {
    state.error = "";
    state.isLoading = true;
    state.loadingMessage = "Hämtar artistinformation från Deezer...";
    render();

    try {
      const payload = await api.suggest({
        isrc: state.suggestionDraft.isrc.trim(),
        confirm_smaller_artist: state.suggestionDraft.confirm,
        note: state.suggestionDraft.note,
      });
      state.suggestionStatus = `${payload.item.artist} lades till och kan nu dyka upp i flödet och rekommendationerna.`;
      state.suggestionDraft = { isrc: "", confirm: false, note: "" };
      await refreshProfile();
      state.feed.card = null;
    } catch (error) {
      state.error = error.message;
    } finally {
      state.isLoading = false;
      render();
    }
    return;
  }

  if (event.target.id === "community-form") {
    const formData = new FormData(event.target);
    const text = String(formData.get("text") || "").trim();
    const tipArtist = String(formData.get("tip_artist") || "").trim();
    const tipSong = String(formData.get("tip_song") || "").trim();

    if (!text) {
      state.error = "Skriv något innan du postar.";
      render();
      return;
    }

    try {
      const payload = await api.createCommunityPost({
        text,
        username: "du",
        tip_artist: tipArtist || null,
        tip_song: tipSong || null,
      });
      state.feed.communityPosts = [payload.item, ...state.feed.communityPosts];
      state.communityTipOpen = false;
      event.target.reset();
    } catch (error) {
      state.error = error.message;
    }

    render();
  }
});

initialize();
