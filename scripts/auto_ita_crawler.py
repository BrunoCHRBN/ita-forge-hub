import os
import re
import time
import json
import fitz  # PyMuPDF
import requests
from pathlib import Path

EXAM_YEAR = os.getenv("EXAM_YEAR", "2026").strip()
INCLUDE_ENGLISH_PORTUGUESE = os.getenv("INCLUDE_LANGUAGES", "false").lower() == "true"
API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "images"
DB_FILE = DATA_DIR / "questions.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

# Árvore de palavras-chave do edital do ITA para classificação 100% gratuita
TOPIC_RULES = {
    "Matemática": [
        ("Números Complexos", "Argand-Gauss, Módulo e Raízes", [r"complexo", r"argand", r"\bi\b", r"imagin[áa]ri", r"conjugado"]),
        ("Polinômios e Equações", "Raízes, Girard e Multiplicidade", [r"polin[ôo]mio", r"ra[íi]zes", r"coeficientes reais", r"divis[íi]vel"]),
        ("Geometria Espacial", "Poliedros, Prismas, Esferas e Cones", [r"poliedro", r"v[ée]rtices", r"arestas", r"faces", r"tetraedro", r"pir[âa]mide", r"esfera", r"cilindro", r"cone"]),
        ("Geometria Analítica", "Cônicas, Retas e Circunferências", [r"elipse", r"hip[ée]rbole", r"par[áa]bola", r"plano cartesiano", r"circunfer[êe]ncia", r"foco", r"excentricidade"]),
        ("Matrizes e Sistemas", "Determinantes, Inversas e Discussão", [r"matriz", r"determinante", r"sistema linear", r"transposta", r"inversa"]),
        ("Combinatória e Binômio", "Contagem, Probabilidade e Newton", [r"termo independente", r"expans[ãa]o", r"probabilidade", r"escolh", r"anagrama", r"combina"]),
        ("Funções e Progressões", "Injetora, Sobrejetora, PA/PG e Logaritmos", [r"injetora", r"sobrejetora", r"bijetora", r"progress[ãa]o", r"\blog\b", r"fun[çc][ãa]o"]),
        ("Trigonometria e Plana", "Triângulos, Leis dos Senos/Cossenos", [r"tri[âa]ngulo", r"\bsen\b", r"\bcos\b", r"tangente", r"circunscrit", r"inscrit"])
    ],
    "Física": [
        ("Mecânica Clássica", "Dinâmica, Cunhas, Atrito e Energia", [r"bloco", r"cunha", r"atrito", r"mola", r"acelera[çc][ãa]o", r"colis[ãa]o", r"centro de massa", r"polia"]),
        ("Gravitação e Estática", "Órbitas, Kepler e Hidrostática", [r"planeta", r"[óo]rbita", r"gravit", r"empuxo", r"fluido", r"tanque", r"press[ãa]o", r"densidade"]),
        ("Termodinâmica", "Gases Ideais, Ciclos e Calorimetria", [r"g[áa]s ideal", r"adiab[áa]tic", r"isot[ée]rmic", r"carnot", r"calor", r"temperatura", r"entropia"]),
        ("Óptica e Ondulatória", "Refração, Lentes, Interferência e Efeito Doppler", [r"arco-[íi]ris", r"refra[çc][ãa]o", r"lente", r"espelho", r"onda", r"frequ[êe]ncia", r"doppler", r"difra[çc][ãa]o"]),
        ("Eletromagnetismo", "Circuitos, Capacitores, Campo Magnético e Indução", [r"resistor", r"capacitor", r"corrente", r"campo magn[ée]tico", r"campo el[ée]trico", r"carga", r"espira", r"indutor"]),
        ("Física Moderna", "Efeito Fotoelétrico, Relatividade e Quântica", [r"f[óo]ton", r"planck", r"relatividad", r"decaimento", r"comprimento de onda de de broglie"])
    ],
    "Química": [
        ("Físico-Química: Equilíbrio", "Kc, Kp, pH, Tampão e Kps", [r"equil[íi]brio", r"\bph\b", r"constante de ioniza", r"solubilidade", r"tamp[ãa]o", r"hidr[óo]lise"]),
        ("Eletroquímica", "Pilhas, Potencial Padrão e Eletrólise", [r"pilha", r"eletr[óo]lise", r"potencial", r"[âa]nodo", r"c[áa]todo", r"oxida[çc][ãa]o", r"faraday"]),
        ("Termoquímica e Cinética", "Entalpia, Energia Livre e Velocidade de Reação", [r"entalpia", r"exot[ée]rmic", r"endot[ée]rmic", r"velocidade da rea", r"energia de ativa", r"gibbs"]),
        ("Química Orgânica", "Isomeria, Reações Orgânicas e Polímeros", [r"org[âa]nic", r"is[ôo]mero", r"carbono", r"éster", r"ácido carbox", r"amina", r"pol[íi]mero", r"benzeno"]),
        ("Química Geral e Inorgânica", "Estequiometria, Ligações, Gases e Radioatividade", [r"estequiometr", r"mol\b", r"massa molar", r"geometria molecular", r"hibridiza", r"rea[çc][ãa]o"])
    ]
}

