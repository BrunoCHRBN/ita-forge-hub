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

# Demonstrações completas em LaTeX nativo para questões de destaque
LATEX_SOLUTIONS = {
    "ITA-2025-1F-Q01": {
        "enunciado": f"Seja {D}z = a + 2i{D} um número complexo, em que {D}a \\in \\mathbb{{R}}{D} é positivo. O valor de {D}a{D} para que as representações de {D}1{D}, {D}z{D} e {D}z^2{D} no plano de Argand-Gauss formem um triângulo de área {D}200{D} é:",
        "alternativas": {"A": f"{D}14{D}", "B": f"{D}15{D}", "C": f"{D}16{D}", "D": f"{D}17{D}", "E": f"{D}18{D}"},
        "gabarito": "B",
        "pulo_do_gato": f"Translade os vértices subtraindo {D}1{D}: os vetores que partem da origem passam a ser {D}w_1 = z - 1{D} e {D}w_2 = z^2 - 1 = (z - 1)(z + 1){D}. Assim, {D}w_2 = w_1(z + 1){D} e a área sai imediatamente de {D}\\frac{{1}}{{2}}|w_1|^2 \\cdot |\\text{{Im}}(z+1)|{D}.",
        "resolucao": (
            f"Sejam {D}P_1(1){D}, {D}P_2(z){D} e {D}P_3(z^2){D} os afixos no plano de Argand-Gauss. Transladando a origem para {D}P_1 = 1{D}, obtemos os números complexos:\n"
            f"{D}{D}w_1 = z - 1 = (a - 1) + 2i{D}{D}\n"
            f"{D}{D}w_2 = z^2 - 1 = (z - 1)(z + 1) = w_1 \\cdot (a + 1 + 2i){D}{D}\n"
            f"A área {D}S{D} do triângulo determinado pelos vetores complexos {D}w_1{D} e {D}w_2{D} é dada por:\n"
            f"{D}{D}S = \\frac{{1}}{{2}} |\\text{{Im}}(\\overline{{w_1}} \\cdot w_2)| = \\frac{{1}}{{2}} |w_1|^2 \\cdot |\\text{{Im}}(a + 1 + 2i)|{D}{D}\n"
            f"Como {D}|w_1|^2 = (a - 1)^2 + 2^2 = (a - 1)^2 + 4{D} e {D}\\text{{Im}}(a + 1 + 2i) = 2{D}, temos:\n"
            f"{D}{D}S = \\frac{{1}}{{2}} \\cdot [(a - 1)^2 + 4] \\cdot 2 = (a - 1)^2 + 4{D}{D}\n"
            f"Igualando à área {D}200{D} fornecida no enunciado:\n"
            f"{D}{D}(a - 1)^2 + 4 = 200 \\implies (a - 1)^2 = 196 \\implies a - 1 = 14 \\implies a = 15{D}{D}"
        )
    },
    "ITA-2026-1F-Q01": {
        "pulo_do_gato": f"A interseção dos dois triângulos equiláteros inscritos de lado {D}L = R\\sqrt{{3}}{D} forma um hexágono regular de lado {D}L/3{D}, cuja área equivale a {D}2/3{D} da área de um dos triângulos equiláteros.",
        "resolucao": (
            f"O lado de cada triângulo equilátero inscrito na circunferência de raio {D}R{D} mede {D}L = R\\sqrt{{3}}{D}, e sua área vale:\n"
            f"{D}{D}S_{{\\triangle}} = \\frac{{L^2\\sqrt{{3}}}}{{4}} = \\frac{{3\\sqrt{{3}}}}{{4}}R^2{D}{D}\n"
            f"A região comum aos dois triângulos é obtida retirando-se {D}3{D} pequenos triângulos equiláteros de lado {D}L/3{D} dos vértices de um dos triângulos maiores. Como cada triângulo menor tem área {D}(1/3)^2 = 1/9{D} de {D}S_{{\\triangle}}{D}:\n"
            f"{D}{D}S_{{\\text{{comum}}}} = S_{{\\triangle}} \\left(1 - 3 \\cdot \\frac{{1}}{{9}}\\right) = \\frac{{2}}{{3}} S_{{\\triangle}} = \\frac{{\\sqrt{{3}}}}{{2}}R^2{D}{D}"
        )
    },
    "ITA-2026-1F-Q02": {
        "pulo_do_gato": f"Fatore os números dados em potências de {D}5{D} e {D}7{D}: {D}6125 = 5^3 \\cdot 7^2{D} e {D}13{{,}}72 = \\frac{{343}}{{25}} = \\frac{{7^3}}{{5^2}}{D}. Isso gera um sistema linear 2x2 imediato em {D}\\log_{{45}} 5{D} e {D}\\log_{{45}} 7{D}.",
        "resolucao": (
            f"Reescrevendo os dados na forma fracionária e fatorada:\n"
            f"1. {D}6125 = 125 \\times 49 = 5^3 \\cdot 7^2 \\implies 3\\log_{{45}} 5 + 2\\log_{{45}} 7 = 2{{,}}2908{D}\n"
            f"2. {D}13{{,}}72 = \\frac{{1372}}{{100}} = \\frac{{343}}{{25}} = 7^3 \\cdot 5^{{-2}} \\implies -2\\log_{{45}} 5 + 3\\log_{{45}} 7 = 0{{,}}6880{D}\n\n"
            f"Multiplicando a primeira equação por {D}2{D} e a segunda por {D}3{D} e somando ambas para eliminar {D}\\log_{{45}} 5{D}:\n"
            f"{D}{D}(4 + 9)\\log_{{45}} 7 = 2(2{{,}}2908) + 3(0{{,}}6880) = 6{{,}}6456{D}{D}\n"
            f"{D}{D}\\log_{{45}} 7 = \\frac{{6{{,}}6456}}{{13}} = 0{{,}}5112{D}{D}"
        )
    },
    "ITA-2025-1F-Q14": {
        "pulo_do_gato": f"Combine Torricelli no trecho horizontal ({D}v_B^2 = 2a_0\\ell{D}), conservação de energia mecânica na descida circular de raio {D}R{D} ({D}v_C^2 = v_B^2 + 2gR{D}) e conservação da quantidade de movimento na colisão perfeitamente inelástica com massa igual ({D}v_f = v_C / 2{D}).",
        "resolucao": (
            f"1. **Trecho horizontal acelerado (de {D}A{D} até {D}B{D}):**\n"
            f"Partindo do repouso com aceleração constante {D}a_0{D} por uma distância {D}\\ell{D}:\n"
            f"{D}{D}v_B^2 = 2 a_0 \\ell{D}{D}\n"
            f"2. **Descida pelo quarto de circunferência vertical de raio {D}R{D} (de {D}B{D} até {D}C{D}):**\n"
            f"Pela conservação da energia mecânica:\n"
            f"{D}{D}\\frac{{1}}{{2}}mv_C^2 = \\frac{{1}}{{2}}mv_B^2 + mgR \\implies v_C = \\sqrt{{2a_0\\ell + 2gR}}{D}{D}\n"
            f"3. **Colisão perfeitamente inelástica em {D}D{D} com outro carrinho de mesma massa {D}m{D}:**\n"
            f"Pela conservação do momento linear:\n"
            f"{D}{D}m v_C = (m + m) v_f \\implies v_f = \\frac{{v_C}}{{2}} = \\frac{{1}}{{2}}\\sqrt{{2a_0\\ell + 2gR}}{D}{D}"
        )
    },
    "ITA-2025-1F-Q18": {
        "pulo_do_gato": f"Como há vácuo no compartimento da mola e a expansão do gás ideal é isotérmica ({D}\\Delta U = 0{D}), todo o calor {D}Q{D} fornecido converte-se integralmente em ganho de energia potencial elástica da mola.",
        "resolucao": (
            f"1. **Deformação inicial de equilíbrio ({D}x_0{D}):**\n"
            f"O gás à pressão {D}P_0{D} atua sobre o êmbolo de área {D}A{D} contra a mola no vácuo:\n"
            f"{D}{D}k x_0 = P_0 A \\implies x_0 = \\frac{{P_0 A}}{{k}}{D}{D}\n"
            f"2. **Balanço energético no processo reversível e isotérmico ({D}\\Delta U = 0{D}):**\n"
            f"{D}{D}Q = W_{{\\text{{gás}}}} = \\Delta E_{{\\text{{elástica}}}} = \\frac{{1}}{{2}}k x_f^2 - \\frac{{1}}{{2}}k x_0^2{D}{D}\n"
            f"Substituindo {D}x_0{D} e isolando {D}x_f{D}:\n"
            f"{D}{D}x_f = \\sqrt{{\\frac{{2Q}}{{k}} + \\left(\\frac{{P_0 A}}{{k}}\\right)^2}}{D}{D}"
        )
    },
    "ITA-2025-1F-Q19": {
        "pulo_do_gato": f"Como a potência sonora {D}P = I \\cdot A{D} é integralmente transferida da área {D}\\pi R_1^2{D} para {D}\\pi R_2^2{D}, a razão de intensidades vale {D}I_2 / I_1 = (R_1 / R_2)^2{D}. Aplicando a definição de nível sonoro em decibéis, o expoente {D}2{D} multiplica o {D}10\\log{D}.",
        "resolucao": (
            f"Sendo a energia sonora integralmente transferida do pistão maior (área {D}A_1 = \\pi R_1^2{D}) para o menor (área {D}A_2 = \\pi R_2^2{D}), a conservação da potência acústica fornece:\n"
            f"{D}{D}I_1 A_1 = I_2 A_2 \\implies \\frac{{I_2}}{{I_1}} = \\frac{{A_1}}{{A_2}} = \\left(\\frac{{R_1}}{{R_2}}\\right)^2{D}{D}\n"
            f"A amplificação sonora {D}\\Delta \\beta{D}, em {D}\\text{{dB}}{D}, é dada por:\n"
            f"{D}{D}\\Delta \\beta = 10 \\log\\left(\\frac{{I_2}}{{I_1}}\\right) = 10 \\log\\left(\\frac{{R_1}}{{R_2}}\\right)^2 = 20 \\log\\left(\\frac{{R_1}}{{R_2}}\\right){D}{D}"
        )
    }
}

