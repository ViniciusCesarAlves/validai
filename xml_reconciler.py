import os
import re
import io
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage

import comparator

# Cores oficiais do padrão de relatórios ValidAí
COLOR_GREEN = "4FD580"
COLOR_DARK = "0F172A"
COLOR_GRAY_BG = "F8FAFC"
COLOR_SUCCESS_BG = "DCFCE7"
COLOR_SUCCESS_TEXT = "15803D"
COLOR_ERROR_BG = "FEE2E2"
COLOR_ERROR_TEXT = "B91C1C"
COLOR_WARN_BG = "FEF3C7"
COLOR_WARN_TEXT = "B45309"
COLOR_ORANGE_BG = "FFEDD5"
COLOR_ORANGE_TEXT = "C2410C"


# ==============================================================================
# 1. UTILITÁRIOS DE LIMPEZA E NORMALIZAÇÃO FISCAL
# ==============================================================================

def clean_digits(val):
    """Extrai apenas dígitos numéricos de qualquer valor."""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return re.sub(r'\D', '', s)


def normalize_nf_number(val, ignore_leading_zeros=True):
    """
    Normaliza o número da Nota Fiscal para cruzamento entre XML e Planilha.
    Ex: 'NF 00001234', '001234.0', '1.234' -> '1234'
    """
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]

    # Se tiver barra ou hífen de série no final (ex: 12345-1 ou 12345/1), pega a parte principal
    if '-' in s or '/' in s:
        parts = re.split(r'[-/]', s)
        # Pega o primeiro bloco que contenha dígitos
        for p in parts:
            d = re.sub(r'\D', '', p)
            if d:
                s = d
                break

    digits = re.sub(r'\D', '', s)
    if not digits:
        return s.upper().strip()

    if ignore_leading_zeros:
        stripped = digits.lstrip('0')
        return stripped if stripped else '0'
    return digits


def normalize_cnpj(val, ignore_punctuation=True):
    """Normaliza CNPJ/CPF para comparação."""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    if not ignore_punctuation:
        return s
    digits = re.sub(r'\D', '', s)
    if not digits:
        return ""
    # Recupera zero à esquerda em CNPJ de 12 ou 13 dígitos ou CPF de 9 ou 10 dígitos
    if len(digits) in (12, 13):
        digits = digits.zfill(14)
    elif len(digits) in (9, 10):
        digits = digits.zfill(11)
    return digits


def format_cnpj_display(val):
    """Formata CNPJ ou CPF para exibição amigável."""
    digits = clean_digits(val)
    if len(digits) in (12, 13):
        digits = digits.zfill(14)
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    elif len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return str(val).strip() if val is not None and not pd.isna(val) else ""


def parse_float_value(val):
    """
    Converte valores monetários em formato brasileiro (R$ 1.234,56) ou internacional (1234.56)
    para float com segurança. Retorna None se não for um número válido.
    """
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return None

    # Remove símbolos de moeda e espaços
    s = re.sub(r'[R$\s€£¥]', '', s, flags=re.IGNORECASE)
    if not s:
        return None

    # Trata parênteses contábeis como negativo: (123,45) -> -123,45
    is_negative = False
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith('-'):
        is_negative = True
        s = s[1:].strip()

    # Caso tenha ponto e vírgula: verifica qual é o separador decimal
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            # Padrão BR: 1.234,56
            s = s.replace('.', '').replace(',', '.')
        else:
            # Padrão US: 1,234.56
            s = s.replace(',', '')
    elif ',' in s:
        # Apenas vírgula: 1234,56
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) <= 4:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')

    try:
        num = float(s)
        return -num if is_negative else num
    except ValueError:
        return None


def format_brl(val):
    """Formata float para moeda BRL: R$ 1.234,56."""
    if val is None or pd.isna(val):
        return "R$ 0,00"
    try:
        v = float(val)
        formatted = f"{abs(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"-R$ {formatted}" if v < 0 else f"R$ {formatted}"
    except Exception:
        return str(val)


def format_date_br(raw_date):
    """Converte datas ISO de XML (2026-10-15T14:30:00-03:00 ou 2026-10-15) para DD/MM/YYYY."""
    if not raw_date:
        return "-"
    s = str(raw_date).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m_br = re.match(r'^(\d{2})/(\d{2})/(\d{4})', s)
    if m_br:
        return f"{m_br.group(1)}/{m_br.group(2)}/{m_br.group(3)}"
    return s[:10]


# ==============================================================================
# 2. PARSER DE XML DE NOTAS FISCAIS (NFe, NFCe, CTe e NFSe)
# ==============================================================================

def _strip_ns(tag):
    """Remove o namespace de uma tag XML: '{http://...}nNF' -> 'nNF'."""
    if '}' in tag:
        return tag.split('}', 1)[1]
    if ':' in tag:
        return tag.split(':', 1)[1]
    return tag


def _strip_tree_namespaces(root):
    """Normaliza todas as tags da árvore XML removendo namespaces."""
    for elem in root.iter():
        if isinstance(elem.tag, str):
            elem.tag = _strip_ns(elem.tag)
    return root


def _find_text(elem, paths, default=""):
    """Busca o primeiro texto não vazio entre múltiplos caminhos XPath relativos."""
    if elem is None:
        return default
    for p in paths:
        found = elem.find(p)
        if found is not None and found.text and found.text.strip():
            return found.text.strip()
    return default


