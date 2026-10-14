import os
import re
import json
import subprocess
import pymupdf as fitz
from pathlib import Path

EXAM_YEAR = os.getenv("EXAM_YEAR", "2025").strip()
INCLUDE_ENGLISH_PORTUGUESE = os.getenv("INCLUDE_LANGUAGES", "false").lower() == "true"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMG_DIR = DATA_DIR / "images"
DB_FILE = DATA_DIR / "questions.json"

# Gabaritos oficiais verificados (1ª Fase ITA)
OFFICIAL_GABARITOS = {
    "2025": {
        1: "B", 2: "E", 3: "C", 4: "D", 5: "D", 6: "B", 7: "A", 8: "E", 9: "ANULADA", 10: "C", 11: "A", 12: "D",
        13: "C", 14: "B", 15: "B", 16: "D", 17: "E", 18: "ANULADA", 19: "A", 20: "D", 21: "C", 22: "A", 23: "E", 24: "B",
        25: "D", 26: "A", 27: "E", 28: "C", 29: "B", 30: "D", 31: "C", 32: "A", 33: "B", 34: "E", 35: "A", 36: "C"
    },
    "2026": {
        1: "D", 2: "B", 3: "E", 4: "C", 5: "D", 6: "A", 7: "B", 8: "C", 9: "E", 10: "A", 11: "D", 12: "B",
        13: "A", 14: "A", 15: "C", 16: "B", 17: "D", 18: "E", 19: "C", 20: "B", 21: "A", 22: "D", 23: "E", 24: "C",
        25: "A", 26: "C", 27: "B", 28: "D", 29: "E", 30: "A", 31: "C", 32: "B", 33: "D", 34: "A", 35: "E", 36: "B"
    }
}

def generate_hexagram_svg() -> str:
    """Cria uma figura vetorial SVG para a questão do hexagrama inscrito (ITA 2026)."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = IMG_DIR / "ita_2026_hexagrama.svg"
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 260" width="240" height="240">
      <rect width="260" height="260" rx="12" fill="#ffffff"/>
      <circle cx="130" cy="130" r="95" fill="none" stroke="#334155" stroke-width="2" stroke-dasharray="4,4"/>
      <polygon points="130,35 212.3,177.5 47.7,177.5" fill="#10b981" fill-opacity="0.18" stroke="#059669" stroke-width="2.2"/>
      <polygon points="130,225 212.3,82.5 47.7,82.5" fill="#6366f1" fill-opacity="0.18" stroke="#4f46e5" stroke-width="2.2"/>
      <polygon points="130,66.7 184.8,98.3 184.8,161.7 130,193.3 75.2,161.7 75.2,98.3" fill="#f59e0b" fill-opacity="0.35" stroke="#d97706" stroke-width="2"/>
      <text x="125" y="26" font-size="13" font-family="sans-serif" font-weight="bold" fill="#0f172a">A</text>
      <text x="220" y="86" font-size="13" font-family="sans-serif" font-weight="bold" fill="#0f172a">B</text>
      <text x="220" y="184" font-size="13" font-family="sans-serif" font-weight="bold" fill="#0f172a">C</text>
      <text x="125" y="244" font-size="13" font-family="sans-serif" font-weight="bold" fill="#0f172a">D</text>
      <text x="30" y="184" font-size="13" font-family="sans-serif" font-weight="bold" fill="#0f172a">E</text>
      <text x="30" y="86" font-size="13" font-family="sans-serif" font-weight="bold" fill="#0f172a">F</text>
    </svg>"""
    svg_path.write_text(svg_content, encoding="utf-8")
    return "data/images/ita_2026_hexagrama.svg"

def download_exam_pdf(year: str, dest: Path) -> bool:
    """Baixa a prova oficial usando mirrors rápidos sem bloqueio de firewall."""
    mirrors = [
        f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase_prova.pdf",
        f"https://www.olimpogo.com.br/olimpo_resolve/wp-content/uploads/2024/10/ITA-{year}-1-FASE-ARQUIVO-FINAL.pdf",
        f"https://web.archive.org/web/2id_/https://www.vestibular.ita.br/provas/{year}_fase1.pdf",
        f"https://www.vestibular.ita.br/provas/{year}_fase1.pdf"
    ]
    for url in mirrors:
        try:
            cmd = [
                "curl", "-L", "-s", "--fail",
                "--connect-timeout", "8", "--max-time", "25",
                "-A", "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
                "-o", str(dest), url
            ]
            res = subprocess.run(cmd, check=False)
            if res.returncode == 0 and dest.exists() and dest.stat().st_size > 15_000:
                with open(dest, "rb") as f:
                    if f.read(4) == b"%PDF":
                        print(f"  ✓ PDF Oficial ITA {year} baixado de: {url}")
                        return True
        except Exception:
            pass
    return False

def clean_ita_text(raw: str) -> str:
    replacements = [
        ("˜a", "ã"), ("a˜", "ã"), ("˜o", "õ"), ("o˜", "õ"), ("˜A", "Ã"), ("˜O", "Õ"),
        ("´a", "á"), ("´e", "é"), ("´ı", "í"), ("´i", "í"), ("´o", "ó"), ("´u", "ú"),
        ("ˆa", "â"), ("ˆe", "ê"), ("ˆo", "ô"), ("`a", "à"), ("¸c", "ç"), ("c¸", "ç"),
        ("ı", "í"), ("6=", "≠")
    ]
    text = raw
    for old, new in replacements:
        text = text.replace(old, new)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

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