def clean_resolution_text(raw: str) -> str:
    """Limpa acentos do PDF comentado SEM cortar a palavra Resolução!"""
    text = raw.replace("\ufffd", "")
    text = re.sub(r"ITA\s*[\-–—]\s*1\.?[ªa]?\s*Fase\s*[\-–—]?\s*[A-Za-zçÇ]+\s*/\s*\d{4}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bOBJETIVO\b", "", text, flags=re.IGNORECASE)

    accent_map = [
        (r"[˜~]\s*a", "ã"), (r"[˜~]\s*o", "õ"), (r"[˜~]\s*A", "Ã"), (r"[˜~]\s*O", "Õ"),
        (r"´\s*a", "á"), (r"´\s*e", "é"), (r"´\s*[ıi]", "í"), (r"´\s*o", "ó"), (r"´\s*u", "ú"),
        (r"ˆ\s*a", "â"), (r"ˆ\s*e", "ê"), (r"ˆ\s*o", "ô"), (r"`\s*a", "à"),
        (r"c\s*¸\s*", "ç"), (r"¸\s*c", "ç"), (r"ı", "í")
    ]
    for pat, repl in accent_map:
        text = re.sub(pat, repl, text)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not re.match(r"^\d{1,2}\Z", ln.strip())]
    return "\n".join(lines).strip()

