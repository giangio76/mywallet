# MyWallet

Portafoglio ETF (Trade Republic) come **PWA installabile su Android**.
I prezzi vengono aggiornati automaticamente da **GitHub Actions** (script Python)
e letti dall'app dallo stesso dominio: niente CORS, niente proxy che cadono.

```
mywallet/
├── index.html              ← l'app (PWA mobile-first)
├── manifest.webmanifest    ← icona, nome, schermo intero
├── sw.js                   ← service worker (offline)
├── icons/                  ← icone app
├── prezzi.json             ← prezzi correnti (lo riscrive l'Action)
├── storico.json            ← storico giornaliero dei prezzi (per il grafico)
├── fetch_prezzi.py         ← scarica i prezzi da Yahoo (in Python: no CORS)
├── requirements.txt
└── .github/workflows/prezzi.yml  ← cron orario + commit di prezzi.json
```

## 1. Crea il repository

1. Crea un repo su GitHub chiamato **`mywallet`** (pubblico è più semplice per Pages).
2. Carica tutti i file di questa cartella (puoi trascinarli, ma **mantieni la cartella `.github/workflows/`**).

## 2. Permessi per l'Action

Settings → **Actions** → **General** → *Workflow permissions* →
seleziona **Read and write permissions** → Save.
(Serve perché l'Action committa `prezzi.json`.)

## 3. Attiva GitHub Pages

Settings → **Pages** → *Build and deployment* → Source: **Deploy from a branch** →
Branch: **main** / **/ (root)** → Save.
Dopo un minuto avrai l'URL: `https://TUO-UTENTE.github.io/mywallet/`

## 4. Genera i primi prezzi reali

Tab **Actions** → workflow **Aggiorna prezzi** → **Run workflow**.
In ~30 s `prezzi.json` viene riscritto con le quotazioni live.
Da lì in poi gira da solo ogni ora nei giorni feriali.

## 5. Installa sul telefono

Apri l'URL Pages con **Chrome su Android** → menu **⋮** →
**Aggiungi a schermata Home** → conferma.
Ora hai l'icona **MyWallet**: si apre a schermo intero come un'app.

## 6. Usa l'app

- Inserisci la **quantità di quote** di ogni ETF (dal dettaglio posizione in
  Trade Republic): da lì calcola valore, prezzo medio e P&L reale.
- Gli **importi investiti** e le **date** sono già precompilati (modificabili).
- I tuoi dati restano salvati **sul telefono** (localStorage del browser).
- Il riquadro **Andamento** mostra il valore del portafoglio nel tempo
  (ricostruito dalle tue quote sullo storico dei prezzi). Alla prima esecuzione
  dell'Action su GitHub viene riempito con ~6 mesi di storico reale da Yahoo;
  poi cresce di un punto al giorno. Tocca o trascina sul grafico per leggere
  valore e data; i pulsanti 1M/6M/1A/Tutto cambiano il periodo.
- **Aggiorna** rilegge l'ultimo `prezzi.json`. "modifica" su una scheda permette
  di inserire un prezzo a mano.

## Personalizzazione

- **Cambiare ETF / pesi / importi:** modifica l'array `ETFS` in `index.html`
  *e* la lista `ETFS` in `fetch_prezzi.py` (stessi ISIN e simboli Yahoo).
- **Frequenza prezzi:** la riga `cron` in `.github/workflows/prezzi.yml`
  (orari in **UTC**; `6-17` copre circa 08:00–19:00 ora italiana).

## Note

- GitHub usa l'ora **UTC** per il cron, e i job schedulati possono partire con
  qualche minuto di ritardo.
- I workflow schedulati si **disattivano dopo 60 giorni di inattività** del repo:
  basta un commit qualsiasi (o un "Run workflow" manuale) per riattivarli.
- Le quotazioni Yahoo sono ritardate di ~15 minuti: per ETF buy&hold va benissimo.
- Se un ETF non si aggiorna, lo script tiene il valore precedente e tu puoi
  sempre inserirlo a mano.

Strumento personale. Non è consulenza finanziaria.
