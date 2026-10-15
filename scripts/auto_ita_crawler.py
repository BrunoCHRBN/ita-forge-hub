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
    },
    "ITA-2025-1F-Q21": {
        "enunciado": f"Considere um tanque cúbico metálico de lado {D}L + a{D} ({D}L \\gg a{D}), aberto no topo, preenchido com água e óleo. O tanque contém, no seu interior, um cubo metálico de lado {D}L{D}, com {D}5{D} de seus lados totalmente submersos e o outro emerso na superfície, centralizado com a face aberta do tanque. Uma diferença de potencial de {D}V{D} é estabelecida entre o cubo e o tanque, de forma que o sistema atue como um capacitor.\n\nA vista frontal do sistema encontra-se ilustrada na figura ao lado. Sabe-se que o óleo possui uma densidade de {D}d_o = 0{{,}}90\\text{{ g/cm}}^3{D} e constante dielétrica {D}\\kappa_o{D}, que a água tem uma densidade igual a {D}d_a = 1{{,}}0\\text{{ g/cm}}^3{D} e constante dielétrica {D}\\kappa_a{D} e que a densidade do cubo é {D}d_c = 0{{,}}92\\text{{ g/cm}}^3{D}. Desconsiderando efeitos de borda, assinale a alternativa que fornece a capacitância do sistema."
    }
}

