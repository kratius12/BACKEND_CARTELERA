import re
import subprocess
import os
import shutil
from datetime import datetime, timedelta

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
    "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
    "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
}


def _extract_text_from_pdf(pdf_path: str) -> str:
    pdftotext_path = shutil.which('pdftotext')
    if pdftotext_path:
        process = subprocess.run([pdftotext_path, pdf_path, '-'], capture_output=True, text=True)
        if process.returncode == 0:
            return process.stdout
        stderr = process.stderr.strip() or process.stdout.strip()
        if PdfReader is None:
            raise RuntimeError(f"Error procesando el PDF con pdftotext: {stderr}")
    
    if PdfReader:
        try:
            reader = PdfReader(pdf_path)
            text_segments = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_segments.append(page_text)
            extracted = '\n'.join(text_segments)
            if extracted.strip():
                return extracted
            raise RuntimeError("El PDF se procesó con PyPDF2 pero no se extrajo texto legible.")
        except Exception as e:
            raise RuntimeError(f"Error procesando el PDF con PyPDF2: {e}")

    raise RuntimeError(
        "No se encontró el comando 'pdftotext' ni la librería PyPDF2. "
        "Instala Poppler/pdftotext o agrega PyPDF2 a tu entorno Python."
    )


def _normalize_text(text: str) -> str:
    text = text.replace('\r', '\n')
    text = re.sub(r'\s+', ' ', text)
    return text


def _extract_year(text: str, default_year: int) -> int:
    m = re.search(r'(20\d{2})', text)
    return int(m.group(1)) if m else default_year


def _parse_spanish_week_range(text: str, base_year: int):
    text = text.upper()
    month_names = '|'.join(MESES.keys())

    m = re.search(rf'(\d{{1,2}})\s*-\s*(\d{{1,2}})\s*DE\s*({month_names})(?:\s*DE\s*(\d{{4}}))?', text)
    if m:
        start_day = int(m.group(1))
        end_day = int(m.group(2))
        month = MESES.get(m.group(3), 1)
        year = int(m.group(4)) if m.group(4) else base_year
        return datetime(year, month, start_day), datetime(year, month, end_day)

    m = re.search(rf'(\d{{1,2}})\s*DE\s*({month_names})\s*A\s*(\d{{1,2}})\s*DE\s*({month_names})(?:\s*DE\s*(\d{{4}}))?', text)
    if m:
        start_day = int(m.group(1))
        start_month = MESES.get(m.group(2), 1)
        end_day = int(m.group(3))
        end_month = MESES.get(m.group(4), start_month)
        year = int(m.group(5)) if m.group(5) else base_year
        end_year = year if end_month >= start_month else year + 1
        return datetime(year, start_month, start_day), datetime(end_year, end_month, end_day)

    return None


def _extract_numbered_parts(section_text: str) -> list[dict]:
    part_re = re.compile(
        r'(?:^|\n)\s*(\d+)\.\s*(.*?)\s*(?:\(?\s*(\d+)\s*(?:mins?|minutos?)\s*\)?(?=\s*(?:\n\s*\d+\.|$))|(?=\n\s*\d+\.|$))',
        re.IGNORECASE | re.DOTALL
    )
    items = []
    for m in part_re.finditer(section_text):
        raw_text = re.sub(r'\s+', ' ', m.group(2)).strip()
        if raw_text.endswith(':'):
            raw_text = raw_text[:-1].strip()
        minutes = int(m.group(3)) if m.group(3) else None
        items.append({"text": raw_text, "minutes": minutes})
    return items


def _split_mwb_sections(block: str) -> dict:
    headings = [
        ("Tesoros de la Biblia", r"tesoros\s+de\s+la\s+biblia"),
        ("Seamos Mejores Maestros", r"seamos\s+mejores\s+maestros"),
        ("Nuestra Vida Cristiana", r"nuestra\s+vida\s+cristiana"),
    ]
    matches = []
    for title, pattern in headings:
        m = re.search(pattern, block, re.IGNORECASE)
        if m:
            matches.append((m.start(), m.end(), title))

    if not matches:
        return {}

    matches.sort(key=lambda x: x[0])
    sections = {}
    for idx, (_, end_pos, title) in enumerate(matches):
        start_pos = end_pos
        end_range = matches[idx + 1][0] if idx + 1 < len(matches) else len(block)
        sections[title] = block[start_pos:end_range]
    return sections


