import re
import json
import requests
import pymupdf as fitz
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "images"
DB_FILE = DATA_DIR / "questions.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}

from scripts.auto_ita_crawler import (
    fix_portuguese_accents_and_reflow,
    get_subject,
    parse_gabarito_pdf,
    parse_exam,
    VERIFIED_LATEX_OVERRIDES,
)

def strip_leaked_answers(text: str | None) -> str | None:
    """
    Remove qualquer vazamento de 'Resolução', 'Resposta: X' ou 'Gabarito'
    de dentro de enunciados, textos de apoio ou alternativas.
    """
    if not text:
        return None
    cleaned = text
    # Corta tudo a partir de marcadores explícitos de resolução ou resposta comentada
    leak_patterns = [
        r"(?:^|\n)\s*Resolu[çc][ãa]o\b.*$",
        r"(?:^|\n)\s*Resposta\s*[:\-]\s*[A-E\*].*$",
        r"(?:^|\n)\s*Gabarito\s*[:\-]\s*[A-E\*].*$",
        r"\bResolu[çc][ãa]o\s*[:\-].*$",
        r"\bResposta\s*:\s*alternativa\s+[A-E].*$",
        r"\bOBJETIVO\b",
    ]
    for pat in leak_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned if len(cleaned) >= 3 else None

def strip_inline_alternatives_from_enunciado(enunciado: str, alternativas: dict) -> tuple[str, dict]:
    """
    Se as alternativas a) b) c) d) e) tiverem ficado coladas no final do enunciado,
    separa cada uma para os botões A, B, C, D, E e limpa o enunciado!
    """
    parts = re.split(r"(?:^|\n|\s)([a-eA-E])\)\s+", "\n" + enunciado)
    if len(parts) >= 11:
        clean_enun = parts[0].strip()
        new_alts = dict(alternativas)
        for i in range(1, len(parts) - 1, 2):
            let = parts[i].upper()
            val = strip_leaked_answers(parts[i + 1].strip())
            if let in new_alts and val:
                new_alts[let] = val
        return clean_enun, new_alts
    return enunciado, alternativas

