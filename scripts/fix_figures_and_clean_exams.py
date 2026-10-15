import re
import json
import subprocess
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
    VERIFIED_LATEX_OVERRIDES,
)

def download_clean_official_pdf(year: str, dest: Path) -> bool:
    """
    Baixa EXCLUSIVAMENTE o Caderno de Prova Original Limpo (sem marcações de cursinho).
    Prioriza o PDF '_prova.pdf' (cópia fiel do caderno oficial do ITA) ou o próprio site do ITA via curl TLS 1.2.
    """
    clean_urls = [
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase_prova.pdf",
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ITA{year}_1fase_prova.pdf",
        f"https://web.archive.org/web/2id_/https://www.vestibular.ita.br/provas/{year}_fase1.pdf",
        f"https://www.vestibular.ita.br/provas/{year}_fase1.pdf",
    ]
    for url in clean_urls:
        try:
            if "vestibular.ita.br" in url and "archive.org" not in url:
                cmd = [
                    "curl", "-4", "--tlsv1.2", "--tls-max", "1.2",
                    "--ciphers", "DEFAULT@SECLEVEL=1", "-k", "-L", "-s", "--fail",
                    "--connect-timeout", "6", "--max-time", "15", "-o", str(dest), url
                ]
                subprocess.run(cmd, check=False)
                if dest.exists() and dest.stat().st_size > 15_000 and dest.read_bytes()[:4] == b"%PDF":
                    print(f"  ✓ Caderno Oficial Limpo ITA {year} baixado direto da banca: {url}")
                    return True
            else:
                r = requests.get(url, headers=HEADERS, timeout=20)
                if r.status_code == 200 and len(r.content) > 15_000 and r.content[:4] == b"%PDF":
                    dest.write_bytes(r.content)
                    print(f"  ✓ Caderno Oficial Limpo ITA {year} baixado: {url}")
                    return True
        except Exception:
            pass
    return False

def download_clean_gabarito(year: str, dest: Path) -> bool:
    gab_urls = [
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase_gabarito.pdf",
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ITA{year}_1fase_gabarito.pdf",
        f"https://web.archive.org/web/2id_/https://www.vestibular.ita.br/provas/gabarito_{year}.pdf",
    ]
    for url in gab_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200 and len(r.content) > 3_000 and r.content[:4] == b"%PDF":
                dest.write_bytes(r.content)
                return True
        except Exception:
            pass
    return False

def extract_uncropped_clean_figures(doc: fitz.Document, year: str) -> tuple[dict[int, str], dict[int, list[tuple[int, fitz.Rect]]]]:
    """
    Recorta figuras do Caderno Oficial Limpo com Margem Generosa (Full-Figure Dilation):
    - Une todos os traços vetoriais, eixos, setas e legendas da questão;
    - Expande a caixa em 18pt em todas as direções para NUNCA cortar pedaços do desenho,
      respeitando apenas o limite da coluna de texto do enunciado.
    """
    q_figures = {}
    q_fig_rects = {}

    for p_idx, page in enumerate(doc):
        blocks = page.get_text("blocks")
        q_anchors = []
        long_text_blocks = []

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            cleaned = fix_portuguese_accents_and_reflow(text)
            m = re.search(r"Quest(?:ão|ao)\s*(\d{1,2})\s*[.\-]", cleaned, re.IGNORECASE)
            if m:
                q_anchors.append((int(m.group(1)), y0, x0))
            # Considera apenas parágrafos largos (> 65 chars) como parede de texto
            if len(cleaned) > 65 and (x1 - x0) > 130:
                long_text_blocks.append(fitz.Rect(x0, y0, x1, y1))

        q_anchors.sort(key=lambda item: item[1])
        if not q_anchors:
            continue

        # Coleta todas as imagens e todos os desenhos vetoriais (sem descartar elementos menores de circuitos/eixos)
        graphic_rects = []
        for img_info in page.get_images(full=True):
            for r in page.get_image_rects(img_info[0]):
                if r.width > 30 and r.height > 25 and r.y0 > 48:
                    graphic_rects.append(r)

        try:
            # x_tolerance e y_tolerance maiores fundem partes separadas do mesmo diagrama!
            for d_rect in page.cluster_drawings(x_tolerance=18, y_tolerance=18):
                if 35 < d_rect.width < page.rect.width * 0.95 and 28 < d_rect.height < page.rect.height * 0.75 and d_rect.y0 > 48:
                    graphic_rects.append(d_rect)
        except Exception:
            try:
                for d_rect in page.cluster_drawings():
                    if 35 < d_rect.width < page.rect.width * 0.95 and 28 < d_rect.height < page.rect.height * 0.75 and d_rect.y0 > 48:
                        graphic_rects.append(d_rect)
            except Exception:
                pass

        for idx, (q_num, y_start, _) in enumerate(q_anchors):
            y_end = q_anchors[idx + 1][1] - 4 if idx + 1 < len(q_anchors) else page.rect.height - 32
            matching = [r for r in graphic_rects if (r.y0 >= y_start - 8 and r.y1 <= y_end + 10)]
            if not matching:
                continue

            union_r = matching[0]
            for mr in matching[1:]:
                union_r |= mr

            # Inclui TODOS os rótulos de texto curtos (eixos, variáveis, legendas) ao redor de 35pt da figura
            for b in blocks:
                bx0, by0, bx1, by1, btxt, *_ = b
                b_clean = btxt.strip()
                if not b_clean or re.search(r"Quest(?:ão|ao)\s*\d", b_clean, re.IGNORECASE):
                    continue
                if re.match(r"^[A-E]\s*[(]\s*[)]", b_clean):
                    continue
                if len(b_clean) <= 42 and (by0 >= union_r.y0 - 25 and by1 <= union_r.y1 + 25):
                    if bx0 >= union_r.x0 - 45 and bx1 <= union_r.x1 + 65:
                        union_r |= fitz.Rect(bx0, by0, bx1, by1)

            # Margem generosa de 16pt para nunca cortar bordas de figuras, setas ou subscritos
            left_limit = 15
            if union_r.x0 > 210:
                # Figura ao lado direito do texto: respeita apenas o fim dos parágrafos longos à esquerda
                left_paras = [
                    tb for tb in long_text_blocks
                    if tb.y1 > union_r.y0 + 5 and tb.y0 < union_r.y1 - 5 and tb.x1 <= union_r.x0 + 8
                ]
                if left_paras:
                    cand = max(tb.x1 for tb in left_paras) + 3
                    if cand < union_r.x0:
                        left_limit = cand

            clip = fitz.Rect(
                max(left_limit, union_r.x0 - 16),
                max(45, union_r.y0 - 14),
                min(page.rect.width - 12, union_r.x1 + 18),
                min(y_end + 8, union_r.y1 + 14)
            )
            clip = clip & page.rect
            if clip.is_empty or clip.width < 35 or clip.height < 30:
                continue

            try:
                pix = page.get_pixmap(clip=clip, dpi=240)
                fname = f"ita_{year}_q{q_num:02d}.png"
                pix.save(str(IMG_DIR / fname))
                q_figures[q_num] = f"data/images/{fname}"
                q_fig_rects.setdefault(q_num, []).append((p_idx, clip))
            except Exception:
                pass

    return q_figures, q_fig_rects

