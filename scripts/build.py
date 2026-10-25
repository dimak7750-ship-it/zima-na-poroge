"""Собирает data/*.json в data/weeks.json и data/bundle.js для дашборда.
Запуск из корня репозитория: python3 scripts/build.py
"""
import json, datetime as dt, os, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, 'data', *p)
load = lambda name: json.load(open(D(name), encoding='utf-8'))

plan = load('plan.json')
acts = load('activities.json')
well = load('wellness.json')
notes = load('notes.json')
status = load('status.json')

RUN = {'running', 'treadmill_running', 'trail_running', 'track_running', 'indoor_running'}
SWIM = {'lap_swimming', 'open_water_swimming', 'swimming'}
STR = {'strength_training'}

def monday(d):
    return d - dt.timedelta(days=d.weekday())

def avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None

plan_by_start = {w['start']: w for w in plan['weeks']}
first = monday(min(dt.date.fromisoformat(a['date']) for a in acts))
last = dt.date.fromisoformat(plan['end'])
today = dt.date.fromisoformat(os.environ.get('TODAY', dt.date.today().isoformat()))

weeks = []
d = first
while d <= last:
    s, e = d.isoformat(), (d + dt.timedelta(days=6)).isoformat()
    wa = [a for a in acts if s <= a['date'] <= e]
    runs = [a for a in wa if a['type'] in RUN]
    ww = [x for x in well if s <= x['date'] <= e]
    p = plan_by_start.get(s)
    sub = sum(a.get('z4_min') or 0 for a in runs)
    above = sum(a.get('z5_min') or 0 for a in runs)
    has_zones = any(a.get('z4_min') is not None for a in runs)
    # качественный день = в беге за день >= 8 мин выше 169
    qdays = 0
    for i in range(7):
        day = (d + dt.timedelta(days=i)).isoformat()
        m = sum((a.get('z4_min') or 0) + (a.get('z5_min') or 0) for a in runs if a['date'] == day)
        if m >= 8:
            qdays += 1
    w = {
        'start': s, 'end': e,
        'week': p['week'] if p else None,
        'tag': p['tag'] if p else '',
        'status': 'done' if dt.date.fromisoformat(e) < today else ('now' if s <= today.isoformat() <= e else 'future'),
        'plan_km': p['km'] if p else None,
        'plan_sub': p['sub_min'] if p else None,
        'plan_key': sum(1 for x in p['days'] if x['key']) if p else None,
        'plan_str': sum(1 for x in p['days'] if x['strength']) if p else None,
        'plan_swim': sum(1 for x in p['days'] if x['swim']) if p else None,
        'km': round(sum(a['km'] or 0 for a in runs), 1) if wa or dt.date.fromisoformat(s) <= today else None,
        'runs': len(runs),
        'long': max([a['km'] or 0 for a in runs], default=0),
        'sub': round(sub) if has_zones else None,
        'above': round(above) if has_zones else None,
        'key': qdays if has_zones else None,
        'str': sum(1 for a in wa if a['type'] in STR),
        'swim': sum(1 for a in wa if a['type'] in SWIM),
        'load': round(sum(a['load'] or 0 for a in wa)) if any(a.get('load') for a in wa) else None,
        'sleep': avg([x['sleep_h'] for x in ww]),
        'hrv': avg([x['hrv'] for x in ww]),
        'rhr': avg([x['rhr'] for x in ww]),
    }
    if w['status'] == 'future':
        w['km'] = None
    weeks.append(w)
    d += dt.timedelta(days=7)

# ---- отклонения от плана ----
EASY_MAX = plan['zones']['easy_hr'][1]          # 150
plan_days = {d['date']: d for w in plan['weeks'] for d in w['days']}

def day_quality_min(day):
    return sum((a.get('z4_min') or 0) + (a.get('z5_min') or 0) for a in acts if a['date'] == day and a['type'] in RUN)

issues = []
RACE = ('старт', 'кубк', 'этап', 'чемпионат', 'контроль', 'тест', 'кросс')
is_race = lambda t: any(r in t.lower() for r in RACE)
def issue(date, kind, text, level='warn'):
    issues.append({'date': date, 'kind': kind, 'text': text, 'level': level})

