import os
import re
import json
import requests
import pymupdf as fitz
from pathlib import Path
from collections import Counter

EXAM_YEAR = os.getenv("EXAM_YEAR", "2025").strip()
INCLUDE_LANGUAGES = os.getenv("INCLUDE_LANGUAGES", "true").lower() == "true"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "images"
DB_FILE = DATA_DIR / "questions.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
}

VERIFIED_LATEX_OVERRIDES = {
    "ITA-2025-1F-Q18": {
        "enunciado": "Um recipiente de paredes diatérmicas é dividido ao meio por um êmbolo de área $A$. O lado esquerdo do êmbolo é conectado ao recipiente por uma mola ideal de constante elástica $k$, em uma região onde há vácuo. No lado direito do êmbolo, há um gás ideal a uma pressão inicial $P_0$. Então, uma quantidade $Q$ de calor é transferida a esse gás por um processo reversível e isotérmico.\n\nAssinale a alternativa que fornece a diferença entre o comprimento natural da mola e o seu comprimento ao final do processo descrito.",
        "alternativas": {
            "A": "$\\sqrt{\\frac{2Q}{k}}$",
            "B": "$\\sqrt{\\frac{2Q}{k}} + \\frac{P_0 A}{k}$",
            "C": "$\\sqrt{\\frac{Q}{2k}} + \\frac{P_0 A}{k}$",
            "D": "$\\sqrt{\\frac{Q}{k} + \\left(\\frac{P_0 A}{k}\\right)^2}$",
            "E": "$\\sqrt{\\frac{2Q}{k} + \\left(\\frac{P_0 A}{k}\\right)^2}$"
        }
    },
    "ITA-2025-1F-Q19": {
        "enunciado": "O estetoscópio é um instrumento amplamente utilizado por profissionais de saúde para auscultar sons internos do corpo humano, como batimentos cardíacos e fluxo sanguíneo. Considere o modelo simplificado de um estetoscópio, ilustrado na figura, composto de um cone truncado de bases circulares, cuja base maior possui raio $R_1$, e a base menor, raio $R_2$. Nos cilindros, perfeitamente conectados em cada base, há pistões finos e rígidos de massa desprezível, que podem se mover para cima e para baixo sem atrito. Considere que a onda sonora atinge toda a superfície do pistão maior e que sua energia é transferida integralmente para o pistão menor.\n\nAssinale a alternativa que corresponde à amplificação, em $\\text{dB}$, em função dos raios das extremidades do estetoscópio.",
        "alternativas": {
            "A": "$10 \\log\\left(\\frac{R_1}{R_2}\\right)$",
            "B": "$20 \\log\\left(\\frac{R_1}{R_2}\\right)$",
            "C": "$20 \\log\\left(\\frac{R_1}{R_2}\\right)^2$",
            "D": "$10 \\log\\left(\\frac{R_2}{R_1}\\right)^2$",
            "E": "$20 \\log\\left(\\frac{R_2}{R_1}\\right)$"
        }
    },
    "ITA-2025-1F-Q21": {
        "enunciado": "Considere um tanque cúbico metálico de lado $L + a$ ($L \\gg a$), aberto no topo, preenchido com água e óleo. O tanque contém, no seu interior, um cubo metálico de lado $L$, com $5$ de seus lados totalmente submersos e o outro emerso na superfície, centralizado com a face aberta do tanque. Uma diferença de potencial de $V$ é estabelecida entre o cubo e o tanque, de forma que o sistema atue como um capacitor.\n\nA vista frontal do sistema encontra-se ilustrada na figura ao lado. Sabe-se que o óleo possui uma densidade de $d_o = 0{,}90\\text{ g/cm}^3$ e constante dielétrica $\\kappa_o$, que a água tem uma densidade igual a $d_a = 1{,}0\\text{ g/cm}^3$ e constante dielétrica $\\kappa_a$ e que a densidade do cubo é $d_c = 0{,}92\\text{ g/cm}^3$. Desconsiderando efeitos de borda, assinale a alternativa que fornece a capacitância do sistema."
    }
}

