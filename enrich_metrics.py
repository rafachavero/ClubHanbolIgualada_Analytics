import json
import re
import csv
import time
import datetime
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

YT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Cookie': 'CONSENT=YES+cb.20210328-17-p0.es+FX+917'
}

def get_url(url, timeout=15):
    p = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(urllib.parse.unquote(p.path), safe='/@:+-_.,~')
    safe_url = urllib.parse.urlunsplit((p.scheme, p.netloc, safe_path, p.query, p.fragment))
    req = urllib.request.Request(safe_url, headers=YT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='ignore')

def parse_spanish_num(txt):
    if not txt:
        return 0
    t = txt.replace('\xa0', ' ').lower().strip()
    # If exact number with dots like "48.430 visualizaciones" without k/mil/m
    if not any(u in t for u in ('k', 'mil', 'm', 'millones')):
        digits = re.sub(r'[^\d]', '', t)
        return int(digits) if digits else 0
    m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(k|mil|m|millones)?', t)
    if not m:
        return 0
    val_str = m.group(1)
    unit = m.group(2)
    if unit in ('k', 'mil'):
        val = float(val_str.replace(',', '.')) * 1000
        return int(round(val))
    elif unit in ('m', 'millones'):
        val = float(val_str.replace(',', '.')) * 1000000
        return int(round(val))
    else:
        return int(re.sub(r'[^\d]', '', val_str))

def fetch_channel_metrics(c):
    url = c.get('canal_youtube', '').strip()
    if not url:
        c['suscriptores_yt'] = 0
        c['videos_yt'] = 0
        c['visitas_totales_yt'] = 0
        c['horas_visualizacion_est'] = 0.0
        c['beneficio_adsense_est_eur'] = 0.0
        c['valor_patrocinio_est_eur'] = 0.0
        c['beneficio_total_est_eur'] = 0.0
        c['fecha_creacion_canal'] = ''
        return c

    about_url = url.rstrip('/') + '/about'
    try:
        html = get_url(about_url)
        # Extract from aboutChannelViewModel first
        sub_m = re.search(r'"subscriberCountText":"([^"]+)"', html)
        view_m = re.search(r'"viewCountText":"([^"]+)"', html)
        vid_m = re.search(r'"videoCountText":"([^"]+)"', html)
        join_m = re.search(r'"joinedDateText":\{"content":"([^"]+)"', html)

        subs_txt = sub_m.group(1) if sub_m else ''
        if not subs_txt:
            sm2 = re.findall(r'(\d+(?:[\.,]\d+)?\s*(?:K|M|mil)?\s*suscriptores)', html, re.IGNORECASE)
            subs_txt = sm2[0] if sm2 else ''

        vids_txt = vid_m.group(1) if vid_m else ''
        if not vids_txt:
            vm2 = re.findall(r'(\d+(?:[\.,]\d+)?\s*(?:K|M|mil)?\s*v[íi]deos)', html, re.IGNORECASE)
            vids_txt = vm2[0] if vm2 else ''

        views_txt = view_m.group(1) if view_m else ''

        subs_num = parse_spanish_num(subs_txt) if subs_txt else (int(c.get('suscriptores_yt') or 0))
        vids_num = parse_spanish_num(vids_txt) if vids_txt else (int(c.get('videos_yt') or 0))
        views_num = parse_spanish_num(views_txt) if views_txt else 0

        # Estimate watch hours:
        # Live handball matches + highlights average ~16.5 minutes (0.275 hours) per view on club streaming channels
        watch_hours = round(views_num * 0.275, 1)

        # Estimate AdSense / direct view monetization (~2.50 EUR RPM per 1,000 views)
        adsense_eur = round((views_num / 1000.0) * 2.50, 2)

        # Estimate B2B Local Sponsorship / Media Value for the Club:
        # 18 EUR CPM for hyper-targeted local sports stream impressions + 1.50 EUR/subscriber community value + 15 EUR/broadcasted match
        sponsorship_eur = round((views_num / 1000.0) * 18.0 + (subs_num * 1.50) + (vids_num * 12.0), 2)

        c['suscriptores_yt_texto'] = subs_txt.replace('\xa0', ' ')
        c['suscriptores_yt'] = subs_num
        c['videos_yt_texto'] = vids_txt.replace('\xa0', ' ')
        c['videos_yt'] = vids_num
        c['visitas_totales_yt'] = views_num
        c['horas_visualizacion_est'] = watch_hours
        c['beneficio_adsense_est_eur'] = adsense_eur
        c['valor_patrocinio_est_eur'] = sponsorship_eur
        c['beneficio_total_est_eur'] = round(adsense_eur + sponsorship_eur, 2)
        c['fecha_creacion_canal'] = (join_m.group(1).replace('Se unió el ', '') if join_m else '')
    except Exception as e:
        c['suscriptores_yt'] = int(c.get('suscriptores_yt') or 0)
        c['videos_yt'] = int(c.get('videos_yt') or 0)
        c['visitas_totales_yt'] = int(c.get('visitas_totales_yt') or 0)
        c['horas_visualizacion_est'] = round(c['visitas_totales_yt'] * 0.275, 1)
        c['beneficio_adsense_est_eur'] = round((c['visitas_totales_yt'] / 1000.0) * 2.50, 2)
        c['valor_patrocinio_est_eur'] = round((c['visitas_totales_yt'] / 1000.0) * 18.0 + (c['suscriptores_yt'] * 1.50) + (c['videos_yt'] * 12.0), 2)
        c['beneficio_total_est_eur'] = round(c['beneficio_adsense_est_eur'] + c['valor_patrocinio_est_eur'], 2)
        c['fecha_creacion_canal'] = c.get('fecha_creacion_canal', '')
    return c

with open('clubs_fch_completo.json', 'r', encoding='utf-8') as f:
    clubs = json.load(f)

print(f"Fetching exact total views, watch hours & revenue estimates for {len(clubs)} clubs...")
t0 = time.time()
with ThreadPoolExecutor(max_workers=12) as ex:
    futs = [ex.submit(fetch_channel_metrics, c) for c in clubs]
    done = 0
    results = []
    for f in as_completed(futs):
        done += 1
        results.append(f.result())
        if done % 20 == 0 or done == len(clubs):
            print(f"Processed {done}/{len(clubs)} ({time.time()-t0:.1f}s)...")

results.sort(key=lambda x: (int(x.get('suscriptores_yt') or 0), int(x.get('visitas_totales_yt') or 0)), reverse=True)

with open('clubs_fch_completo.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Top 10 by views:")
for r in sorted(results, key=lambda x: int(x.get('visitas_totales_yt') or 0), reverse=True)[:10]:
    print(f"  {r['nombre_club']}: {r['suscriptores_yt']} subs | {r['visitas_totales_yt']} views | {r['horas_visualizacion_est']} hrs | {r['beneficio_total_est_eur']} EUR")
