import json
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from lxml import etree

BLUE = RGBColor(0x01, 0x01, 0xFD); YELLOW = RGBColor(0xFF, 0xFF, 0x00)
NAVY = RGBColor(0x0A, 0x0A, 0x5A); GREY = RGBColor(0xCB, 0xD5, 0xE1); LIGHT = RGBColor(0xF1, 0xF5, 0xF9)
DARK = RGBColor(0x0F, 0x17, 0x2A); MID = RGBColor(0x47, 0x55, 0x69); WHITE = RGBColor(255, 255, 255)
SLATE = RGBColor(0x64, 0x74, 0x8B); AMBER = RGBColor(0xF5, 0x9E, 0x0B)

clubs = json.load(open('clubs_fch_completo.json', encoding='utf-8'))
CHI_ID = 100220
def eq(c): return int(c.get('num_equipos_en_competicion_2627') or c.get('num_equipos_distintos') or 1)
pista = [c for c in clubs if 'Pista' in (c.get('modalidades') or '') and c.get('canal_youtube')]
pista_all = [c for c in clubs if 'Pista' in (c.get('modalidades') or '')]
chi = next(c for c in clubs if int(c['id_club']) == CHI_ID)
def rank(key, lst=pista_all):
    s = sorted(lst, key=lambda c: -float(c.get(key) or 0))
    return next(i for i, c in enumerate(s, 1) if int(c['id_club']) == CHI_ID), len(lst)
r_subs, n = rank('suscriptores_yt'); r_vids, _ = rank('videos_yt'); r_views, _ = rank('visitas_totales_yt')
subs = int(chi['suscriptores_yt']); vids = int(chi['videos_yt']); views = int(chi['visitas_totales_yt'])
hrs = float(chi.get('horas_visualizacion_anual_est') or round(views * 0.0775, 1))
print('ranks', r_subs, r_vids, r_views, n, subs, vids, views, hrs)

def nm(c):
    s = c['nombre_club'].title()
    for a, b in (('Club Handbol ', 'CH '), ('Club Balonmano ', 'CB '), ('Handbol ', 'H. '), ('Club Esportiu ', 'CE ')):
        s = s.replace(a, b)
    return s[:26]
def fi(x): return f"{int(round(x)):,}".replace(',', '.')
def fd(x, d=1): return f"{x:,.{d}f}".replace(',', 'X').replace('.', ',').replace('X', '.')

prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]

def add_fade(slide):
    xml = '<p:transition xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" spd="med"><p:fade/></p:transition>'
    el = etree.fromstring(xml)
    sld = slide._element
    anchor = sld.find('{http://schemas.openxmlformats.org/presentationml/2006/main}clrMapOvr')
    if anchor is not None: anchor.addnext(el)
    else: sld.insert(2, el)

def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
    sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line: sh.line.color.rgb = line; sh.line.width = Pt(1)
    else: sh.line.fill.background()
    sh.shadow.inherit = False
    return sh

