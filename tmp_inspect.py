from app.services.mwb_scraper import fetch_html_text
s=fetch_html_text('https://www.jw.org/es/biblioteca/guia-actividades-reunion-testigos-jehova/septiembre-octubre-2026-mwb/')
keys=['Canc','Canción','oraci','Palabras','Estudio bíblico','Tesoros','Nuestra vida Cristiana','Tesoros de la Biblia']
s2=s.lower()
for key in keys:
    if key.lower() in s2:
        i=s2.find(key.lower())
        print('FOUND',key,'at',i)
        print(s[max(0,i-200):i+200])
    else:
        print('NOT',key)
print('\n---SNIPPET---\n')
print(s[:2000])