def extract_resolutions_for_year(year: str) -> dict[int, dict]:
    """
    Baixa o PDF de resolução comentada do ano e extrai para cada questão:
    - O texto da resolução (sem ser apagado!)
    - O recorte em imagem da caixa 'Resolução' (caso a demonstração tenha gráficos, matrizes ou frações em imagem)
    """
    url = f"https://www.curso-objetivo.br/vestibular/resolucao-comentada/ita/{year}/1fase/ita{year}_1fase.pdf"
    out = {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200 or r.content[:4] != b"%PDF":
            return out

        doc = fitz.open(stream=r.content, filetype="pdf")
        q_counter = 0

        for p_idx, page in enumerate(doc):
            blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1] / 10), b[0]))
            page_text = "\n".join(b[4] for b in blocks)
            cleaned_page = clean_resolution_text(page_text)

            # Encontra posições de "Resolução" e "Resposta: X" na página para recortar também a imagem da resolução
            res_anchors = []
            ans_anchors = []
            for b in blocks:
                x0, y0, x1, y1, btxt, *_ = b
                b_clean = clean_resolution_text(btxt)
                if re.search(r"\bResolu[çc][ãa]o\b", b_clean, re.IGNORECASE):
                    res_anchors.append(y0)
                m_ans_b = re.search(r"Resposta\s*[:\-]?\s*([A-E]|\*+)", b_clean, re.IGNORECASE)
                if m_ans_b:
                    ans_anchors.append((y1, m_ans_b.group(1).upper()))

            # Também separa pelo texto completo da página
            ans_matches = list(re.finditer(r"Resposta\s*[:\-]?\s*([A-E]|\*+)", cleaned_page, re.IGNORECASE))
            if not ans_matches:
                continue

            chunks = re.split(r"Resposta\s*[:\-]?\s*(?:[A-E]|\*+)", cleaned_page, flags=re.IGNORECASE)

            for idx, m_ans in enumerate(ans_matches):
                q_counter += 1
                raw_ans = m_ans.group(1).upper()
                gab = "ANULADA" if "*" in raw_ans else raw_ans
                chunk = chunks[idx] if idx < len(chunks) else ""

                res_parts = re.split(r"\bResolu[çc][ãa]o\b", chunk, flags=re.IGNORECASE)
                res_txt = res_parts[-1].strip() if len(res_parts) >= 2 else ""

                # Recorta a imagem do bloco de Resolução (entre 'Resolução' e 'Resposta: X')
                res_img_rel = None
                if idx < len(res_anchors) and idx < len(ans_anchors):
                    y_top = max(35, res_anchors[idx] - 4)
                    y_bot = min(page.rect.height - 25, ans_anchors[idx][0] + 6)
                    if y_bot - y_top > 32:
                        clip = fitz.Rect(28, y_top, page.rect.width - 28, y_bot) & page.rect
                        try:
                            pix = page.get_pixmap(clip=clip, dpi=200)
                            fname = f"res_ita_{year}_q{q_counter:02d}.png"
                            out_img = IMG_DIR / fname
                            pix.save(str(out_img))
                            if out_img.exists() and out_img.stat().st_size > 1000:
                                res_img_rel = f"data/images/{fname}"
                        except Exception:
                            pass

                out[q_counter] = {
                    "gabarito": gab,
                    "resolucao_texto": res_txt,
                    "figura_resolucao": res_img_rel
                }

        doc.close()
    except Exception as e:
        print(f"  [Aviso] Falha ao processar PDF comentado de {year}: {e}")
    return out

