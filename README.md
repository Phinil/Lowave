# Lowave – musikupptäckt för små oberoende artister

> Kursprojekt i systemvetenskap vid Göteborgs universitet (vårterminen 2026).
> Grupprojekt med fem studenter, genomfört med design thinking och Scrum under fyra sprintar.

## Problemet

*"Små oberoende musikaktörer har svårt att bli upptäckta utan att vara signade av ett skivbolag eller lägga mycket tid på marknadsföring."*

Genom intervjuer med oberoende musiker (våra *problem owners*) såg vi att problemet inte är brist på plattformar.
Det är att dagens plattformar styrs av algoritmer som gynnar redan etablerade artister. Musikerna lägger mer tid på
marknadsföring och att förstå algoritmer än på musiken, och de har svårt att bygga en riktig relation med sina lyssnare.

## Lösningen

**Lowave** är en webbapp där lyssnare hittar musik från mindre, oberoende artister, och där artister kan nå rätt publik
utan att jaga visningar. I enlighet med ett *Small Web*-perspektiv ville vi göra upptäckten mer personlig, transparent och mindre
popularitetsdriven.

- **Vibesökning / Musikmix** – användaren beskriver stämningen med reglage (t.ex. energi, dansbarhet, tempo) och får låtar som matchar.
- **Rekommendationsmotor med K-means + närmaste granne-sökning** – reglagen blir en målvektor, K-means väljer rätt musikaliskt område, och inom det klustret hittas de närmaste låtarna med avståndsberäkning (likt KNN): först en *seed-låt*, sedan låtar som liknar den.
- **Small artist-filter** – endast artister under en gräns för lyssnare (t.ex. 50 000 månatliga lyssnare) visas.
- **Förhandslyssning och omslag** via Deezers öppna API, artistdata via Last.fm.
- **Community** – flöde, kommentarer, *community rooms*, konton och sparade låtar.
- **Låtkort för artister** – artister kan lägga upp sin låt med ISRC-kod och se hur lyssnare reagerar.

## Arbetsprocess

Projektet drevs med **Scrum** i fyra sprintar. Vi hade en **scrumboard** för uppgifter, en *Definition of Done* för varje sprint, roterande Scrum master och ett **retrospektiv** efter varje sprint.

Inom sprintarna följde vi **design thinking** (empathize → define → ideate → prototype → test) och använde verktyg som:
semistrukturerade intervjuer, **empathy maps**, **Point of View**, **How Might We**, *What–How–Why*, brainstorming, **ABC-sortering av idéer**,
pappersprototyper, **Figma**-prototyper och användartester.

| Sprint | Fokus | Exempel på material |
|---|---|---|
| **1** | Förstå problemet | Intervjuer med musiker, empathy maps, Point of View, How Might We |
| **2** | Idéer och första prototyp | Brainstorming (18 idéer), ABC-sortering, prototyp i papper, Figma och kod, explorativ dataanalys (EDA) |
| **3** | Utveckla och testa | Användartester, prototyp 2–3, jämförelse av klustringsalgoritmer |
| **4** | Förbättra efter feedback | Prototyp 4–15, ny rekommendationslogik, community, utvärdering |

Totalt tog vi fram **15 prototyper**. Hur produkten utvecklades steg för steg finns beskrivet i
[`Sprint 4/code progression`](Sprint%204/code%20progression), och vad vi ändrade efter användartesterna i
[`Sprint 4/Förbättringar efter feedback`](Sprint%204/F%C3%B6rb%C3%A4ttringar%20efter%20feedback).

### Maskininlärning
Vi jämförde tre oövervakade klustringsalgoritmer på låtarnas ljudegenskaper: **K-means**, **agglomerativ klustring** och **DBSCAN**.
Vi valde K-means eftersom den hanterade stora datamängder bra och gav rimliga kluster när vi lyssnade på resultaten.
Från början användes K-means bara som filter, men i den slutliga versionen styr den vilket musikaliskt område rekommendationerna hämtas från.

