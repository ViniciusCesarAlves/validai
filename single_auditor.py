import os
import re
import unicodedata
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image

import comparator

def is_empty_val(val):
    if val is None:
        return True
    if pd.isna(val):
        return True
    s = str(val).strip()
    return s == '' or s.lower() in ('none', 'nan', 'null', 'nat')

def clean_str(val):
    if is_empty_val(val):
        return ''
    return str(val).strip()

def is_only_letters(val):
    if is_empty_val(val):
        return False
    s = str(val).strip()
    # Remove acentos
    s_norm = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    # Permite apenas letras e espaços
    return bool(re.match(r'^[A-Za-z\s]+$', s_norm))

def is_only_numbers(val):
    if is_empty_val(val):
        return False
    s = str(val).strip()
    # Tenta remover formatações comuns de moeda / números (R$, ., ,)
    s_clean = s.replace('R$', '').replace('$', '').replace(' ', '').strip()
    if re.match(r'^-?\d+([.,]\d+)?$', s_clean):
        return True
    # Tenta converter para float
    try:
        float(s_clean.replace('.', '').replace(',', '.'))
        return True
    except Exception:
        return False

def is_alphanumeric(val):
    if is_empty_val(val):
        return False
    s = str(val).strip()
    s_norm = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return bool(re.match(r'^[A-Za-z0-9\s]+$', s_norm)) and any(c.isalpha() for c in s_norm) and any(c.isdigit() for c in s_norm)

def to_comparable_num(val):
    if is_empty_val(val):
        return None
    try:
        parsed = comparator.parse_cell_value(val, normalize_currency=True, normalize_dates=False)
        if isinstance(parsed, (int, float)):
            return float(parsed)
        # fallback string to float
        s = str(val).replace('R$', '').replace('$', '').replace(' ', '').strip()
        # Se tiver vírgula e ponto
        if '.' in s and ',' in s:
            s = s.replace('.', '').replace(',', '.')
        elif ',' in s:
            s = s.replace(',', '.')
        return float(s)
    except Exception:
        return None

def to_comparable_date(val):
    if is_empty_val(val):
        return None
    try:
        dt = pd.to_datetime(val, dayfirst=True, errors='coerce')
        if pd.notna(dt):
            return dt
    except Exception:
        pass
    return None

def compare_values(val1, val2, op):
    """
    Compara dois valores usando o operador op ('==', '!=', '>', '<', '>=', '<=').
    Tenta comparar como números, datas ou strings.
    """
    if is_empty_val(val1) and is_empty_val(val2):
        return op in ('==', '>=', '<=')
    if is_empty_val(val1) or is_empty_val(val2):
        return op == '!='

    # Tenta numérico
    n1 = to_comparable_num(val1)
    n2 = to_comparable_num(val2)
    if n1 is not None and n2 is not None:
        if op == '==': return abs(n1 - n2) < 1e-6
        if op == '!=': return abs(n1 - n2) >= 1e-6
        if op == '>': return n1 > n2
        if op == '<': return n1 < n2
        if op == '>=': return n1 >= n2
        if op == '<=': return n1 <= n2

    # Tenta data
    d1 = to_comparable_date(val1)
    d2 = to_comparable_date(val2)
    if d1 is not None and d2 is not None:
        if op == '==': return d1 == d2
        if op == '!=': return d1 != d2
        if op == '>': return d1 > d2
        if op == '<': return d1 < d2
        if op == '>=': return d1 >= d2
        if op == '<=': return d1 <= d2

    # Compara como string normalizada
    s1 = str(val1).strip().lower()
    s2 = str(val2).strip().lower()
    if op == '==': return s1 == s2
    if op == '!=': return s1 != s2
    if op == '>': return s1 > s2
    if op == '<': return s1 < s2
    if op == '>=': return s1 >= s2
    if op == '<=': return s1 <= s2
    return False