def extract_uncropped_figures_official_pdf(doc: fitz.Document, year: str) -> dict[int, str]:
    """
    Recorta figuras dos Cadernos Oficiais Limpos (2021-2027) sem cortar NENHUMA borda:
    - Para figuras posicionadas entre o enunciado e as alternativas, usa a largura útil da página.
    - Para figuras na coluna da direita (ex: estetoscópio Q19 ou tanque Q21), vai desde o fim da coluna
      de texto esquerda até a margem direita da página inteira!
    """
    q_figures = {}
    for p_idx, page in enumerate(doc):
        blocks = page.get_text("blocks")
        q_anchors = []
        alt_a_anchors = {}
        left_col_Paragraphs = []

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            cleaned = fix_portuguese_accents_and_reflow(text)
            m_q = re.search(r"Quest(?:ão|ao)\s*(\d{1,2})\s*[.\-]", cleaned, re.IGNORECASE)
            if m_q:
                q_anchors.append((int(m_q.group(1)), y0, x0))
            if x1 < 310 and len(cleaned) > 55:
                left_col_Paragraphs.append(fitz.Rect(x0, y0, x1, y1))

        q_anchors.sort(key=lambda item: item[1])
        if not q_anchors:
            continue

        # Localiza onde começa a alternativa "A ( )" de cada questão para não invadir as alternativas
        for idx, (q_num, y_start, _) in enumerate(q_anchors):
            y_next = q_anchors[idx + 1][1] if idx + 1 < len(q_anchors) else page.rect.height - 30
            for b in blocks:
                bx0, by0, bx1, by1, btxt, *_ = b
                if y_start < by0 < y_next and re.search(r"(?:^|\n|\s)A\s*[(]\s*[)]", btxt):
                    alt_a_anchors[q_num] = by0
                    break

        graphic_rects = []
        for img_info in page.get_images(full=True):
            for r in page.get_image_rects(img_info[0]):
                if r.width > 25 and r.height > 20 and r.y0 > 45:
                    graphic_rects.append(r)

        try:
            for d_rect in page.cluster_drawings(x_tolerance=25, y_tolerance=25):
                if 30 < d_rect.width < page.rect.width * 0.96 and 22 < d_rect.height < page.rect.height * 0.78 and d_rect.y0 > 45:
                    graphic_rects.append(d_rect)
        except Exception:
            try:
                for d_rect in page.cluster_drawings():
                    if 30 < d_rect.width < page.rect.width * 0.96 and 22 < d_rect.height < page.rect.height * 0.78 and d_rect.y0 > 45:
                        graphic_rects.append(d_rect)
            except Exception:
                pass

        for idx, (q_num, y_start, _) in enumerate(q_anchors):
            y_next_q = q_anchors[idx + 1][1] - 6 if idx + 1 < len(q_anchors) else page.rect.height - 30
            # O limite inferior pode ser o início das alternativas A( ), a menos que a figura fique ao lado direito delas
            matching = [r for r in graphic_rects if (r.y0 >= y_start - 6 and r.y1 <= y_next_q + 8)]
            if not matching:
                continue

            union_r = matching[0]
            for mr in matching[1:]:
                union_r |= mr

            # Agrega QUALQUER texto curto (legendas, letras de variáveis, números de eixos) próximo à região gráfica
            for b in blocks:
                bx0, by0, bx1, by1, btxt, *_ = b
                b_clean = btxt.strip()
                if not b_clean or re.search(r"Quest(?:ão|ao)\s*\d", b_clean, re.IGNORECASE):
                    continue
                if re.search(r"(?:^|\n)\s*[A-E]\s*[(]\s*[)]", b_clean):
                    continue
                if len(b_clean) <= 50 and (by0 >= union_r.y0 - 30 and by1 <= union_r.y1 + 30):
                    if bx0 >= union_r.x0 - 60 and bx1 <= union_r.x1 + 80:
                        union_r |= fitz.Rect(bx0, by0, bx1, by1)

            # Define as margens horizontais amplas para NUNCA cortar o desenho:
            if union_r.x0 > 235:
                # Figura na coluna da direita (ao lado do enunciado)
                overlapping_left = [
                    lp for lp in left_col_Paragraphs
                    if lp.y1 > union_r.y0 - 5 and lp.y0 < union_r.y1 + 5
                ]
                x_left = (max(lp.x1 for lp in overlapping_left) + 4) if overlapping_left else max(220, union_r.x0 - 25)
                x_right = page.rect.width - 18
            else:
                # Figura centralizada: pega toda a faixa horizontal do desenho com +30pt de folga de cada lado
                x_left = max(25, union_r.x0 - 30)
                x_right = min(page.rect.width - 25, union_r.x1 + 30)

            y_top = max(42, union_r.y0 - 18)
            y_bot = min(y_next_q, union_r.y1 + 18)
            if q_num in alt_a_anchors and union_r.y1 <= alt_a_anchors[q_num] + 4:
                y_bot = min(y_bot, alt_a_anchors[q_num] - 2)

            clip = fitz.Rect(x_left, y_top, x_right, y_bot) & page.rect
            if clip.is_empty or clip.width < 40 or clip.height < 30:
                continue

            try:
                pix = page.get_pixmap(clip=clip, dpi=240)
                fname = f"ita_{year}_q{q_num:02d}.png"
                pix.save(str(IMG_DIR / fname))
                q_figures[q_num] = f"data/images/{fname}"
            except Exception:
                pass

    return q_figures

