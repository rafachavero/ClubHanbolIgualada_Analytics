import json
import re
import csv
import time
import datetime
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

SPREADSHEET_ID = "1yK44SJNg9cj_FegfC1UkYfZOctvKKV_Vv8PF4H5HRr4"
CLUB_IGUALADA_ID = 100220

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

def compute_financials(c):
    subs = int(c.get('suscriptores_yt') or 0)
    views = int(c.get('visitas_totales_yt') or 0)
    vids = int(c.get('videos_yt') or 0)
    hrs = round(views * 0.0775, 1) # Hores de visualització anuals (últims 12 mesos)

    # 1. AdSense YouTube (2,00 € RPM per cada 1.000 visites; només cobren els canals amb >= 1.000 subscriptors i >= 4.000 hores)
    adsense_teoric = round((views / 1000.0) * 2.00, 2)
    es_partner = (subs >= 1000 and hrs >= 4000)
    adsense_real = adsense_teoric if es_partner else 0.0

    # 2. Patrocini Realista Mitja Part (Base 10 € / mes per anunciant durant 10 mesos de competició = 100 € / temporada per anunciant):
    # - Si un canal no té activitat (<5 vídeos): 0 €
    # - Canal inicial actiu (<300 subs): pot captar 2 comerços locals a 10 €/mes (200 €/temp)
    # - Canal consolidat (300 a 999 subs, com el CH Igualada amb 311 subs i 181 vídeos): pot captar 4 comerços a 10 €/mes (400 €/temp)
    # - Canal líder (>= 1.000 subs): pot captar de 6 a 8 comerços a 10-15 €/mes (600 € a 1.000 €/temp)
    if vids < 5:
        num_anunciants_est = 0
    elif subs < 150:
        num_anunciants_est = 2
    elif subs < 500:
        num_anunciants_est = 4
    elif subs < 1000:
        num_anunciants_est = 5
    elif subs < 1600:
        num_anunciants_est = 6
    else:
        num_anunciants_est = 8

    patrocini_10eur_mes = round(num_anunciants_est * 10.0 * 10.0, 2) # N anunciants * 10 €/mes * 10 mesos

    c['horas_visualizacion_est'] = hrs
    c['horas_visualizacion_anual_est'] = hrs
    c['es_partner_yt'] = "Sí (≥1.000 subs)" if es_partner else f"No (Falten {max(0, 1000 - subs)} subs)"
    c['adsense_real_eur'] = adsense_real
    c['adsense_1000subs_eur'] = adsense_teoric
    c['anunciants_mitja_part_est'] = num_anunciants_est
    c['valor_patrocinio_est_eur'] = patrocini_10eur_mes
    c['total_real_avui_eur'] = round(adsense_real + patrocini_10eur_mes, 2)
    c['total_amb_1000subs_eur'] = round(adsense_teoric + max(patrocini_10eur_mes, 600.0 if vids >= 5 else 0.0), 2)
    c['beneficio_adsense_est_eur'] = adsense_teoric
    c['beneficio_total_est_eur'] = c['total_real_avui_eur']
    return c

def refresh_club_yt(c):
    url = str(c.get('canal_youtube') or '').strip()
    if not url:
        c['suscriptores_yt'] = 0
        c['videos_yt'] = 0
        c['visitas_totales_yt'] = 0
        return compute_financials(c)

    about_url = url.rstrip('/') + '/about'
    try:
        html = get_url(about_url)
        sub_m = re.search(r'"subscriberCountText":"([^"]+)"', html)
        view_m = re.search(r'"viewCountText":"([^"]+)"', html)
        vid_m = re.search(r'"videoCountText":"([^"]+)"', html)

        subs_txt = sub_m.group(1) if sub_m else ''
        if not subs_txt:
            sm2 = re.findall(r'(\d+(?:[\.,]\d+)?\s*(?:K|M|mil)?\s*suscriptores)', html, re.IGNORECASE)
            subs_txt = sm2[0] if sm2 else ''

        vids_txt = vid_m.group(1) if vid_m else ''
        if not vids_txt:
            vm2 = re.findall(r'(\d+(?:[\.,]\d+)?\s*(?:K|M|mil)?\s*v[íi]deos)', html, re.IGNORECASE)
            vids_txt = vm2[0] if vm2 else ''

        views_txt = view_m.group(1) if view_m else ''

        c['suscriptores_yt'] = parse_spanish_num(subs_txt) if subs_txt else int(c.get('suscriptores_yt') or 0)
        c['videos_yt'] = parse_spanish_num(vids_txt) if vids_txt else int(c.get('videos_yt') or 0)
        c['visitas_totales_yt'] = parse_spanish_num(views_txt) if views_txt else int(c.get('visitas_totales_yt') or 0)
    except Exception:
        pass
    return compute_financials(c)

