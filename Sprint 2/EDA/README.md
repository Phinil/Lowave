# Explorativ Dataanalys (EDA)
Denna bransch innehåller en explorativ dataanalys av vårt dataset med fokus på att förbättra datakvaliteten och identifiera samband och mönster i datan. 
Analysen utgår från workshop instruktionerna. 

För bearbetning av datan genomfördes nedanstående steg för att säkerställa att datan var lämplig för analys.  

-Borttagning av irrelevanta kolumner: 
Kolumnen Unnamed: 0 togs bort eftersom den saknade både relevant innehåll och information och troligen uppstod i samband med att datan 
exporterades. 

-Standardisering av kategoriska variabler: 
Textbaserade kolumner som exempelvis `track_genre`, rensades genom att konvertera alla värden till små bokstäver 
samt ta bort överflödiga mellanslag. Detta genomfördes för att säkerställa att samma kategori behandlas konsekvent trots skillnader i stavning eller formatering.

-Analys av dubbletter:
Det identifierades inga fullständiga dubletter i datasetet. 
Däremot förekom flera rader med samma track_id, vilket innebär att samma låt kan förekomma flera gånger med olika attribut.
Dessa behölls eftersom de kan representera en meningsfull variation. 

-Hantering av saknade värden: 
Endast 3 rader av saknade värden indentifierades i kolumnerna `artists`, `album_name` och `track_name`.
Eftersom mängden saknad data var mycket liten valdes dessa rader att tas bort, då de inte bedömdes påverka analysen i någon större utsträckning.

# Explorativ analys
Följande analyser genomfördes: 

-Fördelning av popularitet:
Histogram och boxplot visade att majoriteten av låtarna har låg till medelhög popularitet, 
medan ett mindre antal låtar har mycket hög popularitet.

-Popularitet per genre:
Genom att analysera de 10 vanligaste genrerna framkom att vissa genrer generellt har högre popularitet än andra.

-Korrelationsanalys:
En korrelationsmatris för numeriska variabler visade samband mellan vissa egenskaper, exempelvis mellan energi och loudness.

# Insikter från analysen: 
Genre verkar påverka popularitet men variation finns inom varje genre.

Genre verkar påverka popularitet men variation finns inom varje genre.

Vissa ljudegenskaper uppvisar samband vilket tyder på underliggande relationer mellan låtarnas attribut.




