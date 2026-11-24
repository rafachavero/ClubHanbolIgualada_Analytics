import json
import datetime

with open('clubs_fch_completo.json', 'r', encoding='utf-8') as f:
    clubs = json.load(f)

CLUB_IGUALADA_ID = 100220
pista_clubs = sorted([c for c in clubs if 'Pista' in (c.get('modalidades') or '')], key=lambda x: (int(x.get('suscriptores_yt') or 0), int(x.get('visitas_totales_yt') or 0)), reverse=True)
sorra_clubs = sorted([c for c in clubs if 'Playa' in (c.get('modalidades') or '')], key=lambda x: (int(x.get('suscriptores_yt') or 0), int(x.get('visitas_totales_yt') or 0)), reverse=True)
pista_by_views = sorted(pista_clubs, key=lambda x: int(x.get('visitas_totales_yt') or 0), reverse=True)
pista_by_vids = sorted(pista_clubs, key=lambda x: int(x.get('videos_yt') or 0), reverse=True)

chi = next((c for c in clubs if int(c['id_club']) == CLUB_IGUALADA_ID), {})
rank_subs_pista = next((i for i, c in enumerate(pista_clubs, 1) if int(c['id_club']) == CLUB_IGUALADA_ID), 0)
rank_views_pista = next((i for i, c in enumerate(pista_by_views, 1) if int(c['id_club']) == CLUB_IGUALADA_ID), 0)
rank_vids_pista = next((i for i, c in enumerate(pista_by_vids, 1) if int(c['id_club']) == CLUB_IGUALADA_ID), 0)

chi_subs = int(chi.get('suscriptores_yt') or 311)
chi_views = int(chi.get('visitas_totales_yt') or 48430)
chi_vids = int(chi.get('videos_yt') or 181)
chi_hrs = float(chi.get('horas_visualizacion_est') or 3753.2)
chi_vpw = round(chi_views / max(1, chi_vids), 1)
chi_ads_1000 = float(chi.get('adsense_1000subs_eur') or 96.86)
chi_spon_now = float(chi.get('valor_patrocinio_est_eur') or 400.0)

peers = sorted([c for c in pista_clubs if 9 <= int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 0) <= 14], key=lambda x: int(x.get('suscriptores_yt') or 0), reverse=True)

def fmt_int(n):
    return f"{int(n):,}".replace(",", ".")

def fmt_dec(n, d=2):
    s = f"{float(n):,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

today_str = datetime.datetime.now().strftime('%d/%m/%Y')

# Top 11 by subscribers + CHI for growth bar chart
top12_subs = pista_clubs[:11] + ([chi] if chi not in pista_clubs[:11] else [pista_clubs[11]])
max_sub = max(int(c.get('suscriptores_yt') or 1) for c in top12_subs)

bars_html = ""
for idx, c in enumerate(top12_subs, 1):
    is_chi = int(c['id_club']) == CLUB_IGUALADA_ID
    s = int(c.get('suscriptores_yt') or 0)
    v = int(c.get('visitas_totales_yt') or 0)
    vids = int(c.get('videos_yt') or 0)
    eqs = int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 1)
    subs_per_eq = round(s / max(1, eqs), 1)
    pct = max(4, min(100, round((s / max_sub) * 100, 1)))
    color = "#0101FD" if is_chi else "#1B365D"
    bg_row = "background:#EEF2FF;border-left:4px solid #0101FD;padding-left:6px;" if is_chi else ""
    label = f"⭐ {c['nombre_club']} (#{rank_subs_pista})" if is_chi else f"{idx}. {c['nombre_club']}"
    bars_html += f'<div style="display:flex;align-items:center;margin-bottom:4.5px;font-size:10px;{bg_row}"><div style="width:195px;font-weight:{"800" if is_chi else "600"};color:{color};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div><div style="flex:1;background:#E9EEF5;height:12px;border-radius:3px;margin:0 8px;overflow:hidden;"><div style="width:{pct}%;background:{color};height:100%;border-radius:3px;"></div></div><div style="width:270px;text-align:right;font-weight:700;color:#0C1230;">{fmt_int(s)} subs <span style="color:#475569;font-weight:500;">({eqs} eq. → <b>{fmt_dec(subs_per_eq,1)} subs/eq</b> | {fmt_int(vids)} víd. | {fmt_int(v)} vis.)</span></div></div>'

def make_pista_rows(club_slice, start_idx):
    out = ""
    for idx, c in enumerate(club_slice, start_idx):
        is_chi = int(c['id_club']) == CLUB_IGUALADA_ID
        tr_style = 'style="background:#EEF2FF;font-weight:700;color:#0101FD;"' if is_chi else ''
        vids = int(c.get('videos_yt') or 0)
        views = int(c.get('visitas_totales_yt') or 0)
        subs = int(c.get('suscriptores_yt') or 0)
        eqs = int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 1)
        spe = round(subs / max(1, eqs), 1)
        falten = max(0, 1000 - subs)
        out += f'<tr {tr_style}><td style="text-align:center;">{idx}</td><td>{"⭐ " if is_chi else ""}{c["nombre_club"]}</td><td>{c.get("handle_yt") or "—"}</td><td style="text-align:center;">{eqs}</td><td style="text-align:right;font-weight:700;">{fmt_int(subs)}</td><td style="text-align:right;">{fmt_int(falten) if falten>0 else "Partner ✓"}</td><td style="text-align:right;">{fmt_dec(spe,1)}</td><td style="text-align:right;">{fmt_int(views)}</td><td style="text-align:right;">{fmt_int(vids)}</td><td style="text-align:right;">{fmt_dec(c.get("adsense_real_eur",0),2)} €</td><td style="text-align:right;">{fmt_dec(c.get("valor_patrocinio_est_eur",0),2)} €</td><td style="text-align:right;font-weight:700;">{fmt_dec(c.get("total_real_avui_eur",0),2)} €</td></tr>'
    return out

