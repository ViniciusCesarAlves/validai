import os
import re
import io
import zipfile
from datetime import datetime, timedelta
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage

import ofxparse
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
COLOR_BLUE_BG = "E0F2FE"
COLOR_BLUE_TEXT = "0369A1"


# ==============================================================================
# 1. UTILITÁRIOS DE LIMPEZA, FORMATAÇÃO E NORMALIZAÇÃO
# ==============================================================================

def clean_digits(val):
    """Extrai apenas dígitos de qualquer entrada."""
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return re.sub(r'\D', '', s)


def normalize_nsu(val):
    """
    Normaliza NSU, TID, número de autorização ou comprovante.
    Ex: 'NSU 00987654', '00987654.0' -> '987654'
    """
    if val is None or pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    digits = re.sub(r'\D', '', s)
    if not digits:
        return s.strip().upper()
    stripped = digits.lstrip('0')
    return stripped if stripped else '0'


def parse_currency(val):
    """Converte valores monetários em float."""
    if val is None or pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace('R$', '').replace('r$', '').replace('$', '').strip()
    # Padrão brasileiro: 1.234,56
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_date_flexible(val):
    """Interpreta datas em múltiplos formatos (datetime, ISO, DD/MM/YYYY, YYYYMMDD)."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if hasattr(val, 'date') and callable(getattr(val, 'date')):
        try:
            return val.date()
        except Exception:
            pass

    s = str(val).strip()
    if not s:
        return None

    # Tenta formatos comuns
    formats = [
        '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d',
        '%Y%m%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S',
        '%Y%m%d%H%M%S'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s[:19], fmt).date()
        except Exception:
            continue
    return None


def format_brl(val):
    """Formata valor float para R$ no padrão brasileiro."""
    if val is None:
        return "R$ 0,00"
    try:
        v = float(val)
        neg = "-" if v < 0 else ""
        v = abs(v)
        s = f"{v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"{neg}R$ {s}"
    except Exception:
        return "R$ 0,00"


def format_pct(val):
    """Formata porcentagem float."""
    if val is None:
        return "0,00%"
    try:
        v = float(val)
        return f"{v:.2f}%".replace('.', ',')
    except Exception:
        return "0,00%"


# ==============================================================================
# 2. PARSER ROBUSTO DE ARQUIVOS .OFX (BANCÁRIOS E MAQUININHAS)
# ==============================================================================

def fallback_regex_parse_ofx(raw_text):
    """
    Parser alternativo baseado em Expressões Regulares para arquivos OFX 1.02 / SGML
    caso o arquivo tenha tags não fechadas ou cabeçalho fora de conformidade.
    """
    transactions = []
    # Localiza blocos <STMTTRN>
    blocks = re.findall(r'<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|<BANKTRANLIST>|</BANKTRANLIST>|$)', raw_text, re.DOTALL | re.IGNORECASE)
    
    for b in blocks:
        trntype_m = re.search(r'<TRNTYPE>([^<\r\n]+)', b, re.I)
        dt_m = re.search(r'<DTPOSTED>([0-9]{8})', b, re.I)
        amt_m = re.search(r'<TRNAMT>([^<\r\n]+)', b, re.I)
        fitid_m = re.search(r'<FITID>([^<\r\n]+)', b, re.I)
        memo_m = re.search(r'<MEMO>([^<\r\n]+)', b, re.I)
        checknum_m = re.search(r'<CHECKNUM>([^<\r\n]+)', b, re.I)

        if not amt_m:
            continue

        amt_str = amt_m.group(1).strip()
        amt = parse_currency(amt_str)
        trntype = trntype_m.group(1).strip().lower() if trntype_m else ('credit' if amt >= 0 else 'debit')
        
        parsed_dt = None
        if dt_m:
            try:
                parsed_dt = datetime.strptime(dt_m.group(1), '%Y%m%d').date()
            except Exception:
                pass
        if not parsed_dt:
            parsed_dt = datetime.now().date()

        memo = memo_m.group(1).strip() if memo_m else ""
        fitid = fitid_m.group(1).strip() if fitid_m else f"TX_{len(transactions)+1}"
        checknum = checknum_m.group(1).strip() if checknum_m else ""

        # Tenta extrair NSU do memo ou checknum
        extracted_nsu = ""
        nsu_search = re.search(r'(?:NSU|TID|DOC|AUT|COMPR|PED|REF|NUM)[:\s]*([0-9]{4,14})', f"{memo} {checknum} {fitid}", re.I)
        if nsu_search:
            extracted_nsu = normalize_nsu(nsu_search.group(1))
        elif checknum and checknum.isdigit():
            extracted_nsu = normalize_nsu(checknum)

        transactions.append({
            'fitid': fitid,
            'type': trntype,
            'date': parsed_dt,
            'date_str': parsed_dt.strftime('%Y-%m-%d'),
            'date_display': parsed_dt.strftime('%d/%m/%Y'),
            'amount': amt,
            'amount_fmt': format_brl(amt),
            'memo': memo,
            'checknum': checknum,
            'nsu_extracted': extracted_nsu
        })

    return transactions


def parse_ofx_file(file_path):
    """
    Lê e extrai transações de um arquivo .OFX usando ofxparse com fallback automático.
    Retorna lista de transações e metadados da conta.
    """
    raw_bytes = None
    with open(file_path, 'rb') as f:
        raw_bytes = f.read()

    # Tenta decodificar com diferentes encodings
    raw_text = None
    for enc in ['utf-8', 'iso-8859-1', 'windows-1252', 'cp1252', 'latin1']:
        try:
            raw_text = raw_bytes.decode(enc)
            break
        except Exception:
            continue
    if not raw_text:
        raw_text = raw_bytes.decode('utf-8', errors='replace')

    transactions = []
    metadata = {
        'bank_id': '',
        'account_id': '',
        'account_type': 'CHECKING',
        'currency': 'BRL',
        'dt_start': None,
        'dt_end': None,
        'ledger_balance': 0.0
    }

    # 1. Tenta usar biblioteca padrão ofxparse
    try:
        ofx = ofxparse.OfxParser.parse(io.StringIO(raw_text))
        accounts = []
        if hasattr(ofx, 'accounts') and ofx.accounts:
            accounts = ofx.accounts
        elif hasattr(ofx, 'account') and ofx.account:
            accounts = [ofx.account]

        for acc in accounts:
            if hasattr(acc, 'routing_number') and acc.routing_number:
                metadata['bank_id'] = str(acc.routing_number)
            if hasattr(acc, 'account_id') and acc.account_id:
                metadata['account_id'] = str(acc.account_id)
            if hasattr(acc, 'statement') and acc.statement:
                stmt = acc.statement
                if hasattr(stmt, 'currency') and stmt.currency:
                    metadata['currency'] = str(stmt.currency)
                if hasattr(stmt, 'start_date') and stmt.start_date:
                    metadata['dt_start'] = stmt.start_date.date() if hasattr(stmt.start_date, 'date') else None
                if hasattr(stmt, 'end_date') and stmt.end_date:
                    metadata['dt_end'] = stmt.end_date.date() if hasattr(stmt.end_date, 'date') else None
                if hasattr(stmt, 'balance') and stmt.balance is not None:
                    metadata['ledger_balance'] = float(stmt.balance)

                for t in getattr(stmt, 'transactions', []):
                    amt = float(t.amount) if t.amount is not None else 0.0
                    trntype = str(t.type).lower() if hasattr(t, 'type') and t.type else ('credit' if amt >= 0 else 'debit')
                    
                    t_date = None
                    if hasattr(t, 'date') and t.date:
                        t_date = t.date.date() if hasattr(t.date, 'date') else parse_date_flexible(t.date)
                    if not t_date:
                        t_date = datetime.now().date()

                    memo = str(t.memo or t.payee or "").strip()
                    fitid = str(t.id or "").strip()
                    checknum = str(getattr(t, 'checknum', '') or "").strip()

                    extracted_nsu = ""
                    nsu_search = re.search(r'(?:NSU|TID|DOC|AUT|COMPR|PED|REF|NUM)[:\s]*([0-9]{4,14})', f"{memo} {checknum} {fitid}", re.I)
                    if nsu_search:
                        extracted_nsu = normalize_nsu(nsu_search.group(1))
                    elif checknum and checknum.isdigit():
                        extracted_nsu = normalize_nsu(checknum)

                    transactions.append({
                        'fitid': fitid if fitid else f"TX_{len(transactions)+1}",
                        'type': trntype,
                        'date': t_date,
                        'date_str': t_date.strftime('%Y-%m-%d'),
                        'date_display': t_date.strftime('%d/%m/%Y'),
                        'amount': amt,
                        'amount_fmt': format_brl(amt),
                        'memo': memo,
                        'checknum': checknum,
                        'nsu_extracted': extracted_nsu
                    })

    except Exception:
        # Se ofxparse falhar, utiliza o fallback via regex
        transactions = fallback_regex_parse_ofx(raw_text)

    # Se ainda estiver vazio, roda regex
    if len(transactions) == 0:
        transactions = fallback_regex_parse_ofx(raw_text)

    return transactions, metadata


def extract_ofx_from_uploaded_files(saved_files):
    """
    Recebe lista de tuplas (caminho_arquivo, nome_original) e extrai todas as transações OFX,
    suportando arquivos .ofx diretos ou pacotes .zip contendo .ofx.
    """
    all_transactions = []
    parse_errors = []

    for f_path, original_name in saved_files:
        lower_name = original_name.lower()

        if lower_name.endswith('.zip'):
            try:
                with zipfile.ZipFile(f_path, 'r') as z:
                    for inner_file in z.namelist():
                        if inner_file.lower().endswith('.ofx') and not inner_file.startswith('__MACOSX'):
                            try:
                                content_bytes = z.read(inner_file)
                                # Salva temporário para parse
                                tmp_name = f"extracted_{os.path.basename(inner_file)}"
                                tmp_path = os.path.join(os.path.dirname(f_path), tmp_name)
                                with open(tmp_path, 'wb') as tf:
                                    tf.write(content_bytes)
                                txs, meta = parse_ofx_file(tmp_path)
                                all_transactions.extend(txs)
                            except Exception as ex:
                                parse_errors.append({'file': inner_file, 'error': str(ex)})
            except Exception as e:
                parse_errors.append({'file': original_name, 'error': f'Arquivo ZIP inválido ou corrompido: {str(e)}'})

        elif lower_name.endswith('.ofx'):
            try:
                txs, meta = parse_ofx_file(f_path)
                all_transactions.extend(txs)
            except Exception as e:
                parse_errors.append({'file': original_name, 'error': f'Falha ao ler OFX: {str(e)}'})
        else:
            parse_errors.append({'file': original_name, 'error': 'Formato não suportado. Envie arquivos .ofx ou pacote .zip.'})

    # Ordena transações por data crescente
    all_transactions.sort(key=lambda x: x['date'] if x.get('date') else datetime.min.date())

    return all_transactions, parse_errors


# ==============================================================================
# 3. SUGESTÃO AUTOMÁTICA DE COLUNAS DA PLANILHA DE VENDAS (PDV / ERP)
# ==============================================================================

def suggest_sheet_columns(columns):
    """
    Mapeia e sugere as colunas da planilha financeira de vendas:
    - col_id: NSU, TID, Código da Venda, Pedido
    - col_gross_val: Valor Bruto da Venda
    - col_date: Data da Venda
    - col_acquirer: Adquirente, Maquininha, Meio de Pagamento
    - col_net_val: Valor Líquido (se houver na planilha)
    """
    suggested = {
        'col_id': None,
        'col_gross_val': None,
        'col_date': None,
        'col_acquirer': None,
        'col_net_val': None
    }

    norm_map = {col: re.sub(r'[^a-z0-9]', '', str(col).lower()) for col in columns}

    # 1. Coluna de Identificador / NSU / TID / Pedido
    id_patterns = ['nsu', 'tid', 'idvenda', 'vendaid', 'numeropedido', 'pedido', 'codigo', 'comprovante', 'autorizacao', 'cupom', 'id']
    for p in id_patterns:
        for orig, norm in norm_map.items():
            if p == norm or norm.startswith(p) or norm.endswith(p):
                suggested['col_id'] = orig
                break
        if suggested['col_id']:
            break

    # 2. Coluna de Valor Bruto
    gross_patterns = ['valorbruto', 'vlrbruto', 'vlbruto', 'totalbruto', 'valorvenda', 'vlrvenda', 'valor', 'total', 'vlrtotal', 'valortotal']
    for p in gross_patterns:
        for orig, norm in norm_map.items():
            if p == norm or norm.startswith(p) or norm.endswith(p):
                suggested['col_gross_val'] = orig
                break
        if suggested['col_gross_val']:
            break

    # 3. Coluna de Data
    date_patterns = ['datavenda', 'dtvenda', 'data', 'dt', 'emissao', 'datahora', 'previsao', 'datarepasse']
    for p in date_patterns:
        for orig, norm in norm_map.items():
            if p == norm or norm.startswith(p) or norm.endswith(p):
                suggested['col_date'] = orig
                break
        if suggested['col_date']:
            break

    # 4. Coluna de Adquirente / Bandeira / Meio de Pagamento
    acq_patterns = ['adquirente', 'maquininha', 'operadora', 'bandeira', 'formapagamento', 'formapagto', 'meiopagamento', 'canal', 'plataforma', 'modalidade']
    for p in acq_patterns:
        for orig, norm in norm_map.items():
            if p == norm or norm.startswith(p) or norm.endswith(p):
                suggested['col_acquirer'] = orig
                break
        if suggested['col_acquirer']:
            break

    # 5. Coluna de Valor Líquido (opcional)
    net_patterns = ['valorliquido', 'vlrliquido', 'vlliquido', 'totalliquido', 'liquido']
    for p in net_patterns:
        for orig, norm in norm_map.items():
            if p == norm or norm.startswith(p) or norm.endswith(p):
                suggested['col_net_val'] = orig
                break
        if suggested['col_net_val']:
            break

    return suggested


# ==============================================================================
# 4. MOTOR DE CONCILIAÇÃO DE TAXAS E EXTRATOS (.OFX VS VENDAS ERP)
# ==============================================================================

def reconcile_ofx_vs_sales(
    df_sales,
    ofx_transactions,
    col_id,
    col_gross_val,
    col_date,
    col_acquirer=None,
    expected_rate_pct=3.5,
    tolerance_cents=0.05,
    date_tolerance_days=3
):
    """
    Cruza as vendas da planilha do PDV/ERP com os créditos do extrato .OFX:
    1. Calcula para cada venda o Valor Líquido Esperado baseado na Taxa Contratada (%).
    2. Cruza com os créditos do OFX (primeiro por NSU/ID no memo, depois por Data + Valor Líquido).
    3. Identifica:
       - Vendas Conciliadas (Taxa Cobrada = Taxa Esperada)
       - Divergências de Taxa (Cobrança a Maior da Maquininha / Prejuízo R$)
       - Vendas Não Repassadas (Venda no PDV que não caiu na conta)
       - Créditos Avulsos no OFX (Depósitos sem venda correspondente)
    """
    expected_rate = float(expected_rate_pct)
    tolerance = float(tolerance_cents)
    date_tol = int(date_tolerance_days)

    # 1. Prepara lista de créditos do OFX (apenas créditos > 0 são repasses de vendas)
    ofx_credits = []
    for idx, tx in enumerate(ofx_transactions):
        amt = float(tx.get('amount', 0.0))
        if amt > 0:
            ofx_credits.append({
                'ofx_idx': idx,
                'fitid': tx.get('fitid', ''),
                'date': tx.get('date'),
                'date_str': tx.get('date_str', ''),
                'date_display': tx.get('date_display', ''),
                'amount': amt,
                'memo': tx.get('memo', ''),
                'checknum': tx.get('checknum', ''),
                'nsu_extracted': tx.get('nsu_extracted', ''),
                'matched': False
            })

    # 2. Converte vendas do DataFrame em registros estruturados
    sales_rows = []
    for idx, row in df_sales.iterrows():
        raw_id = row.get(col_id, '') if col_id else f"VENDA_{idx+1}"
        norm_id = normalize_nsu(raw_id)

        raw_gross = row.get(col_gross_val, 0.0) if col_gross_val else 0.0
        gross_val = round(parse_currency(raw_gross), 2)

        raw_date = row.get(col_date) if col_date else None
        sale_date = parse_date_flexible(raw_date)

        acquirer = str(row.get(col_acquirer, '')).strip() if (col_acquirer and col_acquirer in row and not pd.isna(row.get(col_acquirer))) else "Geral"
        if acquirer == "nan" or not acquirer:
            acquirer = "Geral"

        # Cálculo financeiro esperado
        expected_fee_val = round(gross_val * (expected_rate / 100.0), 2)
        expected_net_val = round(gross_val - expected_fee_val, 2)

        sales_rows.append({
            'row_idx': idx + 1,
            'sale_id': str(raw_id).strip(),
            'norm_id': norm_id,
            'sale_date': sale_date,
            'sale_date_display': sale_date.strftime('%d/%m/%Y') if sale_date else "-",
            'gross_val': gross_val,
            'acquirer': acquirer,
            'expected_rate_pct': expected_rate,
            'expected_fee_val': expected_fee_val,
            'expected_net_val': expected_net_val,
            'matched': False,
            'ofx_match': None
        })

    # 3. PASSO 1 DE BATIMENTO: Correspondência Direta por Identificador / NSU / TID
    for sale in sales_rows:
        if not sale['norm_id']:
            continue
        s_id = sale['norm_id']
        for tx in ofx_credits:
            if tx['matched']:
                continue
            # Verifica se o NSU está no memo, no checknum ou na lista extraída
            memo_norm = normalize_nsu(tx['memo'])
            if s_id == tx['nsu_extracted'] or s_id in memo_norm or (tx['checknum'] and s_id == normalize_nsu(tx['checknum'])):
                sale['matched'] = True
                sale['ofx_match'] = tx
                tx['matched'] = True
                break

    # 4. PASSO 2 DE BATIMENTO: Correspondência por Valor Líquido + Janela de Data
    for sale in sales_rows:
        if sale['matched'] or sale['gross_val'] <= 0:
            continue
        exp_net = sale['expected_net_val']
        s_date = sale['sale_date']

        best_candidate = None
        best_diff = 999999.0

        for tx in ofx_credits:
            if tx['matched']:
                continue

            diff = abs(tx['amount'] - exp_net)
            # Verifica tolerância de valor
            if diff <= max(tolerance, 0.05):
                # Verifica tolerância de datas
                if s_date and tx['date']:
                    days_diff = (tx['date'] - s_date).days
                    # Repasses geralmente caem no mesmo dia (D+0) ou dias seguintes (D+1, D+2, D+30)
                    if -1 <= days_diff <= max(date_tol, 1):
                        if diff < best_diff:
                            best_diff = diff
                            best_candidate = tx
                else:
                    if diff < best_diff:
                        best_diff = diff
                        best_candidate = tx

        if best_candidate:
            sale['matched'] = True
            sale['ofx_match'] = best_candidate
            best_candidate['matched'] = True

    # 5. PASSO 3: Classificação dos Resultados e Auditoria de Taxas
    reconciled_items = []
    
    total_gross = 0.0
    total_expected_net = 0.0
    total_expected_fees = 0.0
    total_credited_ofx = 0.0
    total_divergence_loss = 0.0

    count_ok = 0
    count_divergent_rate = 0
    count_unpaid = 0

    for sale in sales_rows:
        gross = sale['gross_val']
        exp_net = sale['expected_net_val']
        exp_fee = sale['expected_fee_val']
        exp_rate = sale['expected_rate_pct']

        total_gross += gross
        total_expected_net += exp_net
        total_expected_fees += exp_fee

        if sale['matched']:
            ofx_tx = sale['ofx_match']
            credited_val = round(ofx_tx['amount'], 2)
            total_credited_ofx += credited_val

            effective_fee_val = round(gross - credited_val, 2)
            effective_rate_pct = round((effective_fee_val / gross) * 100.0, 2) if gross > 0 else 0.0
            diff_val = round(exp_net - credited_val, 2)

            # Avalia tolerância
            if abs(diff_val) <= tolerance:
                status = "CONCILIADO"
                status_label = "Taxa Correta"
                status_badge = "status-ok"
                recommendation = "Repasse e taxa conferidos perfeitamente conforme acordado."
                count_ok += 1
            elif diff_val > tolerance:
                status = "TAXA_A_MAIOR"
                status_label = "Taxa Cobrada a Maior"
                status_badge = "status-error"
                recommendation = f"Taxa de {effective_rate_pct:.2f}% superior à contratada ({exp_rate:.2f}%). Solicitar contestação de {format_brl(diff_val)}."
                count_divergent_rate += 1
                total_divergence_loss += diff_val
            else:
                status = "TAXA_A_MENOR"
                status_label = "Taxa Menor / Bônus"
                status_badge = "status-info"
                recommendation = f"Taxa efetiva praticada ({effective_rate_pct:.2f}%) foi menor que a esperada ({exp_rate:.2f}%)."
                count_ok += 1

            reconciled_items.append({
                'type': 'sale',
                'status': status,
                'status_label': status_label,
                'status_badge': status_badge,
                'sale_id': sale['sale_id'],
                'acquirer': sale['acquirer'],
                'sale_date_display': sale['sale_date_display'],
                'credit_date_display': ofx_tx['date_display'],
                'gross_val': gross,
                'gross_val_fmt': format_brl(gross),
                'expected_rate_pct': exp_rate,
                'expected_rate_fmt': format_pct(exp_rate),
                'expected_net_val': exp_net,
                'expected_net_fmt': format_brl(exp_net),
                'credited_ofx_val': credited_val,
                'credited_ofx_fmt': format_brl(credited_val),
                'effective_rate_pct': effective_rate_pct,
                'effective_rate_fmt': format_pct(effective_rate_pct),
                'diff_val': diff_val,
                'diff_val_fmt': format_brl(diff_val),
                'ofx_memo': ofx_tx['memo'],
                'ofx_fitid': ofx_tx['fitid'],
                'recommendation': recommendation
            })

        else:
            # Venda no ERP que não foi localizada no OFX
            count_unpaid += 1
            reconciled_items.append({
                'type': 'sale',
                'status': "NAO_REPASSADO",
                'status_label': "Não Repassado / Pendente",
                'status_badge': "status-warning",
                'sale_id': sale['sale_id'],
                'acquirer': sale['acquirer'],
                'sale_date_display': sale['sale_date_display'],
                'credit_date_display': "-",
                'gross_val': gross,
                'gross_val_fmt': format_brl(gross),
                'expected_rate_pct': exp_rate,
                'expected_rate_fmt': format_pct(exp_rate),
                'expected_net_val': exp_net,
                'expected_net_fmt': format_brl(exp_net),
                'credited_ofx_val': 0.0,
                'credited_ofx_fmt': "R$ 0,00",
                'effective_rate_pct': 0.0,
                'effective_rate_fmt': "-",
                'diff_val': exp_net,
                'diff_val_fmt': format_brl(exp_net),
                'ofx_memo': "-",
                'ofx_fitid': "-",
                'recommendation': f"Venda registrada no PDV sem crédito identificado no extrato OFX. Cobrar repasse de {format_brl(exp_net)}."
            })

    # 6. PASSO 4: Créditos Avulsos no OFX (dinheiro creditado que não bateu com nenhuma venda do ERP)
    orphan_credits = []
    total_orphan_amount = 0.0
    for tx in ofx_credits:
        if not tx['matched']:
            amt = round(tx['amount'], 2)
            total_orphan_amount += amt
            orphan_item = {
                'type': 'orphan_credit',
                'status': "CREDITO_SEM_VENDA",
                'status_label': "Crédito Avulso no Extrato",
                'status_badge': "status-purple",
                'sale_id': tx['nsu_extracted'] if tx['nsu_extracted'] else f"OFX_{tx['fitid'][-6:]}",
                'acquirer': "Extrato OFX",
                'sale_date_display': "-",
                'credit_date_display': tx['date_display'],
                'gross_val': amt,
                'gross_val_fmt': format_brl(amt),
                'expected_rate_pct': 0.0,
                'expected_rate_fmt': "-",
                'expected_net_val': amt,
                'expected_net_fmt': format_brl(amt),
                'credited_ofx_val': amt,
                'credited_ofx_fmt': format_brl(amt),
                'effective_rate_pct': 0.0,
                'effective_rate_fmt': "-",
                'diff_val': 0.0,
                'diff_val_fmt': "R$ 0,00",
                'ofx_memo': tx['memo'],
                'ofx_fitid': tx['fitid'],
                'recommendation': "Crédito identificado no banco/maquininha sem venda correspondente na planilha do ERP."
            }
            orphan_credits.append(orphan_item)
            reconciled_items.append(orphan_item)

    # 7. Compilação de Indicadores Gerais (KPIs)
    total_sales_count = len(sales_rows)
    reconciled_pct = round((count_ok / total_sales_count) * 100.0, 1) if total_sales_count > 0 else 0.0

    count_reconciled = count_ok
    count_pending = count_unpaid
    count_unidentified = count_divergent_rate + len(orphan_credits)

    val_reconciled = sum(it.get('credited_ofx_val', 0.0) for it in reconciled_items if it.get('status') == 'CONCILIADO')
    val_pending = sum(it.get('expected_net_val', 0.0) for it in reconciled_items if it.get('status') == 'NAO_REPASSADO')
    val_unidentified = round(total_divergence_loss + total_orphan_amount, 2)
    total_actual_fees = round(max(0.0, total_expected_fees + total_divergence_loss), 2)

    kpis = {
        'total_sales_count': total_sales_count,
        'total_gross': total_gross,
        'total_gross_fmt': format_brl(total_gross),
        'total_expected_net': total_expected_net,
        'total_expected_net_fmt': format_brl(total_expected_net),
        'total_expected_fees': total_expected_fees,
        'total_expected_fees_fmt': format_brl(total_expected_fees),
        'total_credited_ofx': total_credited_ofx,
        'total_credited_ofx_fmt': format_brl(total_credited_ofx),
        'reconciled_count': count_ok,
        'reconciled_pct': reconciled_pct,
        'divergent_fees_count': count_divergent_rate,
        'total_divergence_loss': round(total_divergence_loss, 2),
        'total_divergence_loss_fmt': format_brl(total_divergence_loss),
        'unpaid_sales_count': count_unpaid,
        'orphan_credits_count': len(orphan_credits),
        'total_orphan_amount': round(total_orphan_amount, 2),
        'total_orphan_amount_fmt': format_brl(total_orphan_amount),
        'expected_rate_pct': expected_rate,
        'tolerance_cents': tolerance,
        'dashboard_taxas': {
            'status_counts': {
                'reconciled': count_reconciled,
                'pending': count_pending,
                'divergent_or_unidentified': count_unidentified
            },
            'status_values': {
                'reconciled': round(val_reconciled, 2),
                'pending': round(val_pending, 2),
                'divergent_or_unidentified': round(val_unidentified, 2)
            },
            'financial_comparison': {
                'gross_expected': round(total_gross, 2),
                'credited_ofx': round(total_credited_ofx, 2),
                'fees_estimated': round(total_expected_fees, 2),
                'fees_discounted': round(total_actual_fees, 2)
            }
        }
    }

    return {
        'items': reconciled_items,
        'kpis': kpis
    }


# ==============================================================================
# 5. GERADOR DE RELATÓRIO EXCEL COMPLETO DE AUDITORIA COM CÉLULAS PINTADAS
# ==============================================================================

def generate_audit_report(reconciled_data, output_path, logo_path=None):
    """
    Gera uma planilha Excel (.xlsx) com 4 abas completas no padrão visual ValidAí:
    - Aba 1: Resumo Executivo da Auditoria de Taxas e Conciliação
    - Aba 2: Conciliação Completa (todas as transações com células pintadas)
    - Aba 3: Divergências de Taxa e Vendas Pendentes (Ações Imediatas)
    - Aba 4: Espelho Tabulado do Extrato OFX
    """
    items = reconciled_data['items']
    kpis = reconciled_data['kpis']

    wb = openpyxl.Workbook()
    # Remove sheet padrão inicial
    default_sheet = wb.active
    wb.remove(default_sheet)

    # Estilos comuns
    font_family = "Calibri"
    font_title = Font(name=font_family, size=15, bold=True, color=COLOR_DARK)
    font_sub = Font(name=font_family, size=10, italic=True, color="64748B")
    font_sec = Font(name=font_family, size=11, bold=True, color="0F172A")
    font_bold = Font(name=font_family, size=11, bold=True, color=COLOR_DARK)
    font_normal = Font(name=font_family, size=11, color=COLOR_DARK)
    font_header = Font(name=font_family, size=11, bold=True, color="FFFFFF")

    fill_header = PatternFill(start_color=COLOR_GREEN, end_color=COLOR_GREEN, fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    
    fill_ok = PatternFill(start_color=COLOR_SUCCESS_BG, end_color=COLOR_SUCCESS_BG, fill_type="solid")
    font_ok = Font(name=font_family, size=10, bold=True, color=COLOR_SUCCESS_TEXT)

    fill_error = PatternFill(start_color=COLOR_ERROR_BG, end_color=COLOR_ERROR_BG, fill_type="solid")
    font_error = Font(name=font_family, size=10, bold=True, color=COLOR_ERROR_TEXT)

    fill_warn = PatternFill(start_color=COLOR_WARN_BG, end_color=COLOR_WARN_BG, fill_type="solid")
    font_warn = Font(name=font_family, size=10, bold=True, color=COLOR_WARN_TEXT)

    fill_blue = PatternFill(start_color=COLOR_BLUE_BG, end_color=COLOR_BLUE_BG, fill_type="solid")
    font_blue = Font(name=font_family, size=10, bold=True, color=COLOR_BLUE_TEXT)

    thin_border = Border(
        left=Side(style='thin', color="CBD5E1"),
        right=Side(style='thin', color="CBD5E1"),
        top=Side(style='thin', color="CBD5E1"),
        bottom=Side(style='thin', color="CBD5E1")
    )

    # --------------------------------------------------------------------------
    # ABA 1: RESUMO EXECUTIVO
    # --------------------------------------------------------------------------
    ws1 = wb.create_sheet(title="Resumo Executivo")
    ws1.views.sheetView[0].showGridLines = True

    # Logo
    if logo_path and os.path.exists(logo_path):
        try:
            img = OpenpyxlImage(logo_path)
            img.width = 125
            img.height = 36
            ws1.add_image(img, "A1")
        except Exception:
            pass

    ws1["C2"] = "RELATÓRIO DE AUDITORIA DE TAXAS E CONCILIAÇÃO (.OFX)"
    ws1["C2"].font = font_title
    ws1["C3"] = f"Gerado pelo ValidAí em {datetime.now().strftime('%d/%m/%Y às %H:%M')} | Taxa Acordada: {kpis['expected_rate_pct']:.2f}%"
    ws1["C3"].font = font_sub

    # Quadro de KPIs
    ws1["A6"] = "INDICADORES CHAVE DA OPERAÇÃO"
    ws1["A6"].font = font_sec

    kpi_rows = [
        ("Total de Vendas Auditadas (PDV / ERP)", kpis['total_sales_count'], "#,##0"),
        ("Faturamento Bruto em Vendas", kpis['total_gross'], "R$ #,##0.00"),
        ("Valor Líquido Esperado Contratual", kpis['total_expected_net'], "R$ #,##0.00"),
        ("Previsão de Taxas Acordadas", kpis['total_expected_fees'], "R$ #,##0.00"),
        ("Total Líquido Creditado no Extrato (.OFX)", kpis['total_credited_ofx'], "R$ #,##0.00"),
        ("Taxa Geral de Conciliação Aprovada (%)", kpis['reconciled_pct'] / 100.0, "0.0%"),
        ("Vendas com Cobrança de Taxa a Maior", kpis['divergent_fees_count'], "#,##0"),
        ("Prejuízo Estimado por Taxas Cobradas a Maior", kpis['total_divergence_loss'], "R$ #,##0.00"),
        ("Vendas Não Repassadas (Pendente no Extrato)", kpis['unpaid_sales_count'], "#,##0"),
        ("Créditos no Extrato sem Venda no ERP", kpis['orphan_credits_count'], "#,##0"),
        ("Valor Total de Créditos Avulsos Identificados", kpis['total_orphan_amount'], "R$ #,##0.00")
    ]

    cur_row = 7
    for label, val, num_fmt in kpi_rows:
        ws1.merge_cells(f"A{cur_row}:C{cur_row}")
        ws1[f"A{cur_row}"].font = font_bold if "Prejuízo" in label or "Taxa Geral" in label else font_normal
        kpi_fill = fill_error if "Prejuízo" in label and val > 0 else (fill_ok if "Taxa Geral" in label else PatternFill(fill_type=None))
        ws1[f"A{cur_row}"].fill = kpi_fill

        ws1[f"D{cur_row}"] = val
        ws1[f"D{cur_row}"].font = font_bold
        ws1[f"D{cur_row}"].number_format = num_fmt
        ws1[f"D{cur_row}"].alignment = Alignment(horizontal="right")
        ws1[f"D{cur_row}"].fill = kpi_fill

        for col_l in ["A", "B", "C", "D"]:
            ws1[f"{col_l}{cur_row}"].border = thin_border
        cur_row += 1

    # Plano de Ação Recomendado
    cur_row += 2
    ws1[f"A{cur_row}"] = "DIAGNÓSTICO E PLANO DE AÇÃO RECOMENDADO"
    ws1[f"A{cur_row}"].font = font_sec
    cur_row += 1

    actions = []
    if kpis['total_divergence_loss'] > 0:
        actions.append(f"• ABRIR PROTOCOLO DE CONTESTAÇÃO: Foi identificado um total de {kpis['total_divergence_loss_fmt']} cobrado a mais nas taxas das maquininhas. Solicite o estorno retroativo anexando a Aba 'Divergências'.")
    else:
        actions.append("• TAXAS 100% AUDITADAS: Nenhuma cobrança indevida acima da taxa contratada foi identificada nas vendas processadas.")

    if kpis['unpaid_sales_count'] > 0:
        actions.append(f"• COBRAR REPASSES PENDENTES: Há {kpis['unpaid_sales_count']} vendas registradas no seu PDV que ainda não caíram no extrato bancário. Verifique prazos de compensação ou entre em contato com o suporte da adquirente.")

    if kpis['orphan_credits_count'] > 0:
        actions.append(f"• CONCILIAR CRÉDITOS AVULSOS: Existem {kpis['orphan_credits_count']} lançamentos no extrato bancário (totalizando {kpis['total_orphan_amount_fmt']}) sem venda correspondente registrada no ERP.")

    for act in actions:
        ws1.merge_cells(f"A{cur_row}:E{cur_row}")
        ws1[f"A{cur_row}"] = act
        ws1[f"A{cur_row}"].font = font_normal
        ws1.row_dimensions[cur_row].height = 24
        cur_row += 1

    # Crédito Institucional no Rodapé do Resumo
    cur_row += 1
    credit_cell = ws1.cell(
        row=cur_row,
        column=1,
        value="Relatório gerado automaticamente por ValidAí (https://validai.app.br) • Arquitetura e Inteligência de Dados por Vinícius Alves."
    )
    credit_cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")

    ws1.column_dimensions["A"].width = 30
    ws1.column_dimensions["B"].width = 25
    ws1.column_dimensions["C"].width = 25
    ws1.column_dimensions["D"].width = 22
    ws1.column_dimensions["E"].width = 30

    # --------------------------------------------------------------------------
    # ABA 2: CONCILIAÇÃO COMPLETA
    # --------------------------------------------------------------------------
    ws2 = wb.create_sheet(title="Conciliação Completa")
    ws2.views.sheetView[0].showGridLines = True

    headers = [
        "Status", "Situação da Taxa", "ID / NSU Venda", "Adquirente / Canal",
        "Data Venda", "Data Repasse (OFX)", "Valor Bruto (R$)",
        "Taxa Esperada (%)", "Líquido Esperado (R$)", "Creditado OFX (R$)",
        "Taxa Real Efetiva (%)", "Diferença (R$)", "Memo do Extrato (.OFX)", "Ação Recomendada"
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws2.row_dimensions[1].height = 28

    row_num = 2
    for item in items:
        status = item['status']
        ws2.cell(row=row_num, column=1, value=status).alignment = Alignment(horizontal="center")
        ws2.cell(row=row_num, column=2, value=item['status_label'])
        ws2.cell(row=row_num, column=3, value=str(item['sale_id'])).alignment = Alignment(horizontal="center")
        ws2.cell(row=row_num, column=4, value=item['acquirer'])
        ws2.cell(row=row_num, column=5, value=item['sale_date_display']).alignment = Alignment(horizontal="center")
        ws2.cell(row=row_num, column=6, value=item['credit_date_display']).alignment = Alignment(horizontal="center")
        
        c_gross = ws2.cell(row=row_num, column=7, value=item['gross_val'])
        c_gross.number_format = "R$ #,##0.00"

        c_exp_rate = ws2.cell(row=row_num, column=8, value=item['expected_rate_pct'] / 100.0 if item['expected_rate_pct'] else 0.0)
        c_exp_rate.number_format = "0.00%"

        c_exp_net = ws2.cell(row=row_num, column=9, value=item['expected_net_val'])
        c_exp_net.number_format = "R$ #,##0.00"

        c_ofx = ws2.cell(row=row_num, column=10, value=item['credited_ofx_val'])
        c_ofx.number_format = "R$ #,##0.00"

        c_eff_rate = ws2.cell(row=row_num, column=11, value=item['effective_rate_pct'] / 100.0 if item['effective_rate_pct'] else 0.0)
        c_eff_rate.number_format = "0.00%"

        c_diff = ws2.cell(row=row_num, column=12, value=item['diff_val'])
        c_diff.number_format = "R$ #,##0.00"

        ws2.cell(row=row_num, column=13, value=item['ofx_memo'])
        ws2.cell(row=row_num, column=14, value=item['recommendation'])

        # Pintura por status
        for col_idx in range(1, 15):
            c = ws2.cell(row=row_num, column=col_idx)
            c.border = thin_border
            c.font = font_normal

        # Destaque de células
        c_status = ws2.cell(row=row_num, column=1)
        c_label = ws2.cell(row=row_num, column=2)
        if status == "CONCILIADO":
            c_status.fill = fill_ok
            c_status.font = font_ok
            c_label.fill = fill_ok
        elif status == "TAXA_A_MAIOR":
            c_status.fill = fill_error
            c_status.font = font_error
            c_label.fill = fill_error
            c_diff.fill = fill_error
            c_eff_rate.fill = fill_error
        elif status == "NAO_REPASSADO":
            c_status.fill = fill_warn
            c_status.font = font_warn
            c_label.fill = fill_warn
            c_ofx.fill = fill_warn
        elif status == "CREDITO_SEM_VENDA":
            c_status.fill = fill_blue
            c_status.font = font_blue
            c_label.fill = fill_blue

        row_num += 1

    # Auto ajuste de largura das colunas
    for col in ws2.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws2.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # --------------------------------------------------------------------------
    # ABA 3: DIVERGÊNCIAS DE TAXA E VENDAS PENDENTES
    # --------------------------------------------------------------------------
    ws3 = wb.create_sheet(title="Divergências e Pendências")
    ws3.views.sheetView[0].showGridLines = True

    for col_idx, h in enumerate(headers, 1):
        cell = ws3.cell(row=1, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    ws3.row_dimensions[1].height = 28

    row_num_d = 2
    for item in items:
        if item['status'] not in ["TAXA_A_MAIOR", "NAO_REPASSADO"]:
            continue
        status = item['status']
        ws3.cell(row=row_num_d, column=1, value=status).alignment = Alignment(horizontal="center")
        ws3.cell(row=row_num_d, column=2, value=item['status_label'])
        ws3.cell(row=row_num_d, column=3, value=str(item['sale_id'])).alignment = Alignment(horizontal="center")
        ws3.cell(row=row_num_d, column=4, value=item['acquirer'])
        ws3.cell(row=row_num_d, column=5, value=item['sale_date_display']).alignment = Alignment(horizontal="center")
        ws3.cell(row=row_num_d, column=6, value=item['credit_date_display']).alignment = Alignment(horizontal="center")
        
        c_gross = ws3.cell(row=row_num_d, column=7, value=item['gross_val'])
        c_gross.number_format = "R$ #,##0.00"

        c_exp_rate = ws3.cell(row=row_num_d, column=8, value=item['expected_rate_pct'] / 100.0 if item['expected_rate_pct'] else 0.0)
        c_exp_rate.number_format = "0.00%"

        c_exp_net = ws3.cell(row=row_num_d, column=9, value=item['expected_net_val'])
        c_exp_net.number_format = "R$ #,##0.00"

        c_ofx = ws3.cell(row=row_num_d, column=10, value=item['credited_ofx_val'])
        c_ofx.number_format = "R$ #,##0.00"

        c_eff_rate = ws3.cell(row=row_num_d, column=11, value=item['effective_rate_pct'] / 100.0 if item['effective_rate_pct'] else 0.0)
        c_eff_rate.number_format = "0.00%"

        c_diff = ws3.cell(row=row_num_d, column=12, value=item['diff_val'])
        c_diff.number_format = "R$ #,##0.00"

        ws3.cell(row=row_num_d, column=13, value=item['ofx_memo'])
        ws3.cell(row=row_num_d, column=14, value=item['recommendation'])

        for col_idx in range(1, 15):
            c = ws3.cell(row=row_num_d, column=col_idx)
            c.border = thin_border
            c.font = font_normal

        c_status = ws3.cell(row=row_num_d, column=1)
        c_label = ws3.cell(row=row_num_d, column=2)
        if status == "TAXA_A_MAIOR":
            c_status.fill = fill_error
            c_status.font = font_error
            c_label.fill = fill_error
            c_diff.fill = fill_error
        elif status == "NAO_REPASSADO":
            c_status.fill = fill_warn
            c_status.font = font_warn
            c_label.fill = fill_warn

        row_num_d += 1

    for col in ws3.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws3.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # --------------------------------------------------------------------------
    # ABA 4: ESPELHO DO EXTRATO OFX
    # --------------------------------------------------------------------------
    ws4 = wb.create_sheet(title="Espelho Extrato OFX")
    ws4.views.sheetView[0].showGridLines = True

    ofx_headers = ["FITID (Código Único)", "Data Lançamento", "Tipo", "Valor Creditado / Debitado (R$)", "Descrição / Memo", "NSU Detectado"]
    for col_idx, h in enumerate(ofx_headers, 1):
        cell = ws4.cell(row=1, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    ws4.row_dimensions[1].height = 26

    # Coleta transações únicas a partir do items
    row_num_o = 2
    seen_fitids = set()
    for item in items:
        fitid = item.get('ofx_fitid')
        if not fitid or fitid in seen_fitids or fitid == "-":
            continue
        seen_fitids.add(fitid)

        ws4.cell(row=row_num_o, column=1, value=fitid).alignment = Alignment(horizontal="center")
        ws4.cell(row=row_num_o, column=2, value=item.get('credit_date_display', '-')).alignment = Alignment(horizontal="center")
        ws4.cell(row=row_num_o, column=3, value="Crédito").alignment = Alignment(horizontal="center")
        
        c_amt = ws4.cell(row=row_num_o, column=4, value=item.get('credited_ofx_val', 0.0))
        c_amt.number_format = "R$ #,##0.00"
        
        ws4.cell(row=row_num_o, column=5, value=item.get('ofx_memo', ''))
        ws4.cell(row=row_num_o, column=6, value=item.get('sale_id', '')).alignment = Alignment(horizontal="center")

        for col_idx in range(1, 7):
            c = ws4.cell(row=row_num_o, column=col_idx)
            c.border = thin_border
            c.font = font_normal

        row_num_o += 1

    for col in ws4.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws4.column_dimensions[col_letter].width = max(max_len + 3, 14)

    wb.save(output_path)
    return output_path


def generate_ofx_mirror_report(ofx_transactions, output_path, logo_path=None):
    """Gera uma planilha simples de Espelho Tabulado de todas as transações do OFX."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Extrato OFX Tabulado"
    ws.views.sheetView[0].showGridLines = True

    font_family = "Segoe UI"
    font_header = Font(name=font_family, size=10, bold=True, color="065F46")
    font_normal = Font(name=font_family, size=10, color="0F172A")
    fill_header = PatternFill(start_color="BCFFE2", end_color="BCFFE2", fill_type="solid")
    thin_border = Border(left=Side(style='thin', color="E2E8F0"), right=Side(style='thin', color="E2E8F0"),
                         top=Side(style='thin', color="E2E8F0"), bottom=Side(style='thin', color="E2E8F0"))

    headers = ["Nº", "Data", "FITID", "Tipo", "Valor (R$)", "Descrição / Memo", "NSU Detectado"]
    for col_idx, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=col_idx, value=h)
        c.font = font_header
        c.fill = fill_header
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    for idx, tx in enumerate(ofx_transactions, 2):
        ws.cell(row=idx, column=1, value=idx - 1).alignment = Alignment(horizontal="center")
        ws.cell(row=idx, column=2, value=tx.get('date_display', '')).alignment = Alignment(horizontal="center")
        ws.cell(row=idx, column=3, value=tx.get('fitid', '')).alignment = Alignment(horizontal="center")
        ws.cell(row=idx, column=4, value=tx.get('type', '').upper()).alignment = Alignment(horizontal="center")
        
        c_amt = ws.cell(row=idx, column=5, value=tx.get('amount', 0.0))
        c_amt.number_format = "R$ #,##0.00"

        ws.cell(row=idx, column=6, value=tx.get('memo', ''))
        ws.cell(row=idx, column=7, value=tx.get('nsu_extracted', '')).alignment = Alignment(horizontal="center")

        for col_i in range(1, 8):
            cell = ws.cell(row=idx, column=col_i)
            cell.border = thin_border
            cell.font = font_normal

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    wb.save(output_path)
    return output_path


