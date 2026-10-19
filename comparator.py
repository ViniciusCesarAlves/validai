import os
import re
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime, date
import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage

def normalize_column_name(col: str) -> str:
    """Normaliza nome de coluna: sem acentos, sem espaços extras, uppercase e substitui caracteres especiais por _."""
    if not isinstance(col, str):
        col = str(col)
    col = col.replace('\ufeff', '').strip().upper()
    col = unicodedata.normalize('NFKD', col).encode('ASCII', 'ignore').decode('utf-8')
    col = re.sub(r'[\s\-_/\\|]+', '_', col)
    return col.strip('_')

def read_tabular_file(file_path_or_buffer, filename: str) -> pd.DataFrame:
    """Lê arquivo Excel (.xlsx, .xls) ou CSV (.csv) com detecção automática de separador e codificação."""
    ext = filename.lower().split('.')[-1]
    if ext in ['xlsx', 'xls', 'xlsm']:
        # Lê com openpyxl ou padrão
        df = pd.read_excel(file_path_or_buffer)
    elif ext == 'csv':
        # Tenta detectar separador (; ou ,) e encoding (utf-8-sig primeiro para tratar BOM)
        encodings = ['utf-8-sig', 'utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        df = None
        for enc in encodings:
            try:
                if hasattr(file_path_or_buffer, 'seek'):
                    file_path_or_buffer.seek(0)
                # Lê primeira linha para checar delimitador
                sample = file_path_or_buffer.read(4096)
                if isinstance(sample, bytes):
                    sample_text = sample.decode(enc, errors='ignore')
                else:
                    sample_text = str(sample)
                
                delimiter = ';' if sample_text.count(';') > sample_text.count(',') else ','
                if hasattr(file_path_or_buffer, 'seek'):
                    file_path_or_buffer.seek(0)
                
                df = pd.read_csv(file_path_or_buffer, sep=delimiter, encoding=enc)
                break
            except Exception:
                continue
        # Fallback padrão
        if df is None:
            if hasattr(file_path_or_buffer, 'seek'):
                file_path_or_buffer.seek(0)
            df = pd.read_csv(file_path_or_buffer, sep=None, engine='python')
    else:
        raise ValueError(f"Formato de arquivo não suportado: {ext}. Use .xlsx ou .csv")

    # Remove BOM (\ufeff) e espaços das pontas de todos os nomes de colunas
    df.columns = [str(c).replace('\ufeff', '').strip() for c in df.columns]
    return df

def parse_cell_value(val, normalize_currency=True, normalize_dates=True, ignore_case=True, trim_spaces=True):
    """
    Normaliza valores celulares para permitir comparações inteligentes:
    - Trata nulos/vazios
    - Trata moedas brasileiras e números com ponto/vírgula
    - Trata datas e timestamps
    - Trata textos com espaços extras e maiúsculas
    """
    if val is None or pd.isna(val):
        return None

    # Se for Timestamp ou datetime
    if isinstance(val, (datetime, date, pd.Timestamp)):
        if normalize_dates:
            return val.strftime('%Y-%m-%d')
        return str(val)

    s = str(val).replace('\ufeff', '')
    if trim_spaces:
        s = s.strip()

    if s == '' or s.lower() in ('nan', 'none', 'null', '<na>'):
        return None

    # Tenta conversão para Data se tiver formato de data
    if normalize_dates:
        # Padrões comuns: YYYY-MM-DD ou DD/MM/YYYY ou YYYY-MM-DD HH:MM:SS
        date_match = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+00:00(?::00)?)?$', s)
        if date_match:
            y, m, d = date_match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        
        br_date_match = re.match(r'^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})(?:\s+00:00(?::00)?)?$', s)
        if br_date_match:
            d, m, y = br_date_match.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    # Tenta conversão para Número / Moeda
    if normalize_currency:
        clean_num = s.replace('R$', '').replace('$', '').replace('€', '').strip()
        # Remove espaços internos comuns em moeda (ex: R$ 1 000,00)
        clean_num = clean_num.replace(' ', '')
        # Checa se parece com número brasileiro ex: "1.234,56" ou "2580,00" ou "-150,00"
        if re.match(r'^-?\d{1,3}(?:\.\d{3})*,\d+$', clean_num):
            try:
                return round(float(clean_num.replace('.', '').replace(',', '.')), 4)
            except ValueError:
                pass
        # Checa se parece com número decimal com vírgula simples ex: "2580,00" ou "0,5"
        elif re.match(r'^-?\d+,\d+$', clean_num):
            try:
                return round(float(clean_num.replace(',', '.')), 4)
            except ValueError:
                pass
        # Checa se é número float/int internacional padrão ex: "2580.00" ou "2580"
        elif re.match(r'^-?\d+(?:\.\d+)?$', clean_num):
            try:
                return round(float(clean_num), 4)
            except ValueError:
                pass

    if ignore_case:
        s = s.upper()

    return s

def suggest_column_mappings(cols_a, cols_b):
    """
    Mapeia colunas da Base A para a Base B baseado em:
    1. Correspondência exata
    2. Correspondência normalizada (sem acentos/espaços)
    3. Correspondência difflib (similaridade de texto >= 0.75)
    """
    norm_a = {normalize_column_name(c): c for c in cols_a}
    norm_b = {normalize_column_name(c): c for c in cols_b}

    mappings = {}
    used_b = set()

    # 1. Correspondência exata de normalização
    for na, orig_a in norm_a.items():
        if na in norm_b:
            orig_b = norm_b[na]
            mappings[orig_a] = orig_b
            used_b.add(orig_b)

    # 2. Correspondência por similaridade difflib para colunas restantes
    unmapped_a = [c for c in cols_a if c not in mappings]
    remaining_b = [c for c in cols_b if c not in used_b]

    for orig_a in unmapped_a:
        na = normalize_column_name(orig_a)
        best_match = None
        best_ratio = 0.0
        for orig_b in remaining_b:
            nb = normalize_column_name(orig_b)
            ratio = SequenceMatcher(None, na, nb).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = orig_b
        
        if best_match and best_ratio >= 0.75:
            mappings[orig_a] = best_match
            used_b.add(best_match)
            remaining_b.remove(best_match)

    return mappings