def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    questions = json.loads(DB_FILE.read_text(encoding="utf-8"))

    by_year = {}
    for q in questions:
        by_year.setdefault(str(q["ano"]), []).append(q)

    total_injected = 0
    for year, q_list in sorted(by_year.items(), reverse=True):
        print(f"Extraindo resoluções comentadas do ITA {year}...")
        res_data = extract_resolutions_for_year(year)
        count_yr = 0
        for q in q_list:
            qn = q["numero"]
            q_id = q["id"]

            if qn in res_data:
                info = res_data[qn]
                if info["resolucao_texto"] and len(info["resolucao_texto"]) > 10:
                    q["resolucao"] = info["resolucao_texto"]
                if info["figura_resolucao"]:
                    q["figura_resolucao"] = info["figura_resolucao"]
                count_yr += 1
                total_injected += 1

            # Se a questão estiver no dicionário de demonstrações LaTeX nativas, aplica a versão LaTeX premium!
            if q_id in LATEX_SOLUTIONS:
                ov = LATEX_SOLUTIONS[q_id]
                for k, v in ov.items():
                    q[k] = v

        print(f"  ✓ ITA {year}: {count_yr}/{len(q_list)} questões enriquecidas com resolução comentada!")

    DB_FILE.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== CONCLUÍDO! {total_injected} resoluções comentadas injetadas no banco! ===")

if __name__ == "__main__":
    main()
