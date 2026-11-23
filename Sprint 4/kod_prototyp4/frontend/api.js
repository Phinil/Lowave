const JSON_HEADERS = {
  "Content-Type": "application/json",
};

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok) {
    throw new Error(payload?.detail || "Något gick fel.");
  }

  return payload;
}

export const api = {
  bootstrap() {
    return request("/api/bootstrap");
  },

  discover(body) {
    return request("/api/discover", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  search(body) {
    return request("/api/search", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  feed(body) {
    return request("/api/feed", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  profile() {
    return request("/api/profile");
  },

  save(body) {
    return request("/api/save", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  removeArtist(artistKey) {
    return request(`/api/library/${encodeURIComponent(artistKey)}`, {
      method: "DELETE",
    });
  },

  suggest(body) {
    return request("/api/suggestions", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },

  createCommunityPost(body) {
    return request("/api/community", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    });
  },
};