def parse_mwb_text(raw_text: str, filename: str) -> list[dict]:

    raw_text = _normalize_text(raw_text)

    base_year = _extract_year(filename, datetime.now().year)
    base_month = 1

    programs = []

    week_date_re = re.compile(
        r'(\d{1,2})\W*(?:de\W*)?\W*-\W*(\d{1,2})\W*(?:de\W*)?\W*(?:de\W+)?([A-ZÁÉÍÓÚÑ\s]+)',
        re.IGNORECASE
    )
    alt_week_date_re = re.compile(
        r'(\d{1,2})\W*(?:de\W*)?([A-ZÁÉÍÓÚÑ\s]+)\W*A\W*(\d{1,2})\W*(?:de\W*)?([A-ZÁÉÍÓÚÑ\s]+)',
        re.IGNORECASE
    )

    text = raw_text

    intro_song_iter = list(re.finditer(
        r'Canc(?:i[oó]n|ion)\W+(\d+)\W+y\W+oraci(?:ó|on)\W+Palabras\W+de\W+introducci(?:ó|on)',
        text,
        re.IGNORECASE
    ))

    if not intro_song_iter:
        first_song = re.search(r'Canc(?:i[oó]n|ion)\W+(\d+)', text, re.IGNORECASE)
        if first_song:
            intro_song_iter = [first_song]

    if not intro_song_iter:
        return []

    for i, match in enumerate(intro_song_iter):
        start_idx = match.start()
        end_idx = intro_song_iter[i+1].start() if i + 1 < len(intro_song_iter) else len(text)
        block = text[start_idx:end_idx]

        header_area = text[max(0, start_idx - 500):start_idx]
        header_area = re.sub(r'[\n\r]', ' ', header_area)
        header_area = re.sub(r'\s+', ' ', header_area)

        date_search_text = header_area + ' ' + filename
        date_range = _parse_spanish_week_range(date_search_text, base_year) or _parse_spanish_week_range(text, base_year)

        if date_range:
            week_start_date, week_end_date = date_range
        else:
            m_week = week_date_re.search(header_area) or week_date_re.search(text)
            m_alt = alt_week_date_re.search(header_area) or alt_week_date_re.search(text)

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
            else:
                start_day = 1
                end_day = 7
                month_str = ''

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

        song_matches = re.findall(r'Canc(?:i[oó]n|ion)\W+(\d+)', block, re.IGNORECASE)
        opening_song = f"Canción {song_matches[0]}" if song_matches else f"Canción {match.group(1)}"
        middle_song = f"Canción {song_matches[1]}" if len(song_matches) > 1 else "0"
        closing_song = f"Canción {song_matches[-1]}" if len(song_matches) > 1 else "0"

        section_texts = _split_mwb_sections(block)
        use_section_split = bool(section_texts)

        tesoros_items = []
        maestros_items = []
        vida_items = []

        if use_section_split:
            raw_tesoros = _extract_numbered_parts(section_texts.get("Tesoros de la Biblia", ""))
            raw_maestros = _extract_numbered_parts(section_texts.get("Seamos Mejores Maestros", ""))
            raw_vida = _extract_numbered_parts(section_texts.get("Nuestra Vida Cristiana", ""))

            tesoros_items = [
                {"type": "bullet", "text": item["text"], "minutes": item["minutes"], "assigned": ["", ""]}
                for item in raw_tesoros
            ]
            maestros_items = [
                {"type": "bullet", "text": item["text"], "minutes": item["minutes"], "assigned": ["", ""]}
                for item in raw_maestros
            ]
            for item in raw_vida:
                if "estudio bíblico" in item["text"].lower():
                    vida_items.append({"type": "bullet", "text": "Estudio bíblico de la congregación", "minutes": item["minutes"], "assigned": ["", ""]})
                else:
                    vida_items.append({"type": "bullet", "text": item["text"], "minutes": item["minutes"], "assigned": [""]})
        else:
            m_vida_header = re.search(r'NUESTRA\W*VIDA\W*CRISTIANA', block, re.IGNORECASE)
            index_vida = m_vida_header.start() if m_vida_header else len(block)

            parts_iter = list(re.finditer(
                r'(?:^|\n)\s*(\d+)\.\s*(.*?)\s*(?:\((\d+)\s*(?:mins?|minutos?)\)|(?=\n\s*\d+\.|$))',
                block,
                re.DOTALL | re.IGNORECASE
            ))

            for p_match in parts_iter:
                num = int(p_match.group(1))
                raw_t = p_match.group(2).strip()
                raw_t = re.sub(r'\s+', ' ', raw_t)
                time_m = int(p_match.group(3)) if p_match.group(3) else None

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

        parts = []
        parts.append({"type": "song", "text": opening_song})
        parts.append({"type": "bullet", "text": "Palabras de introducción", "minutes": 1, "assigned": [""]})

        parts.append({
            "type": "section",
            "title": "Tesoros de la Biblia",
            "style": "gray",
            "items": tesoros_items
        })

        parts.append({
            "type": "section",
            "title": "Seamos Mejores Maestros",
            "style": "gold",
            "columns": ["Estudiante", "Ayudante"],
            "items": maestros_items
        })

        vida_items.insert(0, {"type": "song", "text": middle_song})
        parts.append({
            "type": "section",
            "title": "Nuestra Vida Cristiana",
            "style": "wine",
            "items": vida_items
        })

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


def parse_mwb_pdf(pdf_path: str, filename: str) -> list[dict]:
    raw_text = _extract_text_from_pdf(pdf_path)
    return parse_mwb_text(raw_text, filename)
