"""確認前端入口引用的本機資源在重構後仍存在。"""

from pathlib import Path
import re
import sys

frontend = Path(__file__).resolve().parents[1] / 'frontend'
html_files = [frontend / 'index.html', *sorted((frontend / 'pages').glob('*.html'))]
refs = []
for html_file in html_files:
    refs.extend(re.findall(r'(?:href|src)="([^"]+)"', html_file.read_text(encoding='utf-8')))

# 頁面片段會被 index.html 以 innerHTML 注入，因此也以 frontend 作為 URL 基準。
missing = [
    ref for ref in refs
    if not ref.startswith(('qrc:', 'http:', 'https:', '#', 'javascript:'))
    and not (frontend / ref).is_file()
]

# 動態產生的本機圖像也必須指向前端根目錄的 assets。
for script in (frontend / 'scripts').rglob('*.js'):
    for asset in re.findall(r"(?:src=|['\"])(assets/[A-Za-z0-9_.-]+)", script.read_text(encoding='utf-8')):
        if not (frontend / asset).is_file():
            missing.append(f'{script.relative_to(frontend)} -> {asset}')
if missing:
    print('Missing frontend files:', ', '.join(missing))
    sys.exit(1)
print(f'Frontend references OK ({len(refs)} checked)')