# ==============================================================================
# 6. GERADOR DE DADOS DE EXEMPLO (DEMO PACK) PARA TESTE IMEDIATO
# ==============================================================================

def create_demo_files(session_folder):
    """
    Cria automaticamente um arquivo .ofx realista da maquininha Stone/Cielo e uma
    planilha Vendas_PDV_Outubro.xlsx com casos reais:
    - Vendas conciliadas na taxa de 3,50%
    - 1 Caso de taxa abusiva/divergente cobrada a maior (5,20% em vez de 3,50%)
    - 1 Caso de venda não repassada (pendente)
    - 1 Caso de crédito avulso no extrato
    """
    ofx_path = os.path.join(session_folder, "Extrato_Maquininha_Stone.ofx")
    excel_path = os.path.join(session_folder, "Relatorio_Vendas_PDV_ERP.xlsx")

    # Conteúdo OFX Realista
    ofx_content = """OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEKEY:NONE
NEWFILEKEY:NONE

<OFX>
<SIGNONMSGSRSV1>
<SONRS>
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<DTSERVER>20261015180000[-3:BRT]
<LANGUAGE>POR
</SONRS>
</SIGNONMSGSRSV1>
<BANKMSGSRSV1>
<STMTTRNRS>
<TRNUID>2026101501
<STATUS>
<CODE>0
<SEVERITY>INFO
</STATUS>
<STMTRS>
<CURDEF>BRL
<BANKACCTFROM>
<BANKID>0197
<ACCTID>98765-4
<ACCTTYPE>CHECKING
</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20261001000000[-3:BRT]
<DTEND>20261015235959[-3:BRT]
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261002120000[-3:BRT]
<TRNAMT>193.00
<FITID>20261002001
<CHECKNUM>98101
<MEMO>STONE PAGAMENTOS NSU 98101
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261003120000[-3:BRT]
<TRNAMT>434.25
<FITID>20261003002
<CHECKNUM>98102
<MEMO>STONE PAGAMENTOS NSU 98102
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261005120000[-3:BRT]
<TRNAMT>96.50
<FITID>20261005003
<CHECKNUM>98103
<MEMO>CIELO REPASSE NSU 98103
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261006120000[-3:BRT]
<TRNAMT>948.00
<FITID>20261006004
<CHECKNUM>98104
<MEMO>STONE PAGAMENTOS NSU 98104
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261008120000[-3:BRT]
<TRNAMT>289.50
<FITID>20261008005
<CHECKNUM>98105
<MEMO>REDE LIQUIDACAO NSU 98105
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261010120000[-3:BRT]
<TRNAMT>579.00
<FITID>20261010006
<CHECKNUM>98106
<MEMO>STONE PAGAMENTOS NSU 98106
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261012120000[-3:BRT]
<TRNAMT>723.75
<FITID>20261012007
<CHECKNUM>98107
<MEMO>IFOOD REPASSE NSU 98107
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20261014120000[-3:BRT]
<TRNAMT>150.00
<FITID>20261014008
<MEMO>PIX RECEBIDO QR CODE BALCAO
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>3414.00
<DTASOF>20261015180000[-3:BRT]
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

    with open(ofx_path, 'w', encoding='utf-8') as f:
        f.write(ofx_content.strip())

    # Dados da Planilha de Vendas do PDV / ERP
    sales_data = [
        # 1. Conciliada 3.50% (Bruto 200,00 -> Líq 193,00)
        {"ID_Venda_NSU": "98101", "Data_Venda": "02/10/2026", "Valor_Bruto": 200.00, "Adquirente": "Stone Crédito", "Cliente": "Mariana Souza"},
        # 2. Conciliada 3.50% (Bruto 450,00 -> Líq 434,25)
        {"ID_Venda_NSU": "98102", "Data_Venda": "03/10/2026", "Valor_Bruto": 450.00, "Adquirente": "Stone Débito", "Cliente": "Carlos Alberto"},
        # 3. Conciliada 3.50% (Bruto 100,00 -> Líq 96,50)
        {"ID_Venda_NSU": "98103", "Data_Venda": "05/10/2026", "Valor_Bruto": 100.00, "Adquirente": "Cielo", "Cliente": "Luciana Ribeiro"},
        # 4. TAXA DIVERGENTE COBRADA A MAIOR:
        # Bruto 1.000,00 -> Esperado Líquido 965,00 (Taxa 3.50%). A Stone creditou 948,00 (Taxa 5.20% cobrada a maior! Prejuízo de R$ 17,00)
        {"ID_Venda_NSU": "98104", "Data_Venda": "06/10/2026", "Valor_Bruto": 1000.00, "Adquirente": "Stone Crédito", "Cliente": "Roberto Dias"},
        # 5. Conciliada 3.50% (Bruto 300,00 -> Líq 289,50)
        {"ID_Venda_NSU": "98105", "Data_Venda": "08/10/2026", "Valor_Bruto": 300.00, "Adquirente": "Rede", "Cliente": "Fernanda Lima"},
        # 6. Conciliada 3.50% (Bruto 600,00 -> Líq 579,00)
        {"ID_Venda_NSU": "98106", "Data_Venda": "10/10/2026", "Valor_Bruto": 600.00, "Adquirente": "Stone Crédito", "Cliente": "Marcos Paulo"},
        # 7. Conciliada 3.50% (Bruto 750,00 -> Líq 723,75)
        {"ID_Venda_NSU": "98107", "Data_Venda": "12/10/2026", "Valor_Bruto": 750.00, "Adquirente": "iFood", "Cliente": "Patricia Santos"},
        # 8. VENDA NÃO REPASSADA / PENDENTE:
        # Venda de R$ 420,00 no dia 13/10 que a adquirente esqueceu de creditar no banco!
        {"ID_Venda_NSU": "98108", "Data_Venda": "13/10/2026", "Valor_Bruto": 420.00, "Adquirente": "Stone Crédito", "Cliente": "Bruno Silveira"}
    ]

    df = pd.DataFrame(sales_data)
    df.to_excel(excel_path, index=False)

    return ofx_path, os.path.basename(ofx_path), excel_path, os.path.basename(excel_path)