def parse_single_invoice_xml(xml_bytes, filename="nota.xml"):
    """
    Faz o parse de um arquivo XML de Nota Fiscal (NFe, NFCe, CTe ou NFSe).
    Retorna um dicionário padronizado com os campos fiscais ou levanta ValueError se inválido.
    """
    try:
        # Remove BOM ou espaços iniciais
        content = xml_bytes.strip()
        root = ET.fromstring(content)
        _strip_tree_namespaces(root)
    except Exception as e:
        raise ValueError(f"Arquivo '{filename}' não é um XML válido: {str(e)}")

    root_tag = root.tag.lower()

    # Detecta se é NFe / NFCe (nfeProc, NFe, infNFe)
    inf_nfe = root.find('.//infNFe')
    if inf_nfe is not None or root_tag in ('nfeproc', 'nfe', 'infnfe'):
        target = inf_nfe if inf_nfe is not None else root
        ide = target.find('ide')
        emit = target.find('emit')
        dest = target.find('dest')
        icms_tot = target.find('.//ICMSTot')
        issqn_tot = target.find('.//ISSQNtot')

        n_nf = _find_text(ide, ['nNF', 'nCT'])
        serie = _find_text(ide, ['serie'], default='1')
        dh_emi = _find_text(ide, ['dhEmi', 'dEmi'])
        nat_op = _find_text(ide, ['natOp'], default='Venda / Operação Fiscal')
        mod = _find_text(ide, ['mod'], default='55')
        tipo_doc = "NFC-e" if mod == "65" else "NF-e"

        emit_cnpj = _find_text(emit, ['CNPJ', 'CPF'])
        emit_nome = _find_text(emit, ['xNome', 'xFant'])

        dest_cnpj = _find_text(dest, ['CNPJ', 'CPF'])
        dest_nome = _find_text(dest, ['xNome'])

        v_nf = parse_float_value(_find_text(icms_tot, ['vNF'])) or 0.0
        v_prod = parse_float_value(_find_text(icms_tot, ['vProd'])) or v_nf
        v_bc = parse_float_value(_find_text(icms_tot, ['vBC'])) or 0.0
        v_icms = parse_float_value(_find_text(icms_tot, ['vICMS'])) or 0.0
        v_st = parse_float_value(_find_text(icms_tot, ['vST', 'vICMSST'])) or 0.0
        v_ipi = parse_float_value(_find_text(icms_tot, ['vIPI'])) or 0.0
        v_pis = parse_float_value(_find_text(icms_tot, ['vPIS'])) or 0.0
        v_cofins = parse_float_value(_find_text(icms_tot, ['vCOFINS'])) or 0.0
        v_desc = parse_float_value(_find_text(icms_tot, ['vDesc'])) or 0.0
        v_tot_trib = parse_float_value(_find_text(icms_tot, ['vTotTrib'])) or 0.0
        v_iss = parse_float_value(_find_text(issqn_tot, ['vISS'])) if issqn_tot is not None else 0.0
        v_iss = v_iss or 0.0

        soma_impostos = round(v_icms + v_st + v_ipi + v_pis + v_cofins + v_iss, 2)
        if soma_impostos == 0.0 and v_tot_trib > 0:
            soma_impostos = round(v_tot_trib, 2)

        # Chave de acesso (protNFe/infProt/chNFe ou atributo Id da infNFe)
        chave = _find_text(root, ['.//infProt/chNFe', './/chNFe'])
        if not chave and target is not None:
            raw_id = target.attrib.get('Id', '')
            chave = re.sub(r'^NFe', '', raw_id, flags=re.IGNORECASE)

        if not n_nf:
            raise ValueError(f"Tag <nNF> não encontrada no XML '{filename}'.")

        return {
            'filename': filename,
            'tipo_doc': tipo_doc,
            'nNF': n_nf,
            'nNF_norm': normalize_nf_number(n_nf, True),
            'serie': serie,
            'data_emissao': format_date_br(dh_emi),
            'emit_cnpj': normalize_cnpj(emit_cnpj),
            'emit_cnpj_fmt': format_cnpj_display(emit_cnpj),
            'emit_nome': emit_nome or "Emitente Não Informado",
            'dest_cnpj': normalize_cnpj(dest_cnpj),
            'dest_cnpj_fmt': format_cnpj_display(dest_cnpj),
            'dest_nome': dest_nome or "-",
            'vProd': round(v_prod, 2),
            'vNF': round(v_nf, 2),
            'vBC': round(v_bc, 2),
            'vICMS': round(v_icms, 2),
            'vST': round(v_st, 2),
            'vIPI': round(v_ipi, 2),
            'vPIS': round(v_pis, 2),
            'vCOFINS': round(v_cofins, 2),
            'vISS': round(v_iss, 2),
            'vDesc': round(v_desc, 2),
            'total_impostos': soma_impostos,
            'chave_acesso': clean_digits(chave) or chave,
            'natureza_operacao': nat_op
        }

    # Caso seja CT-e (Conhecimento de Transporte Eletrônico)
    inf_cte = root.find('.//infCte')
    if inf_cte is not None or root_tag in ('cteproc', 'cte'):
        target = inf_cte if inf_cte is not None else root
        ide = target.find('ide')
        emit = target.find('emit')
        rem = target.find('rem')
        dest = target.find('dest')
        v_prest = target.find('vPrest')

        n_nf = _find_text(ide, ['nCT', 'nNF'])
        serie = _find_text(ide, ['serie'], default='1')
        dh_emi = _find_text(ide, ['dhEmi', 'dEmi'])
        nat_op = _find_text(ide, ['natOp'], default='Transporte de Cargas')

        emit_cnpj = _find_text(emit, ['CNPJ', 'CPF'])
        emit_nome = _find_text(emit, ['xNome', 'xFant'])
        dest_cnpj = _find_text(dest, ['CNPJ', 'CPF']) or _find_text(rem, ['CNPJ', 'CPF'])
        dest_nome = _find_text(dest, ['xNome']) or _find_text(rem, ['xNome'])

        v_nf = parse_float_value(_find_text(v_prest, ['vTPrest', 'vRec'])) or 0.0
        v_icms = parse_float_value(_find_text(target, ['.//imp//vICMS'])) or 0.0
        chave = _find_text(root, ['.//infProt/chCTe', './/chCTe'])
        if not chave and target is not None:
            chave = re.sub(r'^CTe', '', target.attrib.get('Id', ''), flags=re.IGNORECASE)

        return {
            'filename': filename,
            'tipo_doc': 'CT-e',
            'nNF': n_nf,
            'nNF_norm': normalize_nf_number(n_nf, True),
            'serie': serie,
            'data_emissao': format_date_br(dh_emi),
            'emit_cnpj': normalize_cnpj(emit_cnpj),
            'emit_cnpj_fmt': format_cnpj_display(emit_cnpj),
            'emit_nome': emit_nome or "Transportadora",
            'dest_cnpj': normalize_cnpj(dest_cnpj),
            'dest_cnpj_fmt': format_cnpj_display(dest_cnpj),
            'dest_nome': dest_nome or "-",
            'vProd': round(v_nf, 2),
            'vNF': round(v_nf, 2),
            'vBC': 0.0,
            'vICMS': round(v_icms, 2),
            'vST': 0.0,
            'vIPI': 0.0,
            'vPIS': 0.0,
            'vCOFINS': 0.0,
            'vISS': 0.0,
            'vDesc': 0.0,
            'total_impostos': round(v_icms, 2),
            'chave_acesso': clean_digits(chave) or chave,
            'natureza_operacao': nat_op
        }

    # Caso seja NFS-e (Nota Fiscal de Serviços Eletrônica - ABRASF / Nacional / Prefeituras)
    n_nf = _find_text(root, [
        './/InfNfse/Numero', './/NumeroNfse', './/Numero', './/nNFSe', './/nNF', './/NumNota'
    ])
    if n_nf:
        serie = _find_text(root, ['.//Serie', './/IdentificacaoRps/Serie', './/serie'], default='U')
        dh_emi = _find_text(root, ['.//DataEmissao', './/dhEmi', './/dEmi', './/DataEmissaoNFe'])

        emit_cnpj = _find_text(root, [
            './/PrestadorServico//Cnpj', './/Prestador//Cnpj', './/Prestador//CNPJ',
            './/emit//CNPJ', './/CPFCNPJPrestador/CNPJ', './/Cnpj'
        ])
        emit_nome = _find_text(root, [
            './/PrestadorServico/RazaoSocial', './/Prestador/RazaoSocial',
            './/PrestadorServico/NomeFantasia', './/emit/xNome', './/RazaoSocialPrestador', './/xNome'
        ])

        dest_cnpj = _find_text(root, [
            './/TomadorServico//Cnpj', './/TomadorServico//Cpf', './/Tomador//Cnpj',
            './/dest//CNPJ', './/CPFCNPJTomador/CNPJ'
        ])
        dest_nome = _find_text(root, [
            './/TomadorServico/RazaoSocial', './/Tomador/RazaoSocial',
            './/dest/xNome', './/RazaoSocialTomador'
        ])

        v_serv = parse_float_value(_find_text(root, [
            './/Valores/ValorServicos', './/Servico/Valores/ValorServicos',
            './/ValorServicos', './/vServ', './/vProd'
        ]))
        v_liq = parse_float_value(_find_text(root, [
            './/Valores/ValorLiquidoNfse', './/ValorLiquidoNfse', './/vNF', './/vLiq', './/ValorTotalNota'
        ]))

        v_nf = v_liq if v_liq is not None else (v_serv if v_serv is not None else 0.0)
        v_prod = v_serv if v_serv is not None else v_nf

        v_iss = parse_float_value(_find_text(root, ['.//ValorIss', './/vISS', './/ValorISS'])) or 0.0
        v_pis = parse_float_value(_find_text(root, ['.//ValorPis', './/vPIS'])) or 0.0
        v_cofins = parse_float_value(_find_text(root, ['.//ValorCofins', './/vCOFINS'])) or 0.0
        v_inss = parse_float_value(_find_text(root, ['.//ValorInss', './/vINSS'])) or 0.0
        v_ir = parse_float_value(_find_text(root, ['.//ValorIr', './/vIR'])) or 0.0
        v_csll = parse_float_value(_find_text(root, ['.//ValorCsll', './/vCSLL'])) or 0.0

        soma_impostos = round(v_iss + v_pis + v_cofins + v_inss + v_ir + v_csll, 2)
        chave = _find_text(root, ['.//CodigoVerificacao', './/ChaveAcesso', './/chNFSe'])
        discriminacao = _find_text(root, ['.//Discriminacao', './/xServ', './/natOp'], default='Prestação de Serviços')

        return {
            'filename': filename,
            'tipo_doc': 'NFS-e',
            'nNF': n_nf,
            'nNF_norm': normalize_nf_number(n_nf, True),
            'serie': serie,
            'data_emissao': format_date_br(dh_emi),
            'emit_cnpj': normalize_cnpj(emit_cnpj),
            'emit_cnpj_fmt': format_cnpj_display(emit_cnpj),
            'emit_nome': emit_nome or "Prestador de Serviço",
            'dest_cnpj': normalize_cnpj(dest_cnpj),
            'dest_cnpj_fmt': format_cnpj_display(dest_cnpj),
            'dest_nome': dest_nome or "-",
            'vProd': round(v_prod, 2),
            'vNF': round(v_nf, 2),
            'vBC': 0.0,
            'vICMS': 0.0,
            'vST': 0.0,
            'vIPI': 0.0,
            'vPIS': round(v_pis, 2),
            'vCOFINS': round(v_cofins, 2),
            'vISS': round(v_iss, 2),
            'vDesc': 0.0,
            'total_impostos': soma_impostos,
            'chave_acesso': chave or "-",
            'natureza_operacao': discriminacao[:60]
        }

    raise ValueError(f"O arquivo '{filename}' não possui tags reconhecidas de Nota Fiscal (<nNF>, <infNFe> ou <InfNfse>).")