def text(s, x, y, w, h, t, size=18, bold=False, color=DARK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    lines = t if isinstance(t, list) else [t]
    for i, l in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; r = p.add_run(); r.text = l
        r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.name = 'Calibri'
        if len(lines) > 1: p.space_after = Pt(6)
    return tb

def base(title, sub=None, num=None):
    s = prs.slides.add_slide(blank)
    rect(s, 0, 0, 13.333, 7.5, GREY)
    rect(s, 0, 0, 13.333, 1.15, BLUE); rect(s, 0, 1.15, 13.333, 0.07, YELLOW)
    s.shapes.add_picture('LOGO_CHI.png', Inches(0.3), Inches(0.12), height=Inches(0.92))
    text(s, 1.45, 0.14, 11.4, 0.6, title, 28, True, YELLOW)
    if sub: text(s, 1.45, 0.65, 11.4, 0.4, sub, 14, False, WHITE)
    text(s, 0.4, 7.08, 9, 0.3, "Club Handbol Igualada · @CHIOFICIAL · Dades iSquad FCH 2026/2027 i YouTube", 10, False, MID)
    if num: text(s, 12.2, 7.08, 0.8, 0.3, str(num), 10, True, MID, PP_ALIGN.RIGHT)
    add_fade(s); return s

def card(s, x, y, w, h, label, value, note, hl=False):
    rect(s, x, y, w, h, WHITE, BLUE if hl else RGBColor(0x94, 0xA3, 0xB8), MSO_SHAPE.ROUNDED_RECTANGLE).adjustments[0] = 0.06
    text(s, x + 0.15, y + 0.1, w - 0.3, 0.35, label.upper(), 11, True, BLUE if hl else MID)
    text(s, x + 0.15, y + 0.45, w - 0.3, 0.8, value, 34, True, BLUE if hl else DARK)
    text(s, x + 0.15, y + h - 0.65, w - 0.3, 0.6, note, 12, False, MID)

def bar_chart(s, x, y, w, h, cats, vals, hl_idx, fmt='#,##0', color=SLATE, title=None):
    cd = CategoryChartData(); cd.categories = cats; cd.add_series('Valor', vals)
    gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart; ch.has_legend = False; ch.has_title = False
    ch.category_axis.reverse_order = True
    ch.category_axis.tick_labels.font.size = Pt(11); ch.category_axis.format.line.color.rgb = SLATE
    ch.value_axis.visible = False; ch.value_axis.has_major_gridlines = False
    pl = ch.plots[0]; pl.gap_width = 40; pl.has_data_labels = True
    dl = pl.data_labels; dl.number_format = fmt; dl.number_format_is_linked = False
    dl.font.size = Pt(11); dl.font.bold = True; dl.position = XL_LABEL_POSITION.OUTSIDE_END
    ser = pl.series[0]
    for i in range(len(cats)):
        pt = ser.points[i]; pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = BLUE if i in hl_idx else color
    return ch

# 1 Portada
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, BLUE); rect(s, 0, 5.2, 13.333, 0.12, YELLOW)
rect(s, 0.9, 1.1, 2.6, 2.6, WHITE, YELLOW, MSO_SHAPE.ROUNDED_RECTANGLE)
s.shapes.add_picture('LOGO_CHI.png', Inches(1.05), Inches(1.25), height=Inches(2.3))
text(s, 4.0, 1.2, 8.8, 1.6, ["Creixement del canal de YouTube", "i oportunitat de patrocini"], 40, True, YELLOW)
text(s, 4.0, 3.1, 8.8, 1.2, ["Club Handbol Igualada · @CHIOFICIAL", "Presentació a la Junta Directiva"], 22, False, WHITE)
text(s, 0.9, 5.5, 11.5, 1.2, ["Benchmarking de 99 clubs de la Federació Catalana d'Handbol", "Dades reals: iSquad (temporada 2026/2027) i YouTube"], 16, False, WHITE)
add_fade(s)

# 2 KPIs
s = base("On som avui", "Dades reals del canal i del club", 2)
card(s, 0.5, 1.6, 4.0, 2.5, "Equips actius 26/27", "11", "13 inscrits a la fitxa · 82 partits com a local a Les Comes")
card(s, 4.67, 1.6, 4.0, 2.5, "Subscriptors", fi(subs), f"#{r_subs} de {n} clubs de pista · falten {1000-subs} per als 1.000", True)
card(s, 8.83, 1.6, 4.0, 2.5, "Vídeos publicats", fi(vids), f"#{r_vids} de {n} clubs de pista")
card(s, 0.5, 4.3, 4.0, 2.5, "Visites totals", fi(views), f"#{r_views} de {n} · {fd(views/vids)} visites per vídeo")
card(s, 4.67, 4.3, 4.0, 2.5, "Hores de visualització (12 mesos)", f"{fi(hrs)} h", f"{fd(hrs/40,1)}% de les 4.000 h · falten {fi(4000-hrs)} h", True)
card(s, 8.83, 4.3, 4.0, 2.5, "Subscriptors per equip", fd(subs/11), "Objectiu per arribar a 1.000: 91 per equip", True)