Den slutliga rekommendationen kombinerar två tekniker:
1. **K-means (oövervakad klustring)** – låtarnas ljudegenskaper standardiseras (`StandardScaler`) och delas in i kluster. Användarens reglage jämförs med klustrens centroider för att välja rätt område.
2. **Närmaste granne-sökning (k-nearest neighbours-principen)** – inom klustret beräknas det euklidiska avståndet från varje låt till användarens målvektor. Den närmaste låten blir *seed-låt*, och sedan rangordnas låtarna efter avståndet till seed-låten. Sökningen är egenimplementerad med avståndsberäkningar och använder inte scikit-learns KNN-klass.

Därefter justeras resultatet med regler: små artister prioriteras, nyligen visade låtar och upprepade artister får minuspoäng, och lite slumpmässighet ger variation.
Se [`Sprint 4/kod_prototyp15/docs/discovery-flow-diagrams.md`](Sprint%204/kod_prototyp15/docs/discovery-flow-diagrams.md) för flödesdiagram.

## Teknik

- **Backend:** Python, FastAPI, pandas, NumPy, scikit-learn (K-means, StandardScaler), SQLite
- **Frontend:** HTML, CSS och JavaScript
- **Externa API:er:** Deezer (förhandslyssning, omslag), Last.fm (lyssnarsiffror, artistinfo)
- **Data:** Spotify Tracks-dataset från Kaggle (ljudegenskaper för cirka 114 000 låtar)

## Kör appen lokalt (senaste versionen)

```bash
cd "Sprint 4/kod_prototyp15"
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env            # fyll i din egen Last.fm-nyckel (valfritt)
uvicorn backend.app.main:app --reload
```

Öppna sedan http://127.0.0.1:8000.

Deezer kräver ingen nyckel. Last.fm-nyckeln är valfri. Utan den fungerar appen, men med färre artistuppgifter.
API-nycklar ligger aldrig i repot, de läses in från `.env` som är exkluderad via `.gitignore`.

## Mappstruktur

```
├── lowave_report.ipynb    Slutrapport: process, data, ML och reflektion
├── Important decisions    Viktiga beslut under projektet
├── Sprint 1/              Intervjusammanfattning, empathy maps, POV, How Might We
├── Sprint 2/              Brainstorming, EDA, prototyp 1
├── Sprint 3/              Användartester, ML-workshop, prototyp 2–3
└── Sprint 4/              Prototyp 4 och 15, utvärdering, flaskhalsar
```

## Min roll

- **Utveckling:** Jag var en av två i gruppen som byggde kodprototyperna, med backend i Python/FastAPI, rekommendationslogik och frontend. Vi arbetade AI-assisterat med OpenAI Codex och fokuserade på att styra, granska och felsöka koden.
- **Scrum master:** Rollen roterade i gruppen så att alla fick prova den, och jag var Scrum master under en sprintperiod. Då ansvarade jag för scrumboarden, planeringen och att hålla teamet på banan.
- **Egen idé – ISRC-uppladdning:** Jag kom på funktionen där artister lägger upp sina låtar med ISRC-kod i stället för att skapa och verifiera ett artistkonto. Den löste vårt problem med att verifiera artister och uppskattades i användartesterna.
- **Användarförståelse:** Jag genomförde intervjuer med musiker och deltog i analysen med design thinking-verktygen.

## Lärdomar

- Att gå tillbaka till intervjuerna var avgörande. Communitydelen och vibesökningen blev bättre först när vi itererade utifrån vad användarna faktiskt sa.
- Transparens i rekommendationer är svårt. Vi gick från en NLP-baserad lösning som vi inte kunde förklara till en egenskapsbaserad K-means-lösning som går att följa steg för steg.
- Scrum kräver övning. Efter första sprinten blev vi tydligare med scrumboarden och uppgifternas storlek.

---

*Rå intervjumaterial, inspelningar och interna gruppdokument är inte med i detta repo av integritetsskäl. Deltagarna benämns som PO1, PO2 och så vidare.*

*README:n är skriven med hjälp av Claude (Anthropic).*