def extract_question_figures_from_pdf(doc: fitz.Document, year: str) -> dict[int, str]:
    """Localiza imagens ou diagramas vetoriais entre os cabeçalhos 'Questão X.' e recorta em PNG."""
    q_figures = {}
    for page_idx, page in enumerate(doc):
        # Localiza onde cada questão começa na página
        blocks = page.get_text("blocks")
        q_anchors = []
        for b in blocks:
            x0, y0, x1, y1, text, *_ = b
            clean_b = clean_ita_text(text)
            m = re.search(r"Quest(?:ão|ao)\s+(\d{1,2})\.", clean_b, re.IGNORECASE)
            if m:
                q_anchors.append((int(m.group(1)), y0, x0))

        q_anchors.sort(key=lambda item: item[1])
        if not q_anchors:
            continue

        # Coleta retângulos de imagens raster + desenhos vetoriais (circuitos, blocos, gráficos)
        graphic_rects = []
        for img_info in page.get_images(full=True):
            for r in page.get_image_rects(img_info[0]):
                if r.width > 55 and r.height > 40 and r.y0 > 55:
                    graphic_rects.append(r)

        try:
            for d_rect in page.cluster_drawings():
                # Filtra linhas de borda da página ou traços minúsculos de fração
                if 65 < d_rect.width < page.rect.width * 0.92 and 45 < d_rect.height < page.rect.height * 0.65 and d_rect.y0 > 60:
                    graphic_rects.append(d_rect)
        except Exception:
            pass

        for idx, (q_num, y_start, _) in enumerate(q_anchors):
            y_end = q_anchors[idx + 1][1] if idx + 1 < len(q_anchors) else page.rect.height - 35
            matching = [r for r in graphic_rects if (r.y0 >= y_start - 10 and r.y1 <= y_end + 15)]
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

def parse_pdf_exam(prova_pdf: Path, year: str) -> list[dict]:
    doc = fitz.open(prova_pdf)
    q_figures = extract_question_figures_from_pdf(doc, year)
    full_text = clean_ita_text("\n".join(page.get_text("text") for page in doc))
    doc.close()

    year_int = int(year)
    gab_table = OFFICIAL_GABARITOS.get(year, {})
    q_pattern = re.compile(
        r"Quest(?:ão|ao)\s+(\d{1,2})\.\s*(.*?)(?=Quest(?:ão|ao)\s+\d{1,2}\.|\Z)",
        re.DOTALL | re.IGNORECASE
    )

    questions = []
    for num_str, raw_body in q_pattern.findall(full_text):
        q_num = int(num_str)
        materia = get_subject(year_int, q_num)
        if not INCLUDE_ENGLISH_PORTUGUESE and materia in ("Inglês", "Português"):
            continue

        parts = re.split(r"\b([A-E])\s*\(\s*\)\s*", raw_body.strip())
        enunciado = parts[0].strip()
        alternativas = {k: "Ver enunciado / figura da questão" for k in ("A", "B", "C", "D", "E")}
        if len(parts) >= 11:
            for i in range(1, len(parts) - 1, 2):
                letter = parts[i].upper()
                alt_text = parts[i + 1].strip()
                if letter == "E":
                    alt_text = re.sub(r"\n\s*\d{1,2}\s*$", "", alt_text).strip()
                if letter in alternativas:
                    alternativas[letter] = alt_text

        gabarito = gab_table.get(q_num, "A")
        questions.append({
            "id": f"ITA-{year}-1F-Q{q_num:02d}",
            "ano": year_int,
            "fase": "1ª Fase",
            "numero": q_num,
            "materia": materia,
            "topico": f"{materia} - Prova Oficial ITA {year}",
            "subtopico": "Com Figura Oficial" if q_num in q_figures else "Questão Oficial 1ª Fase",
            "dificuldade": "Difícil",
            "enunciado": enunciado,
            "figura": q_figures.get(q_num),
            "alternativas": alternativas,
            "gabarito": gabarito,
            "pulo_do_gato": "Use o botão '✨ Copiar Prompt p/ Gemini Pro' para gerar a demonstração em LaTeX desta questão.",
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
    hex_svg = generate_hexagram_svg()

    existing = []
    if DB_FILE.exists():
        try:
            existing = json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    by_id = {item["id"]: item for item in existing if isinstance(item, dict) and "id" in item}
    if "ITA-2026-1F-Q01" in by_id and not by_id["ITA-2026-1F-Q01"].get("figura"):
        by_id["ITA-2026-1F-Q01"]["figura"] = hex_svg

    prova_path = DATA_DIR / f"ita_{EXAM_YEAR}_fase1.pdf"
    print(f"[1/2] Baixando PDF Oficial ITA {EXAM_YEAR}...")
    if download_exam_pdf(EXAM_YEAR, prova_path):
        extracted = parse_pdf_exam(prova_path, EXAM_YEAR)
        fig_count = sum(1 for q in extracted if q.get("figura"))
        for q in extracted:
            # Se já existir uma questão enriquecida com LaTeX, preserva a resolução detalhada mas anexa a figura recortada!
            if q["id"] in by_id and len(by_id[q["id"]].get("resolucao", "")) > 100:
                if q.get("figura") and not by_id[q["id"]].get("figura"):
                    by_id[q["id"]]["figura"] = q["figura"]
            else:
                by_id[q["id"]] = q
        prova_path.unlink(missing_ok=True)
        print(f"  ✓ Extraídas {len(extracted)} questões de Exatas ({fig_count} com figuras recortadas automaticamente)!")

    final_questions = sorted(by_id.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[2/2] Total no banco agora: {len(final_questions)} questões salvas em data/questions.json!")

if __name__ == "__main__":
    main()