# 3 Camí als requisits
s = base("El camí cap a la monetització de YouTube", "Calen 1.000 subscriptors i 4.000 hores de visualització en 12 mesos", 3)
for i, (lab, val, goal, col, note) in enumerate([
    ("Hores de visualització (últims 12 mesos)", hrs, 4000, AMBER, f"Falten només {fi(4000-hrs)} hores: s'assoleixen amb uns 6 partits en directe"),
    ("Subscriptors", subs, 1000, BLUE, f"Falten {1000-subs} subscriptors")]):
    y = 1.8 + i * 2.2
    text(s, 0.7, y, 9, 0.5, lab, 20, True, DARK)
    rect(s, 0.7, y + 0.6, 11.9, 0.5, WHITE, RGBColor(0x94, 0xA3, 0xB8), MSO_SHAPE.ROUNDED_RECTANGLE)
    rect(s, 0.7, y + 0.6, 11.9 * val / goal, 0.5, col, None, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, 0.7, y + 1.15, 11.9, 0.4, f"{fi(val)} / {fi(goal)}  ({fd(100*val/goal)}%) — {note}", 15, False, MID)
rect(s, 0.7, 6.0, 11.9, 0.9, WHITE, BLUE, MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, 0.9, 6.05, 11.5, 0.8, f"Som el #{r_vids} en vídeos i el #{r_views} en visites, però el #{r_subs} en subscriptors: la gent ja ens veu, però no se subscriu.", 17, True, BLUE, anchor=MSO_ANCHOR.MIDDLE)

# 4 Top subscriptors
s = base("Rànquing de subscriptors · Handbol pista", "Top 15 de Catalunya i posició del CH Igualada", 4)
top = sorted(pista, key=lambda c: -int(c['suscriptores_yt']))[:15]
cats = [nm(c) for c in top]; vals = [int(c['suscriptores_yt']) for c in top]; hl = []
if not any(int(c['id_club']) == CHI_ID for c in top):
    cats.append(f"CH Igualada (#{r_subs})"); vals.append(subs); hl = [len(cats) - 1]
bar_chart(s, 0.6, 1.4, 12.1, 5.6, cats, vals, hl)

# 5 Subs per equip (peers)
s = base("Subscriptors per equip actiu", "Clubs catalans amb 9 a 14 equips, com el CH Igualada (11 equips)", 5)
peers = [c for c in pista if 9 <= eq(c) <= 14]
peers = sorted(peers, key=lambda c: -int(c['suscriptores_yt']) / eq(c))[:14]
cats = [f"{nm(c)} ({eq(c)} eq.)" for c in peers]; vals = [round(int(c['suscriptores_yt']) / eq(c), 1) for c in peers]
hl = [i for i, c in enumerate(peers) if int(c['id_club']) == CHI_ID]
if not hl:
    cats.append("CH Igualada (11 eq.)"); vals.append(round(subs / 11, 1)); hl = [len(cats) - 1]
bar_chart(s, 0.6, 1.4, 12.1, 5.6, cats, vals, hl, fmt='0.0')

# 6 Vídeos i visites
s = base("Contingut i audiència", "Vídeos publicats: top 12 de pista i CH Igualada", 6)
top = sorted(pista, key=lambda c: -int(c['videos_yt']))[:12]
cats = [nm(c) for c in top]; vals = [int(c['videos_yt']) for c in top]
hl = [i for i, c in enumerate(top) if int(c['id_club']) == CHI_ID]
if not hl:
    cats.append(f"CH Igualada (#{r_vids})"); vals.append(vids); hl = [len(cats) - 1]
bar_chart(s, 0.6, 1.4, 8.2, 5.6, cats, vals, hl)
card(s, 9.1, 1.6, 3.7, 2.4, "Visites per vídeo", fd(views / vids), "Mitjana real del canal")
card(s, 9.1, 4.25, 3.7, 2.5, "Partits a emetre", "82", "Tots els partits locals de la temporada a Les Comes", True)