def fetch_commented_resolutions_text_only(year: str) -> dict[int, tuple[str, str]]:
    """
    Baixa o PDF comentado APENAS em memória para extrair o TEXTO da Resolução Comentada e o Gabarito,
    JAMAIS recortando imagens dele (para nunca trazer marcações de gabarito ou marca d'água).
    """
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
            # Remove lixo de marca d'água "OBJETIVO" do texto da resolução
            res_txt = re.sub(r"\bOBJETIVO\b", "", res_txt, flags=re.IGNORECASE).strip()
            if len(res_txt) > 15:
                res_map[q_num] = (gab, f"Resolução Comentada ({year}):\n{res_txt}\n\nGabarito Oficial: {gab}")
    except Exception:
        pass
    return res_map

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    from scripts.auto_ita_crawler import parse_exam

    clean_db = {}

    # Processa todos os anos que possuem Caderno Oficial Limpo (sem gabarito marcado na folha!)
    for year in ["2027", "2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019"]:
        prova_path = DATA_DIR / f"clean_ita_{year}.pdf"
        gab_path = DATA_DIR / f"clean_gab_{year}.pdf"

        print(f"=== Processando Caderno Oficial Limpo ITA {year} ===")
        if not download_clean_official_pdf(year, prova_path):
            print(f"  [Info] Pulando {year}: caderno limpo sem marcação não disponível no mirror.")
            continue

        has_gab = download_clean_gabarito(year, gab_path)
        gab_map = parse_gabarito_pdf(gab_path) if has_gab else {}

        # Usa o extrator de figuras sem cortes (Full-Figure Dilation)
        doc = fitz.open(prova_path)
        q_figs, q_rects = extract_uncropped_clean_figures(doc, year)
        doc.close()

        extracted = parse_exam(prova_path, "ITA", year, gab_map, True)
        res_text_map = fetch_commented_resolutions_text_only(year)

        for q in extracted:
            qn = q["numero"]
            # Substitui pela figura recém-recortada com margem expandida (sem cortes)
            q["figura"] = q_figs.get(qn)
            if qn in res_text_map:
                gab_comm, res_comm = res_text_map[qn]
                if not gab_map.get(qn):
                    q["gabarito"] = gab_comm
                q["resolucao"] = res_comm
            clean_db[q["id"]] = q

        print(f"  ✓ ITA {year}: {len(extracted)} questões limpas | {len(q_figs)} figuras inteiras sem corte | {len(res_text_map)} resoluções comentadas")
        prova_path.unlink(missing_ok=True)
        gab_path.unlink(missing_ok=True)

    final_list = sorted(clean_db.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== CONCLUÍDO! {len(final_list)} questões 100% LIMPAS (sem respostas marcadas na imagem e sem cortes)! ===")

if __name__ == "__main__":
    main()
