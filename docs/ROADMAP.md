# WorldSim — Roadmap

> Come far crescere WorldSim da "ecosistema di cellule" a qualcosa di aperto, e possibilmente a un gioco.
> Regola guida: **un meccanismo nuovo per volta**, ognuno con un esperimento che dica se ha funzionato. L'ordine delle fasi 3–7 è flessibile.

## Visione d'insieme

```
SIMULAZIONE (laboratorio, Python)                 GIOCO (prodotto)
F1 Fondamenta ──► F2 Ambiente vivo + seed mondo ──► G1 Prototipo "pianeta in un barattolo"
                  F3 Sensori e comportamento         G2 Port motore (C#/Burst o Rust)
                  F4 Genoma aperto                   G3 Obiettivi, progressione, UI
                  F5 Due genitori e plasticità
                  F6 Multicellularità vera
                  F7 Segnali → sociale
```

---

## F1 — Fondamenta (prima di aggiungere biologia)
Senza questi strumenti non si capisce cosa succede quando il sistema cresce.
- **Salvataggio/caricamento** del mondo e **determinismo** (stesso seed → stessa storia).
- **Tracciamento delle specie**: clustering dei genomi + albero filogenetico (chi discende da chi).
- **Metriche di novità** (activity statistics di Bedau) per misurare se il sistema inventa ancora o è fermo.
- Test di regressione (conservazione dell'energia, nessuna cellula duplicata nella griglia).
- Profilazione: oggi ~500 passi/s con ~900 cellule. Limite pratico di Python ≈ qualche migliaio di cellule.

**Criterio di uscita**: posso rilanciare una run, vederne l'albero delle specie e un grafico "novità nel tempo".

## F2 — Ambiente vivo + seed del mondo
- Ciclo giorno/notte e **stagioni** (luce variabile).
- Terreno eterogeneo: rocce, zone ricche di minerali, sorgenti termali (energia chimica, non solo luce).
- **Mondo generato da un input** (foto o form, vedi sezione dedicata).
- Esperimento: in ambiente variabile il tasso di mutazione risale? Nascono strategie stagionali (spore, riserve)?

## F3 — Sensori e comportamento
- La cellula percepisce le 8 caselle vicine: luce, organico, presenza di cellule, parentela.
- Movimento **diretto** (verso cibo/luce, lontano dai predatori) invece che casuale.
- Implementazione: piccola rete neurale o insieme di regole pesate, **con i pesi nel genoma**.
- Esperimento: emergono caccia, fuga, migrazioni verticali giorno/notte?

## F4 — Genoma aperto (crescita del numero di geni)
Vedi sezione dedicata. In breve: da vettore fisso a **genoma a lunghezza variabile** con duplicazione e cancellazione di geni.

## F5 — Due genitori e variazione durante la vita
Vedi sezione dedicata: riproduzione sessuale, plasticità, apprendimento, scambio orizzontale di geni.

## F6 — Multicellularità vera
- Le cellule della stessa colonia possono **differenziarsi**: stesso genoma, espressione diversa in base alla posizione o ai segnali (come le cellule di un embrione).
- Organismo = colonia con un "piano di sviluppo"; riproduzione tramite propagulo o spora.
- Esperimento: compaiono organismi con parti specializzate (foglie che fotosintetizzano, radici che assorbono, "bocche")?

## F7 — Segnali e sociale
- Segnali chimici emessi e percepiti (canali nel campo, come l'organico).
- Riconoscimento della parentela, cooperazione, altruismo verso i parenti (kin selection), segnali d'allarme.
- Oltre: gruppi, territori, scambio di risorse → ponte verso la simulazione sociale (Sugarscape).

---

## Quando aumentare il numero di geni?

Oggi ogni gene è **cablato a mano a un tratto** (gene 3 = movimento ecc.). Si possono distinguere tre livelli:

1. **Aggiungere geni fissi**: si fa **ogni volta che si aggiunge un meccanismo** (F2–F3). Esempio: i sensori portano ~10–30 pesi in più. È semplice e si può fare da subito, ma lo spazio resta chiuso: l'evoluzione può solo regolare manopole che ho previsto io.
2. **Genoma a lunghezza variabile** (F4): il genoma diventa una lista di "geni" (es. regole *se percepisco X allora faccio Y con intensità Z*). Le mutazioni possono **duplicare** un gene (la copia è libera di evolvere verso una funzione nuova: è il meccanismo principale con cui in natura sono nate nuove funzioni), **cancellarlo** o modificarlo. Così il numero di geni lo decide l'evoluzione.
3. **Rete regolatoria**: i geni si accendono e spengono a vicenda. È il prerequisito per la differenziazione cellulare di F6.

**Quando passare al livello 2**: quando F3 funziona e le metriche di novità di F1 mostrano che il sistema si stabilizza. Il segnale chiaro è che il sistema "si ferma" anche in ambiente variabile.
**Costo**: più geni significa più calcolo per cellula e mutazioni più spesso dannose. Va bilanciato con un **costo metabolico per gene**, altrimenti i genomi gonfiano senza motivo.

## Variazione dei genitori nel tempo

Ci sono quattro meccanismi distinti, in ordine di difficoltà:

| Meccanismo | Cosa cambia | Effetto atteso | Fase |
|---|---|---|---|
| **Due genitori** (riproduzione sessuale) | Il figlio combina i genomi di due cellule (crossover) | Combina innovazioni nate in linee diverse, ripulisce le mutazioni dannose; richiede di trovare un partner (scelta sessuale!) | F5 |
| **Plasticità / epigenetica** | Durante la vita alcuni tratti si regolano in base all'ambiente (es. più fotosintesi se c'è luce), senza cambiare il DNA; una parte può passare ai figli | Adattamento rapido senza aspettare le mutazioni | F5 |
| **Apprendimento** | Il "cervello" (F3) modifica i pesi durante la vita | Effetto Baldwin: ciò che si impara facilmente tende poi a diventare innato | dopo F3 |
| **Trasferimento orizzontale** | Una cellula assorbe pezzi di genoma da vicine o da organico | Come i batteri: diffusione rapida di innovazioni tra lignaggi | F5 |

**Lamarckismo** (il genitore cambia il proprio genoma durante la vita e lo passa ai figli): si può fare con un flag, ed è un esperimento interessante da confrontare con la versione darwiniana.

---

## Seed del mondo da foto o form

Il seed non è genetico: è il **pianeta**. L'input genera l'ambiente, la vita parte sempre da cellule casuali e si adatta a quel mondo. Il risultato è che **ogni foto diventa un mondo diverso con una storia evolutiva diversa**.

### Da una foto
- Si ridimensiona l'immagine alla griglia.
- **Luminosità → luce / altitudine**: zone chiare = superficie illuminata, zone scure = profondità.
- **Colore → risorse**: es. canale rosso = minerali/calore (energia chimica), canale blu = acqua/nutrienti, canale verde = fertilità iniziale.
- **Bordi forti → rocce/barriere**: separano popolazioni, quindi nascono specie diverse in zone diverse (speciazione geografica).
- **Hash dell'immagine → seed casuale**: stessa foto = stesso mondo, riproducibile e condivisibile.

### Da un form ("crea il tuo pianeta")
Ogni campo del form diventa un parametro di `Config` o della generazione del terreno:
- tipo di stella → intensità e colore della luce, durata di giorno e anno;
- temperatura e stagionalità;
- profondità degli oceani, quantità di terra emersa;
- ricchezza minerale, attività vulcanica (sorgenti di energia chimica);
- **"chimica della vita"**: carbonio / silicio / ammoniaca / … come *preset* di regole. Es. la vita al silicio è lenta, robusta, vive di calore invece che di luce. Recupera l'idea iniziale degli elementi alternativi, ma come **regole diverse del mondo**, che è dove conta davvero.
- difficoltà: frequenza di catastrofi (meteoriti, glaciazioni).

**Implementazione**: è tutta un'aggiunta in F2. Si scrive un modulo `worldgen` che produce le mappe (luce, risorse, rocce) e la `Config` da un'immagine o da un JSON. Il motore non cambia.

---

## Trasformarlo in un gioco

### Riferimenti esistenti
SimLife (Maxis, 1992), Spore (2008), *Species: Artificial Life, Real Evolution*, *Thrive* (open source), Equilinox, The Bibites. Il genere esiste ma è di nicchia. Chi ci è riuscito ha dato al giocatore **verbi chiari**, non solo uno schermo da guardare.

### Il rischio principale
Una simulazione ALife è affascinante da osservare per 10 minuti e poi annoia. Serve un **loop di gioco**: *cosa fa il giocatore, ogni minuto?*

### Concept proposto: "pianeta in un barattolo" (god game sandbox)
- **Creazione**: il giocatore genera il pianeta da una foto o dal form.
- **Osservazione**: guarda la vita emergere, ispeziona le specie, dà loro un nome; c'è un albero della vita visibile.
- **Intervento** (verbi del giocatore, con un budget di "energia divina"): spostare luce o nutrienti, scavare canali, sollevare montagne (separare popolazioni), meteoriti e glaciazioni, introdurre una specie da un altro pianeta.
- **Obiettivi / traguardi**: "primo organismo multicellulare", "primo predatore", "10 specie contemporanee", "sopravvivi a un'estinzione di massa", "fai evolvere la comunicazione". Modalità sfida: "su questo pianeta ostile, ottieni X entro N generazioni".
- **Condivisione**: un pianeta = foto + form, quindi si condivide facilmente; si possono confrontare le storie evolutive diverse dallo stesso seed.

### Architettura
- **Il motore resta separato, deterministico e headless**: il gioco è un front-end.
- Python resta il **laboratorio** per provare le regole.
- Per il gioco serve un **port del motore**, perché Python non regge decine di migliaia di cellule a 60 fps. Due opzioni:
  1. **Unity + C# con Jobs/Burst** (o compute shader): un solo stack, strada più pratica.
  2. **Rust** come libreria nativa chiamata da Unity: più performante e riusabile, ma con due linguaggi da mantenere.
- Momento giusto per il port: **dopo F3**, quando le regole base sono stabili; portare prima vuol dire riscrivere due volte.

### Fasi del gioco
- **G1 (dopo F2)**: prototipo giocabile in Python/pygame. Foto o form → pianeta, 3–4 interventi, 5 traguardi. Si verifica se è divertente **prima** di investire nel port.
- **G2 (dopo F3)**: port del motore e visualizzazione in Unity.
- **G3**: UI, albero della vita, progressione, salvataggi, condivisione.
