const button = document.getElementById("searchButton");
const loading = document.getElementById("loading");
const results = document.getElementById("results");

const genreSelect = document.getElementById("genre");
const moodSelect = document.getElementById("mood");
const artistInput = document.getElementById("artistInput");
const promptInput = document.getElementById("promptInput");

button.addEventListener("click", async () => {
  results.innerHTML = "";
  loading.classList.remove("hidden");

  const genre = genreSelect.value;
  const mood = moodSelect.value;
  const artist = artistInput.value.trim();
  const prompt = promptInput.value.trim();

  try {
    let url = "";

    // Om prompt finns: använd prompt-route
    if (prompt.length > 0) {
      url = `http://127.0.0.1:8000/prompt-artists?prompt=${encodeURIComponent(prompt)}`;
    } else {
      // Annars använd vanliga filter-routen
      url = `http://127.0.0.1:8000/artists?genre=${encodeURIComponent(genre)}&mood=${encodeURIComponent(mood)}&artist_input=${encodeURIComponent(artist)}`;
    }

    const response = await fetch(url);
    const artists = await response.json();

    loading.classList.add("hidden");

    if (!artists || artists.length === 0) {
      results.innerHTML = "<p>Inga små artister hittades. Testa en annan genre, mood eller prompt.</p>";
      return;
    }

    artists.forEach(artist => {
      const card = document.createElement("div");
      card.className = "artist-card";

      card.innerHTML = `
        <h2>${artist.artist}</h2>
        <p><strong>Låt:</strong> ${artist.song}</p>
        <p class="reason">${artist.reason}</p>
        <button>Följ artist</button>
      `;

      results.appendChild(card);
    });

  } catch (error) {
    loading.classList.add("hidden");
    results.innerHTML = "<p>Något gick fel. Kolla att backend och frontend körs.</p>";
    console.error(error);
  }
});
