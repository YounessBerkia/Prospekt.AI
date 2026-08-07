
import argparse
import ollama
import json
import sys
import os




argument_parser = argparse.ArgumentParser(description="Extract offers from a Kaufland PDF.")
argument_parser.add_argument("--model", type=str, default="gemma4:31b-cloud", help="The model used for extracting offers.")
argument_parser.add_argument("--pages-dir", type=str, default="pages", help="Directory containing the extracted pages.")
argument_parser.add_argument("--output", type=str, default="output/offers.json", help="Output file for the extracted offers.")
argument_parser.add_argument("--restart", action="store_true", help="Restart the extraction process, ignoring any existing output file.")
args = argument_parser.parse_args()

progress_path = os.path.join(os.path.dirname(args.output) or ".", "progress.json")


def load_progress(path, restart):
    if restart:
        return set()
    
    if not os.path.exists(path):
        return set()

    with open(path, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return set()
    return set(data)


def save_progress(path, done_pages):
    with open(path, "w") as f:
        liste = sorted(done_pages)
        json.dump(liste, f)

def list_pages(pages_dir):
    pages = []
    for filename in os.listdir(pages_dir):
        if filename.endswith(".png"):
            page_number = int(filename.split("_")[1].split(".")[0])
            pages.append((page_number, os.path.join(pages_dir, filename)))
    return sorted(pages)


def extract_offers_from_page(image_path, model):
    prompt = """Du bekommst die Bildseite eines Kaufland-Prospekts.
Analysiere das gesamte Bild und extrahiere ALLE beworbenen Angebote.

Antworte AUSSCHLIESSLICH mit einem JSON-Array, ohne Erklärungen, ohne Markdown-Codeblock.
Jedes Element im Array ist ein Objekt mit diesen Feldern:
- "produkt": string, der Produktname wie auf dem Bild abgedruckt
- "preis": string, der Preis inklusive Einheit/Währung, z.B. "1.99€"
- "rabatt_oder_menge": string, optional. Rabattangabe (z.B. "-30%") oder Mengenangabe
  (z.B. "500g", "3 Stück"), falls auf dem Bild vorhanden. Sonst weglassen.
- "kategorie": string, optional. Produktkategorie (z.B. "Obst & Gemüse", "Getränke"),
  falls aus dem Layout erkennbar. Sonst weglassen.

Falls auf der Seite keine Angebote zu erkennen sind, antworte mit einem leeren Array: []

Beispiel für die erwartete Struktur:
[
  {"produkt": "Bananen", "preis": "1.99€", "rabatt_oder_menge": "1kg", "kategorie": "Obst & Gemüse"},
  {"produkt": "Kaffee Krönung", "preis": "4.99€", "rabatt_oder_menge": "-1€"}
]"""
    response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt, "images": [image_path]}], format="json")

    # TODO: response["message"]["content"] holen (ist ein String)
    # und mit json.loads(...) in ein Python-Objekt parsen.
    # Kein try/except hier -- Fehler soll bis zur Hauptschleife durchgereicht werden.
    content = response["message"]["content"]
    offers = json.loads(content)

    return offers



done_pages = load_progress(progress_path, args.restart)
pages = list_pages(args.pages_dir)
all_results = []  # sammelt {"seite": N, "angebote": [...]} pro Seite
os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)


for page_number, image_path in pages:

    if page_number in done_pages:
        continue

    print(f"Verarbeite Seite {page_number}...")

    try:
        offers = extract_offers_from_page(image_path, args.model)
    except json.JSONDecodeError as e:
        print(f"Fehler beim Verarbeiten der Seite {page_number}: {e}")
        continue
    except ConnectionError as e:
        print(f"Verbindungsfehler mit Ollama: {e}")
        sys.exit(1)

    all_results.append({"seite": page_number, "angebote": offers})
    done_pages.add(page_number)
    save_progress(progress_path, done_pages)

    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=1, ensure_ascii=False)

    print(f"Seite {page_number} von {len(pages)} verarbeitet. {len(offers)} Angebote gefunden.")