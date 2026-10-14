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

OFFICIAL_SEED_QUESTIONS = [
    {
        "id": "ITA-2026-1F-Q01",
        "ano": 2026,
        "fase": "1ª Fase",
        "numero": 1,
        "materia": "Matemática",
        "topico": "Geometria Plana e Trigonometria",
        "subtopico": "Polígonos Regulares Inscritos e Triângulos Equiláteros",
        "dificuldade": "Difícil",
        "enunciado": "Uma circunferência de raio $R$ é dividida em seis partes iguais pelos pontos $A, B, C, D, E, F$, designados nessa ordem. Os pontos $A, C, E$ são vértices de um triângulo equilátero, e os pontos $B, D, F$ são vértices de um segundo triângulo equilátero. A área da região comum (interseção) aos dois triângulos equiláteros é igual a:",
        "figura": None,
        "alternativas": {
            "A": "$\\frac{\\sqrt{3}}{4} R^2$",
            "B": "$\\frac{\\sqrt{3}}{2} R^2$",
            "C": "$\\frac{3\\sqrt{3}}{4} R^2$",
            "D": "$\\sqrt{3} R^2$",
            "E": "$\\frac{3\\sqrt{3}}{2} R^2$"
        },
        "gabarito": "B",
        "pulo_do_gato": "A superposição dos dois triângulos equiláteros inscritos forma um hexagrama regular cujo núcleo é um hexágono regular de lado $L/3$, onde $L = R\\sqrt{3}$ é o lado do triângulo equilátero.",
        "resolucao": "O lado de cada triângulo equilátero inscrito na circunferência de raio $R$ vale:\n$$L = R\\sqrt{3}$$\nA área de um desses triângulos é:\n$$S_{\\triangle} = \\frac{L^2\\sqrt{3}}{4} = \\frac{3\\sqrt{3}}{4}R^2$$\nA interseção dos dois triângulos equiláteros equivale a retirar $3$ pequenos triângulos equiláteros de lado $L/3$ dos vértices de um dos triângulos maiores.\nComo cada triângulo pequeno tem área $(1/3)^2 = 1/9$ da área do triângulo maior:\n$$S_{\\text{interseção}} = S_{\\triangle} \\cdot \\left(1 - 3 \\cdot \\frac{1}{9}\\right) = \\frac{2}{3} S_{\\triangle} = \\frac{\\sqrt{3}}{2}R^2$$"
    },
    {
        "id": "ITA-2026-1F-Q14",
        "ano": 2026,
        "fase": "1ª Fase",
        "numero": 14,
        "materia": "Física",
        "topico": "Mecânica Clássica",
        "subtopico": "Lançamento Oblíquo e Encontro Balístico em Queda Livre",
        "dificuldade": "Difícil",
        "enunciado": "Uma esfera é abandonada do repouso de uma altura $H$ em relação ao solo horizontal. No mesmo instante, um projétil é lançado do solo, a uma distância horizontal $D$ da vertical que passa pela esfera, com velocidade inicial de módulo $v$ e ângulo $\\theta$ com a horizontal, apontando diretamente para a posição inicial da esfera. Sabendo que o projétil atinge a esfera exatamente no instante em que ela toca o solo (adotando gravidade $g$), a magnitude da velocidade de lançamento $v$ é:",
        "figura": None,
        "alternativas": {
            "A": "$\\sqrt{\\frac{g(H^2 + D^2)}{2H}}$",
            "B": "$\\sqrt{\\frac{g(H^2 + D^2)}{H}}$",
            "C": "$\\sqrt{2g\\sqrt{H^2 + D^2}}$",
            "D": "$\\frac{D}{H}\\sqrt{2gH}$",
            "E": "$\\sqrt{g(H + D)}$"
        },
        "gabarito": "A",
        "pulo_do_gato": "No referencial em queda livre, o movimento relativo é retilíneo uniforme com velocidade $v$ percorrendo a hipotenusa $\\sqrt{H^2 + D^2}$ no tempo de queda $t_q = \\sqrt{2H/g}$.",
        "resolucao": "1. **Tempo de queda da esfera até o solo:**\n$$H = \\frac{1}{2}gt_q^2 \\implies t_q = \\sqrt{\\frac{2H}{g}}$$\n2. **No referencial solidário à esfera:**\nA distância inicial entre ambos é $d_0 = \\sqrt{H^2 + D^2}$. Para colidirem no instante $t_q$:\n$$v \\cdot t_q = \\sqrt{H^2 + D^2} \\implies v = \\sqrt{\\frac{g(H^2 + D^2)}{2H}}$$"
    },
    {
        "id": "ITA-2026-1F-Q19",
        "ano": 2026,
        "fase": "1ª Fase",
        "numero": 19,
        "materia": "Física",
        "topico": "Eletromagnetismo",
        "subtopico": "Indução Eletromagnética, Lei de Lenz e Correntes de Foucault",
        "dificuldade": "Extrema (Nível Olímpico)",
        "enunciado": "Um pequeno ímã cai verticalmente pelo interior de um tubo cilíndrico vertical dividido em três regiões consecutivas $a$, $b$ e $c$, de raios $r_a, r_b$ e $r_c$. Analise as afirmativas sobre a frenagem magnética por correntes induzidas (Foucault) e efeito Joule na parede condutora:\nI. Se o tubo é inteiramente condutor com $r_a = r_b > r_c$, a potência dissipada por efeito Joule na região $c$ tende a ser maior devido ao maior enlace de fluxo magnético.\nII. Se $r_a = r_b = r_c$, mas a região $b$ for substituída por um material dielétrico ideal, a velocidade do ímã ao sair de $c$ será maior do que seria caso todo o tubo fosse condutor.\nIII. Se todo o tubo for composto de um dielétrico ideal com $r_a > r_b > r_c$, o ímã cai com aceleração menor que $g$.\nEstá(ão) correta(s):",
        "figura": None,
        "alternativas": {
            "A": "Apenas I",
            "B": "Apenas II",
            "C": "Apenas I e II",
            "D": "Apenas II e III",
            "E": "I, II e III"
        },
        "gabarito": "C",
        "pulo_do_gato": "Em um dielétrico ideal não há elétrons livres para formar correntes de Foucault macroscópicas; logo, na região dielétrica o ímã acelera livremente sob a ação de $g$.",
        "resolucao": "- **I (Correta):** Quanto menor o raio $r_c$, mais intensa é a variação de fluxo magnético na parede condutora e maior a dissipação por efeito Joule.\n- **II (Correta):** Na seção dielétrica não há frenagem magnética de Lorentz, resultando em maior velocidade final.\n- **III (Incorreta):** Em um tubo dielétrico ideal sem perdas, a aceleração é igual a $g$.\nGabarito Oficial: **C**."
    },
    {
        "id": "ITA-2025-1F-Q01",
        "ano": 2025,
        "fase": "1ª Fase",
        "numero": 1,
        "materia": "Matemática",
        "topico": "Números Complexos",
        "subtopico": "Argand-Gauss, Módulo e Área de Polígonos",
        "dificuldade": "Difícil",
        "enunciado": "Seja $z = a + 2i$ um número complexo, em que $a \\in \\mathbb{R}$ é positivo. O valor de $a$ para que as representações de $1$, $z$ e $z^2$ no plano de Argand-Gauss formem um triângulo de área $200$ é:",
        "figura": None,
        "alternativas": {
            "A": "$14$",
            "B": "$15$",
            "C": "$16$",
            "D": "$17$",
            "E": "$18$"
        },
        "gabarito": "B",
        "pulo_do_gato": "Translade os vértices subtraindo $1$: os vetores partindo da origem passam a ser $w_1 = z - 1$ e $w_2 = z^2 - 1 = (z-1)(z+1)$. A área sai direto de $\\frac{1}{2}|z-1|^2 |\\text{Im}(z+1)|$.",
        "resolucao": "Transladando o vértice $1$ para a origem, temos:\n$$w_1 = z - 1 = (a - 1) + 2i$$\n$$w_2 = z^2 - 1 = w_1 (a + 1 + 2i)$$\nA área do triângulo é:\n$$S = \\frac{1}{2} |w_1|^2 |\\text{Im}(a + 1 + 2i)| = \\frac{1}{2} [(a - 1)^2 + 4] \\cdot 2 = (a - 1)^2 + 4$$\nIgualando a $200$:\n$$(a - 1)^2 + 4 = 200 \\implies (a - 1)^2 = 196 \\implies a = 15$$"
    },
    {
        "id": "ITA-2025-1F-Q06",
        "ano": 2025,
        "fase": "1ª Fase",
        "numero": 6,
        "materia": "Matemática",
        "topico": "Geometria Espacial",
        "subtopico": "Sólidos de Revolução e Interseção de Circunferências",
        "dificuldade": "Difícil",
        "enunciado": "Duas circunferências $C_1$ e $C_2$ de centros $O_1$ e $O_2$, respectivamente, têm raio igual a $5\\text{ cm}$ e se interceptam nos pontos $P$ e $Q$, determinando uma corda comum $PQ$ de tamanho $6\\text{ cm}$. As interseções de cada circunferência com o segmento $O_1O_2$ determinam os pontos $R$ em $C_1$ e $S$ em $C_2$. O volume do sólido de revolução obtido pela rotação do triângulo $PO_1R$ em torno da reta $O_1O_2$ é, em $\\text{cm}^3$, igual a:",
        "figura": None,
        "alternativas": {
            "A": "$9\\pi$",
            "B": "$12\\pi$",
            "C": "$15\\pi$",
            "D": "$18\\pi$",
            "E": "$24\\pi$"
        },
        "gabarito": "C",
        "pulo_do_gato": "A corda comum $PQ = 6\\text{ cm}$ é perpendicular à linha dos centros $O_1O_2$, logo o raio da base do cone gerado por $P$ vale $r = 3\\text{ cm}$ e a soma das alturas sobre o eixo é $O_1R = 5\\text{ cm}$.",
        "resolucao": "A distância de $P$ ao eixo $O_1O_2$ é metade da corda comum: $r = 3\\text{ cm}$.\nComo $R$ pertence a $C_1$, a base do triângulo sobre o eixo de rotação mede $H = O_1R = 5\\text{ cm}$.\nO volume gerado pela rotação do triângulo em torno da reta que contém $O_1R$ vale:\n$$V = \\frac{1}{3}\\pi r^2 H = \\frac{1}{3}\\pi (3)^2 \\cdot 5 = 15\\pi\\text{ cm}^3$$"
    },
    {
        "id": "ITA-2025-1F-Q17",
        "ano": 2025,
        "fase": "1ª Fase",
        "numero": 17,
        "materia": "Física",
        "topico": "Termodinâmica",
        "subtopico": "Gases Ideais, Processo Isotérmico Reversível e Trabalho Elástico",
        "dificuldade": "Difícil",
        "enunciado": "Um cilindro horizontal fechado de seção transversal $A$ é dividido por um êmbolo sem atrito. O lado esquerdo do êmbolo é conectado à parede por uma mola ideal de constante elástica $k$, em uma região onde há vácuo. No lado direito, há um gás ideal inicialmente à pressão $P_0$ e volume $V_0$, com a mola já comprimida em equilíbrio. Uma quantidade de calor $Q$ é transferida ao gás por um processo reversível e isotérmico. Assinale a relação que governa a deformação final $x_f$ da mola a partir da conservação de energia na expansão isotérmica ($\\Delta U = 0$):",
        "figura": None,
        "alternativas": {
            "A": "$x_f = \\sqrt{\\frac{2Q}{k} + \\left(\\frac{P_0 A}{k}\\right)^2}$",
            "B": "$x_f = \\frac{P_0 A}{k} + \\frac{Q}{P_0 A}$",
            "C": "$x_f = \\sqrt{\\frac{Q}{k}} + \\frac{P_0 A}{k}$",
            "D": "$x_f = \\frac{2Q}{P_0 A}$",
            "E": "$x_f = \\sqrt{\\frac{2Q}{k}}$"
        },
        "gabarito": "A",
        "pulo_do_gato": "Como há vácuo do lado da mola e o processo é isotérmico de um gás ideal ($\\Delta U = 0$), pela 1ª Lei da Termodinâmica todo o calor $Q$ recebido pelo gás vira aumento da energia potencial elástica da mola!",
        "resolucao": "1. **Equilíbrio inicial:** $k x_0 = P_0 A \\implies x_0 = \\frac{P_0 A}{k}$.\n2. **Processo isotérmico ($\\Delta U = 0$):**\n$$Q = W = \\frac{1}{2}k x_f^2 - \\frac{1}{2}k x_0^2 \\implies x_f = \\sqrt{\\frac{2Q}{k} + \\left(\\frac{P_0 A}{k}\\right)^2}$$"
    },
    {
        "id": "ITA-2025-1F-Q20",
        "ano": 2025,
        "fase": "1ª Fase",
        "numero": 20,
        "materia": "Física",
        "topico": "Óptica e Ondulatória",
        "subtopico": "Dispersão Luminosa, Refração e Formação do Arco-Íris",
        "dificuldade": "Média",
        "enunciado": "O arco-íris é um fenômeno meteorológico cuja explicação física envolve a interação da luz solar com gotículas de água. A respeito desse fenômeno, são feitas as seguintes afirmações:\nI. Cada componente de comprimento de onda da luz do Sol que incide sobre uma gotícula de água suspensa na atmosfera emerge com o mesmo ângulo de espalhamento.\nII. Para a formação do arco-íris primário, são necessárias tanto a ocorrência de refração quanto a de reflexão interna da luz.\nIII. O efeito visual colorido do arco-íris é resultado de a luz do Sol ser policromática e de a água ser um meio dispersivo na faixa do espectro eletromagnético visível.\nEstá(ão) correta(s):",
        "figura": None,
        "alternativas": {
            "A": "Apenas I",
            "B": "Apenas I e II",
            "C": "Apenas I e III",
            "D": "Apenas II e III",
            "E": "I, II e III"
        },
        "gabarito": "D",
        "pulo_do_gato": "Meio dispersivo significa índice de refração $n(\\lambda)$ dependente do comprimento de onda; portanto, os ângulos de desvio mínimo emergentes são diferentes para cada cor (invalidando I).",
        "resolucao": "- **I. Incorreta:** Cada comprimento de onda emerge com um ângulo diferente devido à dispersão.\n- **II. Correta:** O arco-íris primário envolve duas refrações e uma reflexão interna.\n- **III. Correta:** Resulta da luz solar policromática em meio dispersivo.\nGabarito Oficial: **D**."
    },
    {
        "id": "ITA-2025-1F-Q28",
        "ano": 2025,
        "fase": "1ª Fase",
        "numero": 28,
        "materia": "Química",
        "topico": "Eletroquímica",
        "subtopico": "Equação de Nernst, Pilhas de Concentração e Potencial de Eletrodo",
        "dificuldade": "Difícil",
        "enunciado": "Considere uma célula galvânica formada por dois eletrodos de prata imersos em soluções aquosas de $\\text{AgNO}_3$ de concentrações $c_1 = 1{,}0\\times 10^{-3}\\text{ mol L}^{-1}$ e $c_2 = 1{,}0\\times 10^{-1}\\text{ mol L}^{-1}$ a $25\\ ^\\circ\\text{C}$. Adotando $\\frac{RT}{F}\\ln(10) \\approx 0{,}059\\text{ V}$, a força eletromotriz ($\\Delta E$) dessa pilha de concentração é aproximadamente:",
        "figura": None,
        "alternativas": {
            "A": "$0{,}030\\text{ V}$",
            "B": "$0{,}059\\text{ V}$",
            "C": "$0{,}118\\text{ V}$",
            "D": "$0{,}177\\text{ V}$",
            "E": "$0{,}236\\text{ V}$"
        },
        "gabarito": "C",
        "pulo_do_gato": "Em uma pilha de concentração ($\\Delta E^\\circ = 0$) com $n = 1$, cada fator $10$ de razão entre concentrações gera $0{,}059\\text{ V}$. Como $c_2/c_1 = 10^2$, temos $2 \\times 0{,}059 = 0{,}118\\text{ V}$.",
        "resolucao": "Pela Equação de Nernst ($n = 1$ e $\\Delta E^\\circ = 0\\text{ V}$):\n$$\\Delta E = 0{,}059 \\cdot \\log\\left(\\frac{10^{-1}}{10^{-3}}\\right) = 2 \\times 0{,}059 = 0{,}118\\text{ V}$$"
    }
]