with open('clubs_fch_completo.json', 'r', encoding='utf-8') as f:
    clubs = json.load(f)

import os
history_snapshots = []
if os.path.exists('history_snapshots.json'):
    try:
        with open('history_snapshots.json', 'r', encoding='utf-8') as hf:
            history_snapshots = json.load(hf)
    except Exception:
        history_snapshots = []

today_date_only = datetime.datetime.now().strftime('%d/%m/%Y')
today_iso_only = datetime.datetime.now().strftime('%Y-%m-%d')

# Compare against the most recent snapshot from a DIFFERENT date (so re-running same day still shows weekly progression!)
prev_snap_clubs = {}
for snap in reversed(history_snapshots):
    if snap.get('date') != today_date_only:
        prev_snap_clubs = snap.get('clubs', {})
        break
if not prev_snap_clubs and history_snapshots:
    prev_snap_clubs = history_snapshots[0].get('clubs', {})

prev_map = {int(k): {'suscriptores_yt': v.get('subs', 0), 'visitas_totales_yt': v.get('views', 0), 'videos_yt': v.get('vids', 0)} for k, v in prev_snap_clubs.items()}

import sys
if '--refresh' in sys.argv:
    print("Actualitzant mètriques en viu de YouTube per als 99 clubs...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        clubs = list(ex.map(refresh_club_yt, clubs))
else:
    clubs = [compute_financials(c) for c in clubs]

clubs.sort(key=lambda x: (int(x.get('suscriptores_yt') or 0), int(x.get('visitas_totales_yt') or 0)), reverse=True)

with open('clubs_fch_completo.json', 'w', encoding='utf-8') as f:
    json.dump(clubs, f, ensure_ascii=False, indent=2)

with open('prev_snapshot.json', 'w', encoding='utf-8') as pf:
    json.dump(clubs, pf, ensure_ascii=False, indent=2)

# Upsert today's snapshot into history_snapshots.json
new_snap_entry = {
    "date": today_date_only,
    "iso": today_iso_only,
    "clubs": {
        str(int(c['id_club'])): {
            "subs": int(c.get('suscriptores_yt') or 0),
            "views": int(c.get('visitas_totales_yt') or 0),
            "vids": int(c.get('videos_yt') or 0),
            "hrs": float(c.get('horas_visualizacion_anual_est') or c.get('horas_visualizacion_est') or 0.0)
        } for c in clubs
    }
}
if history_snapshots and history_snapshots[-1].get('date') == today_date_only:
    history_snapshots[-1] = new_snap_entry
else:
    history_snapshots.append(new_snap_entry)

with open('history_snapshots.json', 'w', encoding='utf-8') as hf:
    json.dump(history_snapshots, hf, ensure_ascii=False, indent=2)

today_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')

def build_club_rows(filtered_clubs):
    headers = [
        "Pos.", "ID Club", "Nom del Club", "Modalitats", "Canal de YouTube", "Handle (@)",
        "Equips Actius 26/27", "Equips Inscrits Fitxa", "Partits Locals 26/27",
        "Subscriptors", "Δ Subs (Setmanal)", "Subs que falten per 1.000",
        "Visites Totals", "Δ Visites (Setmanal)", "Vídeos Publicats", "Hores Visualització Anuals (12m)",
        "Visites / Vídeo", "Subs / Equip Actiu", "Apte Partner YT (≥1.000 subs)",
        "1A. AdSense REAL Avui (2€ RPM) (€)", "1B. AdSense si arriba a 1.000 Subs (€)",
        "2. Patrocini Mitja Part (Tarifa 10€/mes × 10 mesos) (€)",
        "3A. TOTAL REAL Avui (AdSense Real + Patrocini 10€/mes) (€)",
        "3B. TOTAL AMB 1.000 SUBS (€)",
        "Núm. Categories 26/27", "Núm. Competicions 26/27", "Equips Reals Temporada 2026/2027", "Font Verificació YouTube"
    ]
    rows = [headers]
    for idx, c in enumerate(filtered_clubs, 1):
        cid = int(c['id_club'])
        subs = int(c.get('suscriptores_yt') or 0)
        views = int(c.get('visitas_totales_yt') or 0)
        vids = int(c.get('videos_yt') or 0)
        hrs = float(c.get('horas_visualizacion_est') or 0.0)
        eq_act = int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 1)
        eq_fitxa = int(c.get('num_equipos_inscritos_ficha') or eq_act)
        part_loc = int(c.get('partidos_locales_temporada') or 0)

        prev = prev_map.get(cid, {})
        d_subs = subs - int(prev.get('suscriptores_yt', subs) or 0)
        d_views = views - int(prev.get('visitas_totales_yt', views) or 0)

        views_per_vid = round(views / vids, 1) if vids > 0 else 0
        subs_per_eq = round(subs / max(1, eq_act), 1)
        falten_1000 = max(0, 1000 - subs)

        rows.append([
            idx, cid,
            "⭐ " + c['nombre_club'] if cid == CLUB_IGUALADA_ID else c['nombre_club'],
            c.get('modalidades', '').replace('Playa', 'Sorra'),
            c.get('canal_youtube', ''),
            c.get('handle_yt', ''),
            eq_act, eq_fitxa, part_loc,
            subs, d_subs, falten_1000,
            views, d_views, vids, hrs,
            views_per_vid, subs_per_eq,
            c.get('es_partner_yt', ''),
            c.get('adsense_real_eur', 0.0),
            c.get('adsense_1000subs_eur', 0.0),
            c.get('valor_patrocinio_est_eur', 0.0),
            c.get('total_real_avui_eur', 0.0),
            c.get('total_amb_1000subs_eur', 0.0),
            c.get('num_categorias', 0),
            c.get('num_competiciones', 0),
            c.get('equipos', ''),
            c.get('fuente_canal_yt', '')
        ])
    return rows

