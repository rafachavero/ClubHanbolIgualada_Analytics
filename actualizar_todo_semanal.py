import subprocess
import sys
import os
import re
import json
import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
SPREADSHEET_ID = "1yK44SJNg9cj_FegfC1UkYfZOctvKKV_Vv8PF4H5HRr4"

print("1. Extraient mètriques actualitzades de YouTube per als 99 clubs FCH...")
subprocess.run([sys.executable, "weekly_fch_youtube_report.py", "--refresh"], check=True)

print("2. Sincronitzant dades i històric amb Google Sheets al Drive...")
subprocess.run(["gsheets", "mutate", "batch", SPREADSHEET_ID, "-f", "gsheets_batch.json"], shell=True, check=False)

print("3. Actualitzant la WebApp (index.html i Presentacio_Junta_CH_Igualada.html)...")
with open('clubs_fch_completo.json', 'r', encoding='utf-8') as f:
    clubs = json.load(f)

compact_clubs = []
for c in clubs:
    subs = int(c.get('suscriptores_yt') or 0)
    views = int(c.get('visitas_totales_yt') or 0)
    vids = int(c.get('videos_yt') or 0)
    hrs = float(c.get('horas_visualizacion_anual_est') or c.get('horas_visualizacion_est') or round(views * 0.0775, 1))
    eq_act = int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 1)
    eq_fitxa = int(c.get('num_equipos_inscritos_ficha') or eq_act)
    part_loc = int(c.get('partidos_locales_temporada') or 0)
    mods = (c.get('modalidades') or 'Pista').replace('Playa', 'Sorra')
    partner_ok = (subs >= 1000 and hrs >= 4000)
    ads_real = float(c.get('adsense_real_eur') or 0.0)
    ads_1000 = float(c.get('adsense_1000subs_eur') or 0.0)
    pat_10 = float(c.get('valor_patrocinio_est_eur') or 0.0)
    compact_clubs.append({
        'id': int(c['id_club']),
        'nom': c['nombre_club'],
        'mods': mods,
        'pista': 'Pista' in mods,
        'sorra': 'Sorra' in mods,
        'yt': c.get('canal_youtube') or '',
        'handle': c.get('handle_yt') or '',
        'subs': subs,
        'views': views,
        'vids': vids,
        'hrs': hrs,
        'eq': eq_act,
        'eq_fitxa': eq_fitxa,
        'part_loc': part_loc,
        'spe': round(subs / max(1, eq_act), 1),
        'vpw': round(views / max(1, vids), 1) if vids > 0 else 0.0,
        'partner': partner_ok,
        'falten': max(0, 1000 - subs),
        'falten_hrs': round(max(0.0, 4000.0 - hrs), 0),
        'ads_real': ads_real,
        'ads_1000': ads_1000,
        'pat_10': pat_10,
        'tot_real': round(ads_real + pat_10, 2),
        'tot_1000': float(c.get('total_amb_1000subs_eur') or 0.0),
    })

history_snapshots = []
if os.path.exists('history_snapshots.json'):
    with open('history_snapshots.json', 'r', encoding='utf-8') as hf:
        history_snapshots = json.load(hf)

today_str = datetime.datetime.now().strftime('%d/%m/%Y')
for fn in ("index.html", "Presentacio_Junta_CH_Igualada.html", os.path.join("junta-chi-2026", "index.html")):
    if os.path.exists(fn):
        with open(fn, "r", encoding="utf-8") as f:
            h = f.read()
        h = re.sub(r'const CLUBS = \[.*?\];', 'const CLUBS = ' + json.dumps(compact_clubs, ensure_ascii=False) + ';', h, flags=re.DOTALL)
        h = re.sub(r'const HISTORY = \[.*?\];', 'const HISTORY = ' + json.dumps(history_snapshots, ensure_ascii=False) + ';', h, flags=re.DOTALL)
        h = re.sub(r'Actualitzat: \d{2}/\d{2}/\d{4}', f'Actualitzat: {today_str}', h)
        with open(fn, "w", encoding="utf-8") as f:
            f.write(h)

print("4. Regenerant el Dossier Executiu en HTML i PDF per a la Junta Directiva...")
subprocess.run([sys.executable, "generate_pdf_report.py"], check=True)
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
if os.path.exists(chrome_path):
    pdf_out = os.path.abspath("Informe_Junta_Club_Handbol_Igualada.pdf")
    html_in = os.path.abspath("Informe_Junta_Club_Handbol_Igualada.html")
    subprocess.run([chrome_path, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_out}", html_in], check=False)

print("5. Pujant canvis a GitHub Pages (ClubHanbolIgualada_Analytics)...")
subprocess.run(["git", "add", "-A"], check=False)
subprocess.run(["git", "commit", "-m", f"Actualització setmanal automàtica ({today_str})"], check=False)
subprocess.run(["git", "push", "origin", "main"], check=False)
print("Actualització completada!")
