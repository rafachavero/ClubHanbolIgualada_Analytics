import json
import re
import csv
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://resultadosbalonmano.isquad.es/maqueta/'
}

def get_token():
    req = urllib.request.Request('https://resultadosbalonmano.isquad.es/maqueta/', headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    m = re.search(r'name="client-token"\s+content="([^"]+)"', html)
    return m.group(1) if m else ''

TOKEN = get_token()
print("Got token:", TOKEN[:30] + "...")

def post_api(url, data, retries=3):
    for attempt in range(retries):
        try:
            headers = dict(HEADERS)
            headers['X-Client-Token'] = TOKEN
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode('utf-8', errors='ignore'))
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(0.5 * (attempt + 1))

# 1. Parse clubs from clubs_17.html
with open('clubs_17.html', 'r', encoding='utf-8', errors='ignore') as f:
    html_17 = f.read()

clubs = {} # id_club -> dict
for m in re.finditer(r"<a href='club\.php\?id=(\d+)&id_superficie=(\d+)'>.*?alt='([^']*)'", html_17, re.DOTALL):
    cid = int(m.group(1))
    cname = m.group(3).strip()
    clubs[cid] = {
        'id_club': cid,
        'nombre_listado': cname,
        'en_listado_oficial': True,
        'temporadas': set(),
        'superficies': set(),
        'categorias': set(),
        'competiciones': set(),
        'equipos_partidos': set()
    }

print(f"Clubs in listado_clubs.php: {len(clubs)}")

# 2. Fetch competition trees for seasons 2627 and 2526, surfaces 1 (Pista) and 2 (Playa)
configs = [
    ('2026/2027', 2627, 1, 'Pista'),
    ('2026/2027', 2627, 2, 'Playa'),
    ('2025/2026', 2526, 1, 'Pista'),
    ('2025/2026', 2526, 2, 'Playa'),
]

torneos_to_fetch = [] # (temp_str, sup_str, cat_name, comp_name, torneo_id)
for temp_str, temp_id, sup_id, sup_str in configs:
    try:
        arbol = post_api('https://resultadosbalonmano.isquad.es/json/isquad_proxy.php', {
            'recurso': 'arbol',
            'ambitos': '3,32,33,34,75',
            'seleccion': 0,
            'id_superficie': sup_id,
            'id_temporada': temp_id
        })
        if isinstance(arbol, list):
            for cat in arbol:
                cat_name = (cat.get('nombre') or '').strip()
                for comp in cat.get('competiciones', []):
                    comp_name = (comp.get('nombre') or '').strip()
                    comp_cat = (comp.get('nombre_categoria') or cat_name).strip()
                    for tor in comp.get('torneos', []):
                        tid = tor.get('id')
                        if tid:
                            torneos_to_fetch.append((temp_str, sup_str, comp_cat or cat_name, comp_name, tid))
    except Exception as e:
        print(f"Error fetching arbol {temp_str} {sup_str}: {e}")

print(f"Total torneos to fetch: {len(torneos_to_fetch)}")

def fetch_torneo(item):
    temp_str, sup_str, cat_name, comp_name, tid = item
    try:
        d = post_api('https://resultadosbalonmano.isquad.es/maqueta/json/beta.php', {
            'tipo': 'torneo',
            'id': tid
        })
        found = []
        if isinstance(d, dict) and 'partidos' in d:
            for m in d.get('partidos', []):
                m_cat = (m.get('categoria') or cat_name).strip()
                m_comp = (m.get('competicion') or comp_name).strip()
                for side in ('l', 'v'):
                    t = m.get(side)
                    if isinstance(t, dict):
                        cid = t.get('club')
                        tname = (t.get('n') or '').strip()
                        if cid:
                            found.append((int(cid), tname, temp_str, sup_str, m_cat, m_comp))
        return found
    except Exception as e:
        return []

t0 = time.time()
done_count = 0
with ThreadPoolExecutor(max_workers=20) as ex:
    futures = [ex.submit(fetch_torneo, item) for item in torneos_to_fetch]
    for fut in as_completed(futures):
        done_count += 1
        if done_count % 100 == 0 or done_count == len(torneos_to_fetch):
            print(f"Fetched {done_count}/{len(torneos_to_fetch)} torneos ({time.time()-t0:.1f}s)...")
        for cid, tname, temp_str, sup_str, m_cat, m_comp in fut.result():
            if cid not in clubs:
                clubs[cid] = {
                    'id_club': cid,
                    'nombre_listado': tname,
                    'en_listado_oficial': False,
                    'temporadas': set(),
                    'superficies': set(),
                    'categorias': set(),
                    'competiciones': set(),
                    'equipos_partidos': set()
                }
            clubs[cid]['temporadas'].add(temp_str)
            clubs[cid]['superficies'].add(sup_str)
            if m_cat:
                clubs[cid]['categorias'].add(m_cat)
            if m_comp:
                clubs[cid]['competiciones'].add(m_comp)
            if tname:
                clubs[cid]['equipos_partidos'].add(tname)