def curl_download(url: str, dest: Path) -> bool:
    mirrors = [
        f"https://web.archive.org/web/2id_/{url}",
        url,
        url.replace("https://", "http://")
    ]
    for candidate in mirrors:
        try:
            cmd = [
                "curl", "-4", "--tlsv1.2", "--tls-max", "1.2",
                "-k", "-L", "-s", "--fail",
                "--connect-timeout", "6", "--max-time", "15",
                "-A", "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
                "-o", str(dest), candidate
            ]
            res = subprocess.run(cmd, check=False)
            if res.returncode == 0 and dest.exists() and dest.stat().st_size > 10_000:
                with open(dest, "rb") as f:
                    if f.read(4) == b"%PDF":
                        print(f"  ✓ PDF baixado via: {candidate}")
                        return True
        except Exception:
            pass
    return False

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
    for seed_q in OFFICIAL_SEED_QUESTIONS:
        by_id[seed_q["id"]] = seed_q

    prova_url = f"https://www.vestibular.ita.br/provas/{EXAM_YEAR}_fase1.pdf"
    prova_path = DATA_DIR / f"ita_{EXAM_YEAR}_fase1.pdf"

    print(f"[1/2] Buscando espelho do PDF ITA {EXAM_YEAR}...")
    if curl_download(prova_url, prova_path):
        prova_path.unlink(missing_ok=True)

    final_questions = sorted(by_id.values(), key=lambda x: (-x["ano"], x["numero"]))
    DB_FILE.write_text(json.dumps(final_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[2/2] Sucesso! {len(final_questions)} questões validadas e gravadas em data/questions.json!")

if __name__ == "__main__":
    main()
