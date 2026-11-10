# WorldSim

Simulazione di vita artificiale: cellule con un genoma che vivono, si nutrono, si riproducono ed evolvono in un mondo 2D. **Nessuna fitness esplicita**: sopravvive chi riesce a procurarsi energia e a riprodursi.

- Ricerca sul campo: [`docs/stato-dell-arte.md`](docs/stato-dell-arte.md)
- Design della v0: [`docs/design-v0.md`](docs/design-v0.md)
- Teoria (perché non è un algoritmo genetico): [`docs/teoria.md`](docs/teoria.md)
- Roadmap (simulazione + gioco): [`docs/roadmap.md`](docs/roadmap.md)

## Avvio rapido

```bash
pip install -r requirements.txt

# visualizzatore interattivo
python view.py

# run headless: CSV, snapshot PNG, grafico
python run.py --steps 10000 --seed 1 --out runs/prova1

# sovrascrivere un parametro al volo
python run.py --steps 5000 --out runs/prova2 --set pred_eff=0.7 --set immigration_rate=0
```

Comandi del visualizzatore: `SPAZIO` pausa · `N` un passo · `+/-` velocità · `O` materia organica · `S` snapshot · `R` nuovo mondo · clic = ispeziona la cellula.

**Colori**: verde = fotosintesi · viola = decompositori · rosso = predatori (i mix danno i colori intermedi, es. giallo = pianta-predatore). Lo sfondo blu indica la luce, il marrone la materia organica.

## Come funziona

Non è un algoritmo genetico classico (fitness → selezione → crossover). È **selezione naturale implicita**:

1. Ogni cellula ha un **genoma** di 9 numeri in [0,1] (fotosintesi, decomposizione, predazione, movimento, soglia di divisione, energia al figlio, tendenza a restare attaccati, condivisione, tasso di mutazione).
2. A ogni passo paga un **costo metabolico** e guadagna energia secondo i suoi geni e l'ambiente (luce, materia organica, vicine da mangiare).
3. Con abbastanza energia si **divide**: il figlio eredita il genoma con **mutazioni gaussiane**. Con energia zero o con l'età massima **muore** e diventa materia organica.
4. I geni di chi si riproduce di più si diffondono. Fine.

L'unica fonte di energia è la luce, che cala con la profondità ed è oscurata dalle cellule sopra.

## Struttura

```
worldsim/
  config.py   parametri (tutto ciò che si tara)
  world.py    motore: griglia, cellule, ciclo di un passo, statistiche
  render.py   mondo -> immagine RGB
run.py        esecuzione headless + CSV + grafico
view.py       visualizzatore pygame
docs/         ricerca e design
runs/         output delle esecuzioni (ignorato da git)
```

## Risultati v0 (seed 1 e 7, 8–12k passi)

![snapshot](docs/v0_snapshot.png)

![statistiche](docs/v0_stats.png)

- Ecosistema stabile, senza estinzioni, con ~900 cellule.
- Le tre strategie convivono, stratificate: in superficie piante e ibridi pianta-predatore, sotto le piante, ancora sotto i decompositori dove la materia organica sedimenta.
- Evolvono da sole: **colonie** (`attach` 0.5 → 0.73, ~70% delle cellule legate), **tasso di mutazione** in calo, **movimento** abbandonato, divisione precoce.

## Prossimi passi

Vedi [`docs/roadmap.md`](docs/roadmap.md).
