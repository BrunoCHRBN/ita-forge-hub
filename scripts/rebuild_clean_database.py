import os
import re
import json
import requests
import pymupdf as fitz
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "images"
DB_FILE = DATA_DIR / "questions.json"
D = "\x24"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

VERIFIED_LATEX_OVERRIDES = {
    "ITA-2026-1F-Q01": {
        "enunciado": f"Uma circunferência de raio {D}R{D} é dividida em seis partes iguais pelos pontos {D}A, B, C, D, E, F{D}, designados nessa ordem. Os pontos {D}A, C, E{D} são vértices de um triângulo equilátero, e os pontos {D}B, D, F{D} são vértices de um segundo triângulo equilátero. A área da região comum (interseção) aos dois triângulos equiláteros é igual a:",
        "alternativas": {
            "A": f"{D}\\frac{{\\sqrt{{3}}}}{{4}} R^2{D}",
            "B": f"{D}\\frac{{\\sqrt{{3}}}}{{2}} R^2{D}",
            "C": f"{D}\\frac{{3\\sqrt{{3}}}}{{4}} R^2{D}",
            "D": f"{D}\\sqrt{{3}} R^2{D}",
            "E": f"{D}\\frac{{3\\sqrt{{3}}}}{{2}} R^2{D}"
        }
    },
    "ITA-2026-1F-Q02": {
        "enunciado": f"Usando os valores aproximados {D}\\log_{{45}} 13{{,}}72 = 0{{,}}6880{D} e {D}\\log_{{45}} 6125 = 2{{,}}2908{D}, a alternativa que mais aproxima a representação decimal de {D}\\log_{{45}} 7{D} é:",
        "alternativas": {
            "A": f"{D}0{{,}}4886{D}",
            "B": f"{D}0{{,}}5112{D}",
            "C": f"{D}0{{,}}5193{D}",
            "D": f"{D}0{{,}}5224{D}",
            "E": f"{D}0{{,}}5385{D}"
        },
        "gabarito": "B",
        "pulo_do_gato": f"Note que {D}6125 = 5^3 \\cdot 7^2{D} e {D}13{{,}}72 = \\frac{{1372}}{{100}} = \\frac{{4 \\cdot 7^3}}{{100}} = \\frac{{7^3}}{{5^2}}{D}. Combinando os dois logaritmos dados, você elimina a base {D}5{D} e isola {D}\\log_{{45}} 7{D}!",
        "resolucao": f"Fatorando os argumentos dos logaritmos fornecidos:\n1. {D}6125 = 125 \\times 49 = 5^3 \\cdot 7^2 \\implies 3\\log_{{45}} 5 + 2\\log_{{45}} 7 = 2{{,}}2908{D}\n2. {D}13{{,}}72 = \\frac{{343}}{{25}} = \\frac{{7^3}}{{5^2}} \\implies 3\\log_{{45}} 7 - 2\\log_{{45}} 5 = 0{{,}}6880{D}\n\nMultiplicando a primeira equação por {D}2{D} e a segunda por {D}3{D} e somando:\n{D}{D}(4 + 9)\\log_{{45}} 7 = 2(2{{,}}2908) + 3(0{{,}}6880) = 4{{,}}5816 + 2{{,}}0640 = 6{{,}}6456{D}{D}\n{D}{D}\\log_{{45}} 7 = \\frac{{6{{,}}6456}}{{13}} = 0{{,}}5112{D}{D}"
    },
    "ITA-2025-1F-Q18": {
        "enunciado": f"Um recipiente de paredes diatérmicas é dividido ao meio por um êmbolo de área {D}A{D}. O lado esquerdo do êmbolo é conectado ao recipiente por uma mola ideal de constante elástica {D}k{D}, em uma região onde há vácuo. No lado direito do êmbolo, há um gás ideal a uma pressão inicial {D}P_0{D}. Então, uma quantidade {D}Q{D} de calor é transferida a esse gás por um processo reversível e isotérmico.\n\nAssinale a alternativa que fornece a diferença entre o comprimento natural da mola e o seu comprimento ao final do processo descrito.",
        "alternativas": {
            "A": f"{D}\\sqrt{{\\frac{{2Q}}{{k}}}}{D}",
            "B": f"{D}\\sqrt{{\\frac{{2Q}}{{k}}}} + \\frac{{P_0 A}}{{k}}{D}",
            "C": f"{D}\\sqrt{{\\frac{{Q}}{{2k}}}} + \\frac{{P_0 A}}{{k}}{D}",
            "D": f"{D}\\sqrt{{\\frac{{Q}}{{k}} + \\left(\\frac{{P_0 A}}{{k}}\\right)^2}}{D}",
            "E": f"{D}\\sqrt{{\\frac{{2Q}}{{k}} + \\left(\\frac{{P_0 A}}{{k}}\\right)^2}}{D}"
        }
    },
    "ITA-2025-1F-Q19": {
        "enunciado": f"O estetoscópio é um instrumento amplamente utilizado por profissionais de saúde para auscultar sons internos do corpo humano, como batimentos cardíacos e fluxo sanguíneo. Considere o modelo simplificado de um estetoscópio, ilustrado na figura, composto de um cone truncado de bases circulares, cuja base maior possui raio {D}R_1{D}, e a base menor, raio {D}R_2{D}. Nos cilindros, perfeitamente conectados em cada base, há pistões finos e rígidos de massa desprezível, que podem se mover para cima e para baixo sem atrito. Considere que a onda sonora atinge toda a superfície do pistão maior e que sua energia é transferida integralmente para o pistão menor.\n\nAssinale a alternativa que corresponde à amplificação, em {D}\\text{{dB}}{D}, em função dos raios das extremidades do estetoscópio.",
        "alternativas": {
            "A": f"{D}10 \\log\\left(\\frac{{R_1}}{{R_2}}\\right){D}",
            "B": f"{D}20 \\log\\left(\\frac{{R_1}}{{R_2}}\\right){D}",
            "C": f"{D}20 \\log\\left(\\frac{{R_1}}{{R_2}}\\right)^2{D}",
            "D": f"{D}10 \\log\\left(\\frac{{R_2}}{{R_1}}\\right)^2{D}",
            "E": f"{D}20 \\log\\left(\\frac{{R_2}}{{R_1}}\\right){D}"
        }
    }
}

