# WorldSim — Stato dell'arte (Artificial Life)

> Ricerca iniziale, 10 novembre 2026. Raccoglie i progetti esistenti di simulazione ed evoluzione di sistemi simil-biologici, divisi per approccio, per decidere la direzione di WorldSim.

## Il campo in breve

Il campo si chiama **Artificial Life (ALife)**. Ha una community accademica (International Society for Artificial Life, conferenza ALIFE annuale) e una scena indie/hobbistica molto attiva.

Il problema centrale del campo è l'**open-ended evolution (OEE)**: quasi tutte le simulazioni producono novità per un po' e poi si stabilizzano. Nessun sistema è ancora passato in modo convincente da "cellula" a "organismo complesso". È qui che si trovano le domande aperte, ed è anche il punto in cui è più facile perdersi.

---

## 1. Organismi digitali (il codice è il DNA)

Gli "organismi" sono programmi che si autoreplicano, mutano e competono per le risorse di calcolo. La chimica non esiste: il substrato è il codice.

| Progetto | Anno | Note | Link |
|---|---|---|---|
| **Tierra** (Thomas Ray) | 1991 | Il capostipite. Programmi in un assembly virtuale competono per la CPU; nascono parassiti e iperparassiti. | — |
| **Avida** (Ofria, Lenski, Adami) | 1993→ | Successore scientifico di Tierra. Usato per veri studi di biologia evolutiva (Nature 2003, origine di funzioni complesse). Esiste anche Avida-ED, la versione didattica. | [github.com/devosoft/avida](https://github.com/devosoft/avida) · [Wikipedia](https://en.wikipedia.org/wiki/Avida_(software)) · [Avida-ED](https://avida-ed.github.io/) |
| **Computational Life / BFF** (Google) | 2024 | Una "zuppa" di programmi casuali in un linguaggio tipo Brainfuck: senza alcuna fitness esplicita emergono **spontaneamente** autoreplicatori. È un risultato chiave sull'origine della vita. | [arXiv 2406.19108](https://arxiv.org/abs/2406.19108) · [Google Research](https://research.google/pubs/computational-life-how-well-formed-self-replicating-programs-emerge-from-simple-interaction/) |

**Pro**: è veloce, il risultato è misurabile e si scrive in poco codice. **Contro**: è poco visivo e lontano dall'idea di "creatura".

---

## 2. Chimiche e fisiche artificiali (la vita emerge dalle regole)

È il percorso "dalla cellula in su". Si definiscono gli "elementi" e le regole di interazione, e si osserva se emergono strutture che si mantengono e si replicano. **È qui che rientra l'idea di una vita non a base di carbonio**: con una chimica inventata, gli elementi li definisci tu.

| Progetto | Anno | Note | Link |
|---|---|---|---|
| **Lenia** (Bert Chan) | 2019 | Automa cellulare continuo (un Game of Life con valori, spazio e tempo continui). Nascono centinaia di "specie" che si muovono e si dividono. Si implementa in poco codice. | — |
| **Flow-Lenia** | 2022/2025 | Aggiunge la conservazione della massa e parametri locali (il "genoma" viaggia con la creatura). Permette evoluzione e competizione tra specie nello stesso mondo. | [Sito](https://sites.google.com/view/flow-lenia) · [arXiv 2212.07906](https://arxiv.org/abs/2212.07906) · [arXiv 2506.08569](https://arxiv.org/abs/2506.08569v1) |
| **ALIEN** (Christian Heinemann) | 2020→ | Motore a particelle CUDA/GPU: particelle legate da connessioni, con cellule specializzate (sensori, muscoli, nervi). Fa evolvere organismi multicellulari. Open source e tra i progetti più maturi. | [alien-project.org](https://alien-project.org) · [github.com/chrxh/alien](https://github.com/chrxh/alien) · [itch.io](https://chrxh.itch.io/alien) |
| **Particle Life** | 2010s→ | N tipi di particelle con una matrice di attrazione/repulsione: da regole minime nascono strutture simil-cellulari. Esistono versioni "evolutive". | [tom-mohr/particle-life](https://awesome.ecosyste.ms/projects/github.com%2Ftom-mohr%2Fparticle-life) · [Evolving Particle Life](https://quasarbright.github.io/evolving-particle-life/) |
| **Microcosmos** | 2026 | Motore ALife su GPU in JAX: organismi fatti di filamenti elastici in un fluido 2D (Lattice Boltzmann + Position-Based Dynamics). Arriva a 500k particelle su una sola GPU ed è differenziabile. Autori: Chan, Stanley e altri. | [arXiv 2607.02954](https://www.alphaxiv.org/abs/2607.02954) |
| **Chimiche artificiali** (Hutton; Kruszewski & Mikolov) | 2002, 2020 | Molecole e reazioni astratte da cui emergono autoreplicatori e metabolismi autocatalitici. | [Hutton – replicating molecules](https://faculty.cc.gatech.edu/~turk/bio_sim/articles/hutton_rep_molecules.pdf) · [Combinatory Chemistry](https://arxiv.org/abs/2003.07916) · [Self-reproducing metabolisms](https://arxiv.org/abs/2103.08245) |

**Pro**: è il filone più "vero" e più spettacolare da vedere. **Contro**: richiede molto calcolo, e spesso non evolve nulla oltre forme semplici.

---

## 3. Agenti con cervello ed ecosistemi

Le creature hanno un genoma che codifica corpo e rete neurale, vivono in un mondo con cibo ed energia, e si riproducono e muoiono. Il comportamento si evolve.

| Progetto | Anno | Note | Link |
|---|---|---|---|
| **Polyworld** (Larry Yaeger) | 1994 | Il classico accademico: agenti 3D con reti neurali, visione, accoppiamento e combattimento. | [shinyverse.org/larryy/PolyWorld](https://shinyverse.org/larryy/PolyWorld.html) |
| **The Bibites** | 2020→ | Simulatore indie molto curato (fatto in Unity): genoma + rete neurale evolvibile, ormoni, predazione. È un ottimo riferimento per UX e design di gioco. | [itch.io](https://thebibites.itch.io/the-bibites) · [Sito](https://thebibites-website.pages.dev/) |
| **JaxLife** (Oxford) | 2024 | Agenti con reti neurali in un mondo con risorse, terraformazione e "robot" programmabili, pensato per l'evoluzione open-ended e per l'emergere di comportamenti sociali e culturali. È scritto in JAX. | [arXiv 2409.00853](https://arxiv.org/html/2409.00853v1) |

---

## 4. Simulazione sociale (Agent-Based Modeling)

I corpi non evolvono: evolvono le strategie, gli scambi, le norme e le culture.

| Progetto | Note | Link |
|---|---|---|
| **Sugarscape** (Epstein & Axtell, 1996) | Il modello di riferimento: agenti su una mappa di risorse, con commercio, migrazione, cultura e conflitti. | — |
| **NetLogo** | Ambiente classico per l'ABM, con una libreria enorme di modelli (Sugarscape incluso). | — |
| **Mesa** | Framework ABM in Python, il più usato oggi. | [mesa.readthedocs.io](https://mesa.readthedocs.io/) · [PyPI](https://pypi.org/project/mesa) |

---

## 5. Strumenti e metodi recenti da tenere d'occhio

- **ASAL — Automating the Search for Artificial Life** (Sakana AI + MIT e altri, 2024): usa foundation model visione-linguaggio (CLIP ecc.) per **cercare automaticamente** nello spazio dei parametri di Lenia, Particle Life, Boids e altri le simulazioni che producono comportamenti interessanti o "aperti". Risolve il problema "ho mille parametri, quali provo?". [sakana.ai/asal](https://sakana.ai/asal/) · [arXiv 2412.17799](https://arxiv.org/abs/2412.17799)
- **Directing OEE via multi-scale path divergence** (2026): metriche per orientare e misurare l'evoluzione open-ended. [astrobiology.com](https://astrobiology.com/2026/06/directing-open-ended-evolution-in-artificial-life-via-multi-scale-path-divergence.html)
- **Tendenza generale**: tutto si sposta su **GPU + JAX** (Microcosmos, JaxLife, ASAL, Flow-Lenia in JAX), con milioni di entità e differenziabilità.

---

## Come sono costruiti, di solito

Quasi tutti i progetti hanno gli stessi 4 strati:

1. **Substrato / fisica**: griglia, particelle o fluido, con le regole di interazione e l'energia.
2. **Genoma → fenotipo**: come l'informazione ereditabile costruisce corpo e comportamento.
3. **Selezione implicita**: niente fitness esplicita. Ci sono risorse scarse, costo energetico e morte, e sopravvive chi si riproduce.
4. **Osservazione**: visualizzazione, metriche di diversità, alberi filogenetici, salvataggio e replay.

Architettura tipica: un **motore di simulazione headless** (C++/CUDA, Rust o Python+JAX) separato dal **visualizzatore** (web, Unity o una GUI nativa).

---

## Opzioni per WorldSim (da decidere)

| Opzione | Cosa emerge | Difficoltà | Riferimenti |
|---|---|---|---|
| **A. Chimica artificiale** con elementi inventati (es. "non-carbonio") | Autoreplicatori, protocellule | Alta, risultati incerti | Hutton, BFF, Flow-Lenia |
| **B. Celle 2D con genoma** (un livello sopra la chimica) | Organismi, multicellularità, ecosistemi | Media | ALIEN, Bibites, Microcosmos |
| **C. Ecosistema di agenti** con reti neurali | Comportamenti, predazione, cooperazione | Media | Polyworld, JaxLife |
| **D. Sociale (ABM)** | Economia, cultura, norme | Bassa-media | Sugarscape, Mesa |

**Raccomandazione iniziale**: partire da **B**, con una fisica semplice e un genoma piccolo, e farla girare presto, aggiungendo poi strati. Comunicazione e comportamento sociale (C → D) diventano fasi successive dello stesso mondo, non progetti alternativi. L'opzione A ha senso solo se l'obiettivo è proprio studiare l'origine della vita, perché il rischio di "non succede niente" è alto.
