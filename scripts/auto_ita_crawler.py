import os
import re
import json
import requests
import pymupdf as fitz
from pathlib import Path
from collections import Counter

EXAM_YEAR = os.getenv("EXAM_YEAR", "2026").strip()
INCLUDE_LANGUAGES = os.getenv("INCLUDE_LANGUAGES", "true").lower() == "true"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "images"
DB_FILE = DATA_DIR / "questions.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

TOPIC_RULES = {
    "Matemática": [
        ("Números Complexos", "Argand-Gauss, Módulo e Raízes", [r"complexo", r"argand", r"imagin[áa]ri", r"conjugado"]),
        ("Polinômios e Equações", "Raízes, Girard e Multiplicidade", [r"polin[ôo]mio", r"ra[íi]zes", r"coeficientes reais", r"divis[íi]vel"]),
        ("Geometria Espacial", "Poliedros, Esferas, Cones e Cilindros", [r"poliedro", r"v[ée]rtices", r"arestas", r"faces", r"tetraedro", r"pir[âa]mide", r"esfera", r"cilindro", r"cone", r"revolu[çc][ãa]o"]),
        ("Geometria Analítica", "Cônicas, Retas e Circunferências", [r"elipse", r"hip[ée]rbole", r"par[áa]bola", r"cartesiano", r"circunfer[êe]ncia", r"foco", r"excentricidade"]),
        ("Matrizes e Sistemas", "Determinantes, Inversas e Discussão", [r"matriz", r"determinante", r"sistema linear", r"transposta", r"inversa"]),
        ("Combinatória e Probabilidade", "Contagem, Binômio e Probabilidade", [r"termo independente", r"expans[ãa]o", r"probabilidade", r"escolh", r"anagrama"]),
        ("Funções e Logaritmos", "Injetora, Sobrejetora, PA/PG e Log", [r"injetora", r"sobrejetora", r"bijetora", r"progress[ãa]o", r"\blog", r"fun[çc][ãa]o"]),
        ("Geometria Plana e Trigonometria", "Triângulos, Polígonos e Funções Trigonométricas", [r"tri[âa]ngulo", r"\bsen", r"\bcos", r"tangente", r"circunscrit", r"inscrit", r"hexagrama", r"corda"])
    ],
    "Física": [
        ("Mecânica Clássica", "Cinemática, Dinâmica, Energia e Colisões", [r"bloco", r"cunha", r"atrito", r"mola", r"acelera[çc][ãa]o", r"colis[ãa]o", r"centro de massa", r"proj[ée]til", r"p[êe]ndulo"]),
        ("Gravitação e Hidrostática", "Órbitas, Kepler, Empuxo e Vasos Comunicantes", [r"planeta", r"[óo]rbita", r"gravit", r"empuxo", r"fluido", r"tanque", r"vaso comunicante", r"submers"]),
        ("Termodinâmica", "Gases Ideais, Ciclos, Êmbolo e Calorimetria", [r"g[áa]s ideal", r"adiab[áa]tic", r"isot[ée]rmic", r"carnot", r"calor", r"temperatura", r"[êe]mbolo"]),
        ("Óptica e Ondulatória", "Refração, Lentes, Interferência e Acústica", [r"arco-[íi]ris", r"refra[çc][ãa]o", r"lente", r"espelho", r"onda", r"frequ[êe]ncia", r"doppler", r"interfer[êe]ncia", r"estetosc[óo]pio"]),
        ("Eletromagnetismo", "Circuitos, Potenciômetro, Campo Magnético e Indução", [r"resistor", r"capacitor", r"corrente", r"magn[ée]tic", r"el[ée]tric", r"carga", r"espira", r"potenci[ôo]metro", r"volt[íi]metro", r"[íi]m[ãa]"]),
        ("Física Moderna", "Relatividade, Fótons e Quântica", [r"f[óo]ton", r"planck", r"relatividad", r"decaimento", r"foguete", r"simult[âa]neo"])
    ],
    "Química": [
        ("Físico-Química: Equilíbrio", "Kc, Kp, pH, Tampão e Solubilidade", [r"equil[íi]brio", r"\bph\b", r"ioniza", r"solubilidade", r"tamp[ãa]o", r"hidr[óo]lise"]),
        ("Eletroquímica", "Pilhas, Nernst, Potencial e Eletrólise", [r"pilha", r"eletr[óo]lise", r"potencial", r"[âa]nodo", r"c[áa]todo", r"oxida[çc][ãa]o", r"galv[âa]nica"]),
        ("Termoquímica e Cinética", "Entalpia, Gibbs, Entropia e Velocidade", [r"entalpia", r"exot[ée]rmic", r"endot[ée]rmic", r"velocidade", r"ativa[çc][ãa]o", r"gibbs"]),
        ("Química Orgânica", "Isomeria, Funções, Reações e Polímeros", [r"org[âa]nic", r"is[ôo]mero", r"carbono", r"[ée]ster", r"amina", r"pol[íi]mero", r"arom[áa]tic", r"cadeia"]),
        ("Química Geral e Inorgânica", "Estequiometria, Gases, Soluções e Estrutura", [r"estequiometr", r"\bmol\b", r"massa molar", r"geometria molecular", r"hibridiza", r"rea[çc][ãa]o", r"solu[çc][ãa]o"])
    ],
    "Inglês": [
        ("Reading Comprehension & Vocabulary", "Interpretação Textual e Gramática Aplicada", [r"the", r"text", r"author", r"paragraph"])
    ],
    "Português": [
        ("Literatura e Interpretação", "Obras Literárias, Gramática e Estilística", [r"texto", r"autor", r"narrador", r"poema", r"romance"])
    ]
}