def audit_single_dataset(df, rules, max_preview_rows=300):
    """
    Executa a auditoria em um único DataFrame com base em uma lista de regras.
    Retorna estatísticas, preview de linhas com divergências, contagens e mapa de células inválidas.
    """
    total_rows = len(df)
    cols = list(df.columns)

    # Identificar duplicatas antecipadamente para regras de 'duplicate' e 'count_equals'
    dup_counts = {}
    for rule in rules:
        rtype = rule.get('rule_type')
        col = rule.get('col')
        if rtype in ('duplicate', 'count_equals') and col in df.columns:
            # Conta ocorrências de cada valor string não vazio
            s_series = df[col].apply(lambda v: str(v).strip().lower() if not is_empty_val(v) else '__EMPTY__')
            counts = s_series.value_counts().to_dict()
            dup_counts[col] = counts

    # Mapeamentos para guardar resultados
    # invalid_cells_by_row: { row_idx: { col_name: [list of error messages] } }
    invalid_cells_by_row = {}
    rule_stats = []
    rule_violation_counts = {i: 0 for i in range(len(rules))}

    # Avaliar regras linha a linha
    for row_idx, row in df.iterrows():
        for r_idx, rule in enumerate(rules):
            rtype = rule.get('rule_type')
            col = rule.get('col')
            if col not in df.columns:
                continue

            val = row[col]
            is_invalid = False
            err_msg = ""

            if rtype == 'not_empty':
                if is_empty_val(val):
                    is_invalid = True
                    err_msg = f"Campo obrigatório vazio"

            elif rtype == 'duplicate':
                if not is_empty_val(val):
                    s_val = str(val).strip().lower()
                    cnt = dup_counts.get(col, {}).get(s_val, 0)
                    if cnt > 1:
                        is_invalid = True
                        err_msg = f"Valor duplicado ({cnt} ocorrências)"

            elif rtype == 'count_equals':
                # Alerta se repetir mais que o limiar (padrão > 1)
                min_threshold = int(rule.get('threshold') or 2)
                if not is_empty_val(val):
                    s_val = str(val).strip().lower()
                    cnt = dup_counts.get(col, {}).get(s_val, 0)
                    if cnt >= min_threshold:
                        is_invalid = True
                        err_msg = f"Valor repetido {cnt} vezes (limite: {min_threshold})"

            elif rtype == 'only_letters':
                if not is_empty_val(val) and not is_only_letters(val):
                    is_invalid = True
                    err_msg = f"Contém caracteres que não são letras"

            elif rtype == 'only_numbers':
                if not is_empty_val(val) and not is_only_numbers(val):
                    is_invalid = True
                    err_msg = f"Contém caracteres que não são números"

            elif rtype == 'alphanumeric':
                if not is_empty_val(val) and not is_alphanumeric(val):
                    is_invalid = True
                    err_msg = f"Deve conter letras e números"

            elif rtype == 'compare_cols':
                target_col = rule.get('target_col')
                op = rule.get('op', '==')
                if target_col in df.columns:
                    val_target = row[target_col]
                    passed = compare_values(val, val_target, op)
                    if not passed:
                        is_invalid = True
                        err_msg = f"Não atendeu: [{col}] {op} [{target_col}]"

            elif rtype in ('greater_than', 'less_than', 'equals', 'not_equals'):
                threshold = rule.get('threshold', '')
                op_map = {
                    'greater_than': '>',
                    'less_than': '<',
                    'equals': '==',
                    'not_equals': '!='
                }
                op = op_map[rtype]
                passed = compare_values(val, threshold, op)
                if not passed:
                    is_invalid = True
                    err_msg = f"Não atendeu: valor {op} {threshold}"

            elif rtype == 'text_length':
                length_op = rule.get('length_op', '==')
                target_len = int(rule.get('length_val', 0))
                s_len = len(str(val).strip()) if not is_empty_val(val) else 0
                passed = False
                if length_op == '==': passed = (s_len == target_len)
                elif length_op == '>=': passed = (s_len >= target_len)
                elif length_op == '<=': passed = (s_len <= target_len)
                if not passed:
                    is_invalid = True
                    err_msg = f"Tamanho {s_len} carac. (esperado {length_op} {target_len})"

            if is_invalid:
                rule_violation_counts[r_idx] += 1
                if row_idx not in invalid_cells_by_row:
                    invalid_cells_by_row[row_idx] = {}
                if col not in invalid_cells_by_row[row_idx]:
                    invalid_cells_by_row[row_idx][col] = []
                invalid_cells_by_row[row_idx][col].append(err_msg)

    # Compila estatísticas das regras
    for r_idx, rule in enumerate(rules):
        v_count = rule_violation_counts[r_idx]
        rtype = rule.get('rule_type')
        col = rule.get('col')
        target_col = rule.get('target_col', '')
        op = rule.get('op', '')
        threshold = rule.get('threshold', '')

        # Descrição amigável
        desc = ""
        if rtype == 'duplicate': desc = f"Valores duplicados na coluna '{col}'"
        elif rtype == 'only_letters': desc = f"Apenas letras em '{col}'"
        elif rtype == 'only_numbers': desc = f"Apenas números em '{col}'"
        elif rtype == 'alphanumeric': desc = f"Letras e números em '{col}'"
        elif rtype == 'not_empty': desc = f"Preenchimento obrigatório em '{col}'"
        elif rtype == 'compare_cols': desc = f"Comparar: '{col}' {op} '{target_col}'"
        elif rtype == 'greater_than': desc = f"'{col}' maior que {threshold}"
        elif rtype == 'less_than': desc = f"'{col}' menor que {threshold}"
        elif rtype == 'equals': desc = f"'{col}' igual a {threshold}"
        elif rtype == 'not_equals': desc = f"'{col}' diferente de {threshold}"
        elif rtype == 'count_equals': desc = f"Contar iguais em '{col}' (limite: {threshold or 2})"
        elif rtype == 'text_length': desc = f"Tamanho de '{col}' {rule.get('length_op')} {rule.get('length_val')}"
        else: desc = f"Regra em '{col}'"

        rule_stats.append({
            'rule_id': r_idx + 1,
            'col': col,
            'rule_type': rtype,
            'description': desc,
            'violations_count': v_count,
            'passed': (v_count == 0)
        })

    # Estatísticas globais
    invalid_rows_count = len(invalid_cells_by_row)
    valid_rows_count = total_rows - invalid_rows_count
    total_cell_errors = sum(len(cols_err) for cols_err in invalid_cells_by_row.values())
    conformity_rate = round((valid_rows_count / total_rows * 100), 2) if total_rows > 0 else 100.0

    # Amostra de linhas para exibição no frontend (foco nas linhas com inconsistências)
    preview_rows = []
    # Mostra primeiro as linhas inválidas
    invalid_row_indices = list(invalid_cells_by_row.keys())[:max_preview_rows]
    for r_idx in invalid_row_indices:
        row_dict = {}
        for c in cols:
            val = df.loc[r_idx, c]
            row_dict[c] = "" if pd.isna(val) else str(val)
        row_dict['_row_idx'] = int(r_idx) + 1  # 1-indexed para o usuário
        row_dict['_errors'] = invalid_cells_by_row[r_idx]
        preview_rows.append(row_dict)

    # Se sobrar espaço no preview e houver linhas válidas, adiciona algumas válidas para contexto
    if len(preview_rows) < 30 and valid_rows_count > 0:
        valid_indices = [idx for idx in df.index if idx not in invalid_cells_by_row][:10]
        for r_idx in valid_indices:
            row_dict = {}
            for c in cols:
                val = df.loc[r_idx, c]
                row_dict[c] = "" if pd.isna(val) else str(val)
            row_dict['_row_idx'] = int(r_idx) + 1
            row_dict['_errors'] = {}
            preview_rows.append(row_dict)

    # Resumo de frequências para regras de duplicatas / contagem
    frequency_breakdown = {}
    for col, counts in dup_counts.items():
        # Filtra top 20 valores mais frequentes
        sorted_counts = sorted(
            [{'value': k, 'count': v} for k, v in counts.items() if k != '__EMPTY__' and v > 1],
            key=lambda x: x['count'],
            reverse=True
        )[:20]
        if sorted_counts:
            frequency_breakdown[col] = sorted_counts

    summary = {
        'total_rows': total_rows,
        'valid_rows': valid_rows_count,
        'invalid_rows': invalid_rows_count,
        'total_errors': total_cell_errors,
        'rules_count': len(rules),
        'conformity_rate': conformity_rate,
        'is_perfect': (invalid_rows_count == 0),
        'rules_stats': rule_stats,
        'frequency_breakdown': frequency_breakdown
    }

    return summary, preview_rows, invalid_cells_by_row, cols

