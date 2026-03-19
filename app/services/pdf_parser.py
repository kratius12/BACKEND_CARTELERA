import re
import subprocess
import os
from datetime import datetime, timedelta

MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
    "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
    "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
}

def parse_mwb_pdf(pdf_path: str, filename: str) -> list[dict]:
    process = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True)
    if process.returncode != 0:
        raise Exception(f"Error procesando el PDF: {process.stderr}")
    
    raw_text = process.stdout
    
    base_year = datetime.now().year
    base_month = 1
    m = re.search(r'(\d{4})(\d{2})', filename)
    if m:
        base_year = int(m.group(1))
        base_month = int(m.group(2))
    
    programs = []
    
    week_date_re = re.compile(r'(\d{1,2})\W*-\W*(\d{1,2})\W+D\W*E\W+([A-ZÁÉÍÓÚ\s]+)', re.IGNORECASE)
    alt_week_date_re = re.compile(r'(\d{1,2})\W+D\W*E\W+([A-ZÁÉÍÓÚ\s]+)\W*A\W*(\d{1,2})\W+D\W*E\W+([A-ZÁÉÍÓÚ\s]+)', re.IGNORECASE)

    text = raw_text
    
    # Tolerante a caracteres de control (\x02) y acentos
    intro_song_iter = re.finditer(r'Canci.*?n\W+(\d+)\W+y\W+oraci.*?n\W+Palabras\W+de\W+introducci.*?n', text, re.IGNORECASE)
    intro_matches = list(intro_song_iter)
    
    for i, match in enumerate(intro_matches):
        start_idx = match.start()
        end_idx = intro_matches[i+1].start() if i + 1 < len(intro_matches) else len(text)
        block = text[start_idx:end_idx]
        
        header_area = text[max(0, start_idx - 500):start_idx]
        header_area = re.sub(r'[\n\r]', ' ', header_area)
        header_area = re.sub(r'\s+', ' ', header_area)
        
        m_week = week_date_re.search(header_area)
        m_alt = alt_week_date_re.search(header_area)
        
        start_day, end_day = None, None
        month_str = ""
        
        if m_alt:
            start_day = int(m_alt.group(1))
            month_str_1 = m_alt.group(2).replace(" ", "").upper()
            end_day = int(m_alt.group(3))
            month_str = month_str_1 
        elif m_week:
            start_day = int(m_week.group(1))
            end_day = int(m_week.group(2))
            month_str = m_week.group(3).replace(" ", "").upper()
            month_str = month_str.replace("I", "I").replace("L", "L")
        else:
            continue
            
        clean_m = ""
        for k in MESES.keys():
            if k in month_str or month_str in k or k.replace(" ", "") in month_str:
                clean_m = k
                break
        
        month_num = MESES.get(clean_m, base_month)
        
        try:
            week_start_date = datetime(base_year, month_num, start_day)
        except ValueError:
            week_start_date = datetime(base_year, base_month, 1)

        if week_start_date.weekday() != 0:
            week_start_date = week_start_date - timedelta(days=week_start_date.weekday())
            
        week_end_date = week_start_date + timedelta(days=6)
        title = "Programa para la reunión de entre semana"
        
        opening_song = f"Canción {match.group(1)}"
        
        m_mid = re.search(r'NUESTRA\W*VIDA\W*CRISTIANA.*?Canci.*?n\W+(\d+)', block, re.IGNORECASE | re.DOTALL)
        middle_song = f"Canción {m_mid.group(1)}" if m_mid else "0"
        
        m_vida_header = re.search(r'NUESTRA\W*VIDA\W*CRISTIANA', block, re.IGNORECASE)
        index_vida = m_vida_header.start() if m_vida_header else len(block)
        
        m_end_iter = list(re.finditer(r'Canci.*?n\W+(\d+)\W+y\W+oraci.*?n', block, re.IGNORECASE))
        closing_song = f"Canción {m_end_iter[-1].group(1)}" if m_end_iter else "0"
        
        parts_iter = list(re.finditer(r'(?:^|\n)\W*(\d+)\.\W+(.*?)\((\d+)\W*mins?\.\)', block, re.DOTALL))
        
        # Build the dynamic payload Parts Array
        parts = []
        
        # 1. Pre-parts
        parts.append({"type": "song", "text": opening_song})
        parts.append({"type": "bullet", "text": "Palabras de introducción", "minutes": 1, "assigned": [""]})

        tesoros_items = []
        maestros_items = []
        vida_items = []
        
        for p_match in parts_iter:
            num = int(p_match.group(1))
            raw_t = p_match.group(2).strip()
            raw_t = re.sub(r'\s+', ' ', raw_t)
            time_m = int(p_match.group(3))
            
            if num in [1, 2, 3]:
                if num == 3: 
                    raw_t = "Lectura de la Biblia"
                    time_m = 4
                tesoros_items.append({"type": "bullet", "text": raw_t, "minutes": time_m, "assigned": ["", ""]})
            else:
                if p_match.start() < index_vida:
                    maestros_items.append({"type": "bullet", "text": raw_t, "minutes": time_m, "assigned": ["", ""]})
                else:
                    if "Estudio bíblico" in raw_t:
                        vida_items.append({"type": "bullet", "text": "Estudio bíblico de la congregación", "minutes": time_m, "assigned": ["", ""]})
                    else:
                        vida_items.append({"type": "bullet", "text": raw_t, "minutes": time_m, "assigned": [""]})
        
        # 2. Sections
        # Tesoros
        parts.append({
            "type": "section",
            "title": "Tesoros de la Biblia",
            "style": "gray",
            "items": tesoros_items
        })
        
        # Seamos
        parts.append({
            "type": "section",
            "title": "Seamos Mejores Maestros",
            "style": "gold",
            "columns": ["Estudiante", "Ayudante"],
            "items": maestros_items
        })
        
        # Vida
        vida_items.insert(0, {"type": "song", "text": middle_song})
        parts.append({
            "type": "section",
            "title": "Nuestra Vida Cristiana",
            "style": "wine",
            "items": vida_items
        })
        
        # 3. Post-parts
        parts.append({"type": "outro", "text": "Palabras de conclusión", "minutes": 3, "assigned": [""]})
        parts.append({"type": "song", "text": closing_song})

        payload_dict = {
            "title": title,
            "meta": {
                "rangeText": "",
                "readingText": "",
                "president": "",
                "openingPrayer": "",
                "closingPrayer": ""
            },
            "parts": parts
        }
        
        programs.append({
            "week_start": week_start_date.strftime("%Y-%m-%d"),
            "week_end": week_end_date.strftime("%Y-%m-%d"),
            **payload_dict
        })

    return programs
