import pymupdf
import os

doc = pymupdf.open("Prospekt-Kaufland.pdf")
matrix = pymupdf.Matrix(200/72, 200/72)


for i, page in enumerate(doc.pages()):
    filepath = f"pages/page_{i:02d}.png"
    
    if os.path.exists(filepath): 
        continue # Überspringt bereits existierende Seiten
        
    pix = page.get_pixmap(matrix=matrix)
    pix.save(filepath)