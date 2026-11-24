import json
import re
import csv
import time
import unicodedata
import urllib.request
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

ISQUAD_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://resultadosbalonmano.isquad.es/maqueta/'
}

YT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Cookie': 'CONSENT=YES+cb.20210328-17-p0.es+FX+917'
}

def norm(s):
    s = str(s or '').lower()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

STOPWORDS = {
    'club', 'handbol', 'balonmano', 'handball', 'beach', 'platja', 'sorra',
    'esportiu', 'associacio', 'agrupacio', 'fundacio', 'unio', 'esportiva',
    'centre', 'esports', 'de', 'del', 'la', 'les', 'el', 'els', 'i', 'd',
    'ch', 'bm', 'hc', 'ce', 'ue', 'ae', 'aeh', 'cf', 'pb', 'se', 'sa',
    'ampa', 'collegi', 'escola', 'comunidad', 'deportivo', 'amigos', 'amics',
    'cultura', 'activa', '2015', '2022', 'sant', 'santa'
}

def distinctive_tokens(name):
    raw = norm(name).split()
    tokens = [t for t in raw if len(t) > 2 and t not in STOPWORDS and not t.isdigit()]
    if not tokens:
        # fallback include sant/santa or numbers if everything was stripped
        tokens = [t for t in raw if len(t) > 2 and t not in {'club', 'handbol', 'balonmano', 'esportiu', 'de', 'del', 'la', 'el'}]
    return tokens

def get_token():
    req = urllib.request.Request('https://resultadosbalonmano.isquad.es/maqueta/', headers=ISQUAD_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    m = re.search(r'name="client-token"\s+content="([^"]+)"', html)
    return m.group(1) if m else ''

TOKEN = get_token()

def post_isquad(url, data):
    headers = dict(ISQUAD_HEADERS)
    headers['X-Client-Token'] = TOKEN
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    body = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode('utf-8', errors='ignore'))

