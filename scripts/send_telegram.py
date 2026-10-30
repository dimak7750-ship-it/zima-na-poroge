"""Шлёт воскресный отчёт в Telegram: раздел «Коротко» текстом + весь отчёт файлом.
Запускается из GitHub Actions (.github/workflows/telegram.yml).
Нужен секрет репозитория TELEGRAM_BOT_TOKEN. TELEGRAM_CHAT_ID необязателен:
если его нет, чат берётся из последнего сообщения, которое писали боту.
Аргументы — пути к отчётам; без аргументов берётся последний в reports/.
"""
import json, os, re, sys, glob, uuid, urllib.request

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
if not TOKEN:
    raise SystemExit('Нет токена бота: добавь секрет TELEGRAM (или TELEGRAM_BOT_TOKEN) в Settings → Secrets → Actions')
CHAT = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
REPO = os.environ.get('GITHUB_REPOSITORY', 'dimak7750-ship-it/zima-na-poroge')
DASH = 'https://dimak7750-ship-it.github.io/zima-na-poroge/'
API = f'https://api.telegram.org/bot{TOKEN}/'


def call(method, data=None, body=None, ctype=None):
    if body is None:
        body = json.dumps(data).encode()
        ctype = 'application/json'
    req = urllib.request.Request(API + method, data=body, headers={'Content-Type': ctype})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    if not res.get('ok'):
        raise SystemExit(f'Telegram {method}: {res}')
    return res


def short_part(md):
    title = md.splitlines()[0].lstrip('# ').strip() if md else ''
    m = re.search(r'^## Коротко\s*\n(.*?)(?=^## |\Z)', md, re.S | re.M)
    part = m.group(1).strip() if m else md[:1500]
    part = re.sub(r'\*\*(.+?)\*\*', r'\1', part)
    part = re.sub(r'^- ', '• ', part, flags=re.M)
    return title, part


def send(path):
    md = open(path, encoding='utf-8').read()
    title, part = short_part(md)
    name = os.path.basename(path)
    text = f'{title}\n\n{part}\n\nОтчёт целиком: https://github.com/{REPO}/blob/main/reports/{name}\nДашборд: {DASH}'
    call('sendMessage', {'chat_id': CHAT, 'text': text[:4096], 'disable_web_page_preview': True})

    b = uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{CHAT}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{name}"\r\n'
            f'Content-Type: text/markdown\r\n\r\n').encode() + md.encode('utf-8') + f'\r\n--{b}--\r\n'.encode()
    call('sendDocument', body=body, ctype=f'multipart/form-data; boundary={b}')
    print('отправлен', name)


if not CHAT:
    upd = call('getUpdates', {'limit': 100})['result']
    chats = [u[k]['chat']['id'] for u in upd for k in ('message', 'edited_message') if k in u]
    if not chats:
        raise SystemExit('Не знаю, куда слать: напиши боту любое сообщение и запусти ещё раз')
    CHAT = str(chats[-1])
    print('chat_id из getUpdates:', CHAT)

paths = [p for p in sys.argv[1:] if p.strip()] or sorted(glob.glob('reports/*.md'))[-1:]
for p in paths:
    send(p)