def clean_ita_text(raw: str) -> str:
    """Une todos os acentos desmembrados pelo pdflatex do ITA (ex: 'Quest ˜ao' -> 'Questão')."""
    text = raw
    accent_patterns = [
        (r"\s*[˜~]\s*a", "ã"), (r"\s*[˜~]\s*o", "õ"),
        (r"\s*[˜~]\s*A", "Ã"), (r"\s*[˜~]\s*O", "Õ"),
        (r"\s*´\s*a", "á"), (r"\s*´\s*e", "é"), (r"\s*´\s*[ıi]", "í"),
        (r"\s*´\s*o", "ó"), (r"\s*´\s*u", "ú"),
        (r"\s*´\s*A", "Á"), (r"\s*´\s*E", "É"), (r"\s*´\s*[IÍ]", "Í"),
        (r"\s*´\s*O", "Ó"), (r"\s*´\s*U", "Ú"),
        (r"\s*ˆ\s*a", "â"), (r"\s*ˆ\s*e", "ê"), (r"\s*ˆ\s*o", "ô"),
        (r"\s*ˆ\s*A", "Â"), (r"\s*ˆ\s*E", "Ê"), (r"\s*ˆ\s*O", "Ô"),
        (r"\s*`\s*a", "à"),
        (r"c\s*¸\s*", "ç"), (r"\s*¸\s*c", "ç"),
        (r"C\s*¸\s*", "Ç"), (r"\s*¸\s*C", "Ç"),
        (r"ı", "í")
    ]
    for pat, repl in accent_patterns:
        text = re.sub(pat, repl, text)
    text = re.sub(r"Quest\s+[ãa]o", "Questão", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def classify_topic(materia: str, text: str) -> tuple[str, str]:
    rules = TOPIC_RULES.get(materia, [])
    lower_text = text.lower()
    for topico, subtopico, patterns in rules:
        for pat in patterns:
            if re.search(pat, lower_text):
                return topico, subtopico
    return f"{materia} Geral", "Tópicos Integrados do Edital"

def get_subject(year: int, q_num: int) -> str:
    if year >= 2025:
        if 1 <= q_num <= 12: return "Matemática"
        if 13 <= q_num <= 24: return "Física"
        if 25 <= q_num <= 36: return "Química"
        return "Inglês"
    else:
        if 1 <= q_num <= 12: return "Física"
        if 13 <= q_num <= 24: return "Português"
        if 25 <= q_num <= 36: return "Inglês"
        if 37 <= q_num <= 48: return "Matemática"
        return "Química"

def fetch_pdf(urls: list[str], dest: Path) -> bool:
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200 and len(r.content) > 8_000 and r.content[:4] == b"%PDF":
                dest.write_bytes(r.content)
                print(f"  ✓ Baixado: {url}")
                return True
        except Exception:
            pass
    return False

def parse_gabarito_pdf(gab_pdf: Path) -> dict[int, str]:
    if not gab_pdf.exists():
        return {}
    doc = fitz.open(gab_pdf)
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    gab_map = {}
    for num_str, ans in re.findall(r"\b(\d{1,2})\s*[\.\-]?\s*([A-E]|\(\*+\))", text):
        q_num = int(num_str)
        if 1 <= q_num <= 60 and q_num not in gab_map:
            gab_map[q_num] = "ANULADA" if "*" in ans else ans
    return gab_map

def extract_question_figures(doc: fitz.Document, year: str) -> dict[int, str]:
    """Recorta automaticamente figuras e diagramas vetoriais no intervalo vertical de cada questão."""
    q_figures = {}
    for page in doc:
        blocks = page.get_text("blocks")
        q_anchors = []
        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            cleaned = clean_ita_text(text)
            m = re.search(r"Quest(?:ão|ao)\s*(\d{1,2})\s*[\.\-]", cleaned, re.IGNORECASE)
            if m:
                q_anchors.append((int(m.group(1)), y0, y1, cleaned))

        q_anchors.sort(key=lambda item: item[1])
        if not q_anchors:
            continue

        graphic_rects = []
        for img_info in page.get_images(full=True):
            for r in page.get_image_rects(img_info[0]):
                if r.width > 45 and r.height > 35 and r.y0 > 50:
                    graphic_rects.append(r)

        try:
            for d_rect in page.cluster_drawings():
                if 55 < d_rect.width < page.rect.width * 0.94 and 38 < d_rect.height < page.rect.height * 0.70 and d_rect.y0 > 50:
                    graphic_rects.append(d_rect)
        except Exception:
            pass

        for idx, (q_num, y_start, _, _) in enumerate(q_anchors):
            y_end = q_anchors[idx + 1][1] if idx + 1 < len(q_anchors) else page.rect.height - 30
            matching = [r for r in graphic_rects if (r.y0 >= y_start - 12 and r.y1 <= y_end + 15)]
            if matching:
                union_r = matching[0]
                for mr in matching[1:]:
                    union_r |= mr
                pad = 8
                clip = fitz.Rect(
                    max(0, union_r.x0 - pad),
                    max(0, union_r.y0 - pad),
                    min(page.rect.width, union_r.x1 + pad),
                    min(page.rect.height, union_r.y1 + pad)
                )
                pix = page.get_pixmap(clip=clip, dpi=220)
                fname = f"ita_{year}_q{q_num:02d}.png"
                pix.save(str(IMG_DIR / fname))
                q_figures[q_num] = f"data/images/{fname}"
    return q_figures

def parse_exam(prova_pdf: Path, year: str, gab_map: dict[int, str]) -> list[dict]:
    doc = fitz.open(prova_pdf)
    q_figures = extract_question_figures(doc, year)
    raw_pages = "\n".join(page.get_text("text") for page in doc)
    doc.close()

    full_text = clean_ita_text(raw_pages)
    year_int = int(year)

    q_pattern = re.compile(
        r"Quest(?:ão|ao)\s*(\d{1,2})\s*[\.\-]\s*(.*?)(?=Quest(?:ão|ao)\s*\d{1,2}\s*[\.\-]|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    questions = []
    for num_str, raw_body in q_pattern.findall(full_text):
        q_num = int(num_str)
        materia = get_subject(year_int, q_num)
        if not INCLUDE_LANGUAGES and materia in ("Inglês", "Português"):
            continue

        parts = re.split(r"(?:^|\n|\s)([A-E])\s*\(\s*\)\s*", raw_body.strip())
        enunciado = parts[0].strip()
        alternativas = {k: "Consulte o enunciado / figura" for k in ("A", "B", "C", "D", "E")}
        if len(parts) >= 11:
            for i in range(1, len(parts) - 1, 2):
                letter = parts[i].upper()
                alt_text = parts[i + 1].strip()
                if letter == "E":
                    alt_text = re.sub(r"\n\s*\d{1,2}\s*$", "", alt_text).strip()
                    alt_text = re.sub(r"\n\s*(?:FÍSICA|QUÍMICA|MATEMÁTICA|INGLÊS|PORTUGUÊS).*$", "", alt_text, flags=re.DOTALL | re.IGNORECASE).strip()
                if letter in alternativas:
                    alternativas[letter] = alt_text

        topico, subtopico = classify_topic(materia, enunciado)
        gabarito = gab_map.get(q_num, "A")

        questions.append({
            "id": f"ITA-{year}-1F-Q{q_num:02d}",
            "ano": year_int,
            "fase": "1ª Fase",
            "numero": q_num,
            "materia": materia,
            "topico": topico,
            "subtopico": subtopico,
            "dificuldade": "Difícil",
            "enunciado": enunciado,
            "figura": q_figures.get(q_num),
            "alternativas": alternativas,
            "gabarito": gabarito,
            "pulo_do_gato": "Use '✨ Copiar Prompt p/ Gemini Pro' para gerar a resolução passo a passo em LaTeX.",
            "resolucao": (
                f"Gabarito Oficial ITA {year}: Alternativa {gabarito}."
                if gabarito != "ANULADA"
                else f"Questão Oficialmente ANULADA pela banca do ITA {year}."
            )
        })
    return questions

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    existing = []
    if DB_FILE.exists():
        try:
            existing = json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    by_id = {item["id"]: item for item in existing if isinstance(item, dict) and "id" in item}

    prova_urls = [
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{EXAM_YEAR}/1fase/ita{EXAM_YEAR}_1fase_prova.pdf",
        f"https://curso-objetivo.br/vestibular/resolucao-comentada/ita/{EXAM_YEAR}/1fase/ita{EXAM_YEAR}_1fase_prova.pdf"
    ]
    gab_urls = [
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{EXAM_YEAR}/1fase/ita{EXAM_YEAR}_1fase_gabarito.pdf",
        f"https://curso-objetivo.br/vestibular/resolucao-comentada/ita/{EXAM_YEAR}/1fase/ita{EXAM_YEAR}_1fase_gabarito.pdf"
    ]

    prova_path = DATA_DIR / f"ita_{EXAM_YEAR}_prova.pdf"
    gab_path = DATA_DIR / f"ita_{EXAM_YEAR}_gabarito.pdf"

    print(f"\n=== Extraindo Prova Oficial ITA {EXAM_YEAR} ===")
    if fetch_pdf(prova_urls, prova_path):
        fetch_pdf(gab_urls, gab_path)
        gab_map = parse_gabarito_pdf(gab_path)
        extracted = parse_exam(prova_path, EXAM_YEAR, gab_map)

        counts = Counter(q["materia"] for q in extracted)
        figs = sum(1 for q in extracted if q.get("figura"))
        print(f"  ✓ Resumo {EXAM_YEAR} por Matéria: {dict(counts)} | Figuras recortadas: {figs}")

        for q in extracted:
            if q["id"] in by_id and len(by_id[q["id"]].get("resolucao", "")) > 110:
                if q.get("figura") and not by_id[q["id"]].get("figura"):
                    by_id[q["id"]]["figura"] = q["figura"]
            else:
                by_id[q["id"]] = q

        prova_path.unlink(missing_ok=True)
        gab_path.unlink(missing_ok=True)
    else:
        print(f"  ✗ Não foi possível baixar o PDF de {EXAM_YEAR}.")

    final_questions = sorted(by_id.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    total_counts = Counter(q["materia"] for q in final_questions)
    print(f"=== Banco Atualizado: {len(final_questions)} questões no total -> {dict(total_counts)} ===")

if __name__ == "__main__":
    main()