def extract_xmls_from_files(saved_files):
    """
    Recebe uma lista de tuplas (filepath, original_filename) que podem ser arquivos .zip ou .xml.
    Retorna:
    - invoices: lista de dicionários com cada nota fiscal extraída
    - errors: lista de erros em arquivos que falharam
    """
    invoices = []
    errors = []

    for filepath, orig_name in saved_files:
        lower_name = orig_name.lower()
        if lower_name.endswith('.zip'):
            try:
                with zipfile.ZipFile(filepath, 'r') as zf:
                    for member in zf.infolist():
                        if member.is_dir():
                            continue
                        m_name = member.filename
                        base_m_name = os.path.basename(m_name)
                        if base_m_name.startswith('.') or '__MACOSX' in m_name:
                            continue
                        if base_m_name.lower().endswith('.xml'):
                            try:
                                xml_bytes = zf.read(member.filename)
                                inv = parse_single_invoice_xml(xml_bytes, base_m_name)
                                invoices.append(inv)
                            except Exception as e:
                                errors.append({'filename': base_m_name, 'error': str(e)})
            except zipfile.BadZipFile:
                errors.append({'filename': orig_name, 'error': 'Arquivo .zip corrompido ou inválido.'})
        elif lower_name.endswith('.xml'):
            try:
                with open(filepath, 'rb') as f:
                    xml_bytes = f.read()
                inv = parse_single_invoice_xml(xml_bytes, orig_name)
                invoices.append(inv)
            except Exception as e:
                errors.append({'filename': orig_name, 'error': str(e)})
        else:
            errors.append({'filename': orig_name, 'error': 'Formato não suportado. Envie arquivos .zip ou .xml.'})

    return invoices, errors


# ==============================================================================
# 3. SUGESTÃO E VALIDAÇÃO DE COLUNAS DA PLANILHA FINANCEIRA
# ==============================================================================

def suggest_sheet_columns(cols):
    """Auto-detecta as colunas da planilha financeira (Contas a Pagar / Faturamento)."""
    def find_col(keywords, exclude=None):
        if exclude is None:
            exclude = set()
        for c in cols:
            if c in exclude:
                continue
            c_norm = comparator.normalize_column_name(c)
            if any(k == c_norm or k in c_norm for k in keywords):
                return c
        return ""

    col_nf = find_col(['NUMERO_NF', 'NUM_NF', 'NNF', 'NOTA_FISCAL', 'NUMERO_NOTA', 'NF', 'NFE', 'NOTA', 'DOCUMENTO', 'NUM_DOC', 'NUMERO'])
    col_val = find_col(['VALOR_TOTAL', 'VLR_TOTAL', 'VNF', 'VALOR_NF', 'VALOR_LIQUIDO', 'VALOR_NOTA', 'VALOR', 'VLR', 'TOTAL', 'MONTANTE'], exclude={col_nf})
    col_cnpj = find_col(['CNPJ_EMITENTE', 'CNPJ_FORNECEDOR', 'CNPJ', 'CPF_CNPJ', 'DOCUMENTO_FORNECEDOR', 'FORNECEDOR_CNPJ'], exclude={col_nf, col_val})
    col_tax = find_col(['IMPOSTOS', 'TOTAL_IMPOSTOS', 'TRIBUTOS', 'ICMS', 'ISS', 'VLR_IMPOSTO', 'IMPOSTO'], exclude={col_nf, col_val, col_cnpj})
    col_fornecedor = find_col(['FORNECEDOR', 'RAZAO_SOCIAL', 'EMITENTE', 'CLIENTE', 'NOME_FORNECEDOR', 'FAVORECIDO', 'EMPRESA', 'NOME'], exclude={col_nf, col_val, col_cnpj, col_tax})
    col_chave = find_col(['CHAVE_ACESSO', 'CHAVE_NFE', 'CHAVE', 'CHNFE'], exclude={col_nf, col_val, col_cnpj, col_tax, col_fornecedor})

    return {
        'col_nf': col_nf,
        'col_val': col_val,
        'col_cnpj': col_cnpj,
        'col_tax': col_tax,
        'col_fornecedor': col_fornecedor,
        'col_chave': col_chave
    }


def validate_mapped_columns(df, col_nf, col_val, col_cnpj=None, col_tax=None):
    """
    Verifica se as colunas selecionadas pelo usuário na planilha realmente condizem
    com Número de NF, Valor Financeiro, CNPJ e Impostos.
    Levanta ValueError detalhado caso o usuário tenha selecionado uma coluna incompatível.
    """
    if not col_nf or col_nf not in df.columns:
        raise ValueError("Selecione a coluna correspondente ao Número da Nota Fiscal (<nNF>) na planilha.")
    if not col_val or col_val not in df.columns:
        raise ValueError("Selecione a coluna correspondente ao Valor Total da Nota (<vNF>) na planilha.")

    # 1. Valida Coluna de Número da Nota Fiscal
    nf_sample = [str(v).strip() for v in df[col_nf].dropna().head(30) if str(v).strip() != ""]
    if nf_sample:
        has_digits_count = sum(1 for v in nf_sample if len(clean_digits(v)) >= 1 and len(clean_digits(v)) <= 15)
        # Se a maioria absoluta não tem números (ex: usuário escolheu coluna de Nome do Fornecedor)
        if has_digits_count / len(nf_sample) < 0.4:
            exemplos = ", ".join(f"'{v[:25]}'" for v in nf_sample[:3])
            raise ValueError(
                f"A coluna escolhida '{col_nf}' não bate com a referência de Número da Nota Fiscal (<nNF>). "
                f"Na amostra analisada, os valores são textos sem numeração fiscal (ex: {exemplos}). "
                f"Selecione a coluna que contém o número da NF."
            )

    # 2. Valida Coluna de Valor Total
    val_sample = [v for v in df[col_val].dropna().head(30) if str(v).strip() != ""]
    if val_sample:
        valid_floats = [parse_float_value(v) for v in val_sample]
        numeric_count = sum(1 for f in valid_floats if f is not None)
        if numeric_count / len(val_sample) < 0.5:
            exemplos = ", ".join(f"'{str(v)[:25]}'" for v in val_sample[:3])
            raise ValueError(
                f"A coluna escolhida '{col_val}' não bate com a referência de Valor Monetário (<vNF>). "
                f"Foram encontrados textos que não representam valores financeiros (ex: {exemplos}). "
                f"Selecione a coluna correta de Valor da Nota."
            )

    # 3. Valida Coluna de CNPJ (se selecionada)
    if col_cnpj and col_cnpj in df.columns:
        cnpj_sample = [str(v).strip() for v in df[col_cnpj].dropna().head(30) if str(v).strip() != ""]
        if cnpj_sample:
            valid_doc_len = sum(1 for v in cnpj_sample if len(clean_digits(v)) in (9, 10, 11, 12, 13, 14))
            if valid_doc_len / len(cnpj_sample) < 0.35:
                exemplos = ", ".join(f"'{v[:25]}'" for v in cnpj_sample[:3])
                raise ValueError(
                    f"A coluna escolhida '{col_cnpj}' não bate com a referência de CNPJ / CPF (11 ou 14 dígitos). "
                    f"Valores encontrados na coluna: {exemplos}. "
                    f"Ajuste a coluna de CNPJ ou deixe-a como '-- Não mapear este campo --'."
                )


