#!/usr/bin/env python3
"""Folletto: dashboard dei limiti di utilizzo di Claude per un vecchio Kindle (600x800, scala di grigi).

Legge ~/.claude/usage-state.json (scritto dalla status line di Claude Code)
e serve sulla rete di casa:
  /dash.png  -> immagine per il Kindle (eips)
  /          -> pagina di anteprima che si aggiorna da sola
Nessuna dipendenza esterna: solo Python 3 standard. Opzionale: icalBuddy per la modalità meeting.

Uso:
  python3 kindle_dash.py                 avvia il server (porta 8765)
  python3 kindle_dash.py --png > x.png   salva un'anteprima
  python3 kindle_dash.py --prova-meeting controlla se vede un meeting in corso
"""
import datetime
import http.server
import json
import os
import struct
import sys
import time
import urllib.parse
import zlib

# ---------------------------------------------------------------- personalizza qui
NOME = ""               # il tuo nome, per gli auguri di compleanno (es. "Federica")
COMPLEANNO = None       # (mese, giorno), es. (9, 7) per il 7 settembre; None = niente festa

STATE = os.path.expanduser("~/.claude/usage-state.json")
PORT = int(os.environ.get("KINDLE_DASH_PORT", "8765"))
W, H = 600, 800
BLACK, DARK, MID, LIGHT, WHITE = 0, 0x55, 0x99, 0xE6, 0xFF

# ---------------------------------------------------------------- font 5x7
_F = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000", ":": "00000 01100 01100 00000 01100 01100 00000",
    "/": "00001 00010 00010 00100 01000 01000 10000", "%": "11000 11001 00010 00100 01000 10011 00011",
    ".": "00000 00000 00000 00000 00000 01100 01100", "-": "00000 00000 00000 11111 00000 00000 00000",
    "!": "00100 00100 00100 00100 00100 00000 00100", "?": "01110 10001 00001 00010 00100 00000 00100",
    "·": "00000 00000 00000 01100 01100 00000 00000",
    ",": "00000 00000 00000 00000 01100 00100 01000", "'": "00100 00100 01000 00000 00000 00000 00000",
    "À": "01000 00100 01110 10001 11111 10001 10001", "È": "01000 00100 11111 10000 11110 10000 11111",
    "É": "00010 00100 11111 10000 11110 10000 11111", "Ì": "01000 00100 01110 00100 00100 00100 01110",
    "Ò": "01000 00100 01110 10001 10001 10001 01110", "Ù": "01000 00100 10001 10001 10001 10001 01110",
    "’": "00100 00100 01000 00000 00000 00000 00000", "°": "01100 10010 10010 01100 00000 00000 00000",
}
FONT = {k: [r for r in v.split()] for k, v in _F.items()}


class Canvas:
    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.px = bytearray([WHITE]) * (w * h)

    def rect(self, x, y, w, h, v):
        for yy in range(max(0, y), min(self.h, y + h)):
            row = yy * self.w
            for xx in range(max(0, x), min(self.w, x + w)):
                self.px[row + xx] = v

    def frame(self, x, y, w, h, t, v):
        self.rect(x, y, w, t, v); self.rect(x, y + h - t, w, t, v)
        self.rect(x, y, t, h, v); self.rect(x + w - t, y, t, h, v)

    def text_width(self, s, scale):
        return len(s) * 6 * scale - scale

    def text(self, s, x, y, scale, v=BLACK, align="left"):
        """align="center": x e' il centro della scritta; "right": x e' il bordo destro."""
        s = s.upper()
        if align == "center":
            x = x - self.text_width(s, scale) // 2
        elif align == "right":
            x = x - self.text_width(s, scale)
        for ch in s:
            glyph = FONT.get(ch, FONT["?"])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        self.rect(x + gx * scale, y + gy * scale, scale, scale, v)
            x += 6 * scale

    def rotated(self, clockwise):
        """Ruota di 90 gradi: serve a mostrare un layout orizzontale sul Kindle."""
        out = Canvas(self.h, self.w)
        for y in range(self.h):
            for x in range(self.w):
                if clockwise:
                    out.px[x * out.w + (self.h - 1 - y)] = self.px[y * self.w + x]
                else:
                    out.px[(self.w - 1 - x) * out.w + y] = self.px[y * self.w + x]
        return out

    def png(self):
        w, h = self.w, self.h
        raw = b"".join(b"\x00" + bytes(self.px[y * w:(y + 1) * w]) for y in range(h))

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- il folletto
N = 32  # griglia del folletto, ogni pixel diventa SCALE x SCALE