print(f"Total unique clubs discovered after scanning all tournaments: {len(clubs)}")

# 3. Now fetch detailed club info for all discovered clubs
def fetch_club_detail(cid):
    try:
        d = post_api('https://resultadosbalonmano.isquad.es/maqueta/json/beta.php', {
            'tipo': 'club',
            'club': cid
        })
        return cid, d
    except Exception as e:
        return cid, None

club_ids = sorted(clubs.keys())
t1 = time.time()
done_clubs = 0
with ThreadPoolExecutor(max_workers=15) as ex:
    futures = [ex.submit(fetch_club_detail, cid) for cid in club_ids]
    for fut in as_completed(futures):
        done_clubs += 1
        if done_clubs % 50 == 0 or done_clubs == len(club_ids):
            print(f"Fetched {done_clubs}/{len(club_ids)} club profiles ({time.time()-t1:.1f}s)...")
        cid, d = fut.result()
        c = clubs[cid]
        if isinstance(d, dict) and d:
            c['nombre_oficial'] = (d.get('n') or c['nombre_listado'] or '').strip()
            c['escudo'] = f"https://balonmano.isquad.es/images/afiliacion_clubs/{cid}/{d.get('e')}" if d.get('e') else ''
            c['direccion'] = (d.get('direccion') or '').strip()
            c['provincia_bd'] = (d.get('provincia') or '').strip()
            c['telefono'] = (d.get('telefono') or '').strip()
            c['email'] = (d.get('email') or '').strip()
            c['web'] = (d.get('web') or '').strip()
            c['twitter'] = (d.get('twitter') or '').strip()
            c['presidente'] = (d.get('presidente') or '').strip()
            eqs = d.get('equipos') or []
            c['num_equipos_ficha'] = len(eqs)
            for eq in eqs:
                if eq.get('cat'):
                    c['categorias'].add(eq.get('cat').strip())
                if eq.get('n'):
                    c['equipos_partidos'].add(eq.get('n').strip())
            for p in d.get('partidos') or []:
                if p.get('categoria'):
                    c['categorias'].add(p.get('categoria').strip())
                if p.get('competicion'):
                    c['competiciones'].add(p.get('competicion').strip())
                if p.get('superficie') == 2 or p.get('playa') == 1:
                    c['superficies'].add('Playa')
                elif p.get('superficie') == 1:
                    c['superficies'].add('Pista')
        else:
            c['nombre_oficial'] = c['nombre_listado']
            c['escudo'] = ''
            c['direccion'] = ''
            c['provincia_bd'] = ''
            c['telefono'] = ''
            c['email'] = ''
            c['web'] = ''
            c['twitter'] = ''
            c['presidente'] = ''
            c['num_equipos_ficha'] = 0

# Convert sets to sorted lists/strings and save JSON + CSV
output_list = []
for cid in sorted(clubs.keys(), key=lambda x: (clubs[x].get('nombre_oficial') or '').upper()):
    c = clubs[cid]
    nombre = c.get('nombre_oficial') or c.get('nombre_listado') or f"Club {cid}"
    yt_query = urllib.parse.quote_plus(f"{nombre} handbol balonmano")
    item = {
        'id_club': cid,
        'nombre_club': nombre,
        'en_listado_principal_fch': 'Sí' if c['en_listado_oficial'] else 'No',
        'temporadas_activas': ', '.join(sorted(c['temporadas'], reverse=True)),
        'modalidades': ', '.join(sorted(c['superficies'])),
        'num_categorias': len(c['categorias']),
        'categorias': ', '.join(sorted(c['categorias'])),
        'num_competiciones': len(c['competiciones']),
        'competiciones': ' | '.join(sorted(c['competiciones'])),
        'num_equipos_distintos': max(c.get('num_equipos_ficha', 0), len(c['equipos_partidos'])),
        'equipos': ' | '.join(sorted(c['equipos_partidos'])),
        'web_oficial': c.get('web', ''),
        'email': c.get('email', ''),
        'telefono': c.get('telefono', ''),
        'twitter': c.get('twitter', ''),
        'direccion': c.get('direccion', ''),
        'presidente': c.get('presidente', ''),
        'url_ficha_isquad': f"https://resultadosbalonmano.isquad.es/maqueta/#v=ver&p=club&club={cid}&t=17&s=1",
        'url_busqueda_youtube': f"https://www.youtube.com/results?search_query={yt_query}&sp=EgIQAg%253D%253D",
        'canal_youtube': '',
        'suscriptores_yt': '',
        'videos_yt': '',
        'visualizaciones_yt': ''
    }
    output_list.append(item)

with open('clubs_fch_completo.json', 'w', encoding='utf-8') as f:
    json.dump(output_list, f, ensure_ascii=False, indent=2)

if output_list:
    fieldnames = list(output_list[0].keys())
    with open('clubs_fch_completo.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(output_list)
    with open('clubs_fch_completo_comma.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=',')
        writer.writeheader()
        writer.writerows(output_list)

print(f"Saved {len(output_list)} clubs to clubs_fch_completo.json and clubs_fch_completo.csv")
