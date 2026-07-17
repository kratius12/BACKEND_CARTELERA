import requests
from bs4 import BeautifulSoup
url='https://www.jw.org/es/biblioteca/guia-actividades-reunion-testigos-jehova/septiembre-octubre-2026-mwb/'
resp=requests.get(url, headers={'User-Agent':'mwbscraper/1.0'})
resp.raise_for_status()
soup=BeautifulSoup(resp.text,'lxml')
main=soup.find('article') or soup.find(attrs={'role':'main'}) or soup.find('main') or soup
links=main.find_all('a')
for a in links[:50]:
    href=a.get('href')
    text=a.get_text(strip=True)
    print(text, '->', href)
print('--- total links in main:', len(links))