def clean_ita_latex_text(raw: str) -> str:
    """Corrige acentos desmembrados pelo LaTeX dos PDFs oficiais do ITA."""
    replacements = [
        ("˜a", "ã"), ("a˜", "ã"), ("˜o", "õ"), ("o˜", "õ"), ("˜A", "Ã"), ("˜O", "Õ"),
        ("´a", "á"), ("´e", "é"), ("´ı", "í"), ("´i", "í"), ("´o", "ó"), ("´u", "ú"),
        ("´A", "Á"), ("´E", "É"), ("´I", "Í"), ("´O", "Ó"), ("´U", "Ú"),
        ("ˆa", "â"), ("ˆe", "ê"), ("ˆo", "ô"), ("`a", "à"), ("¸c", "ç"), ("c¸", "ç"),
        ("ı", "í"), ("6=", "≠"), ("≤", "\\le "), ("≥", "\\ge ")
    ]
    text = raw
    for old, new in replacements:
        text = text.replace(old, new)
    # Remove múltiplos espaços preservando quebras de parágrafo
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
    return f"{materia} Geral", "Conceitos Integrados do Edital"

def get_subject_by_year_and_number(year: int, q_num: int) -> str:
    if year >= 2025:
        if 1 <= q_num <= 12:
            return "Matemática"
        elif 13 <= q_num <= 24:
            return "Física"
        elif 25 <= q_num <= 36:
            return "Química"
        return "Inglês"
    else:
        if 1 <= q_num <= 12:
            return "Física"
        elif 13 <= q_num <= 24:
            return "Português"
        elif 25 <= q_num <= 36:
            return "Inglês"
        elif 37 <= q_num <= 48:
            return "Matemática"
        return "Química"

def download_pdfs(year: str) -> tuple[Path, Path | None]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    prova_url = f"https://www.vestibular.ita.br/provas/{year}_fase1.pdf"
    gab_url = f"https://www.vestibular.ita.br/provas/gabarito_{year}.pdf"

    prova_path = DATA_DIR / f"ita_{year}_fase1.pdf"
    gab_path = DATA_DIR / f"ita_{year}_gabarito.pdf"

    print(f"[1/4] Baixando caderno de prova: {prova_url}")
    r_p = requests.get(prova_url, headers=HEADERS, timeout=60)
    r_p.raise_for_status()
    prova_path.write_bytes(r_p.content)

    print(f"[2/4] Baixando gabarito oficial: {gab_url}")
    r_g = requests.get(gab_url, headers=HEADERS, timeout=60)
    if r_g.status_code == 200:
        gab_path.write_bytes(r_g.content)
    else:
        print(f"[Aviso] Gabarito {year} ainda não publicado ou URL diferente (status {r_g.status_code}).")
        gab_path = None

    return prova_path, gab_path

def parse_gabarito(gab_pdf: Path | None) -> dict[int, str]:
    if not gab_pdf or not gab_pdf.exists():
        return {}
    doc = fitz.open(gab_pdf)
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()

    gab_map = {}
    # Padrão oficial ITA: "1. D." ou "6. (*)" ou "18. (**)"
    for num_str, ans in re.findall(r"\b(\d{1,2})\.\s*([A-E]|\(\*+\))", text):
        q_num = int(num_str)
        if 1 <= q_num <= 60 and q_num not in gab_map:
            gab_map[q_num] = "ANULADA" if "*" in ans else ans
    return gab_map

def extract_page_figures(doc: fitz.Document, year: str) -> dict[int, list[str]]:
    """Extrai imagens de cada página do PDF e mapeia por número de página."""
    page_figs = {}
    for p_idx, page in enumerate(doc):
        saved_for_page = []
        for img_idx, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            base_img = doc.extract_image(xref)
            if base_img["width"] >= 110 and base_img["height"] >= 70:
                ext = base_img["ext"]
                fname = f"ita_{year}_p{p_idx+1}_fig{img_idx+1}.{ext}"
                (IMG_DIR / fname).write_bytes(base_img["image"])
                saved_for_page.append(f"data/images/{fname}")
        if saved_for_page:
            page_figs[p_idx + 1] = saved_for_page
    return page_figs