def get_url(url, timeout=15):
    req = urllib.request.Request(url, headers=YT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', errors='ignore')

def parse_spanish_num(txt):
    if not txt:
        return ''
    t = txt.replace('\xa0', ' ').lower()
    m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(k|mil|m|millones)?', t)
    if not m:
        return ''
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

def extract_video_id(u):
    u = str(u or '').strip()
    m = re.search(r'(?:v=|/live/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})', u)
    return m.group(1) if m else None

def extract_channel_from_url(u):
    u = str(u or '').strip()
    m = re.search(r'youtube\.com/(channel/[A-Za-z0-9_-]+|@[A-Za-z0-9_%.-]+|c/[A-Za-z0-9_%.-]+|user/[A-Za-z0-9_%.-]+)', u)
    return 'https://www.youtube.com/' + m.group(1) if m else None

def get_channel_from_video(vid):
    try:
        html = get_url(f'https://www.youtube.com/watch?v={vid}')
        cid = re.search(r'"externalChannelId":"([^"]+)"', html)
        cname = re.search(r'"ownerChannelName":"([^"]+)"', html)
        curl = re.search(r'"ownerProfileUrl":"([^"]+)"', html)
        if cid or curl:
            url_str = curl.group(1).replace('\\/', '/').replace('http://', 'https://') if curl else f"https://www.youtube.com/channel/{cid.group(1)}"
            return {
                'channel_id': cid.group(1) if cid else '',
                'channel_name': cname.group(1) if cname else '',
                'channel_url': url_str
            }
    except Exception:
        pass
    return None

def enrich_channel_stats(ch_info):
    if not ch_info or not ch_info.get('channel_url'):
        return ch_info
    try:
        html = get_url(ch_info['channel_url'])
        cid = re.search(r'"externalId":"(UC[^"]+)"', html)
        if cid and not ch_info.get('channel_id'):
            ch_info['channel_id'] = cid.group(1)
        cname = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if cname:
            ch_info['channel_name'] = cname.group(1)
        curl = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        handle = re.search(r'"canonicalBaseUrl":"(/@[^"]+)"', html)
        if handle:
            h_dec = urllib.parse.unquote(handle.group(1).lstrip('/'))
            ch_info['handle'] = h_dec
            ch_info['channel_url'] = 'https://www.youtube.com/' + h_dec
        elif curl:
            ch_info['channel_url'] = curl.group(1)

        subs_m = re.findall(r'(\d+(?:[\.,]\d+)?\s*(?:K|M|mil)?\s*suscriptores)', html, re.IGNORECASE)
        vids_m = re.findall(r'(\d+(?:[\.,]\d+)?\s*(?:K|M|mil)?\s*v[íi]deos)', html, re.IGNORECASE)
        ch_info['subs_text'] = subs_m[0].replace('\xa0', ' ') if subs_m else '0 suscriptores'
        ch_info['subs_num'] = parse_spanish_num(ch_info['subs_text']) if subs_m else 0
        ch_info['vids_text'] = vids_m[0].replace('\xa0', ' ') if vids_m else '0 vídeos'
        ch_info['vids_num'] = parse_spanish_num(ch_info['vids_text']) if vids_m else 0
    except Exception:
        pass
    return ch_info

def find_objects(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            yield obj[key]
        for v in obj.values():
            yield from find_objects(v, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from find_objects(item, key)

TV_CHANNEL_KEYWORDS = {'votv', 'televisio', 'radio', 'tv', 'ajuntament', 'esportiu', 'canal'}

def is_tv_channel(ch_name):
    n = norm(ch_name)
    return any(w in n.split() for w in ('votv', 'televisio', 'radio'))

def search_youtube_for_club(club_name):
    dist = distinctive_tokens(club_name)
    queries = [f"{club_name} handbol"]
    short_name = ' '.join(dist)
    if short_name and short_name != norm(club_name):
        queries.append(f"Handbol {short_name}")

    # Known exact overrides for major clubs where generic search mixes with football/TV
    norm_c = norm(club_name)
    if norm_c == 'club balonmano granollers':
        return {'channel_url': 'https://www.youtube.com/@BMGoficial', 'channel_name': 'BMGoficial'}
    if norm_c == 'f c barcelona':
        return {'channel_url': 'https://www.youtube.com/@fcbhandbol', 'channel_name': 'Barça Handbol'}
    if norm_c == 'ueh calella':
        return {'channel_url': 'https://www.youtube.com/@UEHCalella', 'channel_name': 'UEHC'}

    best_candidate = None
    best_score = 0

    for q in queries:
        # 1. Channel filter search
        url_ch = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}&sp=EgIQAg%3D%3D"
        try:
            html = get_url(url_ch)
            m = re.search(r'var ytInitialData = (\{.*?\});</script>', html)
            if m:
                data = json.loads(m.group(1))
                for ch in find_objects(data, 'channelRenderer'):
                    title = ch.get('title', {}).get('simpleText') or ''
                    base_url = urllib.parse.unquote(ch.get('navigationEndpoint', {}).get('browseEndpoint', {}).get('canonicalBaseUrl') or '')
                    cid = ch.get('channelId') or ''
                    hay_title = norm(f"{title} {base_url}")

                    # Must match ALL distinctive tokens (or at least the main location token in title/handle)
                    matched = [t for t in dist if t in hay_title]
                    if not matched:
                        continue
                    # If club has multiple distinctive tokens (e.g. "sant just" -> ["just"], "sant esteve palautordera" -> ["esteve", "palautordera"]), require all or main last token
                    if len(dist) >= 2 and len(matched) < len(dist):
                        # Require at least the last distinctive word (usually the town name) AND at least 1 other word
                        if dist[-1] not in hay_title:
                            continue
                    score = len(matched) * 20
                    if any(w in hay_title for w in ('handbol', 'balonmano', 'ch', 'bm', 'hc', 'ueh', 'aeh', 'ceh', 'oarg', 'geieg', 'bmb', 'chi')):
                        score += 25
                    if score > best_score:
                        best_score = score
                        best_candidate = {
                            'channel_id': cid,
                            'channel_name': title,
                            'channel_url': f"https://www.youtube.com{base_url}" if base_url.startswith('/') else f"https://www.youtube.com/channel/{cid}"
                        }
        except Exception:
            pass

        if best_score >= 40:
            return best_candidate

        # 2. General video search -> inspect video owner channels!
        url_vid = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}"
        try:
            html = get_url(url_vid)
            m = re.search(r'var ytInitialData = (\{.*?\});</script>', html)
            if m:
                data = json.loads(m.group(1))
                for vid in find_objects(data, 'videoRenderer'):
                    runs = vid.get('ownerText', {}).get('runs') or []
                    if not runs:
                        continue
                    owner = runs[0]
                    title = owner.get('text') or ''
                    be = owner.get('navigationEndpoint', {}).get('browseEndpoint', {})
                    base_url = urllib.parse.unquote(be.get('canonicalBaseUrl') or '')
                    cid = be.get('browseId') or ''
                    hay_title = norm(f"{title} {base_url}")
                    matched = [t for t in dist if t in hay_title]
                    if not matched:
                        continue
                    if len(dist) >= 2 and dist[-1] not in hay_title:
                        continue
                    score = len(matched) * 20
                    if any(w in hay_title for w in ('handbol', 'balonmano', 'ch', 'bm', 'hc', 'ueh', 'aeh', 'ceh', 'oarg', 'geieg', 'bmb', 'chi')):
                        score += 25
                    if score > best_score:
                        best_score = score
                        best_candidate = {
                            'channel_id': cid,
                            'channel_name': title,
                            'channel_url': f"https://www.youtube.com{base_url}" if base_url.startswith('/') else f"https://www.youtube.com/channel/{cid}"
                        }
        except Exception:
            pass

        if best_score >= 40:
            return best_candidate

    return best_candidate if best_score >= 35 else None

with open('clubs_fch_completo.json', 'r', encoding='utf-8') as f:
    clubs = json.load(f)

print(f"Refining YouTube channels for {len(clubs)} clubs...")

def process_club_v2(c):
    cid = c['id_club']
    cname = c['nombre_club']
    fuente = ''
    ch_info = None
    other_stream_platform = ''

    # 1. Check all home match streams in iSquad
    stream_channels = []
    try:
        d = post_isquad('https://resultadosbalonmano.isquad.es/maqueta/json/beta.php', {'tipo': 'club', 'club': cid})
        home_streams = []
        if isinstance(d, dict):
            for p in d.get('partidos') or []:
                st = p.get('stream')
                if not st:
                    continue
                is_home = isinstance(p.get('l'), dict) and p['l'].get('club') == cid
                if is_home:
                    u = st.get('url') if isinstance(st, dict) else (st if isinstance(st, str) else '')
                    if u:
                        home_streams.append(u)

        # Sample up to 6 home streams to find the club's true channel (preferring non-TV channels matching club name)
        checked_vids = set()
        for u in home_streams:
            if 'myplay.com' in u or 'twitch.tv' in u or 'instagram.com' in u:
                other_stream_platform = u
            ch_direct = extract_channel_from_url(u)
            if ch_direct:
                stream_channels.append({'channel_url': ch_direct, 'channel_name': ch_direct})
                continue
            vid = extract_video_id(u)
            if vid and vid not in checked_vids and len(checked_vids) < 5:
                checked_vids.add(vid)
                info = get_channel_from_video(vid)
                if info and info.get('channel_url'):
                    stream_channels.append(info)
    except Exception:
        pass

    # Also search YouTube directly for the club's own named channel
    searched_ch = search_youtube_for_club(cname)

    # Decide between stream_channels and searched_ch:
    # If a stream channel matches the club's distinctive tokens (and isn't just a local TV station when the club has its own channel), pick it!
    dist = distinctive_tokens(cname)
    best_stream_ch = None
    if stream_channels:
        # Rank stream channels: prefer those matching club name and not TV station, then most frequent
        counts = Counter(x['channel_url'] for x in stream_channels)
        by_url = {x['channel_url']: x for x in stream_channels}
        ranked = sorted(counts.keys(), key=lambda u: (
            not is_tv_channel(by_url[u].get('channel_name', '')),
            any(t in norm(by_url[u].get('channel_name', '') + ' ' + u) for t in dist),
            counts[u]
        ), reverse=True)
        best_stream_ch = by_url[ranked[0]]

    if best_stream_ch:
        # If the stream channel is a local TV station (like VOTV or Radio Calella) AND we found an official club channel on YouTube, use the official club channel (and note the stream channel)
        if is_tv_channel(best_stream_ch.get('channel_name', '')) and searched_ch:
            ch_info = searched_ch
            fuente = f"Canal oficial del club (también emite en {best_stream_ch.get('channel_name')})"
        else:
            ch_info = best_stream_ch
            fuente = 'Stream oficial en iSquad (Partidos locales)'
    elif searched_ch:
        ch_info = searched_ch
        fuente = 'Búsqueda verificada en YouTube'

    # Check official website if still not found
    if not ch_info and c.get('web_oficial'):
        w = c['web_oficial'].strip()
        if not w.startswith('http'):
            w = 'https://' + w
        try:
            w_html = get_url(w, timeout=8)
            ch_direct = extract_channel_from_url(w_html)
            if ch_direct:
                ch_info = {'channel_url': ch_direct}
                fuente = 'Web oficial del club'
        except Exception:
            pass

    if ch_info:
        ch_info = enrich_channel_stats(ch_info)
        c['canal_youtube'] = ch_info.get('channel_url', '')
        c['nombre_canal_yt'] = ch_info.get('channel_name', '')
        c['handle_yt'] = ch_info.get('handle', '')
        c['channel_id_yt'] = ch_info.get('channel_id', '')
        c['suscriptores_yt_texto'] = ch_info.get('subs_text', '')
        c['suscriptores_yt'] = ch_info.get('subs_num', '')
        c['videos_yt_texto'] = ch_info.get('vids_text', '')
        c['videos_yt'] = ch_info.get('vids_num', '')
        c['fuente_canal_yt'] = fuente
    else:
        c['canal_youtube'] = ''
        c['nombre_canal_yt'] = ''
        c['handle_yt'] = ''
        c['channel_id_yt'] = ''
        c['suscriptores_yt_texto'] = ''
        c['suscriptores_yt'] = ''
        c['videos_yt_texto'] = ''
        c['videos_yt'] = ''
        c['fuente_canal_yt'] = f'Sin canal YT detectado (usa {other_stream_platform})' if other_stream_platform else 'Sin canal YT detectado'

    return c

t0 = time.time()
results = []
with ThreadPoolExecutor(max_workers=12) as ex:
    futs = {ex.submit(process_club_v2, c): c['id_club'] for c in clubs}
    done = 0
    for f in as_completed(futs):
        done += 1
        res = f.result()
        results.append(res)
        if done % 20 == 0 or done == len(clubs):
            found_so_far = sum(1 for r in results if r.get('canal_youtube'))
            print(f"Processed {done}/{len(clubs)} clubs ({found_so_far} channels found, {time.time()-t0:.1f}s)...")

results.sort(key=lambda x: (x.get('nombre_club') or '').upper())

with open('clubs_fch_completo.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

fieldnames = [
    'id_club', 'nombre_club', 'canal_youtube', 'nombre_canal_yt', 'handle_yt',
    'suscriptores_yt', 'suscriptores_yt_texto', 'videos_yt', 'videos_yt_texto', 'fuente_canal_yt',
    'modalidades', 'num_categorias', 'num_competiciones', 'num_equipos_distintos',
    'web_oficial', 'email', 'telefono', 'twitter', 'direccion', 'presidente',
    'categorias', 'competiciones', 'equipos',
    'en_listado_principal_fch', 'temporadas_activas', 'url_ficha_isquad', 'url_busqueda_youtube', 'channel_id_yt'
]

for r in results:
    for k in list(r.keys()):
        if k not in fieldnames:
            del r[k]

with open('clubs_fch_completo.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
    writer.writeheader()
    writer.writerows(results)

with open('clubs_fch_completo_comma.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=',')
    writer.writeheader()
    writer.writerows(results)

found_total = sum(1 for r in results if r.get('canal_youtube'))
print(f"FINISHED! Found {found_total}/{len(results)} verified YouTube channels.")