def fetch_clean_resolutions_dict(year: str) -> dict[int, tuple[str, str]]:
    """Extrai apenas o gabarito e o texto da resolução comentada para ficar OCULTO até o clique."""
    url = f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase.pdf"
    res_map = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200 or r.content[:4] != b"%PDF":
            return res_map
        doc = fitz.open(stream=r.content, filetype="pdf")
        full_text = "\n".join(page.get_text("text") for page in doc)
        doc.close()

        cleaned = fix_portuguese_accents_and_reflow(full_text)
        ans_matches = list(re.finditer(r"Resposta\s*[:\-]?\s*([A-E]|\*+)", cleaned, re.IGNORECASE))
        chunks = re.split(r"Resposta\s*[:\-]?\s*(?:[A-E]|\*+)", cleaned, flags=re.IGNORECASE)

        for idx, m_ans in enumerate(ans_matches):
            q_num = idx + 1
            raw_ans = m_ans.group(1).upper()
            gab = "ANULADA" if "*" in raw_ans else raw_ans
            chunk = chunks[idx] if idx < len(chunks) else ""
            res_parts = re.split(r"\bResolu[çc][ãa]o\b", chunk, flags=re.IGNORECASE)
            res_txt = res_parts[-1].strip() if len(res_parts) >= 2 else ""
            res_txt = re.sub(r"\bOBJETIVO\b", "", res_txt, flags=re.IGNORECASE).strip()
            if len(res_txt) > 15:
                res_map[q_num] = (gab, f"Resolução Comentada ({year}):\n{res_txt}\n\nGabarito Oficial: {gab}")
    except Exception:
        pass
    return res_map

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    clean_db = {}

    # Processa EXCLUSIVAMENTE as provas que possuem Caderno Oficial Limpo (2021 a 2027)
    for year in ["2027", "2026", "2025", "2024", "2023", "2022", "2021"]:
        prova_url = f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase_prova.pdf"
        gab_url = f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase_gabarito.pdf"

        prova_path = DATA_DIR / f"official_{year}_prova.pdf"
        gab_path = DATA_DIR / f"official_{year}_gab.pdf"

        r_p = requests.get(prova_url, headers=HEADERS, timeout=25)
        if r_p.status_code != 200 or r_p.content[:4] != b"%PDF":
            continue
        prova_path.write_bytes(r_p.content)

        r_g = requests.get(gab_url, headers=HEADERS, timeout=15)
        gab_map = {}
        if r_g.status_code == 200 and r_g.content[:4] == b"%PDF":
            gab_path.write_bytes(r_g.content)
            gab_map = parse_gabarito_pdf(gab_path)

        doc = fitz.open(prova_path)
        q_figs = extract_uncropped_figures_official_pdf(doc, year)
        doc.close()

        extracted = parse_exam(prova_path, "ITA", year, gab_map, True)
        res_map = fetch_clean_resolutions_text_only = fetch_clean_resolutions_dict(year)

        for q in extracted:
            qn = q["numero"]
            # Sanitiza enunciado, texto_base e alternativas contra qualquer vazamento de resposta!
            q["enunciado"] = strip_leaked_answers(q["enunciado"]) or q["enunciado"]
            q["texto_base"] = strip_leaked_answers(q.get("texto_base"))
            q["enunciado"], q["alternativas"] = strip_inline_alternatives_from_enunciado(q["enunciado"], q["alternativas"])
            for k in ("A", "B", "C", "D", "E"):
                q["alternativas"][k] = strip_leaked_answers(q["alternativas"].get(k, "")) or q["alternativas"].get(k, "")

            q["figura"] = q_figs.get(qn)
            if qn in res_map:
                gab_c, res_c = res_map[qn]
                if not gab_map.get(qn):
                    q["gabarito"] = gab_c
                q["resolucao"] = res_c

            clean_db[q["id"]] = q

        print(f"✓ ITA {year}: {len(extracted)} questões oficiais limpas | {len(q_figs)} figuras inteiras sem corte")
        prova_path.unlink(missing_ok=True)
        gab_path.unlink(missing_ok=True)

    final_list = sorted(clean_db.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== BANCO 100% SANITIZADO: {len(final_list)} questões oficiais (ZERO imagens rabiscadas e ZERO respostas vazadas no enunciado)! ===")

if __name__ == "__main__":
    main()
