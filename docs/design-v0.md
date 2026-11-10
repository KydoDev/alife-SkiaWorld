# WorldSim v0 — Cellule con genoma ed energia

> Obiettivo v0: un mondo 2D minimale in cui **strategie di vita diverse emergono e convivono** senza fitness esplicita. Successo = ecosistema stabile con almeno 2 strategie (es. produttori + predatori/decompositori) dopo migliaia di passi.

## Principi
- **Semplice prima, poi strati.** Niente fisica dettagliata: griglia, energia, regole locali.
- **Nessuna fitness.** Sopravvive chi si riproduce; l'unica fonte di energia è la luce.
- **Energia conservata.** Ogni joule viene dalla luce e finisce in metabolismo; il resto circola (corpi → materia organica → decompositori).
- **Headless first.** Motore separato dal visualizzatore (portabile poi su JAX/Rust/Unity).

## Il mondo
- Griglia **W×H** (default 160×100). Asse x toroidale (si riavvolge), y = profondità: riga 0 = superficie, ultima riga = fondale.
- **Luce**: massima in superficie, cala esponenzialmente con la profondità **e** viene schermata da ogni cellula sopra (`shade^n`). → competizione per la luce.
- **Materia organica**: campo continuo per casella. Viene da cellule morte / prede non digerite, si **diffonde**, **affonda** lentamente e decade.

## La cellula
Occupa una casella. Stato: energia, età, genoma, legami con vicine (colonia).

### Genoma (9 geni in [0,1], ereditati con mutazione gaussiana)
| # | Gene | Effetto |
|---|---|---|
| 0 | `photo` | affinità fotosintesi |
| 1 | `sapro` | affinità decomposizione (mangia materia organica) |
| 2 | `pred` | affinità predazione (mangia cellule vicine) |
| 3 | `move` | probabilità di muoversi per passo (solo se non legata) |
| 4 | `div` | soglia di energia per dividersi |
| 5 | `child` | frazione di energia data al figlio |
| 6 | `attach` | probabilità che il figlio resti attaccato → colonia |
| 7 | `share` | quanta energia condivide con le cellule legate |
| 8 | `mut` | intensità delle mutazioni dei figli (**il tasso di mutazione evolve**) |

I tre geni trofici sono **normalizzati** (photo+sapro+pred = 1) e il guadagno usa `p^1.5`: specializzarsi conviene, essere generalisti costa. → trade-off da cui nascono "piante", "funghi", "predatori".

### Ciclo di un passo (ordine casuale tra le cellule)
1. **Metabolismo**: paga `base_cost + pred·pred_upkeep + move·move_upkeep` (avere bocca e muscoli costa anche quando non li usi).
2. **Fotosintesi**: `+ photo_gain · photo^1.5 · luce(casella)`.
3. **Decomposizione**: prende materia organica dalla casella, `+ sapro_eff · presa`.
4. **Predazione**: con probabilità `pred^1.5` attacca una vicina **non legata a sé**: ottiene `pred_eff ·` (energia + corpo) della preda; il resto diventa organico.
5. **Movimento**: se non legata, con probabilità `move` va in una casella libera adiacente (costo).
6. **Condivisione**: cede energia alle cellule legate più povere (`share`).
7. **Divisione**: se energia ≥ soglia e c'è una casella libera: paga il **costo del corpo**, il figlio riceve `child` dell'energia rimasta e un genoma mutato; con probabilità `attach` restano legati.
8. **Morte**: energia ≤ 0 o età massima → energia residua + corpo diventano materia organica.

## Immigrazione
Ogni passo compaiono in media 0.5 cellule con genoma casuale in caselle libere. Senza immigrazione le nicchie "lontane" (es. decompositori nel buio) non vengono mai raggiunte, perché le forme intermedie non sopravvivono. È un'aggiunta standard in ALife per mantenere la diversità; si spegne con `--set immigration_rate=0`.

## Taratura v0 (valori in `config.py`)
Griglia 160×64 · 400 cellule iniziali con energia 40 · `photo_gain` 3 · `spec_exp` 2 · `pred_eff` 0.5 · `organic_sink` 0.01 · `body_cost` 5 · `max_age` 600 · immigrazione 0.5/passo.
Primi tentativi: con `photo_gain` 1 la popolazione collassava; con `spec_exp` 1.5 dominavano gli ibridi pianta-predatore; con sedimentazione 0.05 la materia organica finiva subito sul fondale, irraggiungibile.

## Osservazione
- **Colori**: verde = fotosintesi, viola = decomposizione, rosso = predazione (mix in base al genoma). Sfondo: blu = luce, marrone = materia organica.
- **Statistiche** (CSV): popolazione, conteggio per strategia dominante, tratti medi, % cellule in colonia, lignaggi sopravvissuti, energia e organico totali.
- **Snapshot PNG** periodici + grafico delle popolazioni.

## Fuori scope v0 (prossimi strati)
1. Sensori + scelte direzionali (muoversi verso cibo/luce) → mini-cervello.
2. Specializzazione nelle colonie (cellule diverse nello stesso organismo) → multicellularità vera.
3. Segnali chimici tra cellule → comunicazione → base per il sociale.
4. Stagioni / ciclo giorno-notte, ambienti eterogenei.
5. Albero filogenetico e identificazione automatica delle "specie".
6. Port del motore su JAX o Rust per scalare a milioni di cellule.