def generate_single_audit_excel(df, summary, invalid_cells_by_row, cols, output_path):
    """
    Gera relatório Excel estilizado com a identidade ValidAí:
    - Aba 1: Resumo da Auditoria (KPIs, lista de regras e status)
    - Aba 2: Planilha Auditada (células divergentes destacadas em vermelho/amarelo)
    - Aba 3: Frequência de Repetições (se houver regras de contagem/duplicatas)
    """
    wb = openpyxl.Workbook()
    # Remove sheet padrão
    wb.remove(wb.active)

    # Cores ValidAí
    COLOR_ORANGE = "4FD580"
    COLOR_LIGHT_ORANGE = "BCFFE2"
    COLOR_HEADER_FONT = "FFFFFF"
    COLOR_ERROR_FILL = "FDE8E8" # Vermelho suave
    COLOR_ERROR_FONT = "991B1B" # Vermelho escuro
    COLOR_SUCCESS_FILL = "DEF7EC" # Verde suave
    COLOR_SUCCESS_FONT = "03543F" # Verde escuro
    COLOR_ZEBRA = "F9FAFB"

    fill_header = PatternFill(start_color=COLOR_ORANGE, end_color=COLOR_ORANGE, fill_type="solid")
    fill_error = PatternFill(start_color=COLOR_ERROR_FILL, end_color=COLOR_ERROR_FILL, fill_type="solid")
    fill_success = PatternFill(start_color=COLOR_SUCCESS_FILL, end_color=COLOR_SUCCESS_FILL, fill_type="solid")
    fill_zebra = PatternFill(start_color=COLOR_ZEBRA, end_color=COLOR_ZEBRA, fill_type="solid")

    font_header = Font(name="Calibri", size=11, bold=True, color=COLOR_HEADER_FONT)
    font_bold = Font(name="Calibri", size=11, bold=True)
    font_regular = Font(name="Calibri", size=10)
    font_error = Font(name="Calibri", size=10, bold=True, color=COLOR_ERROR_FONT)
    font_success = Font(name="Calibri", size=10, bold=True, color=COLOR_SUCCESS_FONT)

    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='E5E7EB'),
        right=Side(style='thin', color='E5E7EB'),
        top=Side(style='thin', color='E5E7EB'),
        bottom=Side(style='thin', color='E5E7EB')
    )

    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'images', 'logo.png')

    # ==========================================
    # ABA 1: RESUMO DA AUDITORIA
    # ==========================================
    ws_resumo = wb.create_sheet(title="Resumo da Auditoria")
    ws_resumo.views.sheetView[0].showGridLines = True

    # Inserir Logo
    start_row = 1
    if os.path.exists(logo_path):
        try:
            img = Image(logo_path)
            img.width = 130
            img.height = 42
            ws_resumo.add_image(img, "A1")
            start_row = 4
        except Exception:
            start_row = 1

    # Título
    title_cell = ws_resumo.cell(row=start_row, column=1, value="RELATÓRIO DE AUDITORIA DE PLANILHA ÚNICA - VALIDAÍ")
    title_cell.font = Font(name="Calibri", size=14, bold=True, color=COLOR_ORANGE)
    start_row += 2

    # Cards de Indicadores (KPIs)
    kpis = [
        ("Total de Linhas Auditadas", summary['total_rows']),
        ("Linhas Conformes (Sem Erros)", summary['valid_rows']),
        ("Linhas com Inconsistências", summary['invalid_rows']),
        ("Total de Células Inconsistentes", summary['total_errors']),
        ("Taxa de Conformidade", f"{summary['conformity_rate']}%"),
        ("Regras Avaliadas", summary['rules_count'])
    ]

    for k_idx, (label, val) in enumerate(kpis):
        col_pos = (k_idx % 3) * 2 + 1
        r_pos = start_row + (k_idx // 3) * 3

        cell_lbl = ws_resumo.cell(row=r_pos, column=col_pos, value=label)
        cell_lbl.font = Font(name="Calibri", size=9, bold=True, color="6B7280")
        ws_resumo.merge_cells(start_row=r_pos, start_column=col_pos, end_row=r_pos, end_column=col_pos+1)

        cell_v = ws_resumo.cell(row=r_pos+1, column=col_pos, value=val)
        cell_v.font = Font(name="Calibri", size=16, bold=True, color="1F2937")
        ws_resumo.merge_cells(start_row=r_pos+1, start_column=col_pos, end_row=r_pos+1, end_column=col_pos+1)

        for r_box in range(r_pos, r_pos+2):
            for c_box in range(col_pos, col_pos+2):
                ws_resumo.cell(row=r_box, column=c_box).border = thin_border
                ws_resumo.cell(row=r_box, column=c_box).fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

    start_row += 7

    # Tabela de Regras e Violações
    sec_cell = ws_resumo.cell(row=start_row, column=1, value="Detalhamento das Regras Aplicadas")
    sec_cell.font = Font(name="Calibri", size=12, bold=True, color="1F2937")
    start_row += 1

    headers_rules = ["ID", "Coluna Auditada", "Tipo de Regra", "Critério / Descrição", "Qtd. Inconsistências", "Situação"]
    for c_idx, h in enumerate(headers_rules, 1):
        cell = ws_resumo.cell(row=start_row, column=c_idx, value=h)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = align_center if c_idx in (1, 5, 6) else align_left
        cell.border = thin_border

    start_row += 1
    for r_stat in summary['rules_stats']:
        ws_resumo.cell(row=start_row, column=1, value=r_stat['rule_id']).alignment = align_center
        ws_resumo.cell(row=start_row, column=2, value=r_stat['col']).alignment = align_left
        ws_resumo.cell(row=start_row, column=3, value=r_stat['rule_type']).alignment = align_left
        ws_resumo.cell(row=start_row, column=4, value=r_stat['description']).alignment = align_left
        ws_resumo.cell(row=start_row, column=5, value=r_stat['violations_count']).alignment = align_right

        status_cell = ws_resumo.cell(row=start_row, column=6)
        if r_stat['passed']:
            status_cell.value = "100% CONFORME"
            status_cell.font = font_success
            status_cell.fill = fill_success
        else:
            status_cell.value = f"{r_stat['violations_count']} FALHAS"
            status_cell.font = font_error
            status_cell.fill = fill_error
        status_cell.alignment = align_center

        for col_idx in range(1, 7):
            cell = ws_resumo.cell(row=start_row, column=col_idx)
            cell.border = thin_border
            if col_idx < 6:
                cell.font = font_regular
        start_row += 1

    # Crédito Institucional no Rodapé do Resumo
    start_row += 1
    credit_cell = ws_resumo.cell(
        row=start_row,
        column=1,
        value="Relatório gerado automaticamente por ValidAí (https://validai.app.br) • Arquitetura e Inteligência de Dados por Vinícius Alves."
    )
    credit_cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")

    # Ajuste de largura das colunas do resumo
    ws_resumo.column_dimensions['A'].width = 8
    ws_resumo.column_dimensions['B'].width = 24
    ws_resumo.column_dimensions['C'].width = 20
    ws_resumo.column_dimensions['D'].width = 40
    ws_resumo.column_dimensions['E'].width = 22
    ws_resumo.column_dimensions['F'].width = 20

    # ==========================================
    # ABA 2: DADOS AUDITADOS
    # ==========================================
    ws_data = wb.create_sheet(title="Planilha Auditada")
    ws_data.views.sheetView[0].showGridLines = True

    # Cabeçalho da tabela de dados: Linha Original + Inconsistências + Colunas
    data_headers = ["Linha", "Status", "Motivo da Inconsistência"] + cols
    for c_idx, h in enumerate(data_headers, 1):
        cell = ws_data.cell(row=1, column=c_idx, value=h)
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = align_center if c_idx in (1, 2) else align_left
        cell.border = thin_border

    # Preenchimento das linhas
    row_write_idx = 2
    for r_idx, row in df.iterrows():
        has_error = r_idx in invalid_cells_by_row
        row_errors = invalid_cells_by_row.get(r_idx, {})

        # Coluna Linha
        c_line = ws_data.cell(row=row_write_idx, column=1, value=r_idx + 1)
        c_line.alignment = align_center
        c_line.font = font_regular
        c_line.border = thin_border

        # Coluna Status
        c_status = ws_data.cell(row=row_write_idx, column=2)
        if has_error:
            c_status.value = "INCONSISTENTE"
            c_status.font = font_error
            c_status.fill = fill_error
        else:
            c_status.value = "OK"
            c_status.font = font_success
            c_status.fill = fill_success
        c_status.alignment = align_center
        c_status.border = thin_border

        # Coluna Motivo
        motivos = []
        for col_name, err_list in row_errors.items():
            motivos.append(f"[{col_name}]: {', '.join(err_list)}")
        c_motivo = ws_data.cell(row=row_write_idx, column=3, value="; ".join(motivos) if motivos else "Conforme")
        c_motivo.font = font_error if has_error else font_regular
        c_motivo.border = thin_border
        c_motivo.alignment = align_left

        # Colunas de dados reais
        for c_data_idx, col_name in enumerate(cols, 4):
            val = row[col_name]
            cell = ws_data.cell(row=row_write_idx, column=c_data_idx, value="" if pd.isna(val) else str(val))
            cell.border = thin_border
            cell.alignment = align_left

            # Se esta célula específica teve erro
            if col_name in row_errors:
                cell.fill = fill_error
                cell.font = font_error
            else:
                cell.font = font_regular
                if row_write_idx % 2 == 1:
                    cell.fill = fill_zebra

        row_write_idx += 1

    # Larguras na aba de dados
    ws_data.column_dimensions['A'].width = 10
    ws_data.column_dimensions['B'].width = 16
    ws_data.column_dimensions['C'].width = 35
    for c_data_idx, col_name in enumerate(cols, 4):
        col_letter = get_column_letter(c_data_idx)
        ws_data.column_dimensions[col_letter].width = max(len(str(col_name)) + 4, 15)

    # ==========================================
    # ABA 3: FREQUÊNCIA DE REPETIÇÕES (Se aplicável)
    # ==========================================
    if summary.get('frequency_breakdown'):
        ws_freq = wb.create_sheet(title="Frequência de Repetições")
        ws_freq.views.sheetView[0].showGridLines = True

        f_row = 1
        f_title = ws_freq.cell(row=f_row, column=1, value="RANKING DE VALORES REPETIDOS / DUPLICADOS")
        f_title.font = Font(name="Calibri", size=13, bold=True, color=COLOR_ORANGE)
        f_row += 2

        for col_name, items in summary['frequency_breakdown'].items():
            sub = ws_freq.cell(row=f_row, column=1, value=f"Coluna: {col_name}")
            sub.font = Font(name="Calibri", size=11, bold=True)
            f_row += 1

            ws_freq.cell(row=f_row, column=1, value="Valor").fill = fill_header
            ws_freq.cell(row=f_row, column=1).font = font_header
            ws_freq.cell(row=f_row, column=1).border = thin_border

            ws_freq.cell(row=f_row, column=2, value="Qtd. Ocorrências").fill = fill_header
            ws_freq.cell(row=f_row, column=2).font = font_header
            ws_freq.cell(row=f_row, column=2).alignment = align_center
            ws_freq.cell(row=f_row, column=2).border = thin_border
            f_row += 1

            for it in items:
                c1 = ws_freq.cell(row=f_row, column=1, value=it['value'])
                c1.font = font_regular
                c1.border = thin_border

                c2 = ws_freq.cell(row=f_row, column=2, value=it['count'])
                c2.font = font_bold
                c2.alignment = align_center
                c2.border = thin_border
                c2.fill = fill_error
                f_row += 1
            f_row += 2

        ws_freq.column_dimensions['A'].width = 30
        ws_freq.column_dimensions['B'].width = 20

    wb.save(output_path)
    return output_path