for a in acts:
    if a['type'] not in RUN or (a['km'] or 0) < 3 or a.get('hr') is None:
        continue
    p = plan_days.get(a['date'])
    planned_easy = p is not None and not p['key']
    unplanned_q = day_quality_min(a['date']) >= 8
    # до начала плана не судим: без плана не понять, что было лёгким
    if a['hr'] > EASY_MAX and planned_easy and not unplanned_q:
        issue(a['date'], 'лёгкий быстро', f"{a['km']} км по {a['pace']}, пульс {a['hr']} — для лёгкого выше {EASY_MAX}")
    if p is not None and p['key'] and (a.get('z5_min') or 0) >= 3 and not is_race(p['session']):
        issue(a['date'], 'выше порога', f"в работе {round(a['z5_min'])} мин выше 182 — субпорог ушёл в порог")

for w in plan['weeks']:
    if w['end'] >= today.isoformat():
        continue
    for d in w['days']:
        runs = [a for a in acts if a['date'] == d['date'] and a['type'] in RUN]
        if d['km'] and not runs:
            issue(d['date'], 'пропуск', f"по плану: {d['session']} — бега нет", 'miss')
        elif d['key'] and day_quality_min(d['date']) < 8 and runs:
            issue(d['date'], 'работа не сделана', f"по плану: {d['session']} — субпорога почти нет", 'miss')
        if d['strength'] and not any(a['date'] == d['date'] and a['type'] in STR for a in acts):
            issue(d['date'], 'силовая', 'силовая по плану, в часах не записана', 'info')
for w in weeks:
    if w['status'] != 'done' or not w['plan_km'] or w['km'] is None:
        continue
    r = w['km'] / w['plan_km']
    if r < 0.85:
        issue(w['end'], 'объём', f"неделя {w['week']}: {w['km']} из {w['plan_km']} км ({round(r*100)}%)", 'miss')
    elif r > 1.10:
        issue(w['end'], 'объём', f"неделя {w['week']}: {w['km']} км при плане {w['plan_km']} (+{round(r*100)-100}%)")
    if w['plan_sub'] and w['sub'] is not None and w['sub'] < 0.75 * w['plan_sub']:
        issue(w['end'], 'субпорог', f"неделя {w['week']}: {w['sub']} из {w['plan_sub']} мин субпорога", 'miss')

issues.sort(key=lambda x: x['date'])

# сетка выполнения: каждый день плана
grid = []
for w in plan['weeks']:
    for d in w['days']:
        runs = [a for a in acts if a['date'] == d['date'] and a['type'] in RUN]
        km = round(sum(a['km'] or 0 for a in runs), 1)
        di = [i for i in issues if i['date'] == d['date'] and i['level'] != 'info' and i['kind'] not in ('объём', 'субпорог')]
        if d['date'] > today.isoformat():
            st = 'future'
        elif d['date'] == today.isoformat() and not runs:
            st = 'future'
        elif not d['km']:
            st = 'rest' if not runs else 'ok'
        elif not runs:
            st = 'miss'
        elif di:
            st = 'dev'
        else:
            st = 'ok'
        grid.append({'date': d['date'], 'week': w['week'], 'key': d['key'], 'plan_km': d['km'],
                     'km': km, 'st': st, 'session': d['session'], 'why': [i['text'] for i in di]})
for w in weeks:
    w['issues'] = sum(1 for i in issues if w['start'] <= i['date'] <= w['end'] and i['level'] != 'info')

json.dump(weeks, open(D('weeks.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
json.dump(issues, open(D('issues.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

reports = sorted(os.path.basename(f)[:-3] for f in glob.glob(os.path.join(ROOT, 'reports', '*.md')))
bundle = {'built': today.isoformat(), 'plan': plan, 'weeks': weeks, 'activities': acts,
          'wellness': well, 'notes': notes, 'status': status, 'reports': reports, 'issues': issues, 'grid': grid}
with open(D('bundle.js'), 'w', encoding='utf-8') as f:
    f.write('window.DATA = ' + json.dumps(bundle, ensure_ascii=False) + ';\n')
print('ok:', len(weeks), 'недель,', len(acts), 'тренировок,', len(well), 'дней состояния')