def parse_financial_value(val):
    """Converte valor para float tratando moeda brasileira, formatos internacionais e nulos."""
    if pd.isna(val) or val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return 0.0
    clean_num = s.replace('R$', '').replace('$', '').replace('€', '').replace(' ', '')
    try:
        if re.match(r'^-?\d{1,3}(?:\.\d{3})*,\d+$', clean_num):
            return float(clean_num.replace('.', '').replace(',', '.'))
        elif re.match(r'^-?\d+,\d+$', clean_num):
            return float(clean_num.replace(',', '.'))
        elif re.match(r'^-?\d+(?:\.\d+)?$', clean_num):
            return float(clean_num)
    except Exception:
        pass
    return None

def is_monetary_column(col_a: str, col_b: str, series_a: pd.Series, series_b: pd.Series) -> bool:
    """Verifica se o par de colunas possui natureza financeira/monetária."""
    name_a = str(col_a).upper().strip()
    name_b = str(col_b).upper().strip()

    exclude_keywords = [
        'ID', 'COD', 'CODIGO', 'CÓDIGO', 'CPF', 'CNPJ', 'MATRICULA', 'MATRÍCULA', 
        'TICKET', 'SEQ', 'NDF', 'CEP', 'TEL', 'TELEFONE', 'DDD', 'DATA', 'DT_', 
        'HORA', 'REGISTRO', 'ANO', 'MES', 'MÊS', 'DIA', 'VENDEDOR', 'CLIENTE',
        'CARGO', 'FILIAL', 'TIPO', 'NUMERO', 'NÚMERO', 'STATUS', 'SITUACAO', 'DESC_CARGO'
    ]
    for ex in exclude_keywords:
        for n in [name_a, name_b]:
            if n == ex or n.startswith(ex + '_') or n.endswith('_' + ex) or f'_{ex}_' in n:
                if not any(k in n for k in ['VALOR', 'VLR', 'TOTAL', 'SALDO']):
                    return False

    monetary_keywords = [
        'VALOR', 'VLR', 'PRECO', 'PREÇO', 'TOTAL', 'COMISSAO', 'COMISSÃO', 'DESCONTO', 
        'DESC_VALOR', 'FRETE', 'CUSTO', 'SALDO', 'IMPOSTO', 'LIQUIDO', 'LÍQUIDO', 
        'BRUTO', 'BRUTA', 'RECEITA', 'TAXA', 'FATURAMENTO', 'PAGAMENTO', 'PARCELA', 
        'PROVENTO', 'SALARIO', 'SALÁRIO', 'REMUNERACAO', 'REMUNERAÇÃO', 'BENEFICIO', 
        'BENEFÍCIO', 'BONUS', 'BÔNUS', 'PREMIO', 'PRÊMIO', 'BASE_COMISSAO', 'BASE', 
        'ICMS', 'PIS', 'COFINS', 'IPI', 'ISS', 'JUROS', 'MULTA', 'DEBITO', 'DÉBITO', 
        'CREDITO', 'CRÉDITO'
    ]
    has_keyword = any(mk in name_a or mk in name_b for mk in monetary_keywords)
    
    sample_a = series_a.dropna().head(30)
    sample_b = series_b.dropna().head(30)
    has_symbol = any('R$' in str(v) or '$' in str(v) or '€' in str(v) for v in list(sample_a) + list(sample_b))
    if has_symbol:
        return True

    if has_keyword:
        parsed_count = 0
        total_sample = len(sample_a) + len(sample_b)
        if total_sample == 0:
            return True
        for v in list(sample_a) + list(sample_b):
            if parse_financial_value(v) is not None:
                parsed_count += 1
        if parsed_count / total_sample >= 0.5:
            return True

    decimal_count = 0
    total_valid = 0
    for v in list(sample_a) + list(sample_b):
        pv = parse_financial_value(v)
        if pv is not None:
            total_valid += 1
            if not pv.is_integer():
                decimal_count += 1
    if total_valid >= 5 and decimal_count / total_valid >= 0.3:
        return True

    return False

def compute_financial_summary(df_a: pd.DataFrame, df_b: pd.DataFrame, column_mapping: dict, columns_with_differences: dict = None) -> dict:
    """Calcula a sumarização das colunas com valores monetários e as diferenças dos pares."""
    if columns_with_differences is None:
        columns_with_differences = {}

    financial_pairs = []
    for col_a, col_b in column_mapping.items():
        if col_a.startswith('_') or col_b.startswith('_'):
            continue
        if col_a not in df_a.columns or col_b not in df_b.columns:
            continue
        if is_monetary_column(col_a, col_b, df_a[col_a], df_b[col_b]):
            financial_pairs.append((col_a, col_b))

    if not financial_pairs:
        return None

    rows = []
    total_a_overall = 0.0
    total_b_overall = 0.0

    for col_a, col_b in financial_pairs:
        vals_a = [parse_financial_value(v) for v in df_a[col_a]]
        vals_b = [parse_financial_value(v) for v in df_b[col_b]]

        sum_a = sum(v for v in vals_a if v is not None)
        sum_b = sum(v for v in vals_b if v is not None)
        diff = sum_b - sum_a
        abs_diff = abs(diff)

        pct_diff = 0.0
        if sum_a != 0:
            pct_diff = (diff / abs(sum_a)) * 100.0

        diff_count = columns_with_differences.get(col_a, 0)
        status = "OK" if abs_diff < 0.01 else "Divergente"

        rows.append({
            'col_a': col_a,
            'col_b': col_b,
            'sum_a': round(sum_a, 2),
            'sum_b': round(sum_b, 2),
            'diff': round(diff, 2),
            'abs_diff': round(abs_diff, 2),
            'pct_diff': round(pct_diff, 2),
            'diff_count': diff_count,
            'status': status
        })
        total_a_overall += sum_a
        total_b_overall += sum_b

    diff_overall = total_b_overall - total_a_overall
    pct_overall = ((diff_overall / abs(total_a_overall)) * 100.0) if total_a_overall != 0 else 0.0

    return {
        'items': rows,
        'total_sum_a': round(total_a_overall, 2),
        'total_sum_b': round(total_b_overall, 2),
        'total_diff': round(diff_overall, 2),
        'total_abs_diff': round(abs(diff_overall), 2),
        'total_pct_diff': round(pct_overall, 2),
        'total_pairs_count': len(rows),
        'divergent_pairs_count': sum(1 for r in rows if r['status'] == 'Divergente')
    }