peers_rows_html = ""
for idx, p in enumerate(peers[:15], 1):
    is_chi = int(p['id_club']) == CLUB_IGUALADA_ID
    tr_style = 'style="background:#EEF2FF;font-weight:700;color:#0101FD;"' if is_chi else ''
    vids = int(p.get('videos_yt') or 0)
    views = int(p.get('visitas_totales_yt') or 0)
    subs = int(p.get('suscriptores_yt') or 0)
    eqs = int(p.get('num_equipos_en_competicion_2627') or p.get('num_equipos_distintos') or 1)
    spe = round(subs / max(1, eqs), 1)
    vpw = round(views / max(1, vids), 1) if vids > 0 else 0
    peers_rows_html += f'<tr {tr_style}><td style="text-align:center;">{idx}</td><td>{"⭐ " if is_chi else ""}{p["nombre_club"]}</td><td>{p.get("handle_yt") or "Sense canal"}</td><td style="text-align:center;">{eqs}</td><td style="text-align:right;font-weight:700;">{fmt_int(subs)}</td><td style="text-align:right;">{fmt_dec(spe,1)}</td><td style="text-align:right;">{fmt_int(views)}</td><td style="text-align:right;">{fmt_int(vids)}</td><td style="text-align:right;">{fmt_dec(vpw,1)}</td><td style="text-align:right;">{fmt_dec(p.get("adsense_real_eur",0),2)} €</td><td style="text-align:right;">{fmt_dec(p.get("valor_patrocinio_est_eur",0),2)} €</td><td style="text-align:right;font-weight:700;">{fmt_dec(p.get("total_real_avui_eur",0),2)} €</td></tr>'

pista_top38_html = make_pista_rows(pista_clubs[:38], 1)
pista_rest_html = make_pista_rows(pista_clubs[38:76], 39)

sorra_html = ""
for idx, c in enumerate(sorra_clubs, 1):
    vids = int(c.get('videos_yt') or 0)
    views = int(c.get('visitas_totales_yt') or 0)
    subs = int(c.get('suscriptores_yt') or 0)
    eqs = int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 1)
    tipo_sorra = "Exclusiu Sorra" if c.get('modalidades') == 'Playa' else "Pista + Sorra"
    bg_s = '#E0F2FE' if tipo_sorra=='Exclusiu Sorra' else '#F1F5F9'
    fg_s = '#0369A1' if tipo_sorra=='Exclusiu Sorra' else '#334155'
    sorra_html += f'<tr><td style="text-align:center;">{idx}</td><td>{c["nombre_club"]}</td><td style="text-align:center;"><span style="background:{bg_s};color:{fg_s};padding:2px 6px;border-radius:4px;font-size:8.5px;font-weight:700;">{tipo_sorra}</span></td><td>{c.get("handle_yt") or "Sense canal YT"}</td><td style="text-align:center;">{eqs}</td><td style="text-align:right;font-weight:700;">{fmt_int(subs)}</td><td style="text-align:right;">{fmt_int(views)}</td><td style="text-align:right;">{fmt_int(vids)}</td><td style="text-align:right;">{fmt_dec(c.get("horas_visualizacion_est",0),1)} h</td><td style="text-align:right;">{fmt_dec(c.get("adsense_real_eur",0),2)} €</td><td style="text-align:right;">{fmt_dec(c.get("valor_patrocinio_est_eur",0),2)} €</td><td style="text-align:right;font-weight:700;">{fmt_dec(c.get("total_real_avui_eur",0),2)} €</td></tr>'

with open('report_parts.json', 'w', encoding='utf-8') as f:
    json.dump({
        'today_str': today_str,
        'chi_subs': fmt_int(chi_subs),
        'rank_subs_pista': rank_subs_pista,
        'chi_views': fmt_int(chi_views),
        'rank_views_pista': rank_views_pista,
        'chi_vids': fmt_int(chi_vids),
        'rank_vids_pista': rank_vids_pista,
        'chi_hrs': fmt_dec(chi_hrs, 0),
        'chi_vpw': fmt_dec(chi_vpw, 1),
        'chi_ads_1000': fmt_dec(chi_ads_1000, 2),
        'chi_spon_now': fmt_dec(chi_spon_now, 0),
        'bars_html': bars_html,
        'peers_rows_html': peers_rows_html,
        'pista_top38_html': pista_top38_html,
        'pista_rest_html': pista_rest_html,
        'sorra_html': sorra_html
    }, f, ensure_ascii=False)
print("Saved updated report_parts.json")