def folletto(mood, costume=None):
    g = [[None] * N for _ in range(N)]

    def put(x, y, v):
        if 0 <= x < N and 0 <= y < N:
            g[y][x] = v

    def mirror(points, v):
        for x, y in points:
            put(x, y, v); put(N - 1 - x, y, v)

    # corpo tondo, grigio chiaro con contorno nero
    cx, cy, rx, ry = 15.5, 19.5, 11.5, 10.5
    body = {(x, y) for y in range(N) for x in range(N) if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1}
    for x, y in body:
        edge = any((x + dx, y + dy) not in body for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        put(x, y, BLACK if edge else LIGHT)

    # piedini
    mirror([(x, y) for x in range(10, 14) for y in (30, 31)], BLACK)

    # antennine: dritte, oppure afflosciate quando dorme (nascoste se c'è un cappello)
    if costume in CAPPELLI:
        pass
    elif mood == "sleepy":
        mirror([(11, 9), (11, 8), (10, 7), (9, 7), (8, 8), (7, 9), (7, 10)], BLACK)
        mirror([(6, 11), (7, 11), (6, 12), (7, 12)], BLACK)  # pallina che penzola
    else:
        mirror([(11, 9), (11, 8), (10, 7), (10, 6), (9, 5)], BLACK)
        mirror([(7, 2), (8, 2), (7, 3), (8, 3), (9, 3), (8, 4), (9, 4)], BLACK)

    if mood == "happy":
        mirror([(x, y) for x in (10, 11) for y in (16, 17, 18)], BLACK)
        mirror([(10, 16)], WHITE)                                    # luccichio negli occhi
        mirror([(12, 21), (13, 22), (14, 23), (15, 23)], BLACK)      # sorriso
        mirror([(7, 20), (8, 20), (7, 21), (8, 21)], MID)            # guanciotte
        mirror([(3, 24), (2, 25), (1, 26)], BLACK)                   # braccini rilassati
    elif mood == "focused":
        mirror([(9, 18), (10, 18), (11, 18), (12, 18)], BLACK)      # occhi socchiusi
        mirror([(9, 15), (10, 15), (11, 15), (12, 16)], BLACK)      # sopracciglia aggrottate
        mirror([(14, 23), (15, 23)], BLACK)                         # bocca dritta
        mirror([(3, 22), (2, 21), (1, 20)], BLACK)
    elif mood == "sweaty":
        mirror([(x, y) for x in (9, 10, 11) for y in (16, 17, 18)], BLACK)
        mirror([(10, 17)], WHITE)                                    # occhi sbarrati
        for i, x in enumerate(range(11, 21)):                        # bocca a zigzag
            put(x, 23 if i % 2 == 0 else 22, BLACK)
        for x, y in [(26, 9), (25, 10), (26, 10), (27, 10), (25, 11), (26, 11), (27, 11), (26, 12)]:
            put(x, y, DARK)                                          # goccia di sudore
        put(29, 13, MID); put(29, 14, MID)
        mirror([(3, 23), (2, 23), (1, 22)], BLACK)
    elif mood == "sleepy":
        mirror([(9, 18), (10, 19), (11, 19), (12, 18)], BLACK)      # occhi chiusi
        for x, y in [(15, 23), (16, 23), (15, 24), (16, 24)]:
            put(x, y, DARK)                                          # boccuccia aperta
        mirror([(4, 27), (3, 28), (2, 28)], BLACK)
    elif mood == "waking":
        mirror([(9, 18), (10, 17), (11, 16), (12, 17), (13, 18)], BLACK)  # occhi a ^ ^
        for x in range(13, 19):
            put(x, 21, BLACK)
        put(13, 22, BLACK); put(18, 22, BLACK)
        for x in range(14, 18):
            put(x, 22, DARK); put(x, 23, BLACK)                      # bocca aperta felice
        mirror([(4, 16), (3, 15), (3, 14), (2, 13), (2, 12), (1, 11)], BLACK)  # braccia in su
        for x, y in [(2, 4), (1, 5), (2, 5), (3, 5), (2, 6), (29, 7), (28, 8), (29, 8), (30, 8), (29, 9)]:
            put(x, y, DARK)                                          # scintille
    if costume:
        vesti(g, put, body, costume)
    return g


# ---------------------------------------------------------------- costumi
CAPPELLI = {"halloween", "natale", "capodanno", "pasqua", "compleanno"}  # nascondono le antenne
COL = {"#": BLACK, "d": DARK, "m": MID, "l": LIGHT, "w": WHITE}


def stampa(put, x0, y0, rows):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in COL:
                put(x0 + x, y0 + y, COL[ch])


SANTA = ["..................###.", "............####.#www#", "..........##dddd##www#", "........##ddddddd####.",
         "......##dddddddddd#...", "....##dddddddddddddd#.", "...#dddddddddddddddd#.", "#wwwwwwwwwwwwwwwwwwww#",
         "######################"]
CILINDRO = ["..############..", "..#dddddddddd#..", "..#dddddddddd#..", "..#dddddddddd#..", "..#mmmmmmmmmm#..",
            "..#dddddddddd#..", "################"]
CONO = ["....##....", "....##....", "...#dd#...", "...#mm#...", "..#dddd#..", "..#mmmm#..", ".#dddddd#.",
        ".#mmmmmm#.", "##########"]
ORECCHIO = [".###.", "#lml#", "#lml#", "#lml#", "#lml#", "#lml#", "#lml#", "#lml#", ".#l#.", "..#.."]
OCCHIALI = ["#######..#######", "#ddddd####ddddd#", "#ddddd#..#ddddd#", ".#ddd#....#ddd#.", "..###......###.."]
MASCHERA = ["..################..", ".#dddddddddddddddd#.", "#dd....dddddd....dd#", "#dd....dddddd....dd#",
            "#dd....dddddd....dd#", ".#dddddddddddddddd#."]


def vesti(g, put, body, costume):
    """Aggiunge al folletto cappelli, occhiali, maschere e sciarpe."""
    if costume == "halloween":
        for x in range(4, 28):
            put(x, 8, BLACK)                                         # tesa
        for y, (a, b) in enumerate([(19, 21), (17, 19), (15, 18), (14, 17), (13, 18), (12, 19), (11, 20), (10, 21)]):
            for x in range(a, b + 1):
                put(x, y, BLACK)                                     # cono storto
        for x in range(11, 21):
            put(x, 6, MID)
        put(15, 6, WHITE); put(16, 6, WHITE)                         # fibbia
    elif costume == "natale":
        stampa(put, 5, 0, SANTA)
        for x, y in body:                                            # sciarpa
            if y in (24, 25) and g[y][x] == LIGHT:
                g[y][x] = DARK
        stampa(put, 20, 26, ["ddd", "ddd", "d.d", "d.d"])
    elif costume == "capodanno":
        stampa(put, 8, 1, CILINDRO)
    elif costume == "compleanno":
        stampa(put, 11, 0, CONO)
    elif costume == "pasqua":
        stampa(put, 8, 0, ORECCHIO); stampa(put, 19, 0, ORECCHIO)
    elif costume == "estate":
        stampa(put, 8, 15, OCCHIALI)
    elif costume == "carnevale":
        stampa(put, 6, 14, MASCHERA)
        stampa(put, 2, 15, ["###.", "...#"]); stampa(put, 26, 15, [".###", "#..."])  # nastrini
    elif costume == "liberazione":
        for x, y in body:                                            # fazzoletto al collo
            if y in (25, 26) and g[y][x] == LIGHT:
                g[y][x] = DARK
        stampa(put, 19, 24, ["###", "###", "###"])                    # nodo di lato
        stampa(put, 18, 27, ["dd.dd", "d...d", "d....d"])           # due lembi
    elif costume == "primomaggio":
        for y in range(13, 30):                                      # via braccia e faccia: si rilassa
            for x in range(N):
                if (x, y) in body:
                    if 8 <= x <= 23 and 14 <= y <= 25 and g[y][x] != LIGHT:
                        g[y][x] = LIGHT
                elif x < 5 or x > 26:
                    g[y][x] = None
        def mir(pts, v):
            for x, y in pts:
                put(x, y, v); put(N - 1 - x, y, v)
        mir([(9, 18), (10, 17), (11, 17), (12, 18)], BLACK)          # occhi chiusi beati
        mir([(13, 21), (14, 22), (15, 22)], BLACK)                   # sorrisone
        mir([(4, 17), (3, 16), (3, 15), (4, 14), (5, 13), (6, 12)], BLACK)  # mani dietro la testa


BAT = ["#..........#", "##...##...##", "############", ".##########.", "..##.##.##..", "...#....#..."]
PUMPKIN = ["....##....", "..dddddd..", ".dwwddwwd.", "dddddddddd", "ddwdwdwddd", ".dddddddd.", "..dddddd.."]
FIOCCO = [".d.", "ddd", ".d."]
CUORE = [".dd.dd.", "ddddddd", "ddddddd", ".ddddd.", "..ddd..", "...d..."]
UOVO = ["..###..", ".#lll#.", "#lllll#", "#dldld#", "#lllll#", ".#lll#.", "..###.."]
FIORE = [".d.d.", "ddmdd", ".ddd.", "..#..", "..#..", "..#.."]
SOLE = ["d...d...d", ".d.....d.", "...ddd...", "..ddddd..", "dddddddd.", "..ddddd..", "...ddd...", ".d.....d.",
        "d...d...d"]
TORTA = ["....m....", "...#m#...", "....#....", ".#######.", "#lllllll#", "#dmdmdmd#", "#lllllll#", "#########"]
STELLA_F = ["d.....", ".d...d", "..d.d.", "...d..", "..d...", ".d...."]


def accessori(c, ox, oy, scale, costume):
    """Disegna gli accessori intorno al folletto."""
    size = N * scale
    p = max(4, scale // 2 + 1)

    def disegna(rows, x0, y0, q=p):
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch in COL:
                    c.rect(x0 + x * q, y0 + y * q, q, q, COL[ch])

    alto_sx = (ox - 10 * p, oy + 2 * scale)
    basso_sx = (ox - 8 * p, oy + size - 8 * p)
    if costume == "halloween":
        disegna(BAT, *alto_sx); disegna(PUMPKIN, *basso_sx)
    elif costume == "natale":
        for fx, fy in ((-0.25, 0.1), (-0.15, 0.55), (1.08, 0.3), (-0.3, 0.85)):
            disegna(FIOCCO, int(ox + fx * size), int(oy + fy * size))
    elif costume in ("capodanno", "compleanno"):
        for i, (fx, fy) in enumerate(((-0.25, 0.05), (-0.12, 0.35), (1.05, 0.15), (-0.3, 0.6), (1.1, 0.5), (-0.18, 0.8))):
            c.rect(int(ox + fx * size), int(oy + fy * size), p + (i % 2) * 2, p, DARK if i % 2 else MID)
        if costume == "compleanno":
            disegna(TORTA, *basso_sx)
    elif costume == "carnevale":
        disegna(STELLA_F, *alto_sx); disegna(STELLA_F, alto_sx[0] + 2 * p, basso_sx[1])
    elif costume == "sanvalentino":
        disegna(CUORE, *alto_sx); disegna(CUORE, basso_sx[0], basso_sx[1] - 4 * p, max(3, p - 1))
    elif costume == "pasqua":
        disegna(UOVO, *basso_sx)
    elif costume == "liberazione":
        q = p + 1
        disegna(FIORE, ox + 23 * scale - 2 * q - q // 2, oy + 3 * scale - 6 * q, q)
    elif costume == "primomaggio":
        ts = 2 if scale >= 6 else 1                                  # cartellino appeso al collo
        sw, sh = int(size * 0.62), 12 * ts + 14
        sx, sy = ox + (size - sw) // 2, oy + int(size * 0.70)
        for i in range(6):
            c.rect(sx + 10 + i * 3, sy - 6 - i * 4, 3, 3, DARK)
            c.rect(sx + sw - 13 - i * 3, sy - 6 - i * 4, 3, 3, DARK)
        c.rect(sx, sy, sw, sh, WHITE); c.frame(sx, sy, sw, sh, 3, BLACK)
        c.text("CHIUSO", sx + sw // 2, sy + (sh - 7 * ts) // 2, ts, align="center")
    elif costume == "estate":
        disegna(SOLE, *alto_sx)


def pasqua(anno):
    """Data della Pasqua (calendario gregoriano)."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = (h + l - 7 * m + 114) % 31 + 1
    return datetime.date(anno, mese, giorno)


COSTUMI = [  # (mese inizio, giorno inizio, mese fine, giorno fine, costume) — date fisse
    (1, 1, 1, 1, "capodanno"), (12, 31, 12, 31, "capodanno"),
    (2, 14, 2, 14, "sanvalentino"),
    (4, 25, 4, 25, "liberazione"),
    (5, 1, 5, 1, "primomaggio"),
    (10, 25, 10, 31, "halloween"),
    (12, 1, 12, 26, "natale"),
    (7, 1, 8, 31, "estate"),
]


def costume_for(now):
    oggi = datetime.date.fromtimestamp(now)
    if COMPLEANNO and (oggi.month, oggi.day) == tuple(COMPLEANNO):
        return "compleanno"
    p = pasqua(oggi.year)
    if p - datetime.timedelta(days=2) <= oggi <= p + datetime.timedelta(days=1):
        return "pasqua"
    if p - datetime.timedelta(days=52) <= oggi <= p - datetime.timedelta(days=47):
        return "carnevale"
    for m1, g1, m2, g2, nome in COSTUMI:
        if (m1, g1) <= (oggi.month, oggi.day) <= (m2, g2):
            return nome
    return None


MOODS = {
    "happy": "TUTTO TRANQUILLO",
    "focused": "CONCENTRATO",
    "sweaty": "SI SUDA...",
    "sleepy": "PAUSA FORZATA",
    "waking": "SI RIPARTE!",
    "nodata": "NESSUN DATO",
}


# ---------------------------------------------------------------- pensieri
PENSIERI_FILE = os.path.expanduser("~/.claude/folletto/pensieri.txt")  # una frase per riga
OGNI_MINUTI = 20        # ogni quanto cambia il pensiero
PROBABILITA = 0.7       # quante volte su 10 compare il fumetto

PENSIERI = {
    "sempre": [
        "Una cosa alla volta.", "Fatto è meglio di perfetto.", "Hai già fatto più di quanto pensi.",
        "Il primo schizzo serve solo a sbagliare.", "Stai andando forte.", "Respira. Le spalle giù.",
        "Ogni pixel conta, ma non tutti oggi.", "Domanda stupida? Non esiste.", "Sgranchisci le gambe!",
        "Guarda lontano per venti secondi.", "Ricordati di bere.", "Sei forte in quello che fai.",
        "Semplifica. Poi semplifica ancora.", "Un bug è solo una sorpresa.", "Io tifo per te.",
    ],
    "mattina": ["Buongiorno! Che si crea oggi?", "Caffè fatto? Allora si parte.", "Mattina fresca, idee fresche."],
    "pranzo": ["Pausa pranzo? Io dico di sì.", "Il cervello va a carboidrati."],
    "pomeriggio": ["Calo delle tre? Alzati un attimo.", "Ultimo sprint, poi tè."],
    "sera": ["È tardi. Il lavoro aspetta.", "Spegni tutto, domani è un altro giorno."],
    "happy": ["C'è tanto spazio ancora!", "Oggi si vola."],
    "focused": ["Zona di concentrazione attiva.", "Bello ritmo, continua così."],
    "sweaty": ["Rallentiamo un pochino?", "Bevi un bicchiere d'acqua, io intanto sudo."],
    "sleepy": ["Pausa forzata = pausa meritata.", "Fai due passi, io ricarico."],
    "waking": ["Eccomi! Pieno di energia.", "Si riparte, andiamo?"],
    "halloween": ["Dolcetto o scherzetto?", "Bu! Spaventato il tuo bug?", "Questo bug fa più paura di un fantasma.",
                  "Zucca carica, si lavora.", "Stanotte si vola sulla scopa."],
    "natale": ["Oh oh oh! Lista dei regali fatta?", "Panettone o pandoro? Scelta difficile.", "Sciarpa su, si lavora."],
    "capodanno": ["Buon anno! Si riparte da zero.", "Nuovo anno, nuovi pixel.", "Propositi? Uno: bere più acqua."],
    "sanvalentino": ["Ti voglio bene, anche senza cioccolatini.", "Un cuore per ogni bug risolto."],
    "carnevale": ["A carnevale ogni bug vale!", "Chi c'è dietro la maschera? Io!"],
    "pasqua": ["Buona Pasqua! Hai trovato l'ovetto?", "Orecchie da coniglio attivate."],
    "liberazione": ["Bella ciao!", "Buon 25 aprile!", "Ora e sempre libertà."],
    "primomaggio": ["Oggi il folletto sciopera.", "Buon primo maggio!", "Chiuso per festa."],
    "estate": ["Crema solare messa?", "Pensa al mare, manca poco.", "Troppo caldo per i bug."],
    "compleanno": ["Tanti auguri!", "Oggi si festeggia te!", "Torta pronta, candelina accesa."],
}


def pensiero(now, mood):
    """Sceglie un pensiero che resta uguale per OGNI_MINUTI minuti (o None: niente fumetto)."""
    import random
    t = time.localtime(now)
    slot = int(now // (OGNI_MINUTI * 60))
    rng = random.Random(slot)
    if appena_finito(now):
        return random.Random(int(_meeting["finito_alle"])).choice(FINE_MEETING)
    if mood in ("waking", "sleepy"):
        pass  # in questi momenti il folletto parla sempre
    elif rng.random() > PROBABILITA:
        return None
    pool = list(PENSIERI["sempre"])
    h = t.tm_hour
    momento = "mattina" if 7 <= h < 11 else "pranzo" if 12 <= h < 14 else \
        "pomeriggio" if 14 <= h < 18 else "sera" if h >= 19 or h < 5 else None
    if momento:
        pool += PENSIERI[momento] * 2
    pool += PENSIERI.get(mood, []) * (4 if mood in ("sweaty", "sleepy", "waking") else 2)
    tema = costume_for(now)
    if tema:
        pool += PENSIERI.get(tema, []) * 4
        if tema == "compleanno" and NOME:
            pool += [f"Tanti auguri, {NOME}!"] * 4
    try:
        with open(PENSIERI_FILE, encoding="utf-8") as f:
            pool += [r.strip() for r in f if r.strip() and not r.startswith("#")] * 2
    except OSError:
        pass
    return rng.choice(pool)


def a_capo(testo, max_chars):
    righe, riga = [], ""
    for parola in testo.split():
        prova = f"{riga} {parola}".strip()
        if len(prova) <= max_chars:
            riga = prova
        else:
            if riga:
                righe.append(riga)
            riga = parola[:max_chars]
    if riga:
        righe.append(riga)
    return righe[:4]


def fumetto(c, testo, cx, top, width, scale, punta_x):
    """Disegna un fumetto bianco con bordo nero, centrato in cx, con la punta verso il folletto."""
    max_chars = (width - 32) // (6 * scale)
    righe = a_capo(testo, max_chars)
    lh = 10 * scale
    h = len(righe) * lh + 24
    x = cx - width // 2
    c.rect(x + 4, top, width - 8, h, WHITE)
    c.rect(x, top + 4, width, h - 8, WHITE)
    c.rect(x + 4, top, width - 8, 3, BLACK); c.rect(x + 4, top + h - 3, width - 8, 3, BLACK)
    c.rect(x, top + 4, 3, h - 8, BLACK); c.rect(x + width - 3, top + 4, 3, h - 8, BLACK)
    for dx, dy in ((1, 1), (2, 2)):  # angoli smussati
        c.rect(x + 3 - dx + 1, top + 4 - dy, 2, 2, BLACK); c.rect(x + width - 5 + dx - 1, top + 4 - dy, 2, 2, BLACK)
        c.rect(x + 3 - dx + 1, top + h - 6 + dy, 2, 2, BLACK); c.rect(x + width - 5 + dx - 1, top + h - 6 + dy, 2, 2, BLACK)
    for i in range(6):  # punta a triangolo verso il basso
        half, y = 15 - i * 3, top + h - 3 + i * 3
        c.rect(punta_x - half, y, 2 * half, 3, WHITE)
        c.rect(punta_x - half - 3, y, 3, 3, BLACK)
        c.rect(punta_x + half, y, 3, 3, BLACK)
    for i, r in enumerate(righe):
        c.text(r, cx, top + 12 + i * lh, scale, align="center")
    return h


# ---------------------------------------------------------------- meeting (calendario)
import re
import shutil
import subprocess
import threading

_CERCA = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]


def _trova(cmd):
    return shutil.which(cmd, path=os.pathsep.join(_CERCA + [os.environ.get("PATH", "")]))


_meeting = {"checked": 0.0, "info": None, "finito_alle": 0.0}
_lock = threading.Lock()


def meeting_ora(now=None):
    """Ritorna {"inizio": epoch, "fine": "HH:MM"} se c'è un evento in corso nel Calendario, altrimenti None.
    Usa icalBuddy (brew install ical-buddy). Il risultato resta in cache per un minuto."""
    now = now or time.time()
    with _lock:
        if now - _meeting["checked"] < 60:
            return _meeting["info"]
    info = None
    ib = _trova("icalBuddy")
    if ib:
        try:
            out = subprocess.run([ib, "-ea", "-nc", "-nrd", "-b", "", "-iep", "datetime", "-tf", "%H:%M",
                                  "eventsNow"], capture_output=True, text=True, timeout=10).stdout
            orari = re.findall(r"\b(\d{1,2}:\d{2})\b", out)
            if orari:
                h, m = map(int, orari[0].split(":"))
                t = time.localtime(now)
                inizio = time.mktime((t.tm_year, t.tm_mon, t.tm_mday, h, m, 0, 0, 0, -1))
                if inizio > now:          # evento iniziato ieri o formato strano
                    inizio = now
                info = {"inizio": inizio, "fine": orari[-1]}
        except (OSError, subprocess.SubprocessError, ValueError):
            info = None
    with _lock:
        if _meeting["info"] and not info:
            _meeting["finito_alle"] = now
        _meeting["info"], _meeting["checked"] = info, now
    return info


def appena_finito(now):
    with _lock:
        return _meeting["finito_alle"] and now - _meeting["finito_alle"] < 10 * 60


FINE_MEETING = ["Finito! Era proprio necessaria quella call?", "Meeting finito. Guarda che capolavoro ho fatto!",
                "Libera! Torniamo a creare."]

# ---------------------------------------------------------------- dati
def _epoch(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def read_state(now):
    try:
        with open(STATE) as f:
            s = json.load(f)
    except (OSError, ValueError):
        return None

    def window(w):
        if not w or w.get("used_percentage") is None:
            return None
        reset = _epoch(w.get("resets_at"))
        done = reset is not None and reset <= now
        return {"pct": 0 if done else int(w["used_percentage"]), "reset": reset, "just_reset": done}

    return {"five": window(s.get("five_hour")), "week": window(s.get("seven_day")),
            "updated": s.get("updated_at")}


def mood_for(five):
    if five is None:
        return "nodata"
    if five["just_reset"]:
        return "waking"
    p = five["pct"]
    return "happy" if p < 50 else "focused" if p < 70 else "sweaty" if p < 90 else "sleepy"


# ---------------------------------------------------------------- disegno
# ---------------------------------------------------------------- scarabocchi in meeting
SCARABOCCHI = [
    ["111111111", "100000001", "101111101", "101000101", "101010101", "101000101", "101111101", "100000001", "111111111"],
    ["000010000", "000111000", "111111111", "011111110", "001111100", "011101110", "110000011"],
    ["000010000", "000101000", "001000100", "010000010", "111111111", "100000001", "100110001", "100110001", "111111111"],
    ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"],
    ["0011100000", "0100010110", "1000001001", "1000000001", "0111111110"],
    ["100010001", "010101010", "001000100"],
    ["0011100", "0100010", "1001001", "1011101", "1001001", "0100010", "0011100"],
    ["001111111", "010000011", "111111101", "100000101", "100000101", "100000110", "111111100"],
    ["101010101", "010101010", "101010101"],
    ["0000001", "0000010", "0000100", "0101000", "0010000", "0101000"],
    ["0001000", "0010100", "0100010", "1000001", "0100010", "0010100", "0001000"],
    ["111111", "100001", "101101", "101101", "100001", "111111"],
    ["01110", "10001", "10101", "10001", "01110"],
    ["1000001", "0100010", "0011100", "0011100", "0100010", "1000001"],
]
POSTI = [(col, riga) for riga in range(4) for col in range(4)]  # celle del quaderno (4 x 4)


def folletto_meeting(costume):
    g = folletto("focused", costume)
    for y in range(14, 25):                       # pulisco la faccia
        for x in range(8, 24):
            if g[y][x] in (BLACK, MID):
                g[y][x] = LIGHT

    def mir(pts, v):
        for x, y in pts:
            g[y][x] = v; g[y][N - 1 - x] = v
    mir([(9, 17), (10, 17), (11, 17), (12, 17)], BLACK)   # palpebre basse
    mir([(10, 19), (11, 19), (10, 20), (11, 20)], BLACK)  # occhi sul foglio
    for x in range(14, 17):
        g[22][x] = BLACK
    g[23][17] = MID; g[23][18] = MID; g[24][17] = MID     # linguetta di concentrazione
    return g


def scena_meeting(c, cx, top, larghezza, altezza, info, now, costume):
    """Folletto dietro un quaderno che si riempie di scarabocchi man mano che il meeting va avanti."""
    import random
    bh = fumetto(c, f"Shh, sei in meeting. Fino alle {info['fine']}", cx, top, min(300, larghezza), 2, cx)
    scale = 5
    size = N * scale
    ox, oy = cx - size // 2, top + bh + 26
    for y, row in enumerate(folletto_meeting(costume)):
        for x, v in enumerate(row):
            if v is not None:
                c.rect(ox + x * scale, oy + y * scale, scale, scale, v)
    accessori(c, ox, oy, scale, costume)
    sw = min(304, larghezza)
    sx, sy = cx - sw // 2, oy + size - 40
    sh = max(120, top + altezza - sy)
    c.rect(sx + 6, sy + 6, sw, sh, MID)
    c.rect(sx, sy, sw, sh, WHITE); c.frame(sx, sy, sw, sh, 3, BLACK)
    for ly in range(sy + 34, sy + sh - 6, 30):
        c.rect(sx + 10, ly, sw - 20, 1, 0xCC)
    minuti = max(0, int((now - info["inizio"]) // 60))
    rng = random.Random(int(info["inizio"]))       # ogni meeting ha il suo foglio
    ordine = rng.sample(range(len(SCARABOCCHI)), len(SCARABOCCHI))
    posti = rng.sample(POSTI, len(POSTI))
    for i in range(min(len(ordine), len(posti), 1 + minuti // 5)):
        d = SCARABOCCHI[ordine[i]]
        col, riga = posti[i]
        cw, ch = (sw - 24) // 4, (sh - 24) // 4
        dw, dh = len(d[0]) * 5, len(d) * 5
        x0 = sx + 12 + col * cw + rng.randint(0, max(0, cw - dw))
        y0 = sy + 12 + riga * ch + rng.randint(0, max(0, ch - dh))
        for gy, row in enumerate(d):
            for gx, bit in enumerate(row):
                if bit == "1":
                    c.rect(x0 + gx * 5, y0 + gy * 5, 5, 5, DARK)
    for i in range(10):                            # matita in mano
        c.rect(ox + size - 30 - i * 5, sy - 26 + i * 6, 7, 7, BLACK if i < 8 else DARK)


def render(now=None, state=None, mood=None, orient="verticale", costume="auto", render_meeting=True):
    """orient: "verticale", "destra" (porta di ricarica a destra), "sinistra"."""
    now = now or time.time()
    state = state if state is not None else read_state(now)
    landscape = orient in ("destra", "sinistra")
    c = Canvas(H, W) if landscape else Canvas(W, H)
    five = state and state["five"]
    week = state and state["week"]
    mood = mood or mood_for(five)

    def section(x, y, width, label, win, fmt):
        c.text(label, x, y, 3)
        c.text(f"{win['pct']}%" if win else "--", x + width, y - 12, 6, align="right")
        bx, by, bw, bh = x, y + 44, width, 40
        c.frame(bx, by, bw, bh, 4, BLACK)
        if win:
            fill = (bw - 16) * min(win["pct"], 100) // 100
            c.rect(bx + 8, by + 8, fill, bh - 16, BLACK if win["pct"] >= 90 else DARK)
        when = time.strftime(fmt, time.localtime(win["reset"])) if win and win["reset"] else "--"
        text = f"AZZERATO ALLE {when}" if win and win["just_reset"] else f"RESET {when}"
        c.text(text, x, by + bh + 12, 2, DARK)

    if costume == "auto":
        costume = costume_for(now)
    meeting = meeting_ora(now) if render_meeting else None
    if meeting:
        if landscape:
            section(36, 70, 400, "SESSIONE 5 ORE", five, "%H:%M")
            section(36, 250, 400, "SETTIMANALE", week, "%d/%m %H:%M")
            c.rect(472, 50, 2, 500, MID)
            scena_meeting(c, 472 + (c.w - 472) // 2, 16, 310, 560, meeting, now, costume)
            foot_x, foot_y = 36 + 200, c.h - 56
        else:
            section(40, 40, W - 80, "SESSIONE 5 ORE", five, "%H:%M")
            section(40, 190, W - 80, "SETTIMANALE", week, "%d/%m %H:%M")
            c.rect(40, 342, W - 80, 2, MID)
            scena_meeting(c, c.w // 2, 360, 480, 410, meeting, now, costume)
            foot_x, foot_y = c.w // 2, c.h - 24
    else:
        pensa = pensiero(now, mood) if mood != "nodata" else None
        if landscape:
            # barre a sinistra, folletto (con fumetto) a destra
            section(36, 70, 400, "SESSIONE 5 ORE", five, "%H:%M")
            section(36, 250, 400, "SETTIMANALE", week, "%d/%m %H:%M")
            c.rect(472, 50, 2, 500, MID)
            col_cx = 472 + (c.w - 472) // 2
            scale = 7
            oy = 200 if pensa else 130
            if pensa:
                bh = fumetto(c, pensa, col_cx, 30, 300, 2, col_cx)
                oy = max(oy, 30 + bh + 30)
            ox = col_cx - N * scale // 2
            caption_scale, foot_x, foot_y = 3, 36 + 200, c.h - 56
        else:
            section(40, 40, W - 80, "SESSIONE 5 ORE", five, "%H:%M")
            section(40, 190, W - 80, "SETTIMANALE", week, "%d/%m %H:%M")
            c.rect(40, 342, W - 80, 2, MID)
            col_cx = c.w // 2
            scale = 8 if pensa else 9
            oy = 368
            if pensa:
                bh = fumetto(c, pensa, col_cx, 360, 480, 2, col_cx)
                oy = 360 + bh + 30
            ox = col_cx - N * scale // 2
            caption_scale, foot_x, foot_y = 3 if pensa else 4, col_cx, c.h - 30

        for y, row in enumerate(folletto("sleepy" if mood == "nodata" else mood, costume)):
            for x, v in enumerate(row):
                if v is not None:
                    c.rect(ox + x * scale, oy + y * scale, scale, scale, v)
        accessori(c, ox, oy, scale, costume)
        if mood in ("sleepy", "nodata") and not pensa:
            zx = ox + N * scale - (60 if landscape else 20) + (40 if costume else 0)
            c.text("Z", zx, oy + 70, 5, DARK)
            c.text("Z", zx + 38, oy + 25, 3, MID)
        c.text(MOODS[mood], col_cx, oy + N * scale + 18, caption_scale, align="center")


    if state and state.get("updated"):
        mins = int((now - state["updated"]) // 60)
        foot = "AGGIORNATO ORA" if mins < 1 else f"AGGIORNATO {mins} MIN FA" if mins < 120 \
            else "AGGIORNATO " + time.strftime("%d/%m %H:%M", time.localtime(state["updated"]))
        c.text(foot, foot_x, foot_y, 2, MID, align="center")

    if landscape:
        # Kindle girato con la porta a destra = immagine ruotata in senso orario
        c = c.rotated(clockwise=(orient == "destra"))
    return c.png()


PAGE = b"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=120>
<title>Folletto</title><style>body{margin:0;background:#eee;font:14px sans-serif;display:flex;
flex-wrap:wrap;gap:40px;justify-content:center;padding:30px}figure{margin:0;text-align:center}
.land{width:800px;height:600px;overflow:hidden}.land img{transform-origin:0 0}
.sx img{transform:translate(800px,0) rotate(90deg)}.dx img{transform:translate(0,600px) rotate(-90deg)}
</style>
<figure><div class="land sx"><img src="/dash.png?o=sinistra"></div><figcaption>Orizzontale, porta a sinistra</figcaption></figure>
<figure><img src="/dash.png"><figcaption>Verticale</figcaption></figure>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/dash.png"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            orient = q.get("o", ["verticale"])[0]
            body, ctype = render(orient=orient), "image/png"
        elif self.path in ("/", "/index.html"):
            body, ctype = PAGE, "text/html; charset=utf-8"
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--png":
        sys.stdout.buffer.write(render())
    elif len(sys.argv) > 1 and sys.argv[1] == "--prova-meeting":
        print("Meeting in corso:", meeting_ora() or "nessuno (o icalBuddy non installato / senza permesso)")
    else:
        print(f"Dashboard su http://0.0.0.0:{PORT}/  (Ctrl+C per fermare)")
        http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