def fix_portuguese_accents_and_reflow(raw: str, is_alternative: bool = False) -> str:
    text = raw.replace("[[BLOCK_BREAK]]", "\n\n")

    text = re.sub(r"(?<=\s)´\s*e(?=\s|[.,;:!?\)]|$)", "é", text)
    text = re.sub(r"(?<=\s)`\s*a(?=\s|[.,;:!?\)]|$)", "à", text)
    text = re.sub(r"(?<=\s)´\s*a(?=\s|[.,;:!?\)]|$)", "á", text)

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

    # Des-hifenização de fim de linha
    text = re.sub(r"([a-zA-ZçÇáéíóúâêôãõÁÉÍÓÚÂÊÔÃÕ]{2,})-\s*\n\s*([a-zçáéíóúâêôãõ]{2,})", r"\1\2", text)

    if not is_alternative:
        text = re.sub(r"\n\s*[kR12xy]\s*\n", "\n", text)

    # Reflow preservando quebras de parágrafo (\n\n)
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

    if not is_alternative and "$" not in text:
        text = re.sub(r"\b([RPVTdv])([012])\b", r"$\1_\2$", text)
        text = re.sub(r"(\d+[,.]?\d*)\s*g/cm3\b", r"$\1\\text{ g/cm}^3$", text)
        text = re.sub(r"(\d+[,.]?\d*)\s*m/s2\b", r"$\1\\text{ m/s}^2$", text)
        text = text.replace("L >>a", "$L \\gg a$").replace("L >> a", "$L \\gg a$")
        text = text.replace("κo", "$\\kappa_o$").replace("κa", "$\\kappa_a$")

    return re.sub(r"[ \t]{2,}", " ", text).strip()

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

def extract_clean_figures(doc: fitz.Document, year: str) -> tuple[dict[int, str], dict[int, list[tuple[int, fitz.Rect]]]]:
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
            if m:
                q_anchors.append((int(m.group(1)), y0, x0))
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

            for b in blocks:
                bx0, by0, bx1, by1, btxt, *_ = b
                b_rect = fitz.Rect(bx0, by0, bx1, by1)
                if len(btxt.strip()) <= 28 and by0 >= union_r.y0 - 18 and by1 <= union_r.y1 + 18:
                    if bx0 >= union_r.x0 - 30 and bx1 <= union_r.x1 + 55:
                        union_r |= b_rect

            min_allowed_x0 = 0
            if union_r.x0 > 220:
                left_paragraphs = [
                    tb for tb in text_blocks
                    if tb.y1 > union_r.y0 and tb.y0 < union_r.y1 and tb.x1 <= union_r.x0 + 12
                ]
                if left_paragraphs:
                    min_allowed_x0 = max(tb.x1 for tb in left_paragraphs) + 4

            clip = fitz.Rect(
                max(min_allowed_x0, union_r.x0 - 4),
                max(0, union_r.y0 - 6),
                min(page.rect.width, union_r.x1 + 8),
                min(page.rect.height, union_r.y1 + 8)
            )
            pix = page.get_pixmap(clip=clip, dpi=230)
            fname = f"ita_{year}_q{q_num:02d}.png"
            pix.save(str(IMG_DIR / fname))
            q_figures[q_num] = f"data/images/{fname}"
            q_fig_rects.setdefault(q_num, []).append((p_idx, clip))

    return q_figures, q_fig_rects

def extract_structured_blocks_text(doc: fitz.Document, q_fig_rects: dict[int, list[tuple[int, fitz.Rect]]]) -> str:
    """Extrai os blocos de texto preservando marcadores [[BLOCK_BREAK]] entre parágrafos visuais do PDF."""
    all_fig_rects_by_page = {}
    for rects in q_fig_rects.values():
        for p_idx, r in rects:
            all_fig_rects_by_page.setdefault(p_idx, []).append(r)

    blocks_out = []
    for p_idx, page in enumerate(doc):
        fig_rects = all_fig_rects_by_page.get(p_idx, [])
        # Ordena os blocos de cima para baixo, da esquerda para a direita
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
            # Ignora rodapé isolado de número de página
            if re.match(r"^\d{1,2}$", clean_b):
                continue
            blocks_out.append(clean_b)
    return "\n[[BLOCK_BREAK]]\n".join(blocks_out)