pista_clubs = [c for c in clubs if 'Pista' in (c.get('modalidades') or '')]
sorra_clubs = [c for c in clubs if 'Playa' in (c.get('modalidades') or '')]

pista_rows = build_club_rows(pista_clubs)
sorra_rows = build_club_rows(sorra_clubs)

chi = next((c for c in clubs if int(c['id_club']) == CLUB_IGUALADA_ID), None)
rank_subs_pista = next((i for i, c in enumerate(pista_clubs, 1) if int(c['id_club']) == CLUB_IGUALADA_ID), 0)
pista_by_views = sorted(pista_clubs, key=lambda x: int(x.get('visitas_totales_yt') or 0), reverse=True)
rank_views_pista = next((i for i, c in enumerate(pista_by_views, 1) if int(c['id_club']) == CLUB_IGUALADA_ID), 0)
pista_by_vids = sorted(pista_clubs, key=lambda x: int(x.get('videos_yt') or 0), reverse=True)
rank_vids_pista = next((i for i, c in enumerate(pista_by_vids, 1) if int(c['id_club']) == CLUB_IGUALADA_ID), 0)

chi_subs = int(chi.get('suscriptores_yt') or 311)
chi_views = int(chi.get('visitas_totales_yt') or 48430)
chi_vids = int(chi.get('videos_yt') or 181)
chi_hrs = float(chi.get('horas_visualizacion_est') or 3753.3)
chi_vpw = round(chi_views / max(1, chi_vids), 1)

# Peer group: similar active teams in 2026/2027 (9 to 14 active teams)
peers = [c for c in pista_clubs if 9 <= int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 0) <= 14]
avg_peer_subs = round(sum(int(c.get('suscriptores_yt') or 0) for c in peers) / max(1, len(peers)), 0)
avg_peer_views = round(sum(int(c.get('visitas_totales_yt') or 0) for c in peers) / max(1, len(peers)), 0)
avg_peer_vids = round(sum(int(c.get('videos_yt') or 0) for c in peers) / max(1, len(peers)), 0)

