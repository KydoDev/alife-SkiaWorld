# La teoria dietro WorldSim

> Perché WorldSim non è un algoritmo genetico, e quali idee di biologia teorica ed ecologia lavorano dentro il codice.

## 1. La radice comune: l'algoritmo darwiniano

Dennett descrive l'evoluzione come un **algoritmo** indipendente dal substrato. Le condizioni di Lewontin dicono che c'è evoluzione ovunque ci siano:

1. **variazione**: gli individui differiscono;
2. **ereditarietà**: i figli somigliano ai genitori;
3. **riproduzione differenziale**: alcune varianti lasciano più discendenti.

In WorldSim corrispondono a: genoma di 9 numeri → copia con mutazione gaussiana → l'energia decide chi si divide.

## 2. Algoritmo genetico vs vita artificiale

| | Algoritmo genetico (Holland) | Vita artificiale con selezione implicita (Tierra, Avida, WorldSim) |
|---|---|---|
| Scopo | **Ottimizzare**: trovare la soluzione migliore | **Esplorare**: vedere cosa emerge |
| Fitness | **Esogena**: una funzione scritta dal programmatore | **Endogena**: chi si riproduce in quel mondo, in quel momento |
| Selezione | Esterna: si ordinano i candidati e si tengono i migliori | Interna: si muore di fame, si viene mangiati, si resta senza spazio |
| Tempo | Generazioni sincronizzate | Nascite e morti sovrapposte, in continuo |
| Mondo | Non esiste, c'è solo il voto | È tutto: risorse, spazio, altri organismi |
| Fine | Quando si trova la soluzione | Mai, idealmente |

Entrambi appartengono al **calcolo evolutivo**. Il nome preciso di WorldSim è **modello individual-based (agent-based) evolutivo**, nel campo dell'Artificial Life.

## 3. Concetti che operano nel sistema

### Paesaggio adattativo dinamico
Nei GA il paesaggio di fitness è fisso e l'evoluzione "scala colline". In WorldSim il paesaggio lo **costruiscono gli organismi**: molte piante rendono conveniente predare, molti predatori rendono conveniente altro. È la **selezione dipendente dalla frequenza**; nella forma estrema è la **Regina Rossa** (Van Valen): evolvere di continuo per restare fermi.

### Nicchie e compromessi
**Esclusione competitiva** (Gause): due specie che usano la stessa risorsa non coesistono a lungo. In WorldSim le risorse sono tre (luce, materia organica, altre cellule) e i **trade-off** sono imposti dall'esponente `p^spec_exp`: un generalista è mediocre in tutto. Infatti alzando `spec_exp` da 1.5 a 2 le strategie si sono separate.

### Predatore-preda
Le oscillazioni piante/predatori sono la versione a individui di **Lotka-Volterra**. Con individui spazialmente espliciti emergono effetti che le equazioni non vedono (es. colonie legate che non possono essere predate dall'interno).

### Termodinamica
La vita è una **struttura dissipativa** (Prigogine): ordine mantenuto consumando un flusso di energia. Per questo in WorldSim l'energia si conserva: entra solo dalla luce, esce solo dal metabolismo. Senza un flusso vincolato non c'è pressione selettiva.

### Evoluzione dell'evolvibilità
Il tasso di mutazione è un gene. Mutare molto aiuta a esplorare ma rovina i figli di chi è già adattato; oltre la **soglia di errore** (Eigen) l'informazione si degrada più veloce di quanto la selezione la conservi. In ambiente stabile vince chi copia fedelmente: è ciò che si osserva nella v0 (`mut` cala). Previsione: con ambienti variabili il tasso dovrebbe risalire.

### Transizioni evolutive maggiori
Maynard Smith & Szathmáry: momenti in cui replicatori indipendenti diventano parti di un'unità superiore (geni → cromosomi, cellule → organismi, organismi → società). Le colonie della v0 sono il primo gradino; il salto vero richiede **divisione del lavoro** tra cellule dello stesso organismo.

### Emergenza
Nessuna regola dice "formate colonie" o "stratificatevi per profondità": sono comportamenti **emergenti** da regole locali + selezione.

## 4. Il problema aperto: l'evoluzione open-ended

Quasi ogni simulazione converge a un equilibrio e smette di inventare; la biosfera no. È la questione centrale dell'ALife (**open-ended evolution**).

- **Come si misura**: *activity statistics* di Bedau & Packard (innovazioni che compaiono e persistono); metriche **MODES** (change, novelty, complexity, ecology).
- **Cosa la favorirebbe** (ipotesi):
  - ambiente che cambia, anche per effetto degli organismi stessi (niche construction);
  - **rappresentazione genetica aperta**: genoma a lunghezza variabile, regole o programmi invece di un vettore fisso;
  - interazioni ricche tra organismi (coevoluzione, comunicazione).

WorldSim v0 ha un genoma di 9 numeri fissi: lo spazio delle forme è **chiuso per costruzione**, quindi non può essere open-ended. È la direzione naturale delle prossime versioni (vedi [`roadmap.md`](roadmap.md)).

## Letture

- D. Dennett, *L'idea pericolosa di Darwin*.
- J. Holland, *Adaptation in Natural and Artificial Systems* (l'origine dei GA).
- T. Ray, *An approach to the synthesis of life* (Tierra, 1991).
- Lenski, Ofria, Pennock, Adami, *The evolutionary origin of complex features*, Nature 2003 (Avida).
- J. Maynard Smith, E. Szathmáry, *The Major Transitions in Evolution*.
- M. Bedau et al., *Open problems in artificial life*, Artificial Life 2000.
- T. Taylor et al., *Open-Ended Evolution: Perspectives from the OEE Workshop in York*, Artificial Life 2016.
- Stato dell'arte dei progetti: [`stato-dell-arte.md`](stato-dell-arte.md).
