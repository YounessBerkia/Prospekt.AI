# Kaufland-Prospekt-Auswertung — Programmierplan

## Context
Das PDF `/Users/mac/Downloads/Kaufland/Prospekt-Kaufland.pdf` (66 Seiten, reine Bilder, kein Text-Layer) soll automatisch ausgewertet werden: pro Seite sollen alle Angebote (Produkt, Preis, ggf. Rabatt/Menge) extrahiert werden. Der Ansatz nutzt ein lokales multimodales LLM über Ollama, da reines OCR die Zuordnung "Preis gehört zu Produkt X" (Layout-Verständnis) nicht leisten kann. Es existiert bereits ein venv mit dem `ollama`-Python-Paket in `/Users/mac/Downloads/Kaufland/venv`, und `gemma4:e4b` ist bereits lokal installiert (9.6GB, multimodal) — das wird als erstes Modell verwendet. Ausgabe: eine JSON-Datei mit allen Angeboten pro Seite. Das Skript soll bereits verarbeitete Seiten bei erneutem Lauf überspringen (Resume-fähig), da 66 Seiten mehrere Minuten dauern können.

## Projektstruktur
Alles in `/Users/mac/Downloads/Kaufland/`:

```
Kaufland/
├── venv/                      (vorhanden)
├── Prospekt-Kaufland.pdf      (vorhanden)
├── requirements.txt           (neu)
├── extract_pages.py           (neu — PDF → PNGs)
├── extract_offers.py          (neu — PNG → Ollama → JSON, Hauptskript)
├── pages/                     (neu, generiert — page_00.png ... page_65.png)
└── output/
    ├── offers.json            (neu, generiert — Endergebnis)
    └── progress.json          (neu, generiert — Resume-Status)
```

Das alte `main.py` (eigentlich ein leeres Jupyter-Notebook mit nur `import ollama`) wird nicht weiterverwendet, bleibt aber unangetastet liegen — der Nutzer kann es später löschen.

## 1. Abhängigkeiten (`requirements.txt`)
```
pymupdf
ollama
```
(`ollama`-Paket ist schon im venv installiert; `pymupdf` muss ergänzt werden.)
Installation: `venv/bin/pip install -r requirements.txt`

## 2. `extract_pages.py` — PDF → Bilder
- Öffnet das PDF mit PyMuPDF (`fitz.open(...)`)
- Rendert jede Seite bei 200 DPI zu PNG (guter Kompromiss aus Lesbarkeit für das Modell und Dateigröße/Geschwindigkeit)
- Speichert nach `pages/page_00.png` … `page_65.png` (führende Nullen für korrekte Sortierung)
- Überspringt Seiten, deren PNG-Datei schon existiert (idempotent, ermöglicht Neustart)
- CLI: `python extract_pages.py` (kein Argument nötig, Pfade sind fest im Skript, da Projekt-lokal)

## 3. `extract_offers.py` — Bild → Angebote (Hauptskript)
**Ablauf pro Seite:**
1. Lädt `output/progress.json` (Liste bereits verarbeiteter Seiten-IDs). Falls Datei fehlt, startet leer.
2. Iteriert über alle PNGs in `pages/` in sortierter Reihenfolge
3. Überspringt Seiten, die laut `progress.json` schon erledigt sind
4. Für jede offene Seite: Aufruf `ollama.chat()` mit:
   - `model="gemma4:e4b"` (als Konstante/CLI-Argument `--model`, damit später leicht auf `qwen2.5vl:7b` umstellbar)
   - Bild als `images=[page_path]`
   - Prompt (deutsch), der explizit nach JSON-Array fragt mit Feldern `produkt`, `preis`, `rabatt_oder_menge` (optional), `kategorie` (optional, falls erkennbar)
   - `format="json"` Parameter von Ollama, um valides JSON zu erzwingen
5. Parst die Modell-Antwort (`json.loads`), fängt Parse-Fehler ab (bei Fehler: Seite wird geloggt aber nicht in `progress.json` als "done" markiert, damit ein erneuter Lauf sie wiederholt)
6. Hängt Ergebnis unter `{"seite": N, "angebote": [...]}` an eine In-Memory-Liste an, schreibt nach jeder Seite `output/offers.json` komplett neu (einfacher als Streaming, bei 66 Seiten unkritisch für Performance) und aktualisiert `progress.json`
7. Gibt Fortschritt auf der Konsole aus (`Seite 12/66 verarbeitet — 5 Angebote gefunden`)

**Fehlerbehandlung:**
- Netzwerk/Ollama-Verbindungsfehler (z.B. Ollama-Dienst läuft nicht): klare Fehlermeldung mit Hinweis `ollama serve` zu starten, Abbruch
- Ungültiges JSON vom Modell: Seite überspringen, Warnung ausgeben, weiter mit nächster Seite (kein Abbruch des gesamten Laufs)

**CLI-Argumente:**
- `--model` (default `gemma4:e4b`)
- `--pages-dir` (default `pages/`)
- `--output` (default `output/offers.json`)
- `--restart` (Flag, ignoriert `progress.json` und verarbeitet alles neu)

## Verifikation
1. `venv/bin/pip install -r requirements.txt` ausführen, prüfen dass PyMuPDF importierbar ist
2. `venv/bin/python extract_pages.py` laufen lassen → prüfen, dass 66 PNGs in `pages/` liegen und stichprobenartig eines öffnen (lesbar? Angebote erkennbar?)
3. Sicherstellen, dass Ollama läuft (`ollama list` zeigt `gemma4:e4b`)
4. `venv/bin/python extract_offers.py` laufen lassen, Konsolen-Output beobachten
5. Skript nach z.B. 10 Seiten mit Strg+C abbrechen, erneut starten → prüfen, dass es bei Seite 11 weitermacht statt neu bei 1 (Resume-Test)
6. `output/offers.json` öffnen und stichprobenartig 2-3 Seiten gegen das tatsächliche PDF-Bild abgleichen (stimmen Produktname/Preis?)
7. Falls Qualität bei `gemma4:e4b` unzureichend ist: `--model qwen2.5vl:7b` testen (Modell vorher mit `ollama pull qwen2.5vl:7b` laden)