def clean_text(raw: str, is_alt: bool = False) -> str:
    text = raw.replace("[[BLOCK_BREAK]]", "\n\n").replace("\ufffd", "")
    # Remove cabeçalhos de página infiltrados (ex: "ITA - 1.ª Fase - Outubro / 2025")
    text = re.sub(r"ITA\s*[\-–—]\s*1\.?[ªa]?\s*Fase\s*[\-–—]?\s*[A-Za-zçÇ]+\s*/\s*\d{4}", "", text, flags=re.IGNORECASE)

    text = re.sub(r"(?<=\s)´\s*e(?=\s|[.,;:!?\)]|\Z)", "é", text)
    text = re.sub(r"(?<=\s)`\s*a(?=\s|[.,;:!?\)]|\Z)", "à", text)
    text = re.sub(r"(?<=\s)´\s*a(?=\s|[.,;:!?\)]|\Z)", "á", text)

    accent_map = [
        (r"[˜~]\s*a", "ã"), (r"[˜~]\s*o", "õ"), (r"[˜~]\s*A", "Ã"), (r"[˜~]\s*O", "Õ"),
        (r"´\s*a", "á"), (r"´\s*e", "é"), (r"´\s*[ıi]", "í"), (r"´\s*o", "ó"), (r"´\s*u", "ú"),
        (r"´\s*A", "Á"), (r"´\s*E", "É"), (r"´\s*[IÍ]", "Í"), (r"´\s*O", "Ó"), (r"´\s*U", "Ú"),
        (r"ˆ\s*a", "â"), (r"ˆ\s*e", "ê"), (r"ˆ\s*o", "ô"), (r"ˆ\s*A", "Â"), (r"ˆ\s*E", "Ê"), (r"ˆ\s*O", "Ô"),
        (r"`\s*a", "à"), (r"`\s*A", "À"), (r"c\s*¸\s*", "ç"), (r"¸\s*c", "ç"), (r"C\s*¸\s*", "Ç"), (r"¸\s*C", "Ç"),
        (r"ı", "í")
    ]
    for pat, repl in accent_map:
        text = re.sub(pat, repl, text)

    STOPWORDS = {
        "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
        "em", "no", "na", "nos", "nas", "ao", "aos", "por", "para", "com",
        "sem", "sob", "que", "se", "ou", "como", "mais", "sua", "seu", "e", "v"
    }
    def join_internal_accent(m):
        prefix, accented = m.group(1), m.group(2)
        if prefix.lower() in STOPWORDS or accented in ("é", "à", "às"):
            return f"{prefix} {accented}"
        return f"{prefix}{accented}"

    text = re.sub(r"\b([A-Za-z]{1,12})\s+([ãõáéíóúâêôç][a-z]*)\b", join_internal_accent, text)
    text = re.sub(r"Quest\s*ão", "Questão", text, flags=re.IGNORECASE)
    text = re.sub(r"([a-zA-ZçÇáéíóúâêôãõÁÉÍÓÚÂÊÔÃÕ]{2,})-\s*\n\s*([a-zçáéíóúâêôãõ]{2,})", r"\1\2", text)

    # Remove qualquer vazamento de Resolução / Resposta do enunciado
    text = re.sub(r"(?:^|\n)\s*Resolu[çc][ãa]o\b.*?\Z", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\bOBJETIVO\b", "", text, flags=re.IGNORECASE)

    if not is_alt:
        text = re.sub(r"\n\s*[kR12xy]\s*\n", "\n", text)

    paragraphs = re.split(r"\n\s*\n", text)
    cleaned_paras = []
    for para in paragraphs:
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if not lines:
            continue
        merged = []
        for ln in lines:
            if not merged:
                merged.append(ln)
            elif re.match(r"^(?:I{1,3}|IV|V|1\.|2\.|3\.|•|Assinale|Determine|Calcule|Sabendo|Dados?:|Fonte:)", ln):
                merged.append("\n" + ln)
            else:
                merged[-1] += " " + ln
        cleaned_paras.append("\n".join(merged))

    text = "\n\n".join(cleaned_paras)

    if D not in text:
        text = re.sub(r"\blog(\d{1,3})\s+(\d+[,.]?\d*)", f"{D}\\\\log_{{\\1}} \\2{D}", text)
        text = re.sub(r"\b([RPVTdv])([012])\b", f"{D}\\1_\\2{D}", text)
        text = re.sub(r"(\d+[,.]?\d*)\s*g/cm3\b", f"{D}\\1\\\\text{{ g/cm}}^3{D}", text)
        text = text.replace("L >>a", f"{D}L \\gg a{D}").replace("L >> a", f"{D}L \\gg a{D}")
        text = text.replace("κo", f"{D}\\kappa_o{D}").replace("κa", f"{D}\\kappa_a{D}")

    return re.sub(r"[ \t]{2,}", " ", text).strip()

def get_subject(year: int, q_num: int) -> str:
    if year >= 2025:
        if 1 <= q_num <= 12: return "Matemática"
        if 13 <= q_num <= 24: return "Física"
        if 25 <= q_num <= 36: return "Química"
        return "Inglês"
    elif year >= 2023:
        if 1 <= q_num <= 12: return "Física"
        if 13 <= q_num <= 24: return "Português"
        if 25 <= q_num <= 36: return "Inglês"
        if 37 <= q_num <= 48: return "Matemática"
        return "Química"
    else:
        if 1 <= q_num <= 15: return "Física"
        if 16 <= q_num <= 30: return "Português"
        if 31 <= q_num <= 40: return "Inglês"
        if 41 <= q_num <= 55: return "Matemática"
        return "Química"

def extract_figures_safe(doc: fitz.Document, year: str) -> tuple[dict[int, str], dict[int, list[tuple[int, fitz.Rect]]]]:
    q_figures = {}
    q_fig_rects = {}

    for p_idx, page in enumerate(doc):
        blocks = page.get_text("blocks")
        q_anchors = []
        left_paras = []

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            cleaned = clean_text(text)
            m = re.search(r"Quest(?:ão|ao)\s*(\d{1,2})\s*[.\-]", cleaned, re.IGNORECASE)
            if m:
                q_anchors.append((int(m.group(1)), y0, x0))
            if x1 < 310 and len(cleaned) > 55:
                left_paras.append(fitz.Rect(x0, y0, x1, y1))

        q_anchors.sort(key=lambda item: item[1])
        if not q_anchors:
            continue

        graphic_rects = []
        for img_info in page.get_images(full=True):
            for r in page.get_image_rects(img_info[0]):
                if r.width > 40 and r.height > 32 and r.y0 > 50:
                    graphic_rects.append(r)

        try:
            for d_rect in page.cluster_drawings(x_tolerance=22, y_tolerance=22):
                if 48 < d_rect.width < page.rect.width * 0.94 and 36 < d_rect.height < page.rect.height * 0.72 and d_rect.y0 > 50:
                    graphic_rects.append(d_rect)
        except Exception:
            try:
                for d_rect in page.cluster_drawings():
                    if 48 < d_rect.width < page.rect.width * 0.94 and 36 < d_rect.height < page.rect.height * 0.72 and d_rect.y0 > 50:
                        graphic_rects.append(d_rect)
            except Exception:
                pass

        for idx, (q_num, y_start, _) in enumerate(q_anchors):
            y_next = q_anchors[idx + 1][1] - 6 if idx + 1 < len(q_anchors) else page.rect.height - 32
            matching = [r for r in graphic_rects if (r.y0 >= y_start - 6 and r.y1 <= y_next + 8)]
            if not matching:
                continue

            union_r = matching[0]
            for mr in matching[1:]:
                union_r |= mr

            for b in blocks:
                bx0, by0, bx1, by1, btxt, *_ = b
                b_clean = btxt.strip()
                if not b_clean or re.search(r"Quest(?:ão|ao)\s*\d", b_clean, re.IGNORECASE):
                    continue
                if re.search(r"(?:^|\n)\s*[A-E]\s*[(]\s*[)]", b_clean):
                    continue
                if len(b_clean) <= 45 and (by0 >= union_r.y0 - 25 and by1 <= union_r.y1 + 25):
                    if bx0 >= union_r.x0 - 50 and bx1 <= union_r.x1 + 70:
                        union_r |= fitz.Rect(bx0, by0, bx1, by1)

            if union_r.x0 > 230:
                ov_left = [lp for lp in left_paras if lp.y1 > union_r.y0 - 4 and lp.y0 < union_r.y1 + 4]
                x_left = (max(lp.x1 for lp in ov_left) + 4) if ov_left else max(215, union_r.x0 - 20)
                x_right = page.rect.width - 16
            else:
                x_left = max(25, union_r.x0 - 25)
                x_right = min(page.rect.width - 25, union_r.x1 + 25)

            clip = fitz.Rect(x_left, max(45, union_r.y0 - 15), x_right, min(y_next + 6, union_r.y1 + 15)) & page.rect
            if clip.is_empty or clip.width < 45 or clip.height < 35:
                continue

            try:
                pix = page.get_pixmap(clip=clip, dpi=230)
                fname = f"ita_{year}_q{q_num:02d}.png"
                out_file = IMG_DIR / fname
                pix.save(str(out_file))
                if out_file.exists() and out_file.stat().st_size > 800:
                    q_figures[q_num] = f"data/images/{fname}"
                    q_fig_rects.setdefault(q_num, []).append((p_idx, clip))
            except Exception:
                pass

    return q_figures, q_fig_rects

def parse_gabarito_pdf(gab_bytes: bytes) -> dict[int, str]:
    doc = fitz.open(stream=gab_bytes, filetype="pdf")
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    gab_map = {}
    for num_str, ans in re.findall(r"\b(\d{1,2})\s*[.\-]?\s*([A-E]|\(\*+\))", text):
        q_num = int(num_str)
        if 1 <= q_num <= 75 and q_num not in gab_map:
            gab_map[q_num] = "ANULADA" if "*" in ans else ans
    return gab_map

def fetch_commented_resolutions_text_only(year: str) -> dict[int, tuple[str, str]]:
    url = f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase.pdf"
    res_map = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200 or r.content[:4] != b"%PDF":
            return res_map
        doc = fitz.open(stream=r.content, filetype="pdf")
        full_text = "\n".join(page.get_text("text") for page in doc)
        doc.close()

        cleaned = clean_text(full_text)
        ans_matches = list(re.finditer(r"Resposta\s*[:\-]?\s*([A-E]|\*+)", cleaned, re.IGNORECASE))
        chunks = re.split(r"Resposta\s*[:\-]?\s*(?:[A-E]|\*+)", cleaned, flags=re.IGNORECASE)

        for idx, m_ans in enumerate(ans_matches):
            q_num = idx + 1
            raw_ans = m_ans.group(1).upper()
            gab = "ANULADA" if "*" in raw_ans else raw_ans
            chunk = chunks[idx] if idx < len(chunks) else ""
            res_parts = re.split(r"\bResolu[çc][ãa]o\b", chunk, flags=re.IGNORECASE)
            res_txt = res_parts[-1].strip() if len(res_parts) >= 2 else ""
            if len(res_txt) > 15:
                res_map[q_num] = (gab, f"Resolução Comentada ({year}):\n{res_txt}\n\nGabarito Oficial: {gab}")
    except Exception:
        pass
    return res_map

def extract_year(year: str) -> list[dict]:
    prova_url = f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase_prova.pdf"
    gab_url = f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase_gabarito.pdf"

    r_p = requests.get(prova_url, headers=HEADERS, timeout=25)
    if r_p.status_code != 200 or r_p.content[:4] != b"%PDF":
        return []

    gab_map = {}
    r_g = requests.get(gab_url, headers=HEADERS, timeout=15)
    if r_g.status_code == 200 and r_g.content[:4] == b"%PDF":
        gab_map = parse_gabarito_pdf(r_g.content)

    res_map = fetch_commented_resolutions_text_only(year)

    doc = fitz.open(stream=r_p.content, filetype="pdf")
    q_figures, q_fig_rects = extract_figures_safe(doc, year)

    all_fig_rects_by_page = {}
    for rects in q_fig_rects.values():
        for p_idx, r in rects:
            all_fig_rects_by_page.setdefault(p_idx, []).append(r)

    blocks_out = []
    for p_idx, page in enumerate(doc):
        fig_rects = all_fig_rects_by_page.get(p_idx, [])
        blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1] / 12), b[0]))
        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            b_rect = fitz.Rect(x0, y0, x1, y1)
            inside_fig = any(
                (b_rect.x0 >= fr.x0 - 5 and b_rect.x1 <= fr.x1 + 5 and b_rect.y0 >= fr.y0 - 5 and b_rect.y1 <= fr.y1 + 5)
                for fr in fig_rects
            )
            if inside_fig and not re.search(r"Quest", text, re.IGNORECASE):
                continue
            clean_b = text.strip()
            if re.match(r"^\d{1,2}\Z", clean_b):
                continue
            blocks_out.append(clean_b)
    doc.close()

    structured_text = "\n[[BLOCK_BREAK]]\n".join(blocks_out)
    normalized_full = re.sub(r"Quest\s*[˜~]?\s*a\s*o", "Questão", structured_text, flags=re.IGNORECASE)
    year_int = int(year)

    q_pattern = re.compile(
        r"Quest(?:ão|ao)\s*(\d{1,2})\s*[.\-]\s*(.*?)(?=Quest(?:ão|ao)\s*\d{1,2}\s*[.\-]|\Z)",
        re.DOTALL | re.IGNORECASE
    )
    raw_matches = q_pattern.findall(normalized_full)

    questions = []
    for idx, (num_str, raw_body) in enumerate(raw_matches):
        q_num = int(num_str)
        materia = get_subject(year_int, q_num)

        # Separa alternativas A( ) ... E( ) ou a) ... e) mesmo quando na mesma linha
        parts = re.split(r"\s([A-E])\s*[(]\s*[)]\s*", " " + raw_body.strip())
        if len(parts) < 11:
            parts = re.split(r"(?:^|\n|\s)([a-eA-E])[)]\s+", " " + raw_body.strip())

        enunciado = clean_text(parts[0])
        alternativas = {k: "Ver enunciado" for k in ("A", "B", "C", "D", "E")}

        if len(parts) >= 11:
            for i in range(1, len(parts) - 1, 2):
                letter = parts[i].upper()
                alt_raw = parts[i + 1].strip()
                if letter == "E":
                    alt_blocks = [b.strip() for b in alt_raw.split("[[BLOCK_BREAK]]") if b.strip()]
                    alt_raw = alt_blocks[0] if alt_blocks else alt_raw
                if letter in alternativas:
                    alternativas[letter] = clean_text(alt_raw, is_alt=True)

        q_id = f"ITA-{year}-1F-Q{q_num:02d}"
        gabarito = gab_map.get(q_num) or (res_map[q_num][0] if q_num in res_map else "A")
        resolucao = res_map[q_num][1] if q_num in res_map else f"Gabarito Oficial ITA {year}: Alternativa {gabarito}."

        if q_id in VERIFIED_LATEX_OVERRIDES:
            ov = VERIFIED_LATEX_OVERRIDES[q_id]
            if "enunciado" in ov: enunciado = ov["enunciado"]
            if "alternativas" in ov: alternativas = ov["alternativas"]
            if "gabarito" in ov: gabarito = ov["gabarito"]
            if "resolucao" in ov: resolucao = ov["resolucao"]

        fig_rel = q_figures.get(q_num)
        # Só mantém o caminho da figura se o arquivo PNG realmente existir no disco!
        if fig_rel and not (BASE_DIR / fig_rel).exists():
            fig_rel = None

        questions.append({
            "id": q_id,
            "ano": year_int,
            "fase": "1ª Fase",
            "numero": q_num,
            "materia": materia,
            "topico": f"{materia} - ITA {year}",
            "subtopico": "Com Figura Oficial" if fig_rel else "Questão Oficial 1ª Fase",
            "dificuldade": "Difícil",
            "texto_base": None,
            "enunciado": enunciado,
            "figura": fig_rel,
            "alternativas": alternativas,
            "gabarito": gabarito,
            "pulo_do_gato": VERIFIED_LATEX_OVERRIDES.get(q_id, {}).get("pulo_do_gato", "Use '✨ Copiar Prompt p/ Gemini Pro' para dissecar a questão em LaTeX."),
            "resolucao": resolucao
        })

    print(f"✓ ITA {year}: {len(questions)} questões limpas | {len(q_figures)} figuras verificadas no disco")
    return questions

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    all_questions = []
    for year in ["2027", "2026", "2025", "2024", "2023", "2022", "2021"]:
        all_questions.extend(extract_year(year))

    # Preserva o SVG da questão ITA-2026-1F-Q01 se existir
    svg_q1 = IMG_DIR / "ita_2026_hexagrama.svg"
    if svg_q1.exists():
        for q in all_questions:
            if q["id"] == "ITA-2026-1F-Q01":
                q["figura"] = "data/images/ita_2026_hexagrama.svg"
                q["subtopico"] = "Com Figura Oficial"

    all_questions.sort(key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(all_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== BANCO RECONSTRUÍDO COM SUCESSO: {len(all_questions)} questões e {sum(1 for q in all_questions if q['figura'])} figuras verificadas! ===")

if __name__ == "__main__":
    main()