def split_alt_e_and_next_base_text(raw_alt_e: str) -> tuple[str, str | None]:
    """
    Separa o texto real da Alternativa E de qualquer Texto Base / Preâmbulo
    que pertença à próxima questão (ou próximo bloco de questões).
    """
    # Remove títulos de seção isolados (ex: INGLÊS, PORTUGUÊS, QUÍMICA, FÍSICA, MATEMÁTICA)
    section_pat = r"(?:^|\[\[BLOCK_BREAK\]\]|\n)\s*(?:L[ÍI]NGUA\s+PORTUGUESA|L[ÍI]NGUA\s+INGLESA|PORTUGU[ÊE]S|INGL[ÊE]S|MATEM[ÁA]TICA|F[ÍI]SICA|QU[ÍI]MICA|F\s*´\s*I\s*S\s*I\s*C\s*A|Q\s*U\s*´\s*I\s*M\s*I\s*C\s*A)\s*(?=\[\[BLOCK_BREAK\]\]|\n|$)"
    
    blocks = [b.strip() for b in raw_alt_e.split("[[BLOCK_BREAK]]") if b.strip()]
    if not blocks:
        return "", None

    # O primeiro bloco logo após "E ( )" é sempre a Alternativa E
    alt_e_blocks = [blocks[0]]
    remaining_blocks = blocks[1:]

    # Se dentro do próprio primeiro bloco houver uma quebra explícita para início de texto base
    inline_ cue = re.split(
        r"\n\s*(?=(?:As\s+quest[õo]es|Leia\s+o\s+texto|Considere\s+o\s+texto|O\s+texto\s+a\s+seguir|Read\s+the\s+text|Read\s+the\s+following|Texto\s+[I1V]|TEXTO\s+[I1V]|O\s+enunciado\s+a\s+seguir))",
        alt_e_blocks[0],
        maxsplit=1,
        flags=re.IGNORECASE
    )
    if len(inline_cue) == 2:
        alt_e_blocks = [inline_cue[0].strip()]
        remaining_blocks.insert(0, inline_cue[1].strip())

    # Limpa cabeçalhos de matéria e instruções de capa dos blocos restantes
    cleaned_remaining = []
    for rb in remaining_blocks:
        rb_clean = re.sub(section_pat, "", rb, flags=re.IGNORECASE).strip()
        if not rb_clean or re.match(r"^\d{1,2}$", rb_clean):
            continue
        cleaned_remaining.append(rb_clean)

    alt_e_final = fix_portuguese_accents_and_reflow(" ".join(alt_e_blocks), is_alternative=True)

    if not cleaned_remaining:
        return alt_e_final, None

    candidate_base = fix_portuguese_accents_and_reflow("\n\n".join(cleaned_remaining), is_alternative=False)

    # Verifica se os blocos restantes realmente formam um Texto Base / Preâmbulo
    has_cue = bool(re.search(
        r"(?:quest[õo]es|texto|leia|considere|fragmento|excerto|poema|passagem|enunciado|figura\s+a\s+seguir|read\s+the|following|passage|article|adapted\s+from|dispon[íi]vel\s+em|fonte:)",
        candidate_base,
        re.IGNORECASE
    ))
    if has_cue or len(candidate_base) > 95:
        return alt_e_final, candidate_base

    return alt_e_final, None