def parse_exam_questions(prova_pdf: Path, year: str, gab_map: dict[int, str]) -> list[dict]:
    doc = fitz.open(prova_pdf)
    page_figs = extract_page_figures(doc, year)

    # Marca o início de cada página para associar figuras à questão correspondente
    pages_text = []
    for idx, page in enumerate(doc):
        pages_text.append(f"\n[[PAGE_{idx+1}]]\n" + page.get_text("text"))
    doc.close()

    full_text = clean_ita_latex_text("\n".join(pages_text))
    year_int = int(year)

    q_pattern = re.compile(
        r"Quest(?:ão|ao)\s+(\d{1,2})\.\s*(.*?)(?=Quest(?:ão|ao)\s+\d{1,2}\.|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    questions = []
    current_page = 1

    for num_str, raw_body in q_pattern.findall(full_text):
        q_num = int(num_str)
        page_markers = re.findall(r"\[\[PAGE_(\d+)\]\]", raw_body)
        if page_markers:
            current_page = int(page_markers[-1])

        clean_body = re.sub(r"\[\[PAGE_\d+\]\]", "", raw_body).strip()
        materia = get_subject_by_year_and_number(year_int, q_num)

        if not INCLUDE_ENGLISH_PORTUGUESE and materia in ("Inglês", "Português"):
            continue

        # Separa alternativas no padrão ITA: A( ) texto B( ) texto ...
        parts = re.split(r"\b([A-E])\s*\(\s*\)\s*", clean_body)
        enunciado = parts[0].strip()
        alternativas = {k: "Consulte o enunciado completo" for k in ("A", "B", "C", "D", "E")}

        if len(parts) >= 11:
            for i in range(1, len(parts) - 1, 2):
                letter = parts[i].upper()
                alt_text = parts[i + 1].strip()
                # Remove rodapés de numeração de página no final da alternativa E
                if letter == "E":
                    alt_text = re.sub(r"\n\s*\d{1,2}\s*$", "", alt_text).strip()
                if letter in alternativas:
                    alternativas[letter] = alt_text

        topico, subtopico = classify_topic(materia, enunciado)
        gabarito = gab_map.get(q_num, "A")
        figs = page_figs.get(current_page, [])

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
            "figura": figs[0] if figs else None,
            "alternativas": alternativas,
            "gabarito": gabarito,
            "pulo_do_gato": "Clique em '✨ Copiar Prompt p/ Gemini Pro' para dissecar a sacada algébrica desta questão.",
            "resolucao": (
                f"Gabarito Oficial ITA {year}: Alternativa {gabarito}."
                if gabarito != "ANULADA"
                else f"Questão Oficialmente ANULADA pela banca do ITA {year} (pontuação atribuída a todos os candidatos)."
            )
        })

    return questions

def optional_gemini_enrichment(questions: list[dict]):
    if not API_KEY:
        print("[Info] Sem GEMINI_API_KEY: usando extração determinística PyMuPDF + Classificador Local (Custo Zero).")
        return

    from google import genai
    client = genai.Client(api_key=API_KEY)
    max_to_enrich = int(os.getenv("MAX_AI_ENRICH", "6"))
    print(f"[3.5/4] GEMINI_API_KEY detectada! Refinando {max_to_enrich} questões com {GEMINI_MODEL}...")

    for q in questions[:max_to_enrich]:
        prompt = (
            f"Você é um professor do ITA. Reescreva a resolução comentada passo a passo em LaTeX ($...$ e $$...$$) "
            f"chegando ao gabarito oficial ({q['gabarito']}) para a questão {q['id']} de {q['materia']}:\n\n"
            f"Enunciado: {q['enunciado']}\nAlternativas: {json.dumps(q['alternativas'], ensure_ascii=False)}"
        )
        try:
            res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            if res.text:
                q["resolucao"] = res.text.strip()
            time.sleep(13)  # Respeita o Free Tier de 5 RPM
        except Exception as e:
            print(f"[Aviso] Pulo no enriquecimento da questão {q['id']}: {e}")

def main():
    prova_pdf, gab_pdf = download_pdfs(EXAM_YEAR)
    print("[3/4] Extraindo questões, figuras e gabarito oficial via PyMuPDF...")
    gab_map = parse_gabarito(gab_pdf)
    extracted = parse_exam_questions(prova_pdf, EXAM_YEAR, gab_map)

    optional_gemini_enrichment(extracted)

    existing = json.loads(DB_FILE.read_text(encoding="utf-8")) if DB_FILE.exists() else []
    by_id = {item["id"]: item for item in existing}
    for q in extracted:
        # Preserva resoluções já salvas manualmente pelo usuário se existirem
        if q["id"] in by_id and len(by_id[q["id"]].get("resolucao", "")) > 120 and len(q["resolucao"]) <= 120:
            q["resolucao"] = by_id[q["id"]]["resolucao"]
            q["pulo_do_gato"] = by_id[q["id"]].get("pulo_do_gato", q["pulo_do_gato"])
        by_id[q["id"]] = q

    prova_pdf.unlink(missing_ok=True)
    if gab_pdf:
        gab_pdf.unlink(missing_ok=True)

    final_questions = sorted(by_id.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[4/4] Sucesso! {len(extracted)} questões de Exatas do ITA {EXAM_YEAR} integradas em data/questions.json.")

if __name__ == "__main__":
    main()