def compare_datasets(df_a: pd.DataFrame, df_b: pd.DataFrame, 
                     primary_key_a: str, primary_key_b: str,
                     secondary_keys_a: list = None, secondary_keys_b: list = None,
                     secondary_key_a: str = None, secondary_key_b: str = None,
                     column_mapping: dict = None,
                     normalize_currency: bool = True,
                     normalize_dates: bool = True,
                     ignore_case: bool = True,
                     trim_spaces: bool = True,
                     max_sample_rows: int = 500):
    """
    Executa a comparação completa entre os dois DataFrames.
    Suporta uma chave primária (esquerda) e uma ou mais colunas complementares (direita).
    Retorna estatísticas detalhadas, lista de discrepâncias e dados para renderização.
    """
    # Mapeamento padrão se não informado
    if column_mapping is None:
        column_mapping = suggest_column_mappings(df_a.columns, df_b.columns)

    # Verifica se a chave primária existe
    if primary_key_a not in df_a.columns or primary_key_b not in df_b.columns:
        raise ValueError(f"Chave primária '{primary_key_a}' ou '{primary_key_b}' não encontrada nos arquivos.")

    # Processar múltiplas colunas secundárias/complementares
    sec_keys_a = []
    if secondary_keys_a:
        if isinstance(secondary_keys_a, list):
            sec_keys_a = [k for k in secondary_keys_a if k and k in df_a.columns]
        elif isinstance(secondary_keys_a, str):
            sec_keys_a = [secondary_keys_a] if secondary_keys_a in df_a.columns else []
    elif secondary_key_a and secondary_key_a in df_a.columns:
        sec_keys_a = [secondary_key_a]

    sec_keys_b = []
    if secondary_keys_b and isinstance(secondary_keys_b, list):
        sec_keys_b = [k for k in secondary_keys_b if k and k in df_b.columns]
    else:
        sec_keys_b = [column_mapping.get(k, k) for k in sec_keys_a if column_mapping.get(k, k) in df_b.columns]

    has_secondary = len(sec_keys_a) > 0

    # Criar coluna de chave composta normalizada para junção
    def build_key_series(df, pk, sec_keys=None):
        s = df[pk].apply(lambda v: str(parse_cell_value(v, normalize_currency=True, normalize_dates=True, ignore_case=True, trim_spaces=True) or ''))
        if sec_keys:
            for sk in sec_keys:
                if sk in df.columns:
                    s_next = df[sk].apply(lambda v: str(parse_cell_value(v, normalize_currency=True, normalize_dates=True, ignore_case=True, trim_spaces=True) or ''))
                    s = s + " __ " + s_next
        return s

    df_a = df_a.copy()
    df_b = df_b.copy()

    # Guarda o número original da linha na planilha (cabeçalho = 1, dados iniciam na linha 2 do Excel)
    df_a['_ORIG_ROW_NUM_'] = list(range(2, len(df_a) + 2))
    df_b['_ORIG_ROW_NUM_'] = list(range(2, len(df_b) + 2))

    df_a['_JOIN_KEY_'] = build_key_series(df_a, primary_key_a, sec_keys_a if has_secondary else None)
    df_b['_JOIN_KEY_'] = build_key_series(df_b, primary_key_b, sec_keys_b if has_secondary else None)

    # Identificar chaves duplicadas se houver
    dups_a = int(df_a.duplicated(subset=['_JOIN_KEY_']).sum())
    dups_b = int(df_b.duplicated(subset=['_JOIN_KEY_']).sum())

    # Agrupar / indexar por chave (mantém a primeira ocorrência se houver duplicatas)
    df_a_indexed = df_a.drop_duplicates(subset=['_JOIN_KEY_']).set_index('_JOIN_KEY_')
    df_b_indexed = df_b.drop_duplicates(subset=['_JOIN_KEY_']).set_index('_JOIN_KEY_')

    keys_a = set(df_a_indexed.index)
    keys_b = set(df_b_indexed.index)

    common_keys = keys_a & keys_b
    only_in_a = keys_a - keys_b
    only_in_b = keys_b - keys_a

    # Colunas a serem comparadas (apenas aquelas mapeadas e que existem em ambos)
    valid_cols_a = [col_a for col_a, col_b in column_mapping.items() if col_a in df_a.columns and col_b in df_b.columns]

    total_cells_checked = 0
    total_cells_diff = 0
    diff_records = []
    col_diff_counts = {col_a: 0 for col_a in valid_cols_a}

    # Ordena common_keys para consistência
    sorted_common_keys = sorted(list(common_keys))

    # Comparar células das chaves comuns
    for key in sorted_common_keys:
        row_a = df_a_indexed.loc[key]
        row_b = df_b_indexed.loc[key]
        
        row_has_diff = False
        cell_diffs = {}

        for col_a in valid_cols_a:
            col_b = column_mapping[col_a]
            raw_a = row_a[col_a]
            raw_b = row_b[col_b]

            norm_a = parse_cell_value(raw_a, normalize_currency, normalize_dates, ignore_case, trim_spaces)
            norm_b = parse_cell_value(raw_b, normalize_currency, normalize_dates, ignore_case, trim_spaces)

            total_cells_checked += 1

            # Checar igualdade
            is_equal = (norm_a == norm_b)

            if not is_equal:
                total_cells_diff += 1
                row_has_diff = True
                col_diff_counts[col_a] += 1
                cell_diffs[col_a] = {
                    'col_a': col_a,
                    'col_b': col_b,
                    'val_a_raw': str(raw_a) if not pd.isna(raw_a) else "",
                    'val_b_raw': str(raw_b) if not pd.isna(raw_b) else "",
                    'val_a_norm': str(norm_a) if norm_a is not None else "(Vazio)",
                    'val_b_norm': str(norm_b) if norm_b is not None else "(Vazio)"
                }

        if row_has_diff:
            # Captura a linha com informações de exibição
            display_id = str(row_a[primary_key_a])
            if has_secondary:
                display_sec = " | ".join([f"{col}: {row_a[col]}" for col in sec_keys_a if col in row_a])
            else:
                display_sec = None

            row_num_a = int(row_a['_ORIG_ROW_NUM_']) if '_ORIG_ROW_NUM_' in row_a else None
            row_num_b = int(row_b['_ORIG_ROW_NUM_']) if '_ORIG_ROW_NUM_' in row_b else None

            if row_num_a is not None and row_num_b is not None:
                if row_num_a == row_num_b:
                    line_display = row_num_a
                else:
                    line_display = f"Antiga: {row_num_a} | Nova: {row_num_b}"
            elif row_num_a is not None:
                line_display = row_num_a
            elif row_num_b is not None:
                line_display = row_num_b
            else:
                line_display = "-"

            # Constrói registro para exibição na UI
            diff_records.append({
                'join_key': key,
                'primary_key_val': display_id,
                'secondary_key_val': display_sec,
                'row_num_a': row_num_a,
                'row_num_b': row_num_b,
                'line_display': line_display,
                'diff_count': len(cell_diffs),
                'cell_diffs': cell_diffs,
                # Amostra dos valores da linha para contexto
                'row_a_preview': {c: (str(row_a[c]) if not pd.isna(row_a[c]) else "") for c in valid_cols_a[:10]},
                'row_b_preview': {c: (str(row_b[column_mapping[c]]) if not pd.isna(row_b[column_mapping[c]]) else "") for c in valid_cols_a[:10]}
            })

    # Resumo
    columns_with_differences = {col: count for col, count in col_diff_counts.items() if count > 0}
    is_identical = (len(diff_records) == 0 and len(only_in_a) == 0 and len(only_in_b) == 0)

    # Sumarização Financeira dos Pares Monetários
    financial_summary = compute_financial_summary(df_a, df_b, column_mapping, columns_with_differences)

    # Amostra de registros exclusivos para exibição na UI
    cols_display_a = [c for c in df_a.columns if not c.startswith('_')]
    sample_only_in_a = []
    for key in sorted(list(only_in_a))[:max_sample_rows]:
        row_a = df_a_indexed.loc[key]
        line_a = int(row_a['_ORIG_ROW_NUM_']) if '_ORIG_ROW_NUM_' in row_a else None
        sample_only_in_a.append({
            'key': str(key),
            'line': line_a,
            'values': {c: (str(row_a[c]) if not pd.isna(row_a[c]) else "") for c in cols_display_a}
        })

    cols_display_b = [c for c in df_b.columns if not c.startswith('_')]
    sample_only_in_b = []
    for key in sorted(list(only_in_b))[:max_sample_rows]:
        row_b = df_b_indexed.loc[key]
        line_b = int(row_b['_ORIG_ROW_NUM_']) if '_ORIG_ROW_NUM_' in row_b else None
        sample_only_in_b.append({
            'key': str(key),
            'line': line_b,
            'values': {c: (str(row_b[c]) if not pd.isna(row_b[c]) else "") for c in cols_display_b}
        })

    summary = {
        'is_identical': is_identical,
        'total_rows_a': len(df_a),
        'total_rows_b': len(df_b),
        'matched_keys_count': len(common_keys),
        'different_rows_count': len(diff_records),
        'identical_rows_count': len(common_keys) - len(diff_records),
        'only_in_a_count': len(only_in_a),
        'only_in_b_count': len(only_in_b),
        'sample_only_in_a': sample_only_in_a,
        'sample_only_in_b': sample_only_in_b,
        'cols_display_a': cols_display_a,
        'cols_display_b': cols_display_b,
        'total_columns_compared': len(valid_cols_a),
        'columns_with_differences_count': len(columns_with_differences),
        'columns_with_differences': columns_with_differences,
        'financial_summary': financial_summary,
        'total_cells_checked': total_cells_checked,
        'total_cells_diff': total_cells_diff,
        'dups_a': dups_a,
        'dups_b': dups_b,
        'primary_key_a': primary_key_a,
        'primary_key_b': primary_key_b,
        'secondary_keys_a': sec_keys_a,
        'secondary_keys_b': sec_keys_b,
        'secondary_key_a': ", ".join(sec_keys_a) if sec_keys_a else None,
        'secondary_key_b': ", ".join(sec_keys_b) if sec_keys_b else None,
        'sample_diff_records': diff_records[:max_sample_rows],
        'total_diff_records': len(diff_records)
    }

    return summary, diff_records, df_a_indexed, df_b_indexed, valid_cols_a, column_mapping, only_in_a, only_in_b

