import subprocess
import re

files = ['como_usar.html', 'em_breve.html', 'index.html', 'validador_cadastros.html', 'validador_ofx.html', 'validador_texto.html', 'validador_xml.html']
for t in files:
    cmd = ['git', 'show', f'a1a35ad~1:templates/{t}']
    res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    m = re.search(r'<button[^>]+id="lang-toggle-btn"[^>]*>(.*?)</button>', res.stdout, re.DOTALL)
    if m:
        content = re.sub(r'\s+', ' ', m.group(1)).strip()
        print(f'{t}: {content[:150]}')
    else:
        print(f'{t}: NO MATCH')