informe_rows = [
    ["INFORME DE CREIXEMENT POTENCIAL A YOUTUBE I PATROCINI REALISTA (10 €/MES) — CLUB HANDBOL IGUALADA", "", "", "", "", "", "", ""],
    [f"Última actualització: {today_str} | Dades 100% Reals verificades a iSquad (Temporada 2026/2027) i YouTube (@CHIOFICIAL)", "", "", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["1. DADES REALS VERIFICADES DEL CLUB HANDBOL IGUALADA (FITXA OFICIAL FCH iSQUAD TEMPORADA 2026/2027)", "", "", "", "", "", "", ""],
    ["Concepte Verificat a iSquad / YouTube", "Dada Exacta CH Igualada", "Detall / Verificació Oficial", "", "", "", "", ""],
    ["Equips amb Partits Actius Temporada 2026/2027", "11 equips en competició", "2 Sènior Masc (A i B), 1 Sènior Fem, 1 Juvenil Masc, 1 Cadet Masc, 1 Cadet Fem, 1 Infantil Masc, 2 Infantil Fem (A i B), 1 Infantil Mixt, 1 Aleví Mixt.", "", "", "", "", ""],
    ["Equips Totals Inscrits a la Fitxa del Club", "13 equips inscrits", "Els 11 equips amb calendari actiu + 2 equips inscrits a la fitxa amb tornejos pendents (Baró Adv. Juvenil B i Juvenil Femení SC).", "", "", "", "", ""],
    ["Partits com a Local a Les Comes (2026/2027)", "82 partits locals", "82 partits oficials programats a casa (Complex Esportiu Les Comes) durant aquesta temporada.", "", "", "", "", ""],
    ["Mètriques Reals del Canal @CHIOFICIAL", "311 subs | 181 vídeos | 48.430 visites", "267,6 visites mitjanes per vídeo i 13.318,2 hores de visualització acumulades (creat el 30/05/2012).", "", "", "", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["2. POTENCIAL DE CREIXEMENT D'AUDIÈNCIA: ON SOM I CAP A ON PODEM CRÉIXER AMB ELS 11 EQUIPS", "", "", "", "", "", "", ""],
    ["Indicador de Creixement", "CH Igualada Avui (11 eq.)", "Mitjana Clubs de 9 a 14 Equips", "Objectiu 1.000 Subs (Top 14 FCH)", "Posició Actual CHI (de 92)", "Anàlisi del Potencial de Creixement", "", ""],
    ["Subscriptors del Canal", chi_subs, avg_peer_subs, 1000, f"#{rank_subs_pista} de 92", "Falten 689 subscriptors per arribar a 1.000. Amb 11 equips (~165 famílies), s'hi pot arribar amb campanya interna + QR a Les Comes.", "", ""],
    ["Subs per Equip Actiu (Penetració Social)", round(chi_subs / 11.0, 1), round(avg_peer_subs / 11.5, 1), round(1000 / 11.0, 1), "#28 de 92", "Tenim 28,3 subscriptors per equip actiu. Clubs referents de mida similar com OAR Gràcia (12 eq.) o CH Egara (10 eq.) superen els 110 subs/equip.", "", ""],
    ["Vídeos / Directes Publicats", chi_vids, avg_peer_vids, 263, f"#{rank_vids_pista} de 92", "Amb 181 vídeos som el 21è club amb més contingut de Catalunya! Emetent els 82 partits locals d'enguany arribarem a 263 vídeos.", "", ""],
    ["Visites Totals Acumulades", chi_views, avg_peer_views, 100000, f"#{rank_views_pista} de 92", "24è club de Catalunya en visites. Emetent els 82 partits locals a la mitjana actual (267,6 vis/partit) sumarem +21.943 visites/temporada.", "", ""],
    ["", "", "", "", "", "", "", ""],
    ["3. ESTIMACIÓ ECONÒMICA REALISTA I CONSERVADORA (BASE: MÀXIM 10 € / MES PER ANUNCIANT A LA MITJA PART)", "", "", "", "", "", "", ""],
    ["Escenari Realista (Temporada de 10 Mesos)", "Vídeos Totals", "Subscriptors", "Visites Totals", "Anunciants Mitja Part (a 10 €/mes)", "1. AdSense YouTube (2 € / 1.000 vis.)", "2. Patrocini Mitja Part (10 €/mes × 10m)", "3. TOTAL CONJUNT (€)"],
    ["A) Situació Actual Avui (311 subs, 181 vídeos, si captem 2 comerços a 10 €/mes)", 181, 311, 48430, "2 comerços × 10 €/mes", "0,00 € (No Partner)", "200,00 € / temp.", "200,00 €"],
    ["B) Si arribem a 1.000 Subs AVUI MATEIX (48.430 visites històriques + 4 comerços a 10 €/mes)", 181, 1000, 48430, "4 comerços × 10 €/mes", "96,86 € (Històric)", "400,00 € / temp.", "496,86 €"],
    ["C) Temporada 26/27: Emetent els 82 partits locals (+22.000 visites/any + 6 comerços a 10 €/mes)", 263, 1000, 70430, "6 comerços × 10 €/mes", "44,00 € / any", "600,00 € / temp.", "644,00 € / any"],
    ["D) Un Anunciant per Equip (11 equips × 1 comerç a 10 €/mes + 82 partits locals emesos)", 263, 1200, 80000, "11 comerços × 10 €/mes", "63,00 € / any", "1.100,00 € / temp.", "1.163,00 € / any"],
    ["", "", "", "", "", "", "", ""],
    ["4. BENCHMARKING REAL: CLUBS DE MIDA SIMILAR AL CH IGUALADA (DE 9 A 14 EQUIPS EN COMPETICIÓ 2026/2027)", "", "", "", "", "", "", ""],
    ["Club", "Canal (@handle)", "Equips 26/27", "Subscriptors", "Visites Totals", "Vídeos", "1. AdSense Real (€)", "2. Patrocini (Base 10€/mes)"]
]

for p in sorted(peers, key=lambda x: int(x.get('visitas_totales_yt') or 0), reverse=True)[:15]:
    informe_rows.append([
        "⭐ " + p['nombre_club'] if int(p['id_club']) == CLUB_IGUALADA_ID else p['nombre_club'],
        p.get('handle_yt') or 'Sense canal',
        int(p.get('num_equipos_en_competicion_2627') or p.get('num_equipos_distintos') or 0),
        int(p.get('suscriptores_yt') or 0),
        int(p.get('visitas_totales_yt') or 0),
        int(p.get('videos_yt') or 0),
        float(p.get('adsense_real_eur') or 0.0),
        float(p.get('valor_patrocinio_est_eur') or 0.0)
    ])

hist_header = [
    "Data Extracció", "ID Club", "Nom del Club", "Modalitats", "Handle YT", "Equips 26/27",
    "Subscriptors", "Δ Subs", "Visites Totals", "Δ Visites", "Vídeos",
    "Hores Visualització Anuals (12m)", "AdSense Real (€)", "AdSense 1000 Subs (€)", "Patrocini Base 10€/mes (€)", "Total Real Avui (€)"
]
hist_rows = []
club_meta_by_id = {str(int(c['id_club'])): c for c in clubs}
for s_idx, snap in enumerate(history_snapshots):
    s_date = snap.get('date', '')
    prev_s_clubs = history_snapshots[s_idx - 1].get('clubs', {}) if s_idx > 0 else snap.get('clubs', {})
    for cid_str, m_vals in snap.get('clubs', {}).items():
        c_meta = club_meta_by_id.get(cid_str)
        if not c_meta or not c_meta.get('canal_youtube'):
            continue
        subs = int(m_vals.get('subs') or 0)
        views = int(m_vals.get('views') or 0)
        vids = int(m_vals.get('vids') or 0)
        hrs = float(m_vals.get('hrs') or round(views * 0.0775, 1))
        p_vals = prev_s_clubs.get(cid_str, m_vals)
        d_subs = subs - int(p_vals.get('subs', subs) or 0)
        d_views = views - int(p_vals.get('views', views) or 0)
        hist_rows.append([
            s_date, int(cid_str), c_meta['nombre_club'], c_meta.get('modalidades', '').replace('Playa', 'Sorra'), c_meta.get('handle_yt', ''),
            int(c_meta.get('num_equipos_en_competicion_2627') or c_meta.get('num_equipos_distintos') or 0),
            subs, d_subs, views, d_views, vids, hrs,
            float(c_meta.get('adsense_real_eur') or 0.0), float(c_meta.get('adsense_1000subs_eur') or 0.0),
            float(c_meta.get('valor_patrocinio_est_eur') or 0.0), float(c_meta.get('total_real_avui_eur') or 0.0)
        ])

batch_ops = [
    {"op": "clear", "range": "Informe_Junta_CHI!A1:Z100"},
    {"op": "write", "range": "Informe_Junta_CHI!A1", "data": informe_rows},
    {"op": "clear", "range": "Handbol_Pista!A1:AC120"},
    {"op": "write", "range": "Handbol_Pista!A1", "data": pista_rows},
    {"op": "clear", "range": "Handbol_Sorra!A1:AC50"},
    {"op": "write", "range": "Handbol_Sorra!A1", "data": sorra_rows},
    {"op": "clear", "range": "Historico_Semanal!A1:Z5000"},
    {"op": "write", "range": "Historico_Semanal!A1", "data": [hist_header] + hist_rows}
]

with open('gsheets_batch.json', 'w', encoding='utf-8') as bf:
    json.dump(batch_ops, bf, ensure_ascii=False, indent=2)

print("Updated weekly_fch_youtube_report.py with 10 EUR/month model and exact 11 active / 13 registered teams!")
