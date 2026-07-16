import re
import requests
from bs4 import BeautifulSoup
from typing import List

from app.services.pdf_parser import parse_mwb_text


def fetch_html_text(url: str, timeout: int = 10) -> str:
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "mwbscraper/1.0"})
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # Try to pick a main/article section if available
    main = soup.find('article') or soup.find(attrs={"role": "main"}) or soup.find('main')
    if main:
        return main.get_text(separator='\n')

    # Fallback: body text
    body = soup.body
    if body:
        return body.get_text(separator='\n')

    # As last resort, return full HTML stripped
    return soup.get_text(separator='\n')


def parse_mwb_from_url(url: str) -> List[dict]:
    """
    Fetch a JW.org MWB guide index page, follow each weekly link, and return a list of program dicts.
    """
    # Get main index and find per-week links
    resp = requests.get(url, timeout=10, headers={"User-Agent": "mwbscraper/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    main = soup.find('article') or soup.find(attrs={"role": "main"}) or soup.find('main') or soup

    links = []
    for a in main.find_all('a', href=True):
        href = a['href']
        if '/Vida-y-Ministerio-Cristianos-' in href or 'Vida-y-Ministerio-Cristianos' in href:
            full = href if href.startswith('http') else f'https://www.jw.org{href}'
            if full not in links:
                links.append(full)

    programs: List[dict] = []

    for week_url in links:
        try:
            week_text = fetch_html_text(week_url)
            week_programs = parse_mwb_text(week_text, week_url)
            if week_programs:
                programs.extend(week_programs)
        except Exception:
            # ignore individual week failures but continue
            continue

    return programs
