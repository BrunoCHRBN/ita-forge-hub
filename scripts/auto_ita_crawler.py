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

# Substituições de LaTeX verificadas para questões do ITA onde a fonte CMEX10 usa glifos gráficos
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
    """
    1. Converte acentos flutuantes do pdflatex SEM engolir o espaço antes de novas palavras.
    2. Junta palavras hifenizadas na quebra de linha (ex: 'ampla-\\nmente' -> 'amplamente').
    3. Faz o reflow de linhas estreitas em parágrafos fluidos e formata unidades em LaTeX.
    """
    text = raw

    # Acentos isolados após espaço (ex: " ´e" -> " é", " `a" -> " à") mantendo o espaço anterior!
    text = re.sub(r"(?<=\s)´\s*e(?=\s|[.,;:!?\)]|$)", "é", text)
    text = re.sub(r"(?<=\s)`\s*a(?=\s|[.,;:!?\)]|$)", "à", text)
    text = re.sub(r"(?<=\s)´\s*a(?=\s|[.,;:!?\)]|$)", "á", text)

    # Acentos flutuantes SEM consumir espaço anterior (\s* apenas DEPOIS do acento)
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

    # Caso o pdflatex tenha colocado espaço antes do acento no meio da palavra (ex: "Quest ã o"),
    # só junta se a parte anterior NÃO for uma palavra inteira de ligação (de, do, da, um, com, e, o, a...)
    STOPWORDS = {
        "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das",
        "em", "no", "na", "nos", "nas", "ao", "aos", "por", "para", "com",
        "sem", "sob", "que", "se", "ou", "como", "mais", "sua", "seu", "e", "v"
    }
    def join_internal_accent(m):
        prefix = m.group(1)
        accented = m.group(2)
        if prefix.lower() in STOPWORDS or accented in ("é", "à", "às"):
            return f"{prefix} {accented}"
        return f"{prefix}{accented}"

    text = re.sub(r"\b([A-Za-z]{1,12})\s+([ãõáéíóúâêôç][a-z]*)\b", join_internal_accent, text)
    text = re.sub(r"Quest\s*ão", "Questão", text, flags=re.IGNORECASE)

    # Des-hifenização de fim de linha (ex: "ampla-\nmente" -> "amplamente")
    text = re.sub(r"([a-zA-ZçÇáéíóúâêôãõÁÉÍÓÚÂÊÔÃÕ]{2,})-\s*\n\s*([a-zçáéíóúâêôãõ]{2,})", r"\1\2", text)

    # Remove linhas órfãs de 1 caractere que vieram de rótulos de figuras (ex: "\nk\n")
    if not is_alternative:
        text = re.sub(r"\n\s*[kR12xy]\s*\n", "\n", text)

    # Reflow de quebras de linha estreitas (preservando parágrafos e itens I, II, III)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    merged_lines = []
    for ln in lines:
        if not merged_lines:
            merged_lines.append(ln)
            continue
        # Mantém quebra se começar com algarismo romano, item ou frase de comando final
        if re.match(r"^(?:I{1,3}|IV|V|1\.|2\.|3\.|a\)|b\)|c\)|•|Assinale|Determine|Calcule|Sabendo|Dados?:)", ln):
            merged_lines.append("\n" + ln)
        else:
            merged_lines[-1] += " " + ln

    text = "\n".join(merged_lines)

    # Embelezamento automático de variáveis e unidades físicas/químicas para KaTeX
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

def extract_clean_figures_and_alt_crops(doc: fitz.Document, year: str) -> tuple[dict[int, str], dict[int, list[tuple[int, fitz.Rect]]]]:
    """
    Recorta as figuras das questões garantindo que NUNCA invadam a coluna de texto à esquerda,
    e retorna os retângulos recortados para excluir rótulos internos do texto do enunciado.
    """
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
            if len(cleaned) > 35:  # Bloco real de parágrafo de texto
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

            # Inclui rótulos curtos da própria figura (ex: 'Pistão móvel', 'óleo', 'água') que estejam próximos
            for b in blocks:
                bx0, by0, bx1, by1, btxt, *_ = b
                b_rect = fitz.Rect(bx0, by0, bx1, by1)
                if len(btxt.strip()) <= 28 and by0 >= union_r.y0 - 18 and by1 <= union_r.y1 + 18:
                    if bx0 >= union_r.x0 - 30 and bx1 <= union_r.x1 + 55:
                        union_r |= b_rect

            # Se a figura está na direita da página (x0 > 240), impede que o crop invada a coluna de texto à esquerda!
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