# ==============================================================================
# 4. MOTOR DE CONCILIAÇÃO XML vs PLANILHA FINANCEIRA
# ==============================================================================

def reconcile_xml_vs_sheet(invoices, df_sheet, options):
    """
    Executa o batimento completo entre os XMLs extraídos e a planilha financeira.
    """
    col_nf = options.get('col_nf')
    col_val = options.get('col_val')
    col_cnpj = options.get('col_cnpj') or ""
    col_tax = options.get('col_tax') or ""
    col_fornecedor = options.get('col_fornecedor') or ""
    col_chave = options.get('col_chave') or ""

    tolerance = float(options.get('tolerance', 0.05))
    ignore_leading_zeros = bool(options.get('ignore_leading_zeros', True))
    ignore_cnpj_punct = bool(options.get('ignore_cnpj_punct', True))
    check_missing_in_excel = bool(options.get('check_missing_in_excel', True))
    check_missing_xml = bool(options.get('check_missing_xml', True))
    check_taxes = bool(options.get('check_taxes', True))

    # Validação de compatibilidade das colunas escolhidas
    validate_mapped_columns(df_sheet, col_nf, col_val, col_cnpj, col_tax)

    # Indexa as linhas da planilha por Número da NF normalizado
    sheet_by_nf = {}
    sheet_rows_info = []

    for r_idx, row in df_sheet.iterrows():
        raw_nf = row.get(col_nf, "")
        nf_key = normalize_nf_number(raw_nf, ignore_leading_zeros)
        raw_val = row.get(col_val, 0)
        val_float = parse_float_value(raw_val)
        if val_float is None:
            val_float = 0.0

        raw_cnpj = row.get(col_cnpj, "") if (col_cnpj and col_cnpj in df_sheet.columns) else ""
        cnpj_norm = normalize_cnpj(raw_cnpj, ignore_cnpj_punct) if raw_cnpj else ""

        raw_tax = row.get(col_tax, "") if (col_tax and col_tax in df_sheet.columns) else ""
        tax_float = parse_float_value(raw_tax) if raw_tax != "" else None

        fornecedor_str = str(row.get(col_fornecedor, "")).strip() if (col_fornecedor and col_fornecedor in df_sheet.columns and not pd.isna(row.get(col_fornecedor))) else "-"
        chave_str = clean_digits(row.get(col_chave, "")) if (col_chave and col_chave in df_sheet.columns) else ""

        row_info = {
            'row_idx': r_idx,
            'excel_line': r_idx + 2,  # Considerando linha 1 como cabeçalho
            'raw_nf': "" if pd.isna(raw_nf) else str(raw_nf).strip(),
            'nf_key': nf_key,
            'val_float': round(val_float, 2),
            'cnpj_raw': "" if pd.isna(raw_cnpj) else str(raw_cnpj).strip(),
            'cnpj_norm': cnpj_norm,
            'tax_float': round(tax_float, 2) if tax_float is not None else None,
            'fornecedor': fornecedor_str,
            'chave': chave_str,
            'matched_xml': False
        }
        sheet_rows_info.append(row_info)

        if nf_key:
            if nf_key not in sheet_by_nf:
                sheet_by_nf[nf_key] = []
            sheet_by_nf[nf_key].append(row_info)

    # Estruturas de resultado
    divergences = []
    missing_in_excel = []
    missing_xml = []
    all_xml_mirror = []

    row_audit_map = {}      # r_idx -> {status, xml_val, diff, details, err_cols}
    matched_count = 0
    divergent_count = 0

    total_xml_value = 0.0
    total_sheet_value = sum(r['val_float'] for r in sheet_rows_info)

    for inv in invoices:
        total_xml_value += inv['vNF']
        nf_key = normalize_nf_number(inv['nNF'], ignore_leading_zeros)
        matched_rows = sheet_by_nf.get(nf_key, [])

        if not matched_rows:
            # XML não encontrado na planilha financeira!
            status_mirror = "SEM LANÇAMENTO NO EXCEL"
            if check_missing_in_excel:
                missing_in_excel.append({
                    'filename': inv['filename'],
                    'tipo_doc': inv['tipo_doc'],
                    'nNF': inv['nNF'],
                    'serie': inv['serie'],
                    'data_emissao': inv['data_emissao'],
                    'emit_cnpj': inv['emit_cnpj_fmt'] or inv['emit_cnpj'],
                    'emit_nome': inv['emit_nome'],
                    'vNF': inv['vNF'],
                    'vNF_fmt': format_brl(inv['vNF']),
                    'total_impostos': inv['total_impostos'],
                    'total_impostos_fmt': format_brl(inv['total_impostos']),
                    'chave_acesso': inv['chave_acesso'],
                    'motivo': "Nota Fiscal emitida no XML não localizada na planilha financeira"
                })
        else:
            # Marca as linhas como vinculadas a este XML
            for mr in matched_rows:
                mr['matched_xml'] = True

            # Soma valores caso a NF tenha sido lançada em parcelas ou linha única
            excel_val_sum = round(sum(mr['val_float'] for mr in matched_rows), 2)
            diff_val = round(inv['vNF'] - excel_val_sum, 2)
            excel_lines_str = ", ".join(str(mr['excel_line']) for mr in matched_rows)

            issues = []
            err_cols = set()

            # 1. Checagem de Valor Total (<vNF>)
            if abs(diff_val) > tolerance:
                issues.append(f"Valor divergente: XML {format_brl(inv['vNF'])} vs Planilha {format_brl(excel_val_sum)} (Dif: {format_brl(diff_val)})")
                err_cols.add(col_val)

            # 2. Checagem de CNPJ (se mapeado)
            first_row = matched_rows[0]
            if col_cnpj and col_cnpj in df_sheet.columns:
                excel_cnpj = first_row['cnpj_norm']
                xml_emit_cnpj = inv['emit_cnpj']
                xml_dest_cnpj = inv['dest_cnpj']
                if not excel_cnpj:
                    issues.append("CNPJ em branco na planilha financeira")
                    err_cols.add(col_cnpj)
                elif excel_cnpj != xml_emit_cnpj and excel_cnpj != xml_dest_cnpj:
                    issues.append(f"CNPJ divergente: XML ({inv['emit_cnpj_fmt']}) vs Planilha ({format_cnpj_display(excel_cnpj)})")
                    err_cols.add(col_cnpj)

            # 3. Checagem de Impostos (se mapeado e ativo)
            if check_taxes and col_tax and col_tax in df_sheet.columns:
                tax_vals = [mr['tax_float'] for mr in matched_rows if mr['tax_float'] is not None]
                if tax_vals:
                    excel_tax_sum = round(sum(tax_vals), 2)
                    diff_tax = round(inv['total_impostos'] - excel_tax_sum, 2)
                    if abs(diff_tax) > tolerance:
                        issues.append(f"Impostos divergentes: XML {format_brl(inv['total_impostos'])} vs Planilha {format_brl(excel_tax_sum)}")
                        err_cols.add(col_tax)

            if issues:
                divergent_count += 1
                status_mirror = "DIVERGÊNCIA ENCONTRADA"
                motivo_str = " | ".join(issues)
                divergences.append({
                    'excel_line': excel_lines_str,
                    'nNF': inv['nNF'],
                    'emit_nome': inv['emit_nome'],
                    'emit_cnpj_xml': inv['emit_cnpj_fmt'] or "-",
                    'cnpj_planilha': format_cnpj_display(first_row['cnpj_raw']) if first_row['cnpj_raw'] else "-",
                    'vNF_xml': inv['vNF'],
                    'vNF_xml_fmt': format_brl(inv['vNF']),
                    'val_planilha': excel_val_sum,
                    'val_planilha_fmt': format_brl(excel_val_sum),
                    'diff_val': diff_val,
                    'diff_val_fmt': format_brl(diff_val),
                    'impostos_xml_fmt': format_brl(inv['total_impostos']),
                    'motivo': motivo_str
                })
                for mr in matched_rows:
                    row_audit_map[mr['row_idx']] = {
                        'status': 'DIVERGÊNCIA',
                        'xml_val': inv['vNF'],
                        'diff': diff_val,
                        'details': motivo_str,
                        'err_cols': err_cols
                    }
            else:
                matched_count += 1
                status_mirror = "CONCILIADA (OK)"
                for mr in matched_rows:
                    row_audit_map[mr['row_idx']] = {
                        'status': 'CONCILIADA',
                        'xml_val': inv['vNF'],
                        'diff': 0.0,
                        'details': 'Nota Fiscal 100% conciliada com o XML',
                        'err_cols': set()
                    }

        mirror_item = dict(inv)
        mirror_item['vNF_fmt'] = format_brl(inv['vNF'])
        mirror_item['vProd_fmt'] = format_brl(inv['vProd'])
        mirror_item['total_impostos_fmt'] = format_brl(inv['total_impostos'])
        mirror_item['status_conciliacao'] = status_mirror
        all_xml_mirror.append(mirror_item)

    # Verifica lançamentos na planilha que não possuem XML correspondente
    for r_info in sheet_rows_info:
        if not r_info['matched_xml']:
            motivo_sem_xml = "Lançamento financeiro sem arquivo .XML correspondente no lote enviado"
            if not r_info['nf_key']:
                motivo_sem_xml = "Linha na planilha está com o Número da Nota Fiscal vazio"
            if check_missing_xml:
                missing_xml.append({
                    'excel_line': r_info['excel_line'],
                    'nNF_planilha': r_info['raw_nf'] or "(Vazio)",
                    'fornecedor': r_info['fornecedor'],
                    'cnpj_planilha': format_cnpj_display(r_info['cnpj_raw']) if r_info['cnpj_raw'] else "-",
                    'val_planilha': r_info['val_float'],
                    'val_planilha_fmt': format_brl(r_info['val_float']),
                    'motivo': motivo_sem_xml
                })
            row_audit_map[r_info['row_idx']] = {
                'status': 'SEM ARQUIVO XML',
                'xml_val': 0.0,
                'diff': -r_info['val_float'],
                'details': motivo_sem_xml,
                'err_cols': {col_nf}
            }

    total_xmls = len(invoices)
    matched_pct = round((matched_count / total_xmls * 100), 1) if total_xmls > 0 else 0.0
    net_diff = round(total_xml_value - total_sheet_value, 2)

    # Confronto Financeiro e Tributário (XML vs Planilha)
    xml_tot_prod = sum(inv.get('vProd', 0.0) for inv in invoices)
    xml_tot_bc = sum(inv.get('vBC', 0.0) for inv in invoices)
    xml_tot_icms = sum(inv.get('vICMS', 0.0) for inv in invoices)
    xml_tot_pis_cofins = sum(inv.get('vPIS', 0.0) + inv.get('vCOFINS', 0.0) for inv in invoices)

    def _find_sheet_col(keywords):
        for c in df_sheet.columns:
            c_norm = comparator.normalize_column_name(c)
            if any(k == c_norm or k in c_norm for k in keywords):
                return c
        return None

    def _sum_sheet_col(col_name):
        if not col_name or col_name not in df_sheet.columns:
            return 0.0
        s = 0.0
        for val in df_sheet[col_name]:
            fv = parse_float_value(val)
            if fv:
                s += fv
        return s

    col_sheet_prod = _find_sheet_col(['VPROD', 'VALOR_PRODUTOS', 'VALOR_MERCADORIA', 'PRODUTO', 'PRODUTOS']) or col_val
    col_sheet_bc = _find_sheet_col(['BASE_ICMS', 'BC_ICMS', 'VBC', 'BASE_CALCULO', 'BASE_CALC'])
    col_sheet_icms = _find_sheet_col(['VALOR_ICMS', 'VLR_ICMS', 'VICMS', 'ICMS']) or (col_tax if col_tax else None)
    col_sheet_pis_cofins = _find_sheet_col(['PIS_COFINS', 'VALOR_PIS_COFINS', 'PIS', 'COFINS', 'VPIS', 'VCOFINS'])

    sheet_tot_prod = _sum_sheet_col(col_sheet_prod) or total_sheet_value
    sheet_tot_bc = _sum_sheet_col(col_sheet_bc)
    sheet_tot_icms = _sum_sheet_col(col_sheet_icms)
    sheet_tot_pis_cofins = _sum_sheet_col(col_sheet_pis_cofins)

    summary = {
        'total_xmls': total_xmls,
        'total_sheet_rows': len(df_sheet),
        'matched_count': matched_count,
        'matched_percentage': matched_pct,
        'divergences_count': len(divergences),
        'missing_in_excel_count': len(missing_in_excel),
        'missing_xml_count': len(missing_xml),
        'total_xml_value': round(total_xml_value, 2),
        'total_xml_value_fmt': format_brl(total_xml_value),
        'total_sheet_value': round(total_sheet_value, 2),
        'total_sheet_value_fmt': format_brl(total_sheet_value),
        'net_difference': net_diff,
        'net_difference_fmt': format_brl(net_diff),
        'financial_tax_comparison': {
            'xml': {
                'total_prod': round(xml_tot_prod, 2),
                'total_bc': round(xml_tot_bc, 2),
                'total_icms': round(xml_tot_icms, 2),
                'total_pis_cofins': round(xml_tot_pis_cofins, 2)
            },
            'sheet': {
                'total_prod': round(sheet_tot_prod, 2),
                'total_bc': round(sheet_tot_bc, 2),
                'total_icms': round(sheet_tot_icms, 2),
                'total_pis_cofins': round(sheet_tot_pis_cofins, 2)
            }
        }
    }

    return {
        'summary': summary,
        'divergences': divergences,
        'missing_in_excel': missing_in_excel,
        'missing_xml': missing_xml,
        'all_xml_mirror': all_xml_mirror,
        'row_audit_map': row_audit_map
    }