def fix_portuguese_accents_and_reflow(raw: str, is_alternative: bool = False) -> str:
    text = raw.replace("[[BLOCK_BREAK]]", "\n\n")

    text = re.sub(r"(?<=\s)´\s*e(?=\s|[.,;:!?\)]|\Z)", "é", text)
    text = re.sub(r"(?<=\s)`\s*a(?=\s|[.,;:!?\)]|\Z)", "à", text)
    text = re.sub(r"(?<=\s)´\s*a(?=\s|[.,;:!?\)]|\Z)", "á", text)

    accent_map = [
        (r"[˜~]\s*a", "ã"), (r"[˜~]\s*o", "õ"),
        (r"[˜~]\s*A", "Ã"), (r"[˜~]\s*O", "Õ"),
        (r"´\s*a", "á"), (r"´\s*e", "é"), (r"´\s*[ıi]", "í"),
        (r"´\s*o", "ó"), (r"´\s*u", "ú"),
        (r"´\s*A", "Á"), (r"´\s*E", "É"), (r"´\s*[IÍ]", "Í"),
        (r"´\s*O", "Ó"), (r"´\s*U", "Ú"),
        (r"ˆ\s*a", "â"), (r"ˆ\s*e", "ê"), (r"ˆ\s*o", "ô"),
        (r"ˆ\s*A", "Â"), (r"ˆ\s*E", "Ê"), (r"ˆ\s*O", "Ô"),
        (r"`\s*a", "à"), (r"`\s*A", "À"),
        (r"c\s*¸\s*", "ç"), (r"¸\s*c", "ç"),
        (r"C\s*¸\s*", "Ç"), (r"¸\s*C", "Ç"),
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

    if not is_alternative:
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
            elif re.match(r"^(?:I{1,3}|IV|V|1\.|2\.|3\.|a\)|b\)|c\)|•|Assinale|Determine|Calcule|Sabendo|Dados?:|Fonte:|Adaptado)", ln):
                merged.append("\n" + ln)
            else:
                merged[-1] += " " + ln
        cleaned_paras.append("\n".join(merged))

    text = "\n\n".join(cleaned_paras)

    if not is_alternative and D not in text:
        text = re.sub(r"\b([RPVTdv])([012])\b", f"{D}\\1_\\2{D}", text)
        text = re.sub(r"(\d+[,.]?\d*)\s*g/cm3\b", f"{D}\\1\\\\text{{ g/cm}}^3{D}", text)
        text = re.sub(r"(\d+[,.]?\d*)\s*m/s2\b", f"{D}\\1\\\\text{{ m/s}}^2{D}", text)
        text = text.replace("L >>a", f"{D}L \\gg a{D}").replace("L >> a", f"{D}L \\gg a{D}")
        text = text.replace("κo", f"{D}\\kappa_o{D}").replace("κa", f"{D}\\kappa_a{D}")

    return re.sub(r"[ \t]{2,}", " ", text).strip()

def get_subject(banca: str, year: int, q_num: int) -> str:
    if banca == "IME":
        if 1 <= q_num <= 15: return "Matemática"
        if 16 <= q_num <= 30: return "Física"
        return "Química"
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

def discover_and_fetch_pdfs(banca: str, year: str, prova_dest: Path, gab_dest: Path) -> tuple[bool, bool, bool]:
    b = banca.lower()
    direct_prova_urls = [
        (f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/1fase/{b}{year}_1fase_prova.pdf", False),
        (f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/1fase/{b.upper()}{year}_1fase_prova.pdf", False),
        (f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/1fase/{b}{year}_1fase.pdf", True),
        (f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/1fase/{b.upper()}{year}_1fase.pdf", True),
        (f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/{b}{year}_1fase.pdf", True),
        (f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/{b.upper()}{year}_1fase.pdf", True),
        (f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/{b}{year}_prova.pdf", False),
    ]

    aspx_pages = [
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{b}{year}_1fase.aspx",
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{b}{year}.aspx",
    ]
    for page_url in aspx_pages:
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                for href in re.findall(r'href=["\']([^"\']+\.pdf)["\']', r.text, re.IGNORECASE):
                    full_u = href if href.startswith("http") else f"https://www.curso-objetivo.br{href if href.startswith('/') else '/' + href}"
                    is_commented = "_prova" not in full_u.lower() and "_gabarito" not in full_u.lower()
                    if "gabarito" not in full_u.lower() and ("1fase" in full_u.lower() or b in full_u.lower()):
                        direct_prova_urls.append((full_u, is_commented))
        except Exception:
            pass

    got_prova = False
    is_commented_pdf = False
    for url, commented_flag in direct_prova_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code == 200 and len(r.content) > 8_000 and r.content[:4] == b"%PDF":
                prova_dest.write_bytes(r.content)
                got_prova = True
                is_commented_pdf = commented_flag
                print(f"  ✓ PDF baixado ({'Comentado Completo' if is_commented_pdf else 'Caderno Oficial'}): {url}")
                break
        except Exception:
            pass

    got_gab = False
    if got_prova and not is_commented_pdf:
        gab_urls = [
            f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/1fase/{b}{year}_1fase_gabarito.pdf",
            f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/1fase/{b.upper()}{year}_1fase_gabarito.pdf",
            f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/{b}/{year}/{b}{year}_gabarito.pdf",
        ]
        for g_url in gab_urls:
            try:
                r = requests.get(g_url, headers=HEADERS, timeout=20)
                if r.status_code == 200 and len(r.content) > 4_000 and r.content[:4] == b"%PDF":
                    gab_dest.write_bytes(r.content)
                    got_gab = True
                    break
            except Exception:
                pass

    return got_prova, got_gab, is_commented_pdf

def parse_gabarito_pdf(gab_pdf: Path) -> dict[int, str]:
    if not gab_pdf.exists():
        return {}
    doc = fitz.open(gab_pdf)
    text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    gab_map = {}
    for num_str, ans in re.findall(r"\b(\d{1,2})\s*[\.\-]?\s*([A-E]|\(\*+\))", text):
        q_num = int(num_str)
        if 1 <= q_num <= 75 and q_num not in gab_map:
            gab_map[q_num] = "ANULADA" if "*" in ans else ans
    return gab_map

def safe_extract_figures(doc: fitz.Document, banca: str, year: str) -> tuple[dict[int, str], dict[int, list[tuple[int, fitz.Rect]]]]:
    q_figures = {}
    q_fig_rects = {}

    for p_idx, page in enumerate(doc):
        blocks = page.get_text("blocks")
        q_anchors = []
        text_blocks = []

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            cleaned = fix_portuguese_accents_and_reflow(text)
            m = re.search(r"Quest(?:ão|ao)\s*(\d{1,2})\s*[\.\-]", cleaned, re.IGNORECASE)
            if not m:
                m = re.search(r"^\s*(\d{1,2})\.\s+[A-ZÁÉÍÓÚÂÊÔÃÕ]", cleaned)
            if m:
                qn = int(m.group(1))
                if 1 <= qn <= 75:
                    q_anchors.append((qn, y0, x0))
            if len(cleaned) > 35:
                text_blocks.append(fitz.Rect(x0, y0, x1, y1))

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
                if 50 < d_rect.width < page.rect.width * 0.94 and 38 < d_rect.height < page.rect.height * 0.70 and d_rect.y0 > 50:
                    graphic_rects.append(d_rect)
        except Exception:
            pass

        for idx, (q_num, y_start, _) in enumerate(q_anchors):
            y_end = q_anchors[idx + 1][1] if idx + 1 < len(q_anchors) else page.rect.height - 35
            matching = [r for r in graphic_rects if (r.y0 >= y_start - 10 and r.y1 <= y_end + 12)]
            if not matching:
                continue

            union_r = matching[0]
            for mr in matching[1:]:
                union_r |= mr

            min_allowed_x0 = 0
            if union_r.x0 > 220:
                left_paragraphs = [
                    tb for tb in text_blocks
                    if tb.y1 > union_r.y0 and tb.y0 < union_r.y1 and tb.x1 <= union_r.x0 + 12
                ]
                if left_paragraphs:
                    candidate_x0 = max(tb.x1 for tb in left_paragraphs) + 4
                    if candidate_x0 < union_r.x1 - 30:
                        min_allowed_x0 = candidate_x0

            clip = fitz.Rect(
                max(min_allowed_x0, union_r.x0 - 4),
                max(0, union_r.y0 - 6),
                min(page.rect.width, union_r.x1 + 8),
                min(page.rect.height, union_r.y1 + 8)
            )
            clip = clip & page.rect
            if clip.is_empty or clip.width < 22 or clip.height < 22:
                continue

            try:
                pix = page.get_pixmap(clip=clip, dpi=200)
                if pix.width >= 20 and pix.height >= 20:
                    fname = f"{banca.lower()}_{year}_q{q_num:02d}.png"
                    pix.save(str(IMG_DIR / fname))
                    q_figures[q_num] = f"data/images/{fname}"
                    q_fig_rects.setdefault(q_num, []).append((p_idx, clip))
            except Exception:
                pass

    return q_figures, q_fig_rects

def extract_structured_blocks_text(doc: fitz.Document, q_fig_rects: dict[int, list[tuple[int, fitz.Rect]]]) -> str:
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
    return "\n[[BLOCK_BREAK]]\n".join(blocks_out)

def split_alt_e_and_next_base_text(raw_alt_e: str) -> tuple[str, str | None, str | None, str | None]:
    res_extracted = None
    ans_extracted = None

    res_split = re.split(r"\s*Resolu[çc][ãa]o\b", raw_alt_e, maxsplit=1, flags=re.IGNORECASE)
    if len(res_split) == 2:
        raw_alt_e = res_split[0]
        res_tail = res_split[1]
        m_ans = re.search(r"(?:Resposta|Alternativa|Gabarito)\s*[:\-]?\s*([A-E])\b", res_tail, re.IGNORECASE)
        if m_ans:
            ans_extracted = m_ans.group(1).upper()
        res_extracted = fix_portuguese_accents_and_reflow(res_tail)

    blocks = [b.strip() for b in raw_alt_e.split("[[BLOCK_BREAK]]") if b.strip()]
    if not blocks:
        return "", None, res_extracted, ans_extracted

    alt_e_blocks = [blocks[0]]
    remaining_blocks = blocks[1:]

    cleaned_remaining = []
    for rb in remaining_blocks:
        if re.match(r"^(?:L[ÍI]NGUA|PORTUGU[ÊE]S|INGL[ÊE]S|MATEM[ÁA]TICA|F[ÍI]SICA|QU[ÍI]MICA|\d{1,2})\Z", rb.strip(), re.IGNORECASE):
            continue
        cleaned_remaining.append(rb.strip())

    alt_e_final = fix_portuguese_accents_and_reflow(" ".join(alt_e_blocks), is_alternative=True)
    if not cleaned_remaining:
        return alt_e_final, None, res_extracted, ans_extracted

    candidate_base = fix_portuguese_accents_and_reflow("\n\n".join(cleaned_remaining), is_alternative=False)
    if len(candidate_base) > 90:
        return alt_e_final, candidate_base, res_extracted, ans_extracted

    return alt_e_final, None, res_extracted, ans_extracted

def detect_explicit_question_range(base_text: str) -> tuple[int, int] | None:
    m = re.search(r"(?:quest[õo]es|questions?)\s*(?:de\s+|from\s+)?(\d{1,2})\s*(?:a|at[ée]|e|to|\-)\s*(\d{1,2})", base_text, re.IGNORECASE)
    if m:
        start_q, end_q = int(m.group(1)), int(m.group(2))
        if 1 <= start_q <= end_q <= 75:
            return (start_q, end_q)
    return None

def parse_exam(prova_pdf: Path, banca: str, year: str, gab_map: dict[int, str], include_lang: bool) -> list[dict]:
    doc = fitz.open(prova_pdf)
    q_figures, q_fig_rects = safe_extract_figures(doc, banca, year)
    structured_text = extract_structured_blocks_text(doc, q_fig_rects)
    doc.close()

    normalized_full = re.sub(r"Quest\s*[˜~]?\s*a\s*o", "Questão", structured_text, flags=re.IGNORECASE)
    year_int = int(year)

    q_pattern = re.compile(
        r"Quest(?:ão|ao)\s*(\d{1,2})\s*[.\-]\s*(.*?)(?=Quest(?:ão|ao)\s*\d{1,2}\s*[.\-]|\Z)",
        re.DOTALL | re.IGNORECASE
    )
    raw_matches = q_pattern.findall(normalized_full)

    if len(raw_matches) < 10:
        q_pattern_num = re.compile(
            r"(?:^|\n)\s*(\d{1,2})[.]\s+([A-ZÁÉÍÓÚÂÊÔÃÕ(].*?)(?=\n\s*\d{1,2}[.]\s+[A-ZÁÉÍÓÚÂÊÔÃÕ(]|\Z)",
            re.DOTALL
        )
        raw_matches = [m for m in q_pattern_num.findall(normalized_full) if 1 <= int(m[0]) <= 75]

    pending_base_by_qnum = {}
    questions = []
    seen_qnums = set()

    for idx, (num_str, raw_body) in enumerate(raw_matches):
        q_num = int(num_str)
        if q_num in seen_qnums:
            continue
        seen_qnums.add(q_num)

        next_q_num = int(raw_matches[idx + 1][0]) if idx + 1 < len(raw_matches) else q_num + 1
        materia = get_subject(banca, year_int, q_num)

        parts = re.split(r"\s([A-E])\s*[(]\s*[)]\s*", " " + raw_body.strip())
        if len(parts) < 11:
            parts = re.split(r"\s([a-eA-E])[)]\s+", " " + raw_body.strip())

        enunciado = fix_portuguese_accents_and_reflow(parts[0])
        alternativas = {k: "Consulte o enunciado / figura" for k in ("A", "B", "C", "D", "E")}
        custom_res = None
        embedded_ans = None

        if len(parts) >= 11:
            for i in range(1, len(parts) - 1, 2):
                letter = parts[i].upper()
                alt_text = parts[i + 1].strip()
                if letter == "E":
                    alt_e_clean, next_base_text, res_ext, ans_ext = split_alt_e_and_next_base_text(alt_text)
                    alternativas["E"] = alt_e_clean
                    if res_ext:
                        custom_res = res_ext
                    if ans_ext:
                        embedded_ans = ans_ext
                    if next_base_text:
                        pending_base_by_qnum[next_q_num] = next_base_text
                elif letter in alternativas:
                    alternativas[letter] = fix_portuguese_accents_and_reflow(alt_text, is_alternative=True)

        q_id = f"{banca}-{year}-1F-Q{q_num:02d}"
        if q_id in VERIFIED_LATEX_OVERRIDES:
            ov = VERIFIED_LATEX_OVERRIDES[q_id]
            if "enunciado" in ov:
                enunciado = ov["enunciado"]
            if "alternativas" in ov:
                alternativas = ov["alternativas"]

        gabarito = gab_map.get(q_num) or embedded_ans or "A"
        resolucao_final = custom_res if custom_res else (
            f"Gabarito Oficial {banca} {year}: Alternativa {gabarito}."
            if gabarito != "ANULADA"
            else f"Questão Oficialmente ANULADA pela banca do {banca} {year}."
        )

        questions.append({
            "id": q_id,
            "ano": year_int,
            "fase": "1ª Fase",
            "numero": q_num,
            "materia": materia,
            "topico": f"{materia} - {banca} {year}",
            "subtopico": "Questão Oficial 1ª Fase",
            "dificuldade": "Difícil",
            "texto_base": None,
            "enunciado": enunciado,
            "figura": q_figures.get(q_num),
            "alternativas": alternativas,
            "gabarito": gabarito,
            "pulo_do_gato": "Use '✨ Copiar Prompt p/ Gemini Pro' para dissecar a questão em LaTeX.",
            "resolucao": resolucao_final
        })

    q_by_num = {q["numero"]: q for q in questions}
    active_subject_text = {}

    for q in questions:
        qn = q["numero"]
        mat = q["materia"]
        if qn in pending_base_by_qnum:
            new_base = pending_base_by_qnum[qn]
            active_subject_text[mat] = new_base
            rng = detect_explicit_question_range(new_base)
            if rng:
                for target_num in range(rng[0], rng[1] + 1):
                    if target_num in q_by_num:
                        q_by_num[target_num]["texto_base"] = new_base
            else:
                q["texto_base"] = new_base

        if not q["texto_base"] and mat in active_subject_text:
            if mat in ("Inglês", "Português"):
                q["texto_base"] = active_subject_text[mat]

        if not q["texto_base"] and (qn - 1) in q_by_num:
            if re.search(r"(?:quest[ãa]o\s+anterior|enunciado\s+anterior|sistema\s+anterior)", q["enunciado"], re.IGNORECASE):
                prev_q = q_by_num[qn - 1]
                q["texto_base"] = f"[Contexto da Questão Anterior — {prev_q['id']}]:\n{prev_q['enunciado']}"
                if not q["figura"] and prev_q.get("figura"):
                    q["figura"] = prev_q["figura"]

        if q["texto_base"]:
            q["subtopico"] = "Com Texto de Apoio" + (" & Figura" if q.get("figura") else "")
        elif q.get("figura"):
            q["subtopico"] = "Com Figura Oficial"

    if not include_lang:
        questions = [q for q in questions if q["materia"] not in ("Inglês", "Português")]

    return questions

def run_for_target(by_id: dict, banca: str, year: str, include_lang: bool):
    prova_path = DATA_DIR / f"{banca.lower()}_{year}_prova.pdf"
    gab_path = DATA_DIR / f"{banca.lower()}_{year}_gabarito.pdf"

    print(f"=== Extraindo {banca} {year} ===")
    got_prova, got_gab, _ = discover_and_fetch_pdfs(banca, year, prova_path, gab_path)
    if got_prova:
        gab_map = parse_gabarito_pdf(gab_path) if got_gab else {}
        extracted = parse_exam(prova_path, banca, year, gab_map, include_lang)
        with_base = sum(1 for q in extracted if q.get("texto_base"))
        with_fig = sum(1 for q in extracted if q.get("figura"))
        print(f"  ✓ {len(extracted)} questões extraídas | {with_base} com Texto Base | {with_fig} com Figura")
        for q in extracted:
            by_id[q["id"]] = q
        prova_path.unlink(missing_ok=True)
        gab_path.unlink(missing_ok=True)
    else:
        print(f"  ✗ PDF não localizado para {banca} {year}.")

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

    single_year = os.getenv("EXAM_YEAR")
    if single_year:
        banca = os.getenv("EXAM_BANCA", "ITA").strip().upper()
        inc_l = os.getenv("INCLUDE_LANGUAGES", "true").lower() == "true"
        run_for_target(by_id, banca, single_year.strip(), inc_l)
    else:
        # Quando rodado sem variáveis, baixa automaticamente a coleção histórica ITA + IME!
        targets = [
            ("ITA", "2022", True),
            ("ITA", "2020", True),
            ("ITA", "2019", True),
            ("IME", "2026", False),
            ("IME", "2025", False),
            ("IME", "2024", False),
            ("IME", "2023", False),
            ("IME", "2022", False),
        ]
        for banca, year, inc_l in targets:
            run_for_target(by_id, banca, year, inc_l)

    final_questions = sorted(by_id.values(), key=lambda x: (-x["ano"], x["id"]))
    DB_FILE.write_text(json.dumps(final_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== SUCESSO TOTAL! Banco atualizado com {len(final_questions)} questões oficiais! ===")

if __name__ == "__main__":
    main()