def extract_page_text_excluding_figures(doc: fitz.Document, q_fig_rects: dict[int, list[tuple[int, fitz.Rect]]]) -> str:
    """Extrai o texto das páginas ignorando palavras que estão desenhadas dentro das figuras."""
    all_fig_rects_by_page = {}
    for rects in q_fig_rects.values():
        for p_idx, r in rects:
            all_fig_rects_by_page.setdefault(p_idx, []).append(r)

    pages_out = []
    for p_idx, page in enumerate(doc):
        fig_rects = all_fig_rects_by_page.get(p_idx, [])
        blocks = page.get_text("blocks")
        kept_texts = []
        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            b_rect = fitz.Rect(x0, y0, x1, y1)
            # Se o bloco de texto estiver contido dentro de uma figura e não for cabeçalho de Questão, ignora!
            inside_fig = any(
                (b_rect.x0 >= fr.x0 - 5 and b_rect.x1 <= fr.x1 + 5 and b_rect.y0 >= fr.y0 - 5 and b_rect.y1 <= fr.y1 + 5)
                for fr in fig_rects
            )
            if inside_fig and not re.search(r"Quest", text, re.IGNORECASE):
                continue
            kept_texts.append(text)
        pages_out.append("\n".join(kept_texts))
    return "\n".join(pages_out)

def clean_cmex_alternative(alt_raw: str) -> str:
    """Limpa glifos corrompidos da fonte matemática CMEX10 (raízes 'r'/'s' e parênteses '\ufffd')."""
    txt = fix_portuguese_accents_and_reflow(alt_raw, is_alternative=True)
    txt = txt.replace("\ufffd", "")
    # Converte padrão CMEX10 "r A B" -> "\sqrt{A / B}"
    m_rad = re.match(r"^[rs]\s+([0-9A-Za-z_]+)\s+([0-9A-Za-z_]+)(?:\s*\+\s*([0-9A-Za-z_]+)\s+([0-9A-Za-z_]+))?$", txt)
    if m_rad:
        num1, den1, num2, den2 = m_rad.groups()
        if num2 and den2:
            return f"$\\sqrt{{\\frac{{{num1}}}{{{den1}}}}} + \\frac{{{num2}}}{{{den2}}}$"
        return f"$\\sqrt{{\\frac{{{num1}}}{{{den1}}}}}$"
    return txt

def parse_exam(prova_pdf: Path, year: str, gab_map: dict[int, str]) -> list[dict]:
    doc = fitz.open(prova_pdf)
    q_figures, q_fig_rects = extract_clean_figures_and_alt_crops(doc, year)
    raw_pages = extract_page_text_excluding_figures(doc, q_fig_rects)
    doc.close()

    # Normaliza apenas o cabeçalho Questão X. para o split
    normalized_full = re.sub(r"Quest\s*[˜~]?\s*a\s*o", "Questão", raw_pages, flags=re.IGNORECASE)
    year_int = int(year)

    q_pattern = re.compile(
        r"Quest(?:ão|ao)\s*(\d{1,2})\s*[\.\-]\s*(.*?)(?=Quest(?:ão|ao)\s*\d{1,2}\s*[\.\-]|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    questions = []
    for num_str, raw_body in q_pattern.findall(normalized_full):
        q_num = int(num_str)
        materia = get_subject(year_int, q_num)
        if not INCLUDE_LANGUAGES and materia in ("Inglês", "Português"):
            continue

        parts = re.split(r"(?:^|\n|\s)([A-E])\s*\(\s*\)\s*", raw_body.strip())
        enunciado = fix_portuguese_accents_and_reflow(parts[0])
        alternativas = {k: "Consulte o enunciado / figura" for k in ("A", "B", "C", "D", "E")}

        if len(parts) >= 11:
            for i in range(1, len(parts) - 1, 2):
                letter = parts[i].upper()
                alt_text = parts[i + 1].strip()
                if letter == "E":
                    alt_text = re.sub(r"\n\s*\d{1,2}\s*$", "", alt_text).strip()
                    alt_text = re.sub(r"\n\s*(?:FÍSICA|QUÍMICA|MATEMÁTICA|INGLÊS|PORTUGUÊS|F\s*´\s*I\s*S\s*I\s*C\s*A).*$", "", alt_text, flags=re.DOTALL | re.IGNORECASE).strip()
                if letter in alternativas:
                    alternativas[letter] = clean_cmex_alternative(alt_text)

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
            "subtopico": "Com Figura Oficial" if q_num in q_figures else "Questão Oficial 1ª Fase",
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

    print(f"=== Reprocessando ITA {EXAM_YEAR} com Limpeza Tipográfica e Recorte Isolado ===")
    if fetch_pdf(prova_urls, prova_path):
        fetch_pdf(gab_urls, gab_path)
        gab_map = parse_gabarito_pdf(gab_path)
        extracted = parse_exam(prova_path, EXAM_YEAR, gab_map)
        for q in extracted:
            by_id[q["id"]] = q
        prova_path.unlink(missing_ok=True)
        gab_path.unlink(missing_ok=True)
        print(f"  ✓ {len(extracted)} questões atualizadas com sucesso!")

    final_questions = sorted(by_id.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_questions, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
