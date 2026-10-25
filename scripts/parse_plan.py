import re, json, html, sys, datetime as dt
src = sys.argv[1]
s = open(src, encoding='utf-8').read()
def clean(x):
    x = re.sub(r'<br\s*/?>', ' / ', x)
    x = re.sub(r'<[^>]+>', '', x)
    return re.sub(r'\s+', ' ', html.unescape(x)).strip()
start = dt.date(2026, 11, 2)
weeks = []
for m in re.finditer(r'<div class="wkb( down)?">(.*?)</table>', s, re.S):
    b = m.group(2)
    n = re.search(r'wk-n">(.*?)</span>', b).group(1)
    num = int(re.search(r'Неделя (\d+)', n).group(1))
    tag = clean(n).split('·')[1].strip() if '·' in n else ''
    title = clean(re.search(r'<h3>(.*?)</h3>', b).group(1))
    kmline = clean(re.search(r'wk-km">(.*?)</span>', b).group(1))
    km = int(re.search(r'(\d+) км', kmline).group(1))
    sm = re.search(r'(\d+) мин субпорога', kmline)
    focus = re.search(r'wk-focus">(.*?)</p>', b, re.S)
    days = []
    mon = start + dt.timedelta(weeks=num-1)
    for i, r in enumerate(re.finditer(r'<tr( class="(\w+)")?><th>(.*?)</th><td>(.*?)</td><td class="num">(.*?)</td></tr>', b, re.S)):
        td = r.group(4)
        main = clean(re.split(r'<span class="add">', td)[0])
        add = re.search(r'<span class="add">(.*?)</span>\s*$', td, re.S)
        addt = clean(add.group(1)) if add else ''
        kmd = clean(r.group(5))
        full = (main + ' ' + addt).lower()
        days.append({
            'date': (mon + dt.timedelta(days=i)).isoformat(),
            'dow': clean(r.group(3)).split()[0],
            'key': r.group(2) in ('q', 'hi'),
            'session': main, 'extra': addt,
            'km': float(kmd.replace(',', '.')) if re.match(r'^[\d.,]+$', kmd) else 0,
            'strength': 'силовая' in full,
            'swim': 'плавание' in full,
        })
    weeks.append({'week': num, 'tag': tag, 'title': title, 'start': mon.isoformat(),
                  'end': (mon + dt.timedelta(days=6)).isoformat(),
                  'km': km, 'sub_min': int(sm.group(1)) if sm else None,
                  'down': bool(m.group(1)), 'focus': clean(focus.group(1)) if focus else '',
                  'days': days})
# phases
phases = [('Фаза 0 · переход', 1, 2), ('Фаза 1 · втягивание', 3, 7), ('Фаза 2 · ядро базы', 8, 15),
          ('Фаза 3 · конверсия', 16, 21), ('Старты', 22, 23)]
plan = {'name': 'Зима на пороге', 'start': start.isoformat(), 'end': '2027-04-11',
        'goal': '5 км из 18:20, Лужники 4 апреля 2027',
        'zones': {'easy_hr': [135, 150], 'sub_hr': [170, 182], 'lt_hr_plan': 182,
                  'easy_pace': '5:15–5:45', 'sub_long': '4:22–4:28', 'sub_mid': '4:15–4:22'},
        'weeks': weeks}
print(json.dumps(plan, ensure_ascii=False, indent=1))