# 7 Ingressos (escenaris prudents)
s = base("Estimació prudent d'ingressos", "Publicitat a la mitja part a 10 €/mes per comerç · temporada de 10 mesos", 7)
cd = CategoryChartData()
cd.categories = ["A) Avui: 2 comerços", "B) 1.000 subs: 4 comerços", "C) 82 partits: 6 comerços", "D) 1 comerç per equip: 11"]
cd.add_series('Publicitat mitja part (€/temporada)', (200, 400, 600, 1100))
cd.add_series('AdSense YouTube (€/any)', (0, 96.86, 44, 63))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(0.6), Inches(1.45), Inches(8.0), Inches(5.4), cd)
ch = gf.chart; ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout = False
ch.legend.font.size = Pt(12); ch.value_axis.has_major_gridlines = False; ch.value_axis.visible = False
ch.category_axis.tick_labels.font.size = Pt(11)
pl = ch.plots[0]; pl.gap_width = 60; pl.has_data_labels = True
pl.data_labels.number_format = '#,##0"€";;'; pl.data_labels.number_format_is_linked = False
pl.data_labels.font.size = Pt(12); pl.data_labels.font.bold = True; pl.data_labels.font.color.rgb = WHITE
pl.series[0].format.fill.solid(); pl.series[0].format.fill.fore_color.rgb = BLUE
pl.series[1].format.fill.solid(); pl.series[1].format.fill.fore_color.rgb = AMBER
rect(s, 8.9, 1.6, 3.95, 5.2, WHITE, RGBColor(0x94, 0xA3, 0xB8), MSO_SHAPE.ROUNDED_RECTANGLE)
text(s, 9.1, 1.7, 3.6, 5.0, ["Com ho hem calculat",
  "• Cada comerç paga 10 €/mes = 100 € per temporada.",
  "• YouTube només paga a partir de 1.000 subscriptors i 4.000 h anuals: avui 0 €.",
  "• AdSense estimat a 2 € per cada 1.000 visites.",
  "• Són xifres prudents d'inici, no un compromís."], 14, False, DARK)

# 8 Pla d'acció
s = base("Pla d'acció", "Tres línies de treball per créixer i aprofitar l'emissió", 8)
cols = [("1. Arribar a 1.000 subscriptors", ["Demanar a les famílies dels 11 equips que se subscriguin al canal.", "Posar l'enllaç del directe a iSquad abans de cada partit.", "Cartell amb codi QR a Les Comes."]),
        ("2. Emetre els 82 partits locals", [f"Ens falten {fi(4000-hrs)} h anuals per arribar a les 4.000 h.", "Cuidar el títol i la miniatura de cada directe.", "Publicar talls curts de les millors jugades."]),
        ("3. Aprofitar la mitja part", ["Bucle de 10 minuts amb anuncis de comerços d'Igualada.", "Tarifa d'inici: 10 €/mes per comerç.", "Objectiu: un comerç per cada equip."])]
for i, (t, items) in enumerate(cols):
    x = 0.5 + i * 4.17
    rect(s, x, 1.6, 4.0, 5.2, WHITE, BLUE, MSO_SHAPE.ROUNDED_RECTANGLE)
    rect(s, x, 1.6, 4.0, 0.9, BLUE, None, MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + 0.15, 1.65, 3.7, 0.8, t, 18, True, YELLOW, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.2, 2.7, 3.6, 4.0, ["• " + it for it in items], 15, False, DARK)

# 9 Tancament
s = prs.slides.add_slide(blank)
rect(s, 0, 0, 13.333, 7.5, BLUE); rect(s, 0, 4.9, 13.333, 0.12, YELLOW)
rect(s, 5.4, 0.8, 2.5, 2.5, WHITE, YELLOW, MSO_SHAPE.ROUNDED_RECTANGLE)
s.shapes.add_picture('LOGO_CHI.png', Inches(5.55), Inches(0.95), height=Inches(2.2))
text(s, 0.5, 3.5, 12.3, 1.0, "Gràcies!", 44, True, YELLOW, PP_ALIGN.CENTER)
tb = text(s, 0.5, 5.2, 12.3, 0.6, "Dades actualitzades cada setmana a la WebApp interactiva:", 18, False, WHITE, PP_ALIGN.CENTER)
tb2 = text(s, 0.5, 5.8, 12.3, 0.6, "rafachavero.github.io/ClubHanbolIgualada_Analytics", 22, True, YELLOW, PP_ALIGN.CENTER)
tb2.text_frame.paragraphs[0].runs[0].hyperlink.address = "https://rafachavero.github.io/ClubHanbolIgualada_Analytics/"
add_fade(s)

prs.save('Presentacio_Junta_CH_Igualada.pptx'); print('saved')