# ==============================================================================
# 5. GERAÇÃO DOS RELATÓRIOS EXCEL (ESPELHO DOS XMLs E AUDITORIA COM CÉLULAS PINTADAS)
# ==============================================================================

def generate_xml_mirror_excel(all_xml_mirror, output_path):
    """
    Gera a planilha limpa de Espelho das Notas Fiscais (todos os dados extraídos dos XMLs).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Espelho Notas Fiscais XML"
    ws.views.sheetView[0].showGridLines = True

    header_font = Font(name="Calibri", size=11, bold=True, color=COLOR_DARK)
    header_fill = PatternFill(start_color=COLOR_GREEN, end_color=COLOR_GREEN, fill_type="solid")
    regular_font = Font(name="Calibri", size=10)
    zebra_fill = PatternFill(start_color=COLOR_GRAY_BG, end_color=COLOR_GRAY_BG, fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    align_left = Alignment(horizontal='left', vertical='center')
    align_center = Alignment(horizontal='center', vertical='center')
    align_right = Alignment(horizontal='right', vertical='center')

    headers = [
        'Status_Conciliacao', 'Tipo_Doc', 'Numero_NF', 'Serie', 'Data_Emissao',
        'CNPJ_Emitente', 'Razao_Social_Emitente', 'CNPJ_Destinatario', 'Nome_Destinatario',
        'Valor_Produtos_Servicos', 'ICMS', 'IPI', 'PIS', 'COFINS', 'ISS',
        'Total_Impostos', 'Valor_Total_NF', 'Natureza_Operacao', 'Chave_Acesso', 'Arquivo_XML'
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_left
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    fill_ok = PatternFill(start_color=COLOR_SUCCESS_BG, end_color=COLOR_SUCCESS_BG, fill_type="solid")
    font_ok = Font(name="Calibri", size=10, bold=True, color=COLOR_SUCCESS_TEXT)
    fill_err = PatternFill(start_color=COLOR_ERROR_BG, end_color=COLOR_ERROR_BG, fill_type="solid")
    font_err = Font(name="Calibri", size=10, bold=True, color=COLOR_ERROR_TEXT)
    fill_warn = PatternFill(start_color=COLOR_WARN_BG, end_color=COLOR_WARN_BG, fill_type="solid")
    font_warn = Font(name="Calibri", size=10, bold=True, color=COLOR_WARN_TEXT)

    for idx, item in enumerate(all_xml_mirror, 2):
        status = item.get('status_conciliacao', '')
        row_vals = [
            status,
            item.get('tipo_doc', 'NF-e'),
            item.get('nNF', ''),
            item.get('serie', ''),
            item.get('data_emissao', ''),
            item.get('emit_cnpj_fmt', ''),
            item.get('emit_nome', ''),
            item.get('dest_cnpj_fmt', ''),
            item.get('dest_nome', ''),
            item.get('vProd', 0.0),
            item.get('vICMS', 0.0),
            item.get('vIPI', 0.0),
            item.get('vPIS', 0.0),
            item.get('vCOFINS', 0.0),
            item.get('vISS', 0.0),
            item.get('total_impostos', 0.0),
            item.get('vNF', 0.0),
            item.get('natureza_operacao', ''),
            item.get('chave_acesso', ''),
            item.get('filename', '')
        ]

        for col_idx, val in enumerate(row_vals, 1):
            c = ws.cell(row=idx, column=col_idx, value=val)
            c.font = regular_font
            c.border = thin_border
            if isinstance(val, float):
                c.number_format = '#,##0.00'
                c.alignment = align_right
            elif col_idx in (1, 2, 3, 4, 5):
                c.alignment = align_center
            else:
                c.alignment = align_left

            if col_idx == 1:
                if "CONCILIADA" in status:
                    c.fill = fill_ok
                    c.font = font_ok
                elif "DIVERGÊNCIA" in status:
                    c.fill = fill_err
                    c.font = font_err
                else:
                    c.fill = fill_warn
                    c.font = font_warn
            elif idx % 2 == 1:
                c.fill = zebra_fill

        ws.row_dimensions[idx].height = 20

    for col_idx, h in enumerate(headers, 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = max(len(h) + 5, 16)
    ws.column_dimensions['G'].width = 34
    ws.column_dimensions['S'].width = 48

    wb.save(output_path)


def generate_xml_audit_excel(df_sheet, reconcile_results, output_path):
    """
    Gera o Relatório de Auditoria Fiscal com Células Pintadas e Logo ValidAí:
    - Aba 1: Resumo Executivo da Conciliação
    - Aba 2: Planilha Financeira Auditada (Células com erro pintadas)
    - Aba 3: XMLs Sem Lançamento no Excel (Omissões)
    - Aba 4: Divergências de Valor, CNPJ e Impostos
    """
    summary = reconcile_results['summary']
    divergences = reconcile_results['divergences']
    missing_in_excel = reconcile_results['missing_in_excel']
    row_audit_map = reconcile_results['row_audit_map']

    wb = openpyxl.Workbook()

    # ==========================================
    # ABA 1: RESUMO EXECUTIVO
    # ==========================================
    ws_res = wb.active
    ws_res.title = "Resumo da Conciliação"
    ws_res.views.sheetView[0].showGridLines = True

    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images', 'logo.png')
    if os.path.exists(logo_path):
        try:
            logo_img = OpenpyxlImage(logo_path)
            logo_img.width = 165
            logo_img.height = 48
            ws_res.add_image(logo_img, "A1")
        except Exception:
            pass

    ws_res.row_dimensions[1].height = 30
    ws_res.row_dimensions[2].height = 25

    title_cell = ws_res.cell(row=4, column=1, value="RELATÓRIO DE CONCILIAÇÃO DE XML DE NOTAS FISCAIS")
    title_cell.font = Font(name="Calibri", size=14, bold=True, color=COLOR_DARK)

    sub_cell = ws_res.cell(row=5, column=1, value="ValidAí • Auditoria Fiscal e Batimento de XML (NFe/NFSe) vs. Financeiro")
    sub_cell.font = Font(name="Calibri", size=10, italic=True, color="64748B")

    kpi_header_fill = PatternFill(start_color=COLOR_GREEN, end_color=COLOR_GREEN, fill_type="solid")
    kpi_header_font = Font(name="Calibri", size=11, bold=True, color=COLOR_DARK)
    card_title_font = Font(name="Calibri", size=10, bold=True, color="334155")
    card_value_font = Font(name="Calibri", size=11, bold=True, color=COLOR_DARK)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    kpis = [
        ("Total de Arquivos XML Analisados", f"{summary['total_xmls']} notas fiscais", None),
        ("Total de Lançamentos na Planilha", f"{summary['total_sheet_rows']} registros", None),
        ("Notas 100% Conciliadas", f"{summary['matched_count']} ({summary['matched_percentage']}%)", COLOR_SUCCESS_BG),
        ("Notas com Divergência (Valor / CNPJ / Imposto)", f"{summary['divergences_count']} notas", COLOR_ERROR_BG),
        ("XMLs Sem Lançamento na Planilha (Omissão)", f"{summary['missing_in_excel_count']} notas", COLOR_WARN_BG),
        ("Lançamentos na Planilha Sem XML", f"{summary['missing_xml_count']} registros", COLOR_ORANGE_BG),
        ("Soma Financeira Total nos XMLs (<vNF>)", summary['total_xml_value_fmt'], None),
        ("Soma Financeira Total na Planilha", summary['total_sheet_value_fmt'], None),
        ("Diferença Financeira Líquida (XML - Planilha)", summary['net_difference_fmt'], "E0F2FE"),
    ]

    ws_res.cell(row=7, column=1, value="INDICADOR DE AUDITORIA FISCAL").font = kpi_header_font
    ws_res.cell(row=7, column=1).fill = kpi_header_fill
    ws_res.cell(row=7, column=1).border = thin_border

    ws_res.cell(row=7, column=2, value="RESULTADO CONSOLIDADO").font = kpi_header_font
    ws_res.cell(row=7, column=2).fill = kpi_header_fill
    ws_res.cell(row=7, column=2).border = thin_border

    for idx, (label, val, bg_color) in enumerate(kpis, 8):
        c1 = ws_res.cell(row=idx, column=1, value=label)
        c1.font = card_title_font
        c1.border = thin_border

        c2 = ws_res.cell(row=idx, column=2, value=val)
        c2.font = card_value_font
        c2.border = thin_border
        c2.alignment = Alignment(horizontal='center', vertical='center')
        if bg_color:
            c2.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
        ws_res.row_dimensions[idx].height = 22

    # Crédito Institucional no Rodapé do Resumo
    credit_row = 8 + len(kpis) + 1
    credit_cell = ws_res.cell(
        row=credit_row,
        column=1,
        value="Relatório gerado automaticamente por ValidAí (https://validai.app.br) • Arquitetura e Inteligência de Dados por Vinícius Alves."
    )
    credit_cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")

    ws_res.column_dimensions['A'].width = 48
    ws_res.column_dimensions['B'].width = 30

    # ==========================================
    # ABA 2: PLANILHA FINANCEIRA AUDITADA (COM CÉLULAS PINTADAS)
    # ==========================================
    ws_data = wb.create_sheet(title="Planilha Auditada")
    ws_data.views.sheetView[0].showGridLines = True

    fill_error = PatternFill(start_color=COLOR_ERROR_BG, end_color=COLOR_ERROR_BG, fill_type="solid")
    font_error = Font(name="Calibri", size=10, bold=True, color=COLOR_ERROR_TEXT)
    fill_warn = PatternFill(start_color=COLOR_WARN_BG, end_color=COLOR_WARN_BG, fill_type="solid")
    font_warn = Font(name="Calibri", size=10, bold=True, color=COLOR_WARN_TEXT)
    fill_orange = PatternFill(start_color=COLOR_ORANGE_BG, end_color=COLOR_ORANGE_BG, fill_type="solid")
    font_orange = Font(name="Calibri", size=10, bold=True, color=COLOR_ORANGE_TEXT)
    fill_success = PatternFill(start_color=COLOR_SUCCESS_BG, end_color=COLOR_SUCCESS_BG, fill_type="solid")
    font_success = Font(name="Calibri", size=10, bold=True, color=COLOR_SUCCESS_TEXT)
    regular_font = Font(name="Calibri", size=10)
    zebra_fill = PatternFill(start_color=COLOR_GRAY_BG, end_color=COLOR_GRAY_BG, fill_type="solid")
    align_left = Alignment(horizontal='left', vertical='center')
    align_center = Alignment(horizontal='center', vertical='center')

    orig_cols = list(df_sheet.columns)
    audit_headers = ['Linha', 'Status_Conciliacao', 'Valor_no_XML', 'Diferenca_R$', 'Detalhes_Auditoria'] + orig_cols

    for col_idx, h in enumerate(audit_headers, 1):
        cell = ws_data.cell(row=1, column=col_idx, value=str(h))
        cell.font = kpi_header_font
        cell.fill = kpi_header_fill
        cell.alignment = align_left
        cell.border = thin_border
    ws_data.row_dimensions[1].height = 28

    for r_idx, row in df_sheet.iterrows():
        row_num = r_idx + 2
        audit_info = row_audit_map.get(r_idx, {
            'status': 'SEM ARQUIVO XML',
            'xml_val': 0.0,
            'diff': 0.0,
            'details': 'Não conciliado',
            'err_cols': set()
        })
        status = audit_info['status']
        err_cols = audit_info['err_cols']

        c_line = ws_data.cell(row=row_num, column=1, value=row_num)
        c_line.font = regular_font
        c_line.border = thin_border
        c_line.alignment = align_center

        c_st = ws_data.cell(row=row_num, column=2, value=status)
        c_st.border = thin_border
        c_st.alignment = align_center
        if status == 'CONCILIADA':
            c_st.fill = fill_success
            c_st.font = font_success
        elif status == 'DIVERGÊNCIA':
            c_st.fill = fill_error
            c_st.font = font_error
        else:
            c_st.fill = fill_orange
            c_st.font = font_orange

        c_xval = ws_data.cell(row=row_num, column=3, value=format_brl(audit_info['xml_val']))
        c_xval.font = regular_font
        c_xval.border = thin_border
        c_xval.alignment = align_center

        c_diff = ws_data.cell(row=row_num, column=4, value=format_brl(audit_info['diff']))
        c_diff.font = font_error if abs(audit_info['diff']) > 0.01 else regular_font
        c_diff.border = thin_border
        c_diff.alignment = align_center

        c_det = ws_data.cell(row=row_num, column=5, value=audit_info['details'])
        c_det.font = regular_font
        c_det.border = thin_border
        c_det.alignment = align_left

        for col_offset, col_name in enumerate(orig_cols, 6):
            val = row[col_name]
            val_str = "" if pd.isna(val) else str(val)
            cell = ws_data.cell(row=row_num, column=col_offset, value=val_str)
            cell.font = regular_font
            cell.border = thin_border
            cell.alignment = align_left

            if col_name in err_cols:
                cell.fill = fill_error if status == 'DIVERGÊNCIA' else fill_orange
                cell.font = font_error if status == 'DIVERGÊNCIA' else font_orange
            elif row_num % 2 == 1:
                cell.fill = zebra_fill

        ws_data.row_dimensions[row_num].height = 20

    ws_data.column_dimensions['A'].width = 10
    ws_data.column_dimensions['B'].width = 22
    ws_data.column_dimensions['C'].width = 18
    ws_data.column_dimensions['D'].width = 18
    ws_data.column_dimensions['E'].width = 48
    for col_offset, col_name in enumerate(orig_cols, 6):
        col_letter = get_column_letter(col_offset)
        ws_data.column_dimensions[col_letter].width = max(len(str(col_name)) + 5, 16)

    # ==========================================
    # ABA 3: XMLs SEM LANÇAMENTO NO EXCEL (OMISSÕES)
    # ==========================================
    ws_omiss = wb.create_sheet(title="XMLs Sem Lançamento")
    ws_omiss.views.sheetView[0].showGridLines = True

    omiss_headers = ['Tipo', 'Numero_NF', 'Serie', 'Data_Emissao', 'CNPJ_Emitente', 'Emitente_Fornecedor', 'Valor_Total_XML', 'Impostos_XML', 'Chave_Acesso', 'Motivo_Auditoria']
    for col_idx, h in enumerate(omiss_headers, 1):
        cell = ws_omiss.cell(row=1, column=col_idx, value=h)
        cell.font = kpi_header_font
        cell.fill = kpi_header_fill
        cell.alignment = align_left
        cell.border = thin_border
    ws_omiss.row_dimensions[1].height = 28

    for idx, item in enumerate(missing_in_excel, 2):
        vals = [
            item['tipo_doc'], item['nNF'], item['serie'], item['data_emissao'],
            item['emit_cnpj'], item['emit_nome'], item['vNF_fmt'],
            item['total_impostos_fmt'], item['chave_acesso'], item['motivo']
        ]
        for col_idx, v in enumerate(vals, 1):
            c = ws_omiss.cell(row=idx, column=col_idx, value=v)
            c.font = font_warn if col_idx in (2, 7) else regular_font
            if col_idx in (2, 7):
                c.fill = fill_warn
            c.border = thin_border
            c.alignment = align_left
        ws_omiss.row_dimensions[idx].height = 20

    for col_idx, h in enumerate(omiss_headers, 1):
        ws_omiss.column_dimensions[get_column_letter(col_idx)].width = max(len(h) + 5, 16)
    ws_omiss.column_dimensions['F'].width = 34
    ws_omiss.column_dimensions['I'].width = 46
    ws_omiss.column_dimensions['J'].width = 45

    # ==========================================
    # ABA 4: DIVERGÊNCIAS DETALHADAS
    # ==========================================
    ws_div = wb.create_sheet(title="Divergências de Valor e CNPJ")
    ws_div.views.sheetView[0].showGridLines = True

    div_headers = ['Linha_Planilha', 'Numero_NF', 'Fornecedor_Emitente', 'Valor_XML', 'Valor_Planilha', 'Diferenca_R$', 'CNPJ_XML', 'CNPJ_Planilha', 'Diagnostico_da_Divergencia']
    for col_idx, h in enumerate(div_headers, 1):
        cell = ws_div.cell(row=1, column=col_idx, value=h)
        cell.font = kpi_header_font
        cell.fill = kpi_header_fill
        cell.alignment = align_left
        cell.border = thin_border
    ws_div.row_dimensions[1].height = 28

    for idx, item in enumerate(divergences, 2):
        vals = [
            item['excel_line'], item['nNF'], item['emit_nome'],
            item['vNF_xml_fmt'], item['val_planilha_fmt'], item['diff_val_fmt'],
            item['emit_cnpj_xml'], item['cnpj_planilha'], item['motivo']
        ]
        for col_idx, v in enumerate(vals, 1):
            c = ws_div.cell(row=idx, column=col_idx, value=v)
            c.font = font_error if col_idx in (4, 5, 6) else regular_font
            if col_idx in (4, 5, 6):
                c.fill = fill_error
            c.border = thin_border
            c.alignment = align_left
        ws_div.row_dimensions[idx].height = 20

    for col_idx, h in enumerate(div_headers, 1):
        ws_div.column_dimensions[get_column_letter(col_idx)].width = max(len(h) + 5, 18)
    ws_div.column_dimensions['I'].width = 55

    wb.save(output_path)


# ==============================================================================
# 6. GERADOR DE LOTE DE EXEMPLO REALISTA (PARA O BOTÃO "TESTAR EXEMPLO")
# ==============================================================================

def create_demo_files(session_folder):
    """
    Cria um arquivo .zip com 7 XMLs realistas de Notas Fiscais (NFe e NFSe)
    e uma planilha financeira Contas_a_Pagar_Outubro.xlsx para teste imediato.
    """
    zip_path = os.path.join(session_folder, "Lote_XMLs_Notas_Fiscais.zip")
    excel_path = os.path.join(session_folder, "Relatorio_Contas_a_Pagar_ERP.xlsx")

    sample_nfe_list = [
        # 1. Conciliada perfeitamente
        ("NFe_0001045.xml", "1045", "1", "2026-10-02T10:15:00-03:00", "12345678000199", "TECH SOLUTIONS BRASIL LTDA", "15400.00", "1848.00", "770.00", "35261012345678000199550010000010451000010451"),
        # 2. Conciliada perfeitamente (com zero à esquerda no XML)
        ("NFe_0001046.xml", "0001046", "1", "2026-10-04T14:22:00-03:00", "45987123000118", "SUPRIMENTOS INDUSTRIAIS ALFA SA", "3850.50", "462.06", "192.52", "35261045987123000118550010000010461000010468"),
        # 3. Conciliada perfeitamente
        ("NFe_0001047.xml", "1047", "1", "2026-10-06T09:10:00-03:00", "78123456000144", "LOGISTICA EXPRESS TRANSPORTES LTDA", "2190.00", "262.80", "80.00", "35261078123456000144550010000010471000010475"),
        # 4. Divergência de Valor (XML é 8.900,00, mas no Excel lançaram 8.400,00)
        ("NFe_0001048.xml", "1048", "1", "2026-10-08T16:40:00-03:00", "33654987000102", "DISTRIBUIDORA NACIONAL DE PECAS LTDA", "8900.00", "1068.00", "445.00", "35261033654987000102550010000010481000010482"),
        # 5. Divergência de CNPJ (Valor bate, mas CNPJ na planilha foi digitado errado)
        ("NFe_0001049.xml", "1049", "2", "2026-10-10T11:05:00-03:00", "91827364000155", "CLOUD SERVICOS DIGITAIS S.A.", "6200.00", "744.00", "226.30", "35261091827364000155550020000010491000010499"),
        # 6. XML sem lançamento na planilha (Nota emitida contra o CNPJ, mas não lançada no Contas a Pagar!)
        ("NFe_0001050.xml", "1050", "1", "2026-10-12T17:50:00-03:00", "22334455000188", "PAPELARIA E ESCRITORIO CENTRAL LTDA", "1475.80", "177.10", "53.86", "35261022334455000188550010000010501000010503"),
    ]

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname, nnf, serie, dhemi, cnpj, xnome, vnf, vicms, vpis, chave in sample_nfe_list:
            xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe{chave}" versao="4.00">
      <ide>
        <nNF>{nnf}</nNF>
        <serie>{serie}</serie>
        <dhEmi>{dhemi}</dhEmi>
        <mod>55</mod>
        <natOp>Venda de Mercadoria / Servico</natOp>
      </ide>
      <emit>
        <CNPJ>{cnpj}</CNPJ>
        <xNome>{xnome}</xNome>
      </emit>
      <dest>
        <CNPJ>11222333000100</CNPJ>
        <xNome>EMPRESA MATRIZ VALIDAI S/A</xNome>
      </dest>
      <total>
        <ICMSTot>
          <vProd>{vnf}</vProd>
          <vNF>{vnf}</vNF>
          <vICMS>{vicms}</vICMS>
          <vST>0.00</vST>
          <vIPI>0.00</vIPI>
          <vPIS>{vpis}</vPIS>
          <vCOFINS>0.00</vCOFINS>
          <vDesc>0.00</vDesc>
        </ICMSTot>
      </total>
    </infNFe>
  </NFe>
  <protNFe versao="4.00">
    <infProt>
      <chNFe>{chave}</chNFe>
    </infProt>
  </protNFe>
</nfeProc>"""
            zf.writestr(fname, xml_str.encode('utf-8'))

    # Cria a planilha financeira correspondente com casos reais
    df_demo = pd.DataFrame([
        {
            'Numero_NF': '1045',
            'Fornecedor': 'TECH SOLUTIONS BRASIL LTDA',
            'CNPJ_Fornecedor': '12.345.678/0001-99',
            'Data_Lancamento': '02/10/2026',
            'Valor_Total_NF': 15400.00,
            'Total_Impostos': 2618.00,
            'Centro_Custo': 'TI / Infraestrutura'
        },
        {
            'Numero_NF': '1046',
            'Fornecedor': 'SUPRIMENTOS INDUSTRIAIS ALFA SA',
            'CNPJ_Fornecedor': '45.987.123/0001-18',
            'Data_Lancamento': '04/10/2026',
            'Valor_Total_NF': 3850.50,
            'Total_Impostos': 654.58,
            'Centro_Custo': 'Operações'
        },
        {
            'Numero_NF': '1047',
            'Fornecedor': 'LOGISTICA EXPRESS TRANSPORTES LTDA',
            'CNPJ_Fornecedor': '78.123.456/0001-44',
            'Data_Lancamento': '06/10/2026',
            'Valor_Total_NF': 2190.00,
            'Total_Impostos': 342.80,
            'Centro_Custo': 'Logística'
        },
        {
            'Numero_NF': '1048',
            'Fornecedor': 'DISTRIBUIDORA NACIONAL DE PECAS LTDA',
            'CNPJ_Fornecedor': '33.654.987/0001-02',
            'Data_Lancamento': '08/10/2026',
            'Valor_Total_NF': 8400.00,  # Divergência de R$ 500,00 (XML é 8900.00)
            'Total_Impostos': 1513.00,
            'Centro_Custo': 'Manutenção'
        },
        {
            'Numero_NF': '1049',
            'Fornecedor': 'CLOUD SERVICOS DIGITAIS S.A.',
            'CNPJ_Fornecedor': '91.827.364/0099-00',  # CNPJ divergente do XML
            'Data_Lancamento': '10/10/2026',
            'Valor_Total_NF': 6200.00,
            'Total_Impostos': 970.30,
            'Centro_Custo': 'Tecnologia'
        },
        {
            'Numero_NF': '1099',  # Lançada no Excel mas sem arquivo XML na pasta!
            'Fornecedor': 'CONSULTORIA EMPRESARIAL DELTA LTDA',
            'CNPJ_Fornecedor': '66.777.888/0001-12',
            'Data_Lancamento': '14/10/2026',
            'Valor_Total_NF': 4500.00,
            'Total_Impostos': 450.00,
            'Centro_Custo': 'Diretoria'
        }
    ])

    df_demo.to_excel(excel_path, index=False)
    return zip_path, "Lote_XMLs_Notas_Fiscais.zip", excel_path, "Relatorio_Contas_a_Pagar_ERP.xlsx"

