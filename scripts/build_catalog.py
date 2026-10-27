"""Monta o catálogo de incidentes públicos no Brasil.

Plano:
1. Baixar alegações abertas de ransomware com país BR.
2. Ler RSS recente e o GDELT, quando a API responde.
3. Ficar com incidente digital, inclusive manchete pública de CVE, PHP ou webshell no Brasil.
4. Achar município ou UF no texto, sem gravar o texto original.
5. Juntar notícias que citam a mesma organização.
6. Gravar web/data/catalog.json e o contorno dos estados.

Não há API ao vivo no mapa. Rodar este script de novo baixa as fontes e regrava o catálogo.

O arquivo de saída não leva URL de site .onion, descrição de arquivo vazado
nem dado pessoal. Localização é estimada pelo nome do lugar no texto público.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
WEB_DATA = ROOT / "web" / "data"
USER_AGENT = "AtaquesWordMap/0.1 (catalogo publico de incidentes; uso local)"

MUNICIPIOS_URL = (
    "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/json/municipios.json"
)
ESTADOS_URL = (
    "https://raw.githubusercontent.com/kelvins/Municipios-Brasileiros/main/json/estados.json"
)
VITIMAS_URL = "https://data.ransomware.live/victims.json"
ESTADOS_GEOJSON_URL = (
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
)

RSS_FEEDS = [
    "https://g1.globo.com/dynamo/tecnologia/rss2.xml",
    "https://olhardigital.com.br/feed/",
    "https://www.tecmundo.com.br/rss",
    "https://www.canaltech.com.br/rss/",
    "https://cryptoid.com.br/feed/",
    "https://www.cisoadvisor.com.br/feed/",
    "https://convergenciadigital.com.br/feed/",
    "https://www.baguete.com.br/rss.xml",
    "https://www.itforum.com.br/feed/",
    "https://www.techtudo.com.br/rss/",
    "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",
    "https://feeds.folha.uol.com.br/tec/rss091.xml",
    "https://tecnoblog.net/tema/seguranca-e-privacidade/feed/",
    "https://seginfo.com.br/feed/",
    "https://rss.uol.com.br/feed/tecnologia.xml",
]

IMPRENSA_URL = "https://www.ransomware.live/cyberattacks"

# Nomes de município que também são palavra comum. Capitais curtas ficam de fora desta lista.
# Palavra única que existe como município e também como termo comum em texto.
CIDADES_ESTRANGEIRAS = {
    "barcelona",
    "berlim",
    "londres",
    "lisboa",
    "madrid",
    "madri",
    "miami",
    "paris",
    "roma",
    "toquio",
}

BLOQUEIO_SIMPLES = {
    "america",
    "brasil",
    "brasileira",
    "brasileiro",
    "central",
    "comercial",
    "digital",
    "energia",
    "group",
    "holding",
    "industrial",
    "internacional",
    "logistica",
    "nacional",
    "sales",
    "saude",
    "security",
    "services",
    "sistemas",
    "solutions",
    "tecnologia",
}

NOMES_AMBIGUOS = {
    "boa",
    "bom",
    "centro",
    "flor",
    "geral",
    "leste",
    "monte",
    "norte",
    "nova",
    "novo",
    "oeste",
    "oriente",
    "para",
    "paz",
    "rio",
    "santa",
    "santo",
    "sao",
    "sul",
    "uniao",
    "velha",
}

TERMOS_INCIDENTE = (
    "ransomware",
    "sequestro de dados",
    "vazamento de dados",
    "dados vazad",
    "vazamento de inform",
    "ataque cibernetico",
    "ciberataque",
    "cyber attack",
    "ataque hacker",
    "ataques hacker",
    "invasao hacker",
    "hacker invad",
    "hackers invad",
    "hackers atac",
    "grupo hacker",
    "incidente de seguranca",
    "site invadid",
    "sistemas invadid",
    "prefeitura hacke",
    "foi hackeada",
    "foi hackeado",
    "webshell",
    "web shell",
    "shell web",
)

PISTAS_PHP = (
    "falha",
    "brecha",
    "vulnerab",
    "suspend",
    "alerta",
    " explor",
    " invad",
    " atac",
    "webshell",
    "web shell",
    "compromet",
    "infect",
    "backdoor",
    "cve",
)

TERMOS_EXCLUIR = (
    "invasao de terra",
    "invasao agraria",
    "sem terra",
    "sem-terra",
    "invasao de campo",
    "invadiu o campo",
    "invasao de domicilio",
    "invadiu a casa",
    "vazamento de oleo",
    "vazamento de petróleo",
    "vazamento de petroleo",
)


def norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("'", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_bytes(url: str, timeout: int = 90) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
    if payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    return payload


def load_json_url(url: str, cache_name: str):
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE / cache_name
    try:
        payload = fetch_bytes(url)
        cache_path.write_bytes(payload)
    except Exception as exc:
        if not cache_path.exists():
            raise
        print(f"aviso: falha ao baixar {url} ({exc}); usando cache {cache_name}")
        payload = cache_path.read_bytes()
    return json.loads(payload.decode("utf-8-sig"))


def slug(*parts: str) -> str:
    raw = norm(" ".join(parts))[:180]
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    compact = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")[:48]
    return f"{compact}-{digest}" if compact else digest


def citar_cve(text: str) -> list[str]:
    achados = re.findall(r"\bCVE-\d{4}-\d{4,7}\b", text or "", flags=re.IGNORECASE)
    vistos = []
    for item in achados:
        codigo = item.upper()
        if codigo not in vistos:
            vistos.append(codigo)
    return vistos[:3]


def incidente_php(folded: str) -> bool:
    if "php" not in folded:
        return False
    return any(pista in folded for pista in PISTAS_PHP)


def classify(text: str) -> str | None:
    folded = norm(text)
    if any(term in folded for term in TERMOS_EXCLUIR):
        return None
    if "ransomware" in folded or "sequestro de dados" in folded:
        return "ransomware"
    if "vazamento de dados" in folded or "dados vazad" in folded or "vazamento de inform" in folded:
        return "vazamento"
    if "webshell" in folded or "web shell" in folded or "shell web" in folded:
        return "ataque"
    if citar_cve(text) or incidente_php(folded):
        return "ataque"
    if any(term in folded for term in TERMOS_INCIDENTE):
        return "ataque"
    return None


def hostname(website: str) -> str | None:
    raw = (website or "").strip()
    if not raw or "onion" in raw.lower():
        return None
    if "://" not in raw:
        raw = "https://" + raw
    host = urllib.parse.urlparse(raw).hostname or ""
    host = host.lower().strip(".")
    if not host or "." not in host or "onion" in host or " " in host:
        return None
    return host


class Gazetteer:
    def __init__(self, estados: list[dict], municipios: list[dict]):
        self.estados = []
        uf_por_codigo = {}
        for estado in estados:
            sigla = str(estado["uf"]).upper()
            uf_por_codigo[int(estado["codigo_uf"])] = sigla
            self.estados.append(
                {
                    "sigla": sigla,
                    "nome": estado["nome"],
                    "norm": norm(estado["nome"]),
                    "lat": float(estado["latitude"]),
                    "lon": float(estado["longitude"]),
                }
            )
        self.por_sigla = {item["sigla"]: item for item in self.estados}
        self.municipios = []
        for municipio in municipios:
            nome_norm = norm(municipio["nome"])
            if len(nome_norm) < 5 and not municipio.get("capital"):
                continue
            if nome_norm in NOMES_AMBIGUOS and not municipio.get("capital"):
                continue
            sigla = uf_por_codigo.get(int(municipio["codigo_uf"]))
            if not sigla:
                continue
            self.municipios.append(
                {
                    "nome": municipio["nome"],
                    "norm": nome_norm,
                    "uf": sigla,
                    "lat": float(municipio["latitude"]),
                    "lon": float(municipio["longitude"]),
                    "capital": bool(municipio.get("capital")),
                }
            )
        self.municipios.sort(key=lambda item: len(item["norm"]), reverse=True)
        self.indice = defaultdict(list)
        for municipio in self.municipios:
            token = municipio["norm"].split()[0]
            self.indice[token].append(municipio)

    def localizar(self, text: str) -> dict | None:
        folded = f" {norm(text)} "
        if not folded.strip():
            return None
        palavras = set(folded.split())
        candidatos = []
        vistos = set()
        for token in palavras:
            for municipio in self.indice.get(token, []):
                chave = (municipio["norm"], municipio["uf"])
                if chave in vistos:
                    continue
                if f" {municipio['norm']} " in folded and self._municipio_aceitavel(municipio, folded, text):
                    vistos.add(chave)
                    candidatos.append(municipio)
        candidatos = [item for item in candidatos if not self._nome_cortado(item["norm"], folded, candidatos)]
        estados = [
            estado
            for estado in self.estados
            if self._estado_no_texto(estado, folded, text)
        ]
        candidatos = [
            municipio
            for municipio in candidatos
            if not any(
                estado["norm"] == municipio["norm"] or estado["norm"].startswith(municipio["norm"] + " ")
                for estado in estados
            )
        ]
        ufs_no_texto = {estado["sigla"] for estado in estados}
        if candidatos and ufs_no_texto:
            no_estado = [item for item in candidatos if item["uf"] in ufs_no_texto]
            if no_estado:
                candidatos = no_estado
        if len(candidatos) == 1:
            escolhido = candidatos[0]
        elif candidatos:
            maior = max(len(item["norm"]) for item in candidatos)
            finais = [item for item in candidatos if len(item["norm"]) == maior]
            capitais = [item for item in finais if item["capital"]]
            if len(capitais) == 1:
                escolhido = capitais[0]
            elif len(finais) == 1:
                escolhido = finais[0]
            else:
                escolhido = None
        else:
            escolhido = None
        if escolhido:
            return {
                "cidade": escolhido["nome"],
                "uf": escolhido["uf"],
                "lat": round(escolhido["lat"], 5),
                "lon": round(escolhido["lon"], 5),
                "precisao": "municipio",
            }
        if len(ufs_no_texto) == 1:
            estado = self.por_sigla[next(iter(ufs_no_texto))]
            return {
                "cidade": None,
                "uf": estado["sigla"],
                "lat": round(estado["lat"], 5),
                "lon": round(estado["lon"], 5),
                "precisao": "uf",
            }
        return None

    @staticmethod
    def _municipio_aceitavel(municipio: dict, folded: str, original: str) -> bool:
        nome = municipio["norm"]
        if nome in BLOQUEIO_SIMPLES or nome in CIDADES_ESTRANGEIRAS:
            return False
        if nome == "franca" and re.search(r"França|\bFrance\b", original or "", re.I):
            return False
        if len(nome.split()) >= 2 or municipio["capital"] or len(nome) >= 8:
            return True
        inicio = folded.find(f" {nome} ")
        if inicio < 0:
            return False
        antes = folded[: inicio + 1]
        return any(antes.endswith(pista) for pista in (" em ", " de ", " do ", " da ", " no ", " na ", " in ", " of ", " at "))

    @staticmethod
    def _nome_cortado(nome: str, folded: str, candidatos: list[dict]) -> bool:
        for ligacao in (" de ", " do ", " da ", " dos ", " das "):
            if f" {nome}{ligacao}" not in folded:
                continue
            tem_nome_maior = any(
                outro["norm"] != nome and outro["norm"].startswith(nome + " ") and f" {outro['norm']} " in folded
                for outro in candidatos
            )
            if not tem_nome_maior:
                return True
        return False

    def _estado_no_texto(self, estado: dict, folded: str, original: str) -> bool:
        if self._sigla_presente(estado["sigla"], original):
            return True
        if estado["norm"] == "para":
            return any(pista in folded for pista in (" estado do para ", " no para ", " do para ", " paraense "))
        return f" {estado['norm']} " in folded

    @staticmethod
    def _sigla_presente(sigla: str, original: str) -> bool:
        return re.search(rf"(?<![A-Za-z0-9.]){sigla}(?![A-Za-z0-9.])", original or "") is not None


def data_curta(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else None


def texto_para_lugar(*partes: str) -> str:
    text = " ".join(parte for parte in partes if parte)
    text = re.sub(r"https?://\S+", " ", text, flags=re.I)
    text = re.sub(r"\bwww\.[^\s]+", " ", text, flags=re.I)
    text = re.sub(r"\b[\w.-]+\.(?:gov|com|net|org)(?:\.br)?\b", " ", text, flags=re.I)
    return text


def titulo_util(titulo: str) -> bool:
    folded = norm(titulo)
    if len(folded) < 3:
        return False
    if re.match(r"^(zzq|probe|company|test)\b", folded):
        return False
    if any(trecho in folded for trecho in ("come to chat", "we will attack", "employee credential")):
        return False
    if re.search(r"\b\d+\s?(gb|tb)\b", folded):
        return False
    return True


def blurbs_do_mapa() -> dict[str, str]:
    try:
        html = fetch_bytes("https://www.ransomware.live/map/BR", timeout=60).decode("utf-8", "replace")
    except Exception as exc:
        print(f"aviso: página do mapa não entrou na geocodificação ({exc})")
        return {}
    titulos = re.findall(r'victim-title[^>]*>(.*?)</a>', html, flags=re.S)
    descricoes = re.findall(r'victim-desc[^>]*>(.*?)</', html, flags=re.S)
    pares = {}
    for titulo, descricao in zip(titulos, descricoes):
        limpo = re.sub(r"<[^>]+>", " ", titulo)
        limpo = re.sub(r"\s+", " ", limpo).strip()
        texto = re.sub(r"<[^>]+>", " ", descricao)
        texto = re.sub(r"\s+", " ", texto).strip(" …")
        if limpo and texto and texto.upper() != "N/A":
            pares[norm(limpo)] = texto
    print(f"blurbs do mapa: {len(pares)}")
    return pares


def incidente_ransomware(registro: dict, gazetteer: Gazetteer, blurbs: dict[str, str]) -> dict | None:
    titulo = re.sub(r"\s+", " ", (registro.get("post_title") or "")).strip()
    if not titulo_util(titulo):
        return None
    if (registro.get("country") or "").upper() != "BR":
        return None
    grupo = (registro.get("group_name") or "").strip() or None
    setor = (registro.get("activity") or "").strip()
    if setor.lower() in {"", "not found", "n/a", "unknown"}:
        setor = None
    data = data_curta(registro.get("discovered") or registro.get("published"))
    texto_local = texto_para_lugar(
        titulo,
        setor or "",
        blurbs.get(norm(titulo), ""),
        registro.get("description") or "",
    )
    lugar = gazetteer.localizar(texto_local)
    site = hostname(registro.get("website") or "")
    resumo = f"Organização citada em listagem pública de ransomware em {data or 'data não informada'}."
    if setor:
        resumo += f" Setor informado na base: {setor}."
    if grupo:
        resumo += f" Grupo citado: {grupo}."
    resumo += " É uma alegação de terceiro, não uma confirmação oficial."
    item = {
        "id": slug("rw", titulo, grupo or "", data or ""),
        "titulo": titulo,
        "tipo": "ransomware",
        "setor": setor,
        "grupo": grupo,
        "data": data,
        "website": site,
        "resumo": resumo,
        "origem": "ransomware.live",
        "fontes": [
            {
                "nome": "Ransomware.live",
                "url": "https://www.ransomware.live/map/BR",
            }
        ],
    }
    if lugar:
        item.update(lugar)
    else:
        item.update({"cidade": None, "uf": None, "lat": None, "lon": None, "precisao": "pais"})
    return item


def local_tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def texto(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return re.sub(r"\s+", " ", element.text).strip()


def parse_feed(payload: bytes, feed_url: str) -> list[dict]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []
    itens = []
    for node in root.iter():
        if local_tag(node) not in {"item", "entry"}:
            continue
        titulo = ""
        link = ""
        quando = ""
        veiculo = ""
        for child in list(node):
            tag = local_tag(child)
            if tag == "title" and not titulo:
                titulo = texto(child)
            elif tag == "link" and not link:
                link = (child.get("href") or texto(child)).strip()
            elif tag in {"pubDate", "published", "updated", "date"} and not quando:
                quando = texto(child)
            elif tag == "source" and not veiculo:
                veiculo = texto(child)
        if not titulo or not link or link.startswith("javascript:"):
            continue
        data = None
        if quando:
            try:
                data = parsedate_to_datetime(quando).date().isoformat()
            except (TypeError, ValueError, IndexError):
                match = re.search(r"\d{4}-\d{2}-\d{2}", quando)
                data = match.group(0) if match else None
        itens.append(
            {
                "titulo": titulo,
                "url": link,
                "data": data,
                "veiculo": veiculo or urllib.parse.urlparse(feed_url).hostname or "RSS",
                "feed": feed_url,
            }
        )
    return itens


def coletar_rss() -> list[dict]:
    noticias = []
    for feed_url in RSS_FEEDS:
        try:
            payload = fetch_bytes(feed_url, timeout=25)
        except Exception as exc:
            print(f"rss ignorado {feed_url}: {exc}")
            continue
        found = parse_feed(payload, feed_url)
        kept = []
        for item in found:
            tipo = classify(item["titulo"])
            if not tipo:
                continue
            item["tipo"] = tipo
            kept.append(item)
        print(f"rss {feed_url}: {len(found)} itens, {len(kept)} incidentes")
        noticias.extend(kept)
        time.sleep(0.4)
    return noticias


def coletar_imprensa() -> list[dict]:
    """Fichas públicas de ataque com bandeira do Brasil.

    A página só mostra a janela recente. O parágrafo e o contador de
    infostealer ficam de fora do catálogo.
    """
    try:
        html = fetch_bytes(IMPRENSA_URL, timeout=60).decode("utf-8", "replace")
    except Exception as exc:
        print(f"imprensa ignorada: {exc}")
        return []
    noticias = []
    for part in html.split('class="col-md-6 col-xl-4 mb-4 press-item"')[1:]:
        bandeira = re.search(r"flags/([A-Z]{2})\.svg", part)
        if not bandeira or bandeira.group(1) != "BR":
            continue
        limpo = re.sub(r"\sdata-is='[^']*'", "", part)
        limpo = re.sub(r'\sdata-is="[^"]*"', "", limpo)
        titulo_html = re.search(r'fw-bold">(.*?)</span>', limpo, flags=re.S)
        data_html = re.search(r'text-muted small mb-1 mt-2">(\d{4}-\d{2}-\d{2})</p>', limpo)
        link_html = re.search(r'href="(https?://[^"]+)"[^>]*>\s*Read more', limpo)
        if not titulo_html or not link_html:
            continue
        titulo = unescape(re.sub(r"<[^>]+>", "", titulo_html.group(1)))
        titulo = re.sub(r"\s+", " ", titulo).strip()
        url = link_html.group(1).strip()
        if not titulo_util(titulo) or "onion" in url.lower():
            continue
        pista_html = re.search(r'<p class="small">(.*?)</p>', limpo, flags=re.S)
        pista = unescape(re.sub(r"<[^>]+>", " ", pista_html.group(1))) if pista_html else ""
        tipo = "ransomware" if re.search(r"ransomware|ransom", pista, re.I) else "ataque"
        veiculo = urllib.parse.urlparse(url).hostname or "imprensa"
        noticias.append(
            {
                "titulo": titulo,
                "url": url,
                "data": data_html.group(1) if data_html else None,
                "veiculo": veiculo,
                "feed": "imprensa",
                "tipo": tipo,
            }
        )
    print(f"imprensa BR: {len(noticias)} fichas")
    return noticias


def coletar_gdelt() -> list[dict]:
    consultas = [
        (
            "gdelt-articles.json",
            'sourcecountry:brazil (ransomware OR "vazamento de dados" OR '
            '"ataque cibernetico" OR ciberataque OR "sequestro de dados" OR "ataque hacker" OR '
            'webshell OR "web shell")',
        ),
        (
            "gdelt-cve.json",
            'sourcecountry:brazil (webshell OR "web shell" OR CVE OR '
            '"falha no PHP" OR "vulnerabilidade PHP" OR "sites em PHP")',
        ),
    ]
    noticias = []
    vistos = set()
    for cache_name, query in consultas:
        for item in consultar_gdelt(query, cache_name):
            chave = norm(item["titulo"])
            if chave in vistos:
                continue
            vistos.add(chave)
            noticias.append(item)
    print(f"gdelt: {len(noticias)} artigos depois do filtro")
    return noticias


def consultar_gdelt(query: str, cache_name: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": "75",
            "sort": "datedesc",
            "timespan": "12m",
        }
    )
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + params
    cache_path = CACHE / cache_name
    CACHE.mkdir(parents=True, exist_ok=True)
    try:
        time.sleep(2)
        payload = fetch_bytes(url, timeout=90)
        data = json.loads(payload.decode("utf-8", "replace"))
        if data.get("articles"):
            cache_path.write_bytes(payload)
            print(f"gdelt {cache_name}: resposta nova")
        else:
            print(f"gdelt {cache_name}: resposta sem artigos")
            data = {}
    except json.JSONDecodeError:
        print(f"gdelt {cache_name}: resposta não é JSON")
        return []
    except Exception as exc:
        print(f"gdelt {cache_name} indisponível ({exc})")
        if not cache_path.exists():
            return []
        print(f"gdelt {cache_name}: usando cache")
        payload = cache_path.read_bytes()
        try:
            data = json.loads(payload.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            print(f"gdelt {cache_name}: cache não é JSON")
            return []
    noticias = []
    for article in data.get("articles") or []:
        titulo = (article.get("title") or "").strip()
        link = (article.get("url") or "").strip()
        tipo = classify(titulo)
        if not titulo or not link or not tipo:
            continue
        seen = article.get("seendate") or ""
        data_iso = None
        if re.match(r"\d{8}T", seen):
            data_iso = f"{seen[0:4]}-{seen[4:6]}-{seen[6:8]}"
        noticias.append(
            {
                "titulo": titulo,
                "url": link,
                "data": data_iso,
                "veiculo": article.get("domain") or "GDELT",
                "feed": "gdelt",
                "tipo": tipo,
            }
        )
    print(f"gdelt {cache_name}: {len(noticias)} artigos depois do filtro")
    return noticias


def noticia_sobre_brasil(titulo: str, lugar: dict | None) -> bool:
    folded = f" {norm(titulo)} "
    if re.search(r"França|\bFrance\b|\bJapan\b|Japão", titulo or "") and " brasil " not in folded and " brasileir" not in folded:
        return False
    estrangeiros = (
        " japao ",
        " china ",
        " portugal ",
        " argentina ",
        " alemanha ",
        " espanha ",
        " italia ",
        " mexico ",
        " estados unidos ",
        " reino unido ",
        " europa ",
    )
    if any(pais in folded for pais in estrangeiros) and " brasil " not in folded and " brasileir" not in folded:
        return False
    if lugar and lugar.get("precisao") in {"municipio", "uf"}:
        return True
    ancoras = (
        " brasil ",
        " brasileir",
        " prefeitura ",
        " anpd ",
        " conab ",
        " inss ",
        " serpro ",
        " dataprev ",
        " policia federal ",
        " receita federal ",
        " ministerio ",
        " anatel ",
        " tribunal ",
    )
    return any(ancora in folded for ancora in ancoras)


def anexar_noticias(incidentes: list[dict], noticias: list[dict], gazetteer: Gazetteer) -> None:
    por_nome = sorted(
        ((norm(item["titulo"]), item) for item in incidentes if len(norm(item["titulo"])) >= 8),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    vistos = set()
    for noticia in noticias:
        chave = norm(noticia["titulo"])
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        fonte = {"nome": noticia["veiculo"], "url": noticia["url"], "data": noticia.get("data")}
        acoplado = None
        for nome, incidente in por_nome:
            if nome in chave:
                acoplado = incidente
                break
        if acoplado:
            urls = {item["url"] for item in acoplado["fontes"]}
            if fonte["url"] not in urls:
                acoplado["fontes"].append(fonte)
            if noticia.get("data") and not acoplado.get("data"):
                acoplado["data"] = noticia["data"]
            continue
        lugar = gazetteer.localizar(texto_para_lugar(noticia["titulo"]))
        if noticia.get("feed") == "imprensa" and lugar and lugar.get("precisao") == "municipio":
            titulo_norm = norm(noticia["titulo"])
            cidade_norm = norm(lugar["cidade"])
            marca_empresa = titulo_norm.startswith(("viacao ", "grupo ", "companhia ", "empresa "))
            if cidade_norm != titulo_norm and marca_empresa:
                lugar = None
        if noticia.get("feed") != "imprensa" and not noticia_sobre_brasil(noticia["titulo"], lugar):
            continue
        cves = citar_cve(noticia["titulo"])
        codigo = f" Identificador citado: {', '.join(cves)}." if cves else ""
        relato = " É um relato de imprensa, não uma confirmação oficial." if noticia.get("feed") == "imprensa" else ""
        item = {
            "id": slug("news", noticia["titulo"], noticia.get("data") or ""),
            "titulo": noticia["titulo"],
            "tipo": noticia["tipo"],
            "setor": None,
            "grupo": cves[0] if cves else None,
            "data": noticia.get("data"),
            "website": None,
            "resumo": (
                "Notícia pública sobre incidente digital."
                + codigo
                + relato
                + " O ponto usa o município ou o estado citado no título."
            ),
            "origem": noticia.get("feed") if noticia.get("feed") in {"gdelt", "imprensa"} else "rss",
            "fontes": [fonte],
        }
        if lugar:
            item.update(lugar)
        else:
            item.update({"cidade": None, "uf": None, "lat": None, "lon": None, "precisao": "pais"})
        incidentes.append(item)


# Relatos com notícia pública que o RSS não arquiva. O texto não descreve o método.
CASOS_CURADOS = (
    {
        "titulo": "Administração dos Portos de Paranaguá e Antonina",
        "tipo": "ataque",
        "data": "2021-04-16",
        "cidade": "Paranaguá",
        "uf": "PR",
        "resumo": (
            "A página da administração dos portos estava entre os sites do governo do Paraná "
            "alterados na noite de 16 de abril de 2021. A Celepar descreveu a alteração como "
            "superficial. Não há relato de parada da operação do porto."
        ),
        "fonte_nome": "g1.globo.com",
        "fonte_url": "https://g1.globo.com/pr/parana/noticia/2021/04/17/sites-do-governo-do-parana-voltam-a-funcionar-apos-invasao-de-hackers-dados-estao-preservados-informou-celepar.ghtml",
    },
    {
        "titulo": "Sites do Governo do Paraná",
        "tipo": "ataque",
        "data": "2021-04-16",
        "cidade": "Curitiba",
        "uf": "PR",
        "resumo": (
            "A Celepar informou alteração de páginas oficiais na noite de 16 de abril de 2021, "
            "nas camadas superficiais, e disse que os dados estavam preservados."
        ),
        "fonte_nome": "g1.globo.com",
        "fonte_url": "https://g1.globo.com/pr/parana/noticia/2021/04/17/sites-do-governo-do-parana-voltam-a-funcionar-apos-invasao-de-hackers-dados-estao-preservados-informou-celepar.ghtml",
    },
    {
        "titulo": "Sites do Governo do Paraná e do Ministério Público",
        "tipo": "ataque",
        "data": "2020-05-16",
        "cidade": "Curitiba",
        "uf": "PR",
        "resumo": (
            "A Celepar informou invasão de páginas do governo e do Ministério Público em 16 de maio de 2020. "
            "O órgão classificou o caso como superficial e disse que os dados estavam preservados."
        ),
        "fonte_nome": "g1.globo.com",
        "fonte_url": "https://g1.globo.com/pr/parana/noticia/2020/05/16/sites-do-governo-do-parana-e-do-ministerio-publico-sao-invadidos-por-hackers.ghtml",
    },
    {
        "titulo": "Instituto Federal do Paraná",
        "tipo": "ataque",
        "data": "2021-12-10",
        "cidade": "Curitiba",
        "uf": "PR",
        "resumo": (
            "O Instituto Federal do Paraná informou indisponibilidade dos sistemas em 10 de dezembro de 2021. "
            "É um relato do órgão, não uma confirmação do alcance."
        ),
        "fonte_nome": "uol.com.br",
        "fonte_url": "https://www.uol.com.br/tilt/noticias/redacao/2021/12/14/invasao-hacker-orgaos-do-governo.htm",
    },
    {
        "titulo": "Tribunal de Contas do Estado do Paraná",
        "tipo": "ransomware",
        "data": "2022-05-13",
        "cidade": "Curitiba",
        "uf": "PR",
        "resumo": (
            "O Tribunal de Contas do Paraná informou indisponibilidade dos sistemas a partir de 13 de maio de 2022 "
            "e um pedido de resgate que não foi atendido. O órgão disse não ter havido vazamento."
        ),
        "fonte_nome": "ric.com.br",
        "fonte_url": "https://ric.com.br/seguranca/hackers-que-atacaram-tce-do-parana-pediram-resgate-com-pagamento-em-bitcoins/",
    },
    {
        "titulo": "Prefeitura de Matelândia",
        "tipo": "ataque",
        "data": "2021-12-16",
        "cidade": "Matelândia",
        "uf": "PR",
        "resumo": (
            "A prefeitura informou desvio de recursos de contas municipais entre 16 e 17 de dezembro de 2021. "
            "É um relato público, não uma descrição do método."
        ),
        "fonte_nome": "ric.com.br",
        "fonte_url": "https://ric.com.br/politica/prefeitura-de-matelandia-diz-tentar-recuperar-r-419-mil-apos-ataque-hacker/",
    },
    {
        "titulo": "Prefeitura de Pontal do Paraná",
        "tipo": "ataque",
        "data": "2023-01-02",
        "cidade": "Pontal do Paraná",
        "uf": "PR",
        "resumo": (
            "A prefeitura informou que o sistema de finanças ficou fora do ar em 2 de janeiro de 2023 "
            "depois de um ataque à empresa que operava o sistema. A emissão de IPTU foi suspensa."
        ),
        "fonte_nome": "jblitoral.com.br",
        "fonte_url": "https://jblitoral.com.br/cidades/ataque-cibernetico-suspende-pagamento-de-iptu-em-pontal-do-parana-diz-prefeitura/",
    },
    {
        "titulo": "Prefeitura de Roncador",
        "tipo": "ataque",
        "data": "2023-03-29",
        "cidade": "Roncador",
        "uf": "PR",
        "resumo": (
            "A polícia investigou desvio de recursos de conta da prefeitura em 29 de março de 2023 "
            "e informou que a ação foi externa. É um relato público, não uma descrição do método."
        ),
        "fonte_nome": "tribunadointerior.com.br",
        "fonte_url": "https://www.tribunadointerior.com.br/policial/pericia-confirma-que-r-750-mil-desviados-das-contas-de-roncador-nao-foi-falha-da-prefeitura/",
    },
    {
        "titulo": "Prefeitura de Jacarezinho",
        "tipo": "ataque",
        "data": "2023-07-24",
        "cidade": "Jacarezinho",
        "uf": "PR",
        "resumo": (
            "A prefeitura informou que banco de dados e sistemas ficaram fora do ar em 24 de julho de 2023, "
            "incluindo nota fiscal, tributos e o portal da transparência."
        ),
        "fonte_nome": "npdiario.com.br",
        "fonte_url": "https://npdiario.com.br/cidades/hacker-invade-prefeitura-e-danifica-sistema-em-jacarezinho/",
    },
    {
        "titulo": "Prefeitura de Ponta Grossa",
        "tipo": "ataque",
        "data": "2024-08-18",
        "cidade": "Ponta Grossa",
        "uf": "PR",
        "resumo": (
            "A prefeitura informou ataque à rede no fim de semana de 18 de agosto de 2024 "
            "e disse ter desligado sistemas hospedados. As autoridades foram acionadas."
        ),
        "fonte_nome": "ric.com.br",
        "fonte_url": "https://ric.com.br/seguranca/prefeitura-de-ponta-grossa-e-alvo-de-ataque-cibernetico/",
    },
    {
        "titulo": "Prefeitura de Palmeira",
        "tipo": "ransomware",
        "data": "2025-03-12",
        "cidade": "Palmeira",
        "uf": "PR",
        "resumo": (
            "A prefeitura informou indisponibilidade do e-mail institucional em 12 de março de 2025 "
            "por um ataque que ela classificou como ransomware. Não há confirmação de vazamento na nota."
        ),
        "fonte_nome": "securityleaders.com.br",
        "fonte_url": "https://securityleaders.com.br/comunicacao-oficial-da-prefeitura-de-palmeira-pr-sofre-ataque-cibernetico/",
    },
)


def lugar_da_cidade(gazetteer: Gazetteer, cidade: str, uf: str) -> dict | None:
    alvo = norm(cidade)
    for municipio in gazetteer.municipios:
        if municipio["uf"] == uf and municipio["norm"] == alvo:
            return {
                "cidade": municipio["nome"],
                "uf": uf,
                "lat": round(municipio["lat"], 5),
                "lon": round(municipio["lon"], 5),
                "precisao": "municipio",
            }
    estado = gazetteer.por_sigla.get(uf)
    if not estado:
        return None
    return {
        "cidade": None,
        "uf": uf,
        "lat": round(estado["lat"], 5),
        "lon": round(estado["lon"], 5),
        "precisao": "uf",
    }


def anexar_casos_curados(incidentes: list[dict], gazetteer: Gazetteer) -> None:
    existentes = {norm(item["titulo"]) for item in incidentes}
    adicionados = 0
    for caso in CASOS_CURADOS:
        if norm(caso["titulo"]) in existentes:
            continue
        lugar = lugar_da_cidade(gazetteer, caso["cidade"], caso["uf"])
        if not lugar:
            print(f"caso curado sem lugar: {caso['titulo']}")
            continue
        item = {
            "id": slug("news", caso["titulo"], caso["data"]),
            "titulo": caso["titulo"],
            "tipo": caso["tipo"],
            "setor": None,
            "grupo": None,
            "data": caso["data"],
            "website": None,
            "resumo": caso["resumo"],
            "origem": "pesquisa",
            "fontes": [{"nome": caso["fonte_nome"], "url": caso["fonte_url"], "data": caso["data"]}],
        }
        item.update(lugar)
        incidentes.append(item)
        existentes.add(norm(caso["titulo"]))
        adicionados += 1
    for item in incidentes:
        if norm(item["titulo"]) != "companhia paranaense de energia copel":
            continue
        if item.get("precisao") != "pais":
            continue
        estado = gazetteer.por_sigla["PR"]
        item.update(
            {
                "cidade": None,
                "uf": "PR",
                "lat": round(estado["lat"], 5),
                "lon": round(estado["lon"], 5),
                "precisao": "uf",
            }
        )
        urls = {fonte["url"] for fonte in item["fontes"]}
        extra = "https://www.baguete.com.br/noticias/copel-confirma-ter-sofrido-ataque-cibernetico"
        if extra not in urls:
            item["fontes"].append({"nome": "baguete.com.br", "url": extra, "data": item.get("data")})
    print(f"casos curados do Paraná: {adicionados}")


def preparar_geojson(estados: list[dict]) -> None:
    try:
        payload = fetch_bytes(ESTADOS_GEOJSON_URL, timeout=60)
    except Exception as exc:
        print(f"aviso: contorno dos estados não baixou ({exc})")
        return
    data = json.loads(payload.decode("utf-8"))
    por_nome = {norm(item["nome"]): item["uf"].upper() for item in estados}
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        sigla = props.get("sigla") or props.get("SIGLA") or props.get("uf") or props.get("UF")
        nome = props.get("name") or props.get("nome") or props.get("NM_ESTADO") or ""
        if isinstance(sigla, str) and "-" in sigla:
            sigla = sigla.split("-")[-1]
        if not sigla:
            sigla = por_nome.get(norm(str(nome)))
        feature["properties"] = {"sigla": str(sigla or "").upper(), "nome": nome}
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "brazil-states.geojson").write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    print("baixando municípios, estados e vítimas...")
    estados = load_json_url(ESTADOS_URL, "estados.json")
    municipios = load_json_url(MUNICIPIOS_URL, "municipios.json")
    vitimas = load_json_url(VITIMAS_URL, "victims.json")
    gazetteer = Gazetteer(estados, municipios)
    blurbs = blurbs_do_mapa()
    incidentes = []
    for registro in vitimas:
        item = incidente_ransomware(registro, gazetteer, blurbs)
        if item:
            incidentes.append(item)
    antes = len(incidentes)
    unicos = {}
    for item in incidentes:
        unicos.setdefault(item["id"], item)
    incidentes = list(unicos.values())
    print(f"ransomware BR: {antes} registros, {len(incidentes)} depois da deduplicação")
    noticias = coletar_rss()
    noticias.extend(coletar_imprensa())
    noticias.extend(coletar_gdelt())
    anexar_noticias(incidentes, noticias, gazetteer)
    anexar_casos_curados(incidentes, gazetteer)
    incidentes.sort(key=lambda item: (item.get("data") or "", item["titulo"]), reverse=True)
    no_mapa = sum(1 for item in incidentes if item.get("precisao") in {"municipio", "uf"})
    por_tipo = defaultdict(int)
    por_precisao = defaultdict(int)
    for item in incidentes:
        por_tipo[item["tipo"]] += 1
        por_precisao[item["precisao"]] += 1
    catalogo = {
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "avisos": [
            "Cada ponto é um incidente público, não um ataque observado em tempo real.",
            "Alegações de ransomware vêm da base aberta do Ransomware.live e não foram confirmadas uma a uma.",
            "A coordenada é o município ou o centro do estado citado no texto. Pode ser a sede, não o local atingido.",
            "Notícias sem município ou UF ficam na lista e não entram no mapa.",
            "CVE, PHP e webshell entram só quando uma manchete pública descreve o caso. Não há exploração nem código.",
            "O catálogo não se atualiza sozinho. Rode python scripts/build_catalog.py para baixar as fontes de novo.",
        ],
        "totais": {
            "incidentes": len(incidentes),
            "no_mapa": no_mapa,
            "por_tipo": dict(por_tipo),
            "por_precisao": dict(por_precisao),
        },
        "incidentes": incidentes,
    }
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (WEB_DATA / "catalog.json").write_text(
        json.dumps(catalogo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    preparar_geojson(estados)
    print(json.dumps(catalogo["totais"], ensure_ascii=False, indent=2))
    print(f"gravado {WEB_DATA / 'catalog.json'}")


if __name__ == "__main__":
    main()