def extract_preamble_before_q1(full_blocks_text: str) -> str | None:
    """Captura eventual texto de apoio posicionado antes da Questão 1 (ex: provas que iniciam com texto)."""
    m = re.search(r"^(.*?)(?=Quest(?:ão|ao)\s*1\s*[\.\-])", full_blocks_text, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    pre_raw = m.group(1)
    # Procura marcador típico de início de texto base após as instruções da capa
    cue_match = re.search(
        r"((?:As\s+quest[õo]es\s+de\s+1\s+a|Leia\s+o\s+texto|Considere\s+o\s+texto|Texto\s+I|O\s+enunciado\s+a\s+seguir).*)$",
        pre_raw,
        re.DOTALL | re.IGNORECASE
    )
    if cue_match:
        return fix_portuguese_accents_and_reflow(cue_match.group(1))
    return None

def detect_explicit_question_range(base_text: str) -> tuple[int, int] | None:
    """Detecta instruções como 'As questões de 37 a 40' ou 'questions 25 to 28'."""
    patterns = [
        r"(?:quest[õo]es|itens|questions?)\s*(?:de\s+|from\s+|n[úu]meros?\s+)?(\d{1,2})\s*(?:a|at[ée]|e|to|through|and|\-)\s*(\d{1,2})",
        r"responder\s+[àa]s\s+quest[õo]es\s+(?:de\s+)?(\d{1,2})\s*(?:a|at[ée]|e)\s*(\d{1,2})"
    ]
    for pat in patterns:
        m = re.search(pat, base_text, re.IGNORECASE)
        if m:
            start_q, end_q = int(m.group(1)), int(m.group(2))
            if 1 <= start_q <= end_q <= 60:
                return (start_q, end_q)
    return None

def clean_cmex_alternative(alt_raw: str) -> str:
    txt = alt_raw.replace("\ufffd", "").strip()
    m_rad = re.match(r"^[rs]\s+([0-9A-Za-z_]+)\s+([0-9A-Za-z_]+)(?:\s*\+\s*([0-9A-Za-z_]+)\s+([0-9A-Za-z_]+))?$", txt)
    if m_rad:
        num1, den1, num2, den2 = m_rad.groups()
        if num2 and den2:
            return f"$\\sqrt{{\\frac{{{num1}}}{{{den1}}}}} + \\frac{{{num2}}}{{{den2}}}$"
        return f"$\\sqrt{{\\frac{{{num1}}}{{{den1}}}}}$"
    return txt

def parse_exam(prova_pdf: Path, year: str, gab_map: dict[int, str]) -> list[dict]:
    doc = fitz.open(prova_pdf)
    q_figures, q_fig_rects = extract_clean_figures(doc, year)
    structured_text = extract_structured_blocks_text(doc, q_fig_rects)
    doc.close()

    normalized_full = re.sub(r"Quest\s*[˜~]?\s*a\s*o", "Questão", structured_text, flags=re.IGNORECASE)
    year_int = int(year)

    q_pattern = re.compile(
        r"Quest(?:ão|ao)\s*(\d{1,2})\s*[\.\-]\s*(.*?)(?=Quest(?:ão|ao)\s*\d{1,2}\s*[\.\-]|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    pending_base_by_qnum: dict[int, str] = {}
    q1_preamble = extract_preamble_before_q1(normalized_full)
    if q1_preamble:
        pending_base_by_qnum[1] = q1_preamble

    raw_matches = q_pattern.findall(normalized_full)
    questions = []

    for idx, (num_str, raw_body) in enumerate(raw_matches):
        q_num = int(num_str)
        next_q_num = int(raw_matches[idx + 1][0]) if idx + 1 < len(raw_matches) else q_num + 1
        materia = get_subject(year_int, q_num)

        parts = re.split(r"(?:^|\n|\s|\[\[BLOCK_BREAK\]\])([A-E])\s*\(\s*\)\s*", raw_body.strip())
        enunciado = fix_portuguese_accents_and_reflow(parts[0])
        alternativas = {k: "Consulte o enunciado / figura" for k in ("A", "B", "C", "D", "E")}

        if len(parts) >= 11:
            for i in range(1, len(parts) - 1, 2):
                letter = parts[i].upper()
                alt_text = parts[i + 1].strip()
                if letter == "E":
                    alt_e_clean, next_base_text = split_alt_e_and_next_base_text(alt_text)
                    alternativas["E"] = clean_cmex_alternative(alt_e_clean)
                    if next_base_text:
                        pending_base_by_qnum[next_q_num] = next_base_text
                elif letter in alternativas:
                    alternativas[letter] = clean_cmex_alternative(
                        fix_portuguese_accents_and_reflow(alt_text, is_alternative=True)
                    )

        q_id = f"ITA-{year}-1F-Q{q_num:02d}"
        if q_id in VERIFIED_LATEX_OVERRIDES:
            ov = VERIFIED_LATEX_OVERRIDES[q_id]
            if "enunciado" in ov:
                enunciado = ov["enunciado"]
            if "alternativas" in ov:
                alternativas = ov["alternativas"]

        gabarito = gab_map.get(q_num, "A")
        questions.append({
            "id": q_id,
            "ano": year_int,
            "fase": "1ª Fase",
            "numero": q_num,
            "materia": materia,
            "topico": f"{materia} - ITA {year}",
            "subtopico": "Questão Oficial 1ª Fase",
            "dificuldade": "Difícil",
            "texto_base": None,
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

    # Segunda passagem: Propaga os Textos de Apoio (por intervalo explícito, matéria de leitura ou referência à questão anterior)
    q_by_num = {q["numero"]: q for q in questions}
    active_subject_text: dict[str, str] = {}
    active_range_end: dict[str, int] = {}

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
                active_range_end[mat] = rng[1]
            else:
                q["texto_base"] = new_base

        # Se for Inglês ou Português (ou mencionar "segundo o texto" / "in the text"), herda o texto ativo da seção
        if not q["texto_base"] and mat in active_subject_text:
            mentions_text = bool(re.search(
                r"(?:texto|text|paragraph|par[áa]grafo|autor|author|poema|excerto|fragmento|passagem|passage|line\s+\d|linha\s+\d)",
                q["enunciado"],
                re.IGNORECASE
            ))
            if mat in ("Inglês", "Português") or mentions_text:
                q["texto_base"] = active_subject_text[mat]

        # Se mencionar "questão anterior" / "enunciado anterior" / "sistema anterior" em Física/Química/Matemática
        if not q["texto_base"] and (qn - 1) in q_by_num:
            if re.search(r"(?:quest[ãa]o\s+anterior|enunciado\s+anterior|sistema\s+anterior|situa[çc][ãa]o\s+anterior|problema\s+anterior)", q["enunciado"], re.IGNORECASE):
                prev_q = q_by_num[qn - 1]
                q["texto_base"] = f"[Contexto da Questão Anterior — {prev_q['id']}]:\n{prev_q['enunciado']}"
                if not q["figura"] and prev_q.get("figura"):
                    q["figura"] = prev_q["figura"]

        if q["texto_base"]:
            q["subtopico"] = "Com Texto de Apoio" + (" & Figura" if q.get("figura") else "")
        elif q.get("figura"):
            q["subtopico"] = "Com Figura Oficial"

    if not INCLUDE_LANGUAGES:
        questions = [q for q in questions if q["materia"] not in ("Inglês", "Português")]

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

    print(f"=== Extraindo ITA {EXAM_YEAR} (Com Textos de Apoio + Figuras) ===")
    if fetch_pdf(prova_urls, prova_path):
        fetch_pdf(gab_urls, gab_path)
        gab_map = parse_gabarito_pdf(gab_path)
        extracted = parse_exam(prova_path, EXAM_YEAR, gab_map)
        with_base = sum(1 for q in extracted if q.get("texto_base"))
        with_fig = sum(1 for q in extracted if q.get("figura"))
        print(f"  ✓ {len(extracted)} questões extraídas | {with_base} com Texto de Apoio | {with_fig} com Figura")

        for q in extracted:
            by_id[q["id"]] = q
        prova_path.unlink(missing_ok=True)
        gab_path.unlink(missing_ok=True)

    final_questions = sorted(by_id.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_questions, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