def generate_excel_diff_report(summary: dict, diff_records: list, 
                               df_a_indexed: pd.DataFrame, df_b_indexed: pd.DataFrame, 
                               valid_cols_a: list, column_mapping: dict,
                               only_in_a: set, only_in_b: set,
                               output_path: str):
    """
    Gera um relatório Excel (.xlsx) altamente profissional e visual usando openpyxl.
    - As células divergentes são pintadas com cor de destaque (vermelho suave).
    - Inclui aba de Resumo Executivo com KPIs.
    - Inclui aba com visão comparativa das divergências.
    - Inclui abas para registros exclusivos de cada base.
    """
    wb = Workbook()
    
    # -----------------------------
    # 1. ABA DE RESUMO
    # -----------------------------
    ws_summary = wb.active
    ws_summary.title = "Resumo da Validação"
    ws_summary.views.sheetView[0].showGridLines = True

    # Cores e Estilos alinhados à marca SplitC
    color_primary = "4FD580"    # Verde oficial SplitC (#4FD580)
    color_col_header = "4FD580" # Verde oficial SplitC para títulos das colunas (#4FD580)
    color_diff_fill = "FEE2E2"  # Vermelho suave para diferenças
    color_diff_font = "991B1B"  # Vermelho escuro
    color_success_fill = "DCFCE7" # Verde suave
    color_success_font = "166534"
    
    font_title = Font(name="Calibri", size=15, bold=True, color="FFFFFF")
    font_col_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_normal = Font(name="Calibri", size=11)
    
    fill_title = PatternFill(start_color=color_col_header, end_color=color_col_header, fill_type="solid")
    fill_col_header = PatternFill(start_color=color_col_header, end_color=color_col_header, fill_type="solid")
    fill_diff = PatternFill(start_color=color_diff_fill, end_color=color_diff_fill, fill_type="solid")
    fill_success = PatternFill(start_color=color_success_fill, end_color=color_success_fill, fill_type="solid")
    
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Banner do Título (A1:C2) na cor laranja oficial (#F87F06)
    ws_summary.merge_cells("A1:C2")
    title_cell = ws_summary["A1"]
    title_cell.value = "  ValidAí - RELATÓRIO DE VALIDAÇÃO DE DADOS"
    title_cell.font = font_title
    title_cell.fill = fill_title
    title_cell.alignment = Alignment(vertical="center", horizontal="left")
    ws_summary.row_dimensions[1].height = 24
    ws_summary.row_dimensions[2].height = 24

    # Espaçamento entre a header e a logo (Coluna D como espaçador, Logo na E1)
    ws_summary.column_dimensions['C'].width = 8
    ws_summary.column_dimensions['D'].width = 4
    ws_summary.column_dimensions['E'].width = 28

    # Adiciona a logo SplitC lateralmente com espaçamento visual
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images', 'logo.png')
    if os.path.exists(logo_path):
        try:
            logo_img = OpenpyxlImage(logo_path)
            logo_img.width = 175
            logo_img.height = 52
            ws_summary.add_image(logo_img, "E1")
        except Exception:
            pass

    ws_summary["A4"] = "STATUS GERAL:"
    ws_summary["A4"].font = font_bold
    ws_summary["B4"] = "BASES 100% IDÊNTICAS!" if summary['is_identical'] else "DIVERGÊNCIAS DETECTADAS"
    ws_summary["B4"].font = Font(name="Calibri", size=12, bold=True, color=color_success_font if summary['is_identical'] else color_diff_font)
    ws_summary["B4"].fill = fill_success if summary['is_identical'] else fill_diff

    # Tabela de Métricas
    metrics = [
        ("Data da Validação", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        ("Chave Primária de Comparação", f"{summary['primary_key_a']} ↔ {summary['primary_key_b']}"),
        ("Colunas Complementares (Refinamento)", f"{summary['secondary_key_a']} ↔ {summary['secondary_key_b']}" if summary.get('secondary_key_a') else "Não utilizada"),
        ("Total de Linhas na Base Antiga", summary['total_rows_a']),
        ("Total de Linhas na Base Nova", summary['total_rows_b']),
        ("Chaves Correspondentes Encontradas", summary['matched_keys_count']),
        ("Linhas com Dados Idênticos", summary['identical_rows_count']),
        ("Linhas com Divergências nas Células", summary['different_rows_count']),
        ("Total de Células com Valores Diferentes", summary['total_cells_diff']),
        ("Registros Apenas na Base Antiga", summary['only_in_a_count']),
        ("Registros Apenas na Base Nova", summary['only_in_b_count']),
        ("Total de Colunas Comparadas", summary['total_columns_compared']),
    ]

    row_idx = 6
    c_m = ws_summary.cell(row=row_idx, column=1, value="MÉTRICA")
    c_v = ws_summary.cell(row=row_idx, column=2, value="VALOR")
    c_m.font = font_col_header
    c_m.fill = fill_col_header
    c_v.font = font_col_header
    c_v.fill = fill_col_header
    c_m.border = border_thin
    c_v.border = border_thin
    
    for label, val in metrics:
        row_idx += 1
        c1 = ws_summary.cell(row=row_idx, column=1, value=label)
        c2 = ws_summary.cell(row=row_idx, column=2, value=val)
        c1.font = font_normal
        c2.font = font_bold if isinstance(val, (int, float)) and val > 0 and 'Divergências' in label else font_normal
        c1.border = border_thin
        c2.border = border_thin

    # Tabela de Colunas com Divergências
    if summary['columns_with_differences']:
        row_idx += 3
        c_cd = ws_summary.cell(row=row_idx, column=1, value="COLUNA DIVERGENTE")
        c_qd = ws_summary.cell(row=row_idx, column=2, value="QTD. LINHAS DIVERGENTES")
        c_cd.font = font_col_header
        c_cd.fill = fill_col_header
        c_qd.font = font_col_header
        c_qd.fill = fill_col_header
        c_cd.border = border_thin
        c_qd.border = border_thin

        for col_name, count in sorted(summary['columns_with_differences'].items(), key=lambda x: x[1], reverse=True):
            row_idx += 1
            c1 = ws_summary.cell(row=row_idx, column=1, value=col_name)
            c2 = ws_summary.cell(row=row_idx, column=2, value=count)
            c1.font = font_normal
            c2.font = font_bold
            c1.border = border_thin
            c2.border = border_thin

    # Ajuste de larguras de colunas
    ws_summary.column_dimensions['A'].width = 38
    ws_summary.column_dimensions['B'].width = 32

    # -----------------------------
    # 2. ABA DE DIVERGÊNCIAS (CÉLULAS PINTADAS)
    # -----------------------------
    if diff_records:
        ws_diff = wb.create_sheet(title="Divergências Detalhadas")
        ws_diff.views.sheetView[0].showGridLines = True

        # Cabeçalhos: Chave, Linha, Coluna, Valor Base Antiga, Valor Base Nova
        headers = ["Chave Identificadora", "Linha", "Coluna", "Valor Base Antiga", "Valor Base Nova"]
        for col_num, h in enumerate(headers, 1):
            cell = ws_diff.cell(row=1, column=col_num, value=h)
            cell.font = font_col_header
            cell.fill = fill_col_header
            cell.alignment = Alignment(horizontal="center")

        diff_row_idx = 2
        max_excel_diff_rows = 25000
        truncated = False

        for rec in diff_records:
            if diff_row_idx > max_excel_diff_rows:
                truncated = True
                break

            key_val = rec['primary_key_val']
            if rec.get('secondary_key_val'):
                key_val += f" (Data/Ref: {rec['secondary_key_val']})"

            line_val = rec.get('line_display', rec.get('row_num_a', '-'))

            for col_a, c_diff in rec['cell_diffs'].items():
                if diff_row_idx > max_excel_diff_rows:
                    truncated = True
                    break

                c_key = ws_diff.cell(row=diff_row_idx, column=1, value=key_val)
                c_line = ws_diff.cell(row=diff_row_idx, column=2, value=line_val)
                c_col = ws_diff.cell(row=diff_row_idx, column=3, value=col_a)
                c_va = ws_diff.cell(row=diff_row_idx, column=4, value=c_diff['val_a_raw'])
                c_vb = ws_diff.cell(row=diff_row_idx, column=5, value=c_diff['val_b_raw'])

                # Formatação da coluna Linha
                c_line.font = font_normal
                c_line.alignment = Alignment(horizontal="center")

                # Pinta as células divergentes em vermelho claro
                c_va.fill = fill_diff
                c_vb.fill = fill_diff
                c_va.font = Font(name="Calibri", color=color_diff_font)
                c_vb.font = Font(name="Calibri", color=color_diff_font, bold=True)

                for c in [c_key, c_line, c_col, c_va, c_vb]:
                    c.border = border_thin

                diff_row_idx += 1

        if truncated:
            ws_diff.cell(row=diff_row_idx, column=1, value=f"* Exibindo as primeiras {max_excel_diff_rows} células divergentes para manter a performance do arquivo Excel.").font = Font(name="Calibri", italic=True, color="64748B")

        ws_diff.column_dimensions['A'].width = 38
        ws_diff.column_dimensions['B'].width = 16
        ws_diff.column_dimensions['C'].width = 30
        ws_diff.column_dimensions['D'].width = 30
        ws_diff.column_dimensions['E'].width = 30
        ws_diff.freeze_panes = "A2"

    # -----------------------------
    # 3. ABA DE SUMARIZAÇÃO FINANCEIRA (SE HOUVER DIVERGÊNCIAS)
    # -----------------------------
    financial_summary = summary.get('financial_summary')
    if (not summary['is_identical']) and financial_summary and financial_summary.get('items'):
        ws_fin = wb.create_sheet(title="Sumarização Financeira")
        ws_fin.views.sheetView[0].showGridLines = True

        fin_headers = [
            "Coluna Base Antiga",
            "Coluna Base Nova",
            "Total Base Antiga (R$)",
            "Total Base Nova (R$)",
            "Diferença (Nova - Antiga)",
            "% Variação",
            "Situação",
            "Qtd. Linhas Divergentes"
        ]

        for col_num, h in enumerate(fin_headers, 1):
            c = ws_fin.cell(row=1, column=col_num, value=h)
            c.font = font_col_header
            c.fill = fill_col_header
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = border_thin

        ws_fin.row_dimensions[1].height = 26

        curr_row = 2
        for item in financial_summary['items']:
            c_ca = ws_fin.cell(row=curr_row, column=1, value=item['col_a'])
            c_cb = ws_fin.cell(row=curr_row, column=2, value=item['col_b'])
            c_sa = ws_fin.cell(row=curr_row, column=3, value=item['sum_a'])
            c_sb = ws_fin.cell(row=curr_row, column=4, value=item['sum_b'])
            c_df = ws_fin.cell(row=curr_row, column=5, value=item['diff'])
            c_pct = ws_fin.cell(row=curr_row, column=6, value=f"{item['pct_diff']:+.2f}%" if item['pct_diff'] != 0 else "0.00%")
            c_st = ws_fin.cell(row=curr_row, column=7, value="OK / Conciliado" if item['status'] == 'OK' else "DIVERGENTE")
            c_cnt = ws_fin.cell(row=curr_row, column=8, value=item['diff_count'])

            for cell in [c_ca, c_cb, c_sa, c_sb, c_df, c_pct, c_st, c_cnt]:
                cell.font = font_normal
                cell.border = border_thin

            c_sa.number_format = '"R$" #,##0.00'
            c_sb.number_format = '"R$" #,##0.00'
            c_df.number_format = '"R$" #,##0.00'
            c_cnt.number_format = '#,##0'

            c_pct.alignment = Alignment(horizontal="center")
            c_st.alignment = Alignment(horizontal="center")
            c_cnt.alignment = Alignment(horizontal="center")

            if item['status'] == 'OK':
                c_st.fill = fill_success
                c_st.font = Font(name="Calibri", size=11, bold=True, color=color_success_font)
            else:
                c_st.fill = fill_diff
                c_st.font = Font(name="Calibri", size=11, bold=True, color=color_diff_font)
                c_df.font = Font(name="Calibri", size=11, bold=True, color=color_diff_font)

            curr_row += 1

        # Linha de Totais Gerais Consolidados
        c_tot_lbl = ws_fin.cell(row=curr_row, column=1, value="TOTAL GERAL DOS PARES MONETÁRIOS")
        ws_fin.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=2)
        c_tot_a = ws_fin.cell(row=curr_row, column=3, value=financial_summary['total_sum_a'])
        c_tot_b = ws_fin.cell(row=curr_row, column=4, value=financial_summary['total_sum_b'])
        c_tot_df = ws_fin.cell(row=curr_row, column=5, value=financial_summary['total_diff'])
        c_tot_pct = ws_fin.cell(row=curr_row, column=6, value=f"{financial_summary['total_pct_diff']:+.2f}%" if financial_summary['total_pct_diff'] != 0 else "0.00%")
        c_tot_st = ws_fin.cell(row=curr_row, column=7, value="OK / CONCILIADO" if financial_summary['divergent_pairs_count'] == 0 else f"{financial_summary['divergent_pairs_count']} PAR(ES) DIVERGENTE(S)")
        c_tot_cnt = ws_fin.cell(row=curr_row, column=8, value=sum(it['diff_count'] for it in financial_summary['items']))

        font_total = Font(name="Calibri", size=11, bold=True, color="1E293B")
        fill_total = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

        for c in [c_tot_lbl, ws_fin.cell(row=curr_row, column=2), c_tot_a, c_tot_b, c_tot_df, c_tot_pct, c_tot_st, c_tot_cnt]:
            c.font = font_total
            c.fill = fill_total
            c.border = border_thin

        c_tot_a.number_format = '"R$" #,##0.00'
        c_tot_b.number_format = '"R$" #,##0.00'
        c_tot_df.number_format = '"R$" #,##0.00'
        c_tot_pct.alignment = Alignment(horizontal="center")
        c_tot_st.alignment = Alignment(horizontal="center")
        c_tot_cnt.alignment = Alignment(horizontal="center")

        ws_fin.column_dimensions['A'].width = 32
        ws_fin.column_dimensions['B'].width = 32
        ws_fin.column_dimensions['C'].width = 24
        ws_fin.column_dimensions['D'].width = 24
        ws_fin.column_dimensions['E'].width = 26
        ws_fin.column_dimensions['F'].width = 16
        ws_fin.column_dimensions['G'].width = 20
        ws_fin.column_dimensions['H'].width = 22
        ws_fin.freeze_panes = "A2"

    # -----------------------------
    # 4. ABA: APENAS NA BASE ANTIGA
    # -----------------------------
    if only_in_a:
        ws_only_a = wb.create_sheet(title="Apenas na Base Antiga")
        ws_only_a.views.sheetView[0].showGridLines = True
        
        # Copia cabeçalhos da Base A (ignorando colunas internas de sistema)
        cols = [c for c in df_a_indexed.columns if not c.startswith('_')]
        for col_num, col_name in enumerate(cols, 1):
            cell = ws_only_a.cell(row=1, column=col_num, value=col_name)
            cell.font = font_col_header
            cell.fill = fill_col_header
            cell.border = border_thin

        for row_num, key in enumerate(sorted(list(only_in_a)), 2):
            row_data = df_a_indexed.loc[key]
            for col_num, col_name in enumerate(cols, 1):
                val = row_data[col_name]
                c = ws_only_a.cell(row=row_num, column=col_num, value=str(val) if not pd.isna(val) else "")
                c.font = font_normal
                c.border = border_thin

    # -----------------------------
    # 5. ABA: APENAS NA BASE NOVA
    # -----------------------------
    if only_in_b:
        ws_only_b = wb.create_sheet(title="Apenas na Base Nova")
        ws_only_b.views.sheetView[0].showGridLines = True
        
        cols = [c for c in df_b_indexed.columns if not c.startswith('_')]
        for col_num, col_name in enumerate(cols, 1):
            cell = ws_only_b.cell(row=1, column=col_num, value=col_name)
            cell.font = font_col_header
            cell.fill = fill_col_header
            cell.border = border_thin

        for row_num, key in enumerate(sorted(list(only_in_b)), 2):
            row_data = df_b_indexed.loc[key]
            for col_num, col_name in enumerate(cols, 1):
                val = row_data[col_name]
                c = ws_only_b.cell(row=row_num, column=col_num, value=str(val) if not pd.isna(val) else "")
                c.font = font_normal
                c.border = border_thin

    wb.save(output_path)
    return output_path


def create_demo_files(output_dir):
    """
    Cria dois arquivos Excel (.xlsx) com bases fictícias empresariais para demonstração
    do comparador de planilhas.
    Contém:
    - 11 registros de vendas/pedidos
    - Divergência de valores e descontos em PED-1004
    - Divergência de status de entrega em PED-1006
    - 1 pedido exclusivo da Base A (PED-1011 cancelado/removido na Base B)
    - 1 pedido exclusivo da Base B (PED-1012 novo faturamento inserido)
    """
    path_a = os.path.join(output_dir, "Base_Vendas_ERP_Anterior.xlsx")
    path_b = os.path.join(output_dir, "Base_Vendas_ERP_Atualizada.xlsx")

    data_a = [
        {"ID_Pedido": "PED-1001", "Data_Venda": "01/10/2026", "Cliente": "Tech Solutions Brasil Ltda", "Vendedor": "Ana Paula", "Valor_Bruto": 4500.00, "Desconto": 150.00, "Valor_Liquido": 4350.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1002", "Data_Venda": "02/10/2026", "Cliente": "Mercado & Varejo Express", "Vendedor": "Lucas Silva", "Valor_Bruto": 1850.50, "Desconto": 0.00, "Valor_Liquido": 1850.50, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1003", "Data_Venda": "03/10/2026", "Cliente": "Indústrias Alfa S/A", "Vendedor": "Mariana Souza", "Valor_Bruto": 9200.00, "Desconto": 300.00, "Valor_Liquido": 8900.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1004", "Data_Venda": "04/10/2026", "Cliente": "Distribuidora Nacional de Peças", "Vendedor": "Carlos Eduardo", "Valor_Bruto": 1540.00, "Desconto": 40.00, "Valor_Liquido": 1500.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1005", "Data_Venda": "05/10/2026", "Cliente": "Hospital Santa Clara", "Vendedor": "Ana Paula", "Valor_Bruto": 12800.00, "Desconto": 500.00, "Valor_Liquido": 12300.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1006", "Data_Venda": "06/10/2026", "Cliente": "Logística Global Express", "Vendedor": "Lucas Silva", "Valor_Bruto": 3200.00, "Desconto": 100.00, "Valor_Liquido": 3100.00, "Status_Entrega": "Pendente"},
        {"ID_Pedido": "PED-1007", "Data_Venda": "07/10/2026", "Cliente": "Padaria & Confeitaria Central", "Vendedor": "Mariana Souza", "Valor_Bruto": 890.00, "Desconto": 0.00, "Valor_Liquido": 890.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1008", "Data_Venda": "08/10/2026", "Cliente": "Escola Futuro Brilhante", "Vendedor": "Carlos Eduardo", "Valor_Bruto": 6400.00, "Desconto": 200.00, "Valor_Liquido": 6200.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1009", "Data_Venda": "09/10/2026", "Cliente": "Auto Peças Progresso", "Vendedor": "Ana Paula", "Valor_Bruto": 2750.00, "Desconto": 50.00, "Valor_Liquido": 2700.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1010", "Data_Venda": "10/10/2026", "Cliente": "Construtora Horizonte S/A", "Vendedor": "Lucas Silva", "Valor_Bruto": 15200.00, "Desconto": 800.00, "Valor_Liquido": 14400.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1011", "Data_Venda": "11/10/2026", "Cliente": "Farmácia Popular do Povo", "Vendedor": "Mariana Souza", "Valor_Bruto": 1150.00, "Desconto": 0.00, "Valor_Liquido": 1150.00, "Status_Entrega": "Cancelado"}
    ]

    data_b = [
        {"ID_Pedido": "PED-1001", "Data_Venda": "01/10/2026", "Cliente": "Tech Solutions Brasil Ltda", "Vendedor": "Ana Paula", "Valor_Bruto": 4500.00, "Desconto": 150.00, "Valor_Liquido": 4350.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1002", "Data_Venda": "02/10/2026", "Cliente": "Mercado & Varejo Express", "Vendedor": "Lucas Silva", "Valor_Bruto": 1850.50, "Desconto": 0.00, "Valor_Liquido": 1850.50, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1003", "Data_Venda": "03/10/2026", "Cliente": "Indústrias Alfa S/A", "Vendedor": "Mariana Souza", "Valor_Bruto": 9200.00, "Desconto": 300.00, "Valor_Liquido": 8900.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1004", "Data_Venda": "04/10/2026", "Cliente": "Distribuidora Nacional de Peças", "Vendedor": "Carlos Eduardo", "Valor_Bruto": 1540.00, "Desconto": 120.00, "Valor_Liquido": 1420.00, "Status_Entrega": "Entregue"}, # Divergência de Desconto e Líquido!
        {"ID_Pedido": "PED-1005", "Data_Venda": "05/10/2026", "Cliente": "Hospital Santa Clara", "Vendedor": "Ana Paula", "Valor_Bruto": 12800.00, "Desconto": 500.00, "Valor_Liquido": 12300.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1006", "Data_Venda": "06/10/2026", "Cliente": "Logística Global Express", "Vendedor": "Lucas Silva", "Valor_Bruto": 3200.00, "Desconto": 100.00, "Valor_Liquido": 3100.00, "Status_Entrega": "Faturado"}, # Divergência de Status (era Pendente)!
        {"ID_Pedido": "PED-1007", "Data_Venda": "07/10/2026", "Cliente": "Padaria & Confeitaria Central", "Vendedor": "Mariana Souza", "Valor_Bruto": 890.00, "Desconto": 0.00, "Valor_Liquido": 890.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1008", "Data_Venda": "08/10/2026", "Cliente": "Escola Futuro Brilhante", "Vendedor": "Carlos Eduardo", "Valor_Bruto": 6400.00, "Desconto": 200.00, "Valor_Liquido": 6200.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1009", "Data_Venda": "09/10/2026", "Cliente": "Auto Peças Progresso", "Vendedor": "Ana Paula", "Valor_Bruto": 2750.00, "Desconto": 50.00, "Valor_Liquido": 2700.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1010", "Data_Venda": "10/10/2026", "Cliente": "Construtora Horizonte S/A", "Vendedor": "Lucas Silva", "Valor_Bruto": 15200.00, "Desconto": 800.00, "Valor_Liquido": 14400.00, "Status_Entrega": "Entregue"},
        {"ID_Pedido": "PED-1012", "Data_Venda": "12/10/2026", "Cliente": "Restaurante Sabor & Cia", "Vendedor": "Carlos Eduardo", "Valor_Bruto": 2300.00, "Desconto": 50.00, "Valor_Liquido": 2250.00, "Status_Entrega": "Entregue"} # Novo pedido em B
    ]

    pd.DataFrame(data_a).to_excel(path_a, index=False)
    pd.DataFrame(data_b).to_excel(path_b, index=False)
    return path_a, "Base_Vendas_ERP_Anterior.xlsx", path_b, "Base_Vendas_ERP_Atualizada.xlsx"

