import os
import re
import html
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from difflib import SequenceMatcher


def extract_text_from_file(filepath: str, filename: str) -> dict:
    """
    Extrai texto de arquivos .pdf, .docx ou .txt.
    Retorna um dicionário com:
      - text: texto completo extraído
      - pages_count: número de páginas (se aplicável, ou estimado)
      - file_type: extensão identificada (PDF, DOCX, TXT)
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.txt':
        raw_bytes = open(filepath, 'rb').read()
        text = None
        for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
            try:
                text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw_bytes.decode('utf-8', errors='replace')
        pages = max(1, (len(text) // 2500) + 1)
        return {
            'text': text,
            'pages_count': pages,
            'file_type': 'TXT'
        }

    elif ext == '.docx':
        paragraphs = []
        try:
            import docx
            doc = docx.Document(filepath)
            for p in doc.paragraphs:
                paragraphs.append(p.text)
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [c.text.strip().replace('\n', ' ') for c in row.cells]
                    if any(row_cells):
                        paragraphs.append(' | '.join(row_cells))
        except Exception:
            # Fallback via XML nativo caso python-docx encontre algum elemento atípico
            try:
                with zipfile.ZipFile(filepath) as zf:
                    xml_content = zf.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for p in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    texts = [t.text for t in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
                    paragraphs.append(''.join(texts))
            except Exception as e:
                raise ValueError(f"Não foi possível ler o arquivo DOCX ({filename}): {str(e)}")

        full_text = '\n'.join(paragraphs)
        pages = max(1, (len(full_text) // 2500) + 1)
        return {
            'text': full_text,
            'pages_count': pages,
            'file_type': 'DOCX'
        }

    elif ext == '.pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            pages_text = []
            for idx, page in enumerate(reader.pages):
                page_txt = page.extract_text() or ''
                pages_text.append(page_txt)
            full_text = '\n'.join(pages_text)
            return {
                'text': full_text,
                'pages_count': max(1, len(reader.pages)),
                'file_type': 'PDF'
            }
        except Exception as e:
            raise ValueError(f"Não foi possível ler o arquivo PDF ({filename}): {str(e)}")

    else:
        raise ValueError(f"Formato de arquivo não suportado ({ext}). Envie arquivos .pdf, .docx ou .txt.")


def _tokenize_for_inline_diff(text: str, granularity: str = 'word') -> list:
    """
    Divide uma linha em tokens para diff interno:
    - 'word': preserva palavras, números, pontuações e espaços para reconstrução fiel
    - 'char': divide caractere por caractere
    """
    if granularity == 'char':
        return list(text)
    # Divide mantendo espaços e palavras/pontuações separados
    return re.findall(r'\s+|\w+|[^\w\s]', text, re.UNICODE)


def _compute_inline_segments(line_a: str, line_b: str, granularity: str = 'word', ignore_case: bool = False):
    """
    Calcula os segmentos de diferença inline entre duas linhas modificadas.
    Retorna (segments_a, segments_b, words_removed, words_added).
    """
    tokens_a = _tokenize_for_inline_diff(line_a, granularity)
    tokens_b = _tokenize_for_inline_diff(line_b, granularity)

    if ignore_case:
        cmp_a = [t.lower() for t in tokens_a]
        cmp_b = [t.lower() for t in tokens_b]
    else:
        cmp_a = tokens_a
        cmp_b = tokens_b

    matcher = SequenceMatcher(None, cmp_a, cmp_b)
    segments_a = []
    segments_b = []
    words_removed = 0
    words_added = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        piece_a = ''.join(tokens_a[i1:i2])
        piece_b = ''.join(tokens_b[j1:j2])

        if tag == 'equal':
            if piece_a:
                segments_a.append({'text': piece_a, 'type': 'equal'})
            if piece_b:
                segments_b.append({'text': piece_b, 'type': 'equal'})
        elif tag == 'delete':
            if piece_a:
                segments_a.append({'text': piece_a, 'type': 'delete'})
                words_removed += len(re.findall(r'\S+', piece_a))
        elif tag == 'insert':
            if piece_b:
                segments_b.append({'text': piece_b, 'type': 'insert'})
                words_added += len(re.findall(r'\S+', piece_b))
        elif tag == 'replace':
            if piece_a:
                segments_a.append({'text': piece_a, 'type': 'delete'})
                words_removed += len(re.findall(r'\S+', piece_a))
            if piece_b:
                segments_b.append({'text': piece_b, 'type': 'insert'})
                words_added += len(re.findall(r'\S+', piece_b))

    return segments_a, segments_b, words_removed, words_added


def _normalize_line_for_comparison(line: str, trim_spaces: bool, ignore_case: bool) -> str:
    res = line
    if trim_spaces:
        res = re.sub(r'\s+', ' ', res.strip())
    if ignore_case:
        res = res.lower()
    return res


def _count_words(text: str) -> list:
    return re.findall(r'\b\w+\b', text, re.UNICODE)


def compare_texts(
    text_a: str,
    text_b: str,
    filename_a: str = "Documento Original",
    filename_b: str = "Documento Novo",
    pages_a: int = 1,
    pages_b: int = 1,
    file_type_a: str = "TXT",
    file_type_b: str = "TXT",
    ignore_case: bool = False,
    trim_spaces: bool = True,
    ignore_empty_lines: bool = False,
    diff_granularity: str = 'word'
) -> dict:
    """
    Realiza a comparação detalhada entre dois textos/documentos e retorna:
      - summary: KPIs e métricas executivas
      - side_by_side_blocks: blocos para visualização Rich Text / Plain Text lado a lado
      - redline_blocks: blocos compilados em documento único (Redline)
      - diff_table_rows: linhas apenas com divergências para tabela analítica
      - stats_comparison: comparativo estatístico entre os dois documentos
    """
    raw_lines_a = text_a.splitlines()
    raw_lines_b = text_b.splitlines()

    if ignore_empty_lines:
        lines_a = [ln for ln in raw_lines_a if ln.strip() != '']
        lines_b = [ln for ln in raw_lines_b if ln.strip() != '']
    else:
        lines_a = raw_lines_a
        lines_b = raw_lines_b

    norm_lines_a = [_normalize_line_for_comparison(ln, trim_spaces, ignore_case) for ln in lines_a]
    norm_lines_b = [_normalize_line_for_comparison(ln, trim_spaces, ignore_case) for ln in lines_b]

    matcher = SequenceMatcher(None, norm_lines_a, norm_lines_b)

    side_by_side_blocks = []
    redline_blocks = []
    diff_table_rows = []

    identical_lines_count = 0
    modified_lines_count = 0
    added_lines_count = 0
    removed_lines_count = 0

    total_words_added = 0
    total_words_removed = 0

    diff_idx = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for offset in range(i2 - i1):
                idx_a = i1 + offset
                idx_b = j1 + offset
                ln_a = lines_a[idx_a]
                ln_b = lines_b[idx_b]
                identical_lines_count += 1

                side_by_side_blocks.append({
                    'type': 'equal',
                    'line_a': idx_a + 1,
                    'line_b': idx_b + 1,
                    'text_a': ln_a,
                    'text_b': ln_b,
                    'segments_a': [{'text': ln_a, 'type': 'equal'}],
                    'segments_b': [{'text': ln_b, 'type': 'equal'}]
                })
                redline_blocks.append({
                    'type': 'equal',
                    'line_a': idx_a + 1,
                    'line_b': idx_b + 1,
                    'segments': [{'text': ln_b, 'type': 'equal'}]
                })

        elif tag == 'delete':
            for idx_a in range(i1, i2):
                ln_a = lines_a[idx_a]
                removed_lines_count += 1
                w_rem = len(re.findall(r'\S+', ln_a))
                total_words_removed += w_rem
                diff_idx += 1

                segs_a = [{'text': ln_a, 'type': 'delete'}]
                side_by_side_blocks.append({
                    'type': 'delete',
                    'line_a': idx_a + 1,
                    'line_b': None,
                    'text_a': ln_a,
                    'text_b': '',
                    'segments_a': segs_a,
                    'segments_b': []
                })
                redline_blocks.append({
                    'type': 'delete',
                    'line_a': idx_a + 1,
                    'line_b': None,
                    'segments': segs_a
                })
                diff_table_rows.append({
                    'diff_id': diff_idx,
                    'change_type': 'Removido',
                    'badge_class': 'danger',
                    'line_a': idx_a + 1,
                    'line_b': '-',
                    'text_a': ln_a,
                    'text_b': '(Linha removida no documento novo)',
                    'segments_a': segs_a,
                    'segments_b': [],
                    'words_removed': w_rem,
                    'words_added': 0
                })

        elif tag == 'insert':
            for idx_b in range(j1, j2):
                ln_b = lines_b[idx_b]
                added_lines_count += 1
                w_add = len(re.findall(r'\S+', ln_b))
                total_words_added += w_add
                diff_idx += 1

                segs_b = [{'text': ln_b, 'type': 'insert'}]
                side_by_side_blocks.append({
                    'type': 'insert',
                    'line_a': None,
                    'line_b': idx_b + 1,
                    'text_a': '',
                    'text_b': ln_b,
                    'segments_a': [],
                    'segments_b': segs_b
                })
                redline_blocks.append({
                    'type': 'insert',
                    'line_a': None,
                    'line_b': idx_b + 1,
                    'segments': segs_b
                })
                diff_table_rows.append({
                    'diff_id': diff_idx,
                    'change_type': 'Adicionado',
                    'badge_class': 'success',
                    'line_a': '-',
                    'line_b': idx_b + 1,
                    'text_a': '(Linha inexistente no documento original)',
                    'text_b': ln_b,
                    'segments_a': [],
                    'segments_b': segs_b,
                    'words_removed': 0,
                    'words_added': w_add
                })

        elif tag == 'replace':
            len_a = i2 - i1
            len_b = j2 - j1
            max_len = max(len_a, len_b)

            for offset in range(max_len):
                has_a = offset < len_a
                has_b = offset < len_b
                idx_a = (i1 + offset) if has_a else None
                idx_b = (j1 + offset) if has_b else None
                ln_a = lines_a[idx_a] if has_a else ''
                ln_b = lines_b[idx_b] if has_b else ''

                if has_a and has_b:
                    modified_lines_count += 1
                    segs_a, segs_b, w_rem, w_add = _compute_inline_segments(
                        ln_a, ln_b, granularity=diff_granularity, ignore_case=ignore_case
                    )
                    total_words_removed += w_rem
                    total_words_added += w_add
                    diff_idx += 1

                    # Compila segmentos unificados para visão Redline
                    unified_segs = []
                    tokens_a = _tokenize_for_inline_diff(ln_a, diff_granularity)
                    tokens_b = _tokenize_for_inline_diff(ln_b, diff_granularity)
                    cmp_a = [t.lower() for t in tokens_a] if ignore_case else tokens_a
                    cmp_b = [t.lower() for t in tokens_b] if ignore_case else tokens_b
                    sub_matcher = SequenceMatcher(None, cmp_a, cmp_b)
                    for sub_tag, si1, si2, sj1, sj2 in sub_matcher.get_opcodes():
                        pa = ''.join(tokens_a[si1:si2])
                        pb = ''.join(tokens_b[sj1:sj2])
                        if sub_tag == 'equal' and pb:
                            unified_segs.append({'text': pb, 'type': 'equal'})
                        elif sub_tag == 'delete' and pa:
                            unified_segs.append({'text': pa, 'type': 'delete'})
                        elif sub_tag == 'insert' and pb:
                            unified_segs.append({'text': pb, 'type': 'insert'})
                        elif sub_tag == 'replace':
                            if pa:
                                unified_segs.append({'text': pa, 'type': 'delete'})
                            if pb:
                                unified_segs.append({'text': pb, 'type': 'insert'})

                    side_by_side_blocks.append({
                        'type': 'replace',
                        'line_a': idx_a + 1,
                        'line_b': idx_b + 1,
                        'text_a': ln_a,
                        'text_b': ln_b,
                        'segments_a': segs_a,
                        'segments_b': segs_b
                    })
                    redline_blocks.append({
                        'type': 'replace',
                        'line_a': idx_a + 1,
                        'line_b': idx_b + 1,
                        'segments': unified_segs
                    })
                    diff_table_rows.append({
                        'diff_id': diff_idx,
                        'change_type': 'Modificado',
                        'badge_class': 'warning',
                        'line_a': idx_a + 1,
                        'line_b': idx_b + 1,
                        'text_a': ln_a,
                        'text_b': ln_b,
                        'segments_a': segs_a,
                        'segments_b': segs_b,
                        'words_removed': w_rem,
                        'words_added': w_add
                    })

                elif has_a and not has_b:
                    removed_lines_count += 1
                    w_rem = len(re.findall(r'\S+', ln_a))
                    total_words_removed += w_rem
                    diff_idx += 1
                    segs_a = [{'text': ln_a, 'type': 'delete'}]

                    side_by_side_blocks.append({
                        'type': 'delete',
                        'line_a': idx_a + 1,
                        'line_b': None,
                        'text_a': ln_a,
                        'text_b': '',
                        'segments_a': segs_a,
                        'segments_b': []
                    })
                    redline_blocks.append({
                        'type': 'delete',
                        'line_a': idx_a + 1,
                        'line_b': None,
                        'segments': segs_a
                    })
                    diff_table_rows.append({
                        'diff_id': diff_idx,
                        'change_type': 'Removido',
                        'badge_class': 'danger',
                        'line_a': idx_a + 1,
                        'line_b': '-',
                        'text_a': ln_a,
                        'text_b': '(Linha removida no documento novo)',
                        'segments_a': segs_a,
                        'segments_b': [],
                        'words_removed': w_rem,
                        'words_added': 0
                    })

                elif has_b and not has_a:
                    added_lines_count += 1
                    w_add = len(re.findall(r'\S+', ln_b))
                    total_words_added += w_add
                    diff_idx += 1
                    segs_b = [{'text': ln_b, 'type': 'insert'}]

                    side_by_side_blocks.append({
                        'type': 'insert',
                        'line_a': None,
                        'line_b': idx_b + 1,
                        'text_a': '',
                        'text_b': ln_b,
                        'segments_a': [],
                        'segments_b': segs_b
                    })
                    redline_blocks.append({
                        'type': 'insert',
                        'line_a': None,
                        'line_b': idx_b + 1,
                        'segments': segs_b
                    })
                    diff_table_rows.append({
                        'diff_id': diff_idx,
                        'change_type': 'Adicionado',
                        'badge_class': 'success',
                        'line_a': '-',
                        'line_b': idx_b + 1,
                        'text_a': '(Linha inexistente no documento original)',
                        'text_b': ln_b,
                        'segments_a': [],
                        'segments_b': segs_b,
                        'words_removed': 0,
                        'words_added': w_add
                    })

    # Estatísticas globais
    words_list_a = _count_words(text_a)
    words_list_b = _count_words(text_b)
    total_words_a = len(words_list_a)
    total_words_b = len(words_list_b)

    chars_a = len(text_a)
    chars_b = len(text_b)
    chars_no_space_a = len(re.sub(r'\s+', '', text_a))
    chars_no_space_b = len(re.sub(r'\s+', '', text_b))

    vocab_a = len(set(w.lower() for w in words_list_a))
    vocab_b = len(set(w.lower() for w in words_list_b))

    read_time_a = max(1, round(total_words_a / 200)) if total_words_a > 0 else 0
    read_time_b = max(1, round(total_words_b / 200)) if total_words_b > 0 else 0

    total_changes = modified_lines_count + added_lines_count + removed_lines_count
    is_identical = (total_changes == 0)

    if is_identical:
        similarity_pct = 100.0
    else:
        similarity_pct = round(matcher.ratio() * 100, 1)

    stats_comparison = [
        {
            'metric': 'Total de Linhas / Parágrafos',
            'val_a': len(lines_a),
            'val_b': len(lines_b),
            'diff': len(lines_b) - len(lines_a),
            'unit': 'linhas'
        },
        {
            'metric': 'Total de Palavras',
            'val_a': total_words_a,
            'val_b': total_words_b,
            'diff': total_words_b - total_words_a,
            'unit': 'palavras'
        },
        {
            'metric': 'Total de Caracteres (com espaços)',
            'val_a': chars_a,
            'val_b': chars_b,
            'diff': chars_b - chars_a,
            'unit': 'caracteres'
        },
        {
            'metric': 'Total de Caracteres (sem espaços)',
            'val_a': chars_no_space_a,
            'val_b': chars_no_space_b,
            'diff': chars_no_space_b - chars_no_space_a,
            'unit': 'caracteres'
        },
        {
            'metric': 'Vocabulário Único (palavras distintas)',
            'val_a': vocab_a,
            'val_b': vocab_b,
            'diff': vocab_b - vocab_a,
            'unit': 'termos'
        },
        {
            'metric': 'Páginas Estimadas / Extraídas',
            'val_a': pages_a,
            'val_b': pages_b,
            'diff': pages_b - pages_a,
            'unit': 'pág.'
        },
        {
            'metric': 'Tempo Estimado de Leitura',
            'val_a': f"{read_time_a} min",
            'val_b': f"{read_time_b} min",
            'diff': read_time_b - read_time_a,
            'unit': 'min'
        }
    ]

    words_unchanged = total_words_a if is_identical else max(0, total_words_b - total_words_added)
    chars_unchanged = chars_a if is_identical else min(chars_a, chars_b)
    chars_added = max(0, chars_b - chars_a) if not is_identical and chars_b > chars_a else 0
    chars_removed = max(0, chars_a - chars_b) if not is_identical and chars_a > chars_b else 0

    summary = {
        'filename_a': filename_a,
        'filename_b': filename_b,
        'file_type_a': file_type_a,
        'file_type_b': file_type_b,
        'pages_a': pages_a,
        'pages_b': pages_b,
        'is_identical': is_identical,
        'similarity_pct': similarity_pct,
        'total_lines_a': len(lines_a),
        'total_lines_b': len(lines_b),
        'identical_lines_count': identical_lines_count,
        'modified_lines_count': modified_lines_count,
        'added_lines_count': added_lines_count,
        'removed_lines_count': removed_lines_count,
        'total_diff_blocks': total_changes,
        'total_words_a': total_words_a,
        'total_words_b': total_words_b,
        'words_added': total_words_added,
        'words_removed': total_words_removed,
        'words_unchanged': words_unchanged,
        'chars_a': chars_a,
        'chars_b': chars_b,
        'chars_unchanged': chars_unchanged,
        'chars_added': chars_added,
        'chars_removed': chars_removed,
        'text_composition': {
            'words_unchanged': words_unchanged,
            'words_added': total_words_added,
            'words_removed': total_words_removed,
            'similarity_pct': similarity_pct
        }
    }

    return {
        'summary': summary,
        'side_by_side_blocks': side_by_side_blocks,
        'redline_blocks': redline_blocks,
        'diff_table_rows': diff_table_rows,
        'stats_comparison': stats_comparison
    }


def _segments_to_reportlab_xml(segments: list) -> str:
    """
    Converte uma lista de segmentos ({text, type}) em marcação XML segura para Paragraph do ReportLab.
    - 'delete': fundo vermelho suave / texto vermelho escuro tachado
    - 'insert': fundo verde suave / texto verde escuro em negrito
    - 'equal': texto padrão escapado
    """
    parts = []
    for seg in segments:
        txt = html.escape(seg.get('text', ''))
        if not txt:
            continue
        seg_type = seg.get('type', 'equal')
        if seg_type == 'delete':
            parts.append(f'<font backColor="#FEE2E2" color="#991B1B"><strike>{txt}</strike></font>')
        elif seg_type == 'insert':
            parts.append(f'<font backColor="#DCFCE7" color="#166534"><b>{txt}</b></font>')
        else:
            parts.append(txt)
    result = ''.join(parts).strip()
    return result if result else '<font color="#94A3B8"><i>(linha em branco)</i></font>'


def generate_pdf_diff_report(comparison_result: dict, output_path: str):
    """
    Gera um relatório PDF executivo e detalhado com a identidade visual ValidAí (#4FD580),
    contendo:
      1. Cabeçalho institucional com Logo ValidAí
      2. Quadro de Resumo Executivo e KPIs de Similaridade
      3. Visão Redline / Comparativa com adições em verde e remoções em vermelho
      4. Tabela Detalhada de Divergências Linha a Linha
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
    )

    summary = comparison_result['summary']
    diff_rows = comparison_result['diff_table_rows']
    redline_blocks = comparison_result['redline_blocks']

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="ValidAí - Relatório de Validação de Textos e Documentos"
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        'ValidAiTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=2
    )
    style_subtitle = ParagraphStyle(
        'ValidAiSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=8
    )
    style_section = ParagraphStyle(
        'ValidAiSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=6
    )
    style_cell = ParagraphStyle(
        'ValidAiCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#1E293B'),
        wordWrap='CJK'
    )
    style_cell_header = ParagraphStyle(
        'ValidAiCellHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )
    style_redline = ParagraphStyle(
        'ValidAiRedline',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#1E293B'),
        wordWrap='CJK'
    )

    story = []

    # 1. Cabeçalho com Logo ValidAí
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images', 'logo.png')
    header_title_para = Paragraph("ValidAí — Relatório de Comparação de Documentos", style_title)
    header_sub_para = Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')} • "
        f"Original: <b>{html.escape(summary['filename_a'])}</b> vs "
        f"Novo: <b>{html.escape(summary['filename_b'])}</b>",
        style_subtitle
    )

    if os.path.exists(logo_path):
        try:
            logo = RLImage(logo_path, width=38 * mm, height=12 * mm)
            header_table = Table(
                [[[header_title_para, header_sub_para], logo]],
                colWidths=[140 * mm, 42 * mm]
            )
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(header_table)
        except Exception:
            story.append(header_title_para)
            story.append(header_sub_para)
    else:
        story.append(header_title_para)
        story.append(header_sub_para)

    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#4FD580'), spaceBefore=4, spaceAfter=10))

    # 2. Quadro de Resumo Executivo (KPIs)
    story.append(Paragraph("1. Resumo Executivo e Indicadores (Analytics)", style_section))

    status_label = "DOCUMENTOS 100% IDÊNTICOS" if summary['is_identical'] else "DIVERGÊNCIAS ENCONTRADAS"
    kpi_data = [
        [
            Paragraph("<b>Indicador</b>", style_cell_header),
            Paragraph("<b>Resultado</b>", style_cell_header),
            Paragraph("<b>Indicador</b>", style_cell_header),
            Paragraph("<b>Resultado</b>", style_cell_header),
        ],
        [
            Paragraph("<b>Status da Validação</b>", style_cell),
            Paragraph(f"<b>{status_label}</b>", style_cell),
            Paragraph("<b>Índice de Similaridade</b>", style_cell),
            Paragraph(f"<b>{summary['similarity_pct']}%</b>", style_cell),
        ],
        [
            Paragraph("Linhas (Original vs Novo)", style_cell),
            Paragraph(f"{summary['total_lines_a']} vs {summary['total_lines_b']}", style_cell),
            Paragraph("Palavras (Original vs Novo)", style_cell),
            Paragraph(f"{summary['total_words_a']} vs {summary['total_words_b']}", style_cell),
        ],
        [
            Paragraph("Linhas Idênticas / Alteradas", style_cell),
            Paragraph(f"{summary['identical_lines_count']} idênticas / {summary['total_diff_blocks']} divergentes", style_cell),
            Paragraph("Palavras Adicionadas / Removidas", style_cell),
            Paragraph(
                f'<font color="#166534"><b>+{summary["words_added"]} adicionadas</b></font> / '
                f'<font color="#991B1B"><b>-{summary["words_removed"]} removidas</b></font>',
                style_cell
            ),
        ]
    ]

    kpi_table = Table(kpi_data, colWidths=[45 * mm, 46 * mm, 48 * mm, 43 * mm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4FD580')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # Legenda de cores
    legend_para = Paragraph(
        '<b>Legenda de Marcações:</b> &nbsp;&nbsp;'
        '<font backColor="#DCFCE7" color="#166534"><b> Texto Adicionado </b></font> &nbsp;&nbsp;&nbsp;'
        '<font backColor="#FEE2E2" color="#991B1B"><strike> Texto Removido </strike></font>',
        style_cell
    )
    story.append(legend_para)
    story.append(Spacer(1, 8))

    # 3. Tabela Detalhada de Divergências
    story.append(Paragraph("2. Detalhamento das Divergências Encontradas", style_section))

    if not diff_rows:
        story.append(Paragraph(
            '<font color="#166534"><b>Nenhuma diferença encontrada! Os dois documentos possuem conteúdo 100% idêntico.</b></font>',
            style_cell
        ))
    else:
        table_data = [[
            Paragraph("<b>#</b>", style_cell_header),
            Paragraph("<b>Tipo</b>", style_cell_header),
            Paragraph("<b>Linhas (Orig/Novo)</b>", style_cell_header),
            Paragraph("<b>Conteúdo no Documento Original</b>", style_cell_header),
            Paragraph("<b>Conteúdo no Documento Novo</b>", style_cell_header),
        ]]

        max_pdf_rows = 250
        for row in diff_rows[:max_pdf_rows]:
            if row['segments_a']:
                xml_a = _segments_to_reportlab_xml(row['segments_a'])
            else:
                xml_a = f'<font color="#94A3B8"><i>{html.escape(row["text_a"])}</i></font>'

            if row['segments_b']:
                xml_b = _segments_to_reportlab_xml(row['segments_b'])
            else:
                xml_b = f'<font color="#94A3B8"><i>{html.escape(row["text_b"])}</i></font>'

            c_type = row['change_type']
            if c_type == 'Adicionado':
                type_xml = '<font color="#166534"><b>+ Adicionado</b></font>'
            elif c_type == 'Removido':
                type_xml = '<font color="#991B1B"><b>- Removido</b></font>'
            else:
                type_xml = '<font color="#B45309"><b>~ Modificado</b></font>'

            table_data.append([
                Paragraph(str(row['diff_id']), style_cell),
                Paragraph(type_xml, style_cell),
                Paragraph(f"{row['line_a']} / {row['line_b']}", style_cell),
                Paragraph(xml_a, style_cell),
                Paragraph(xml_b, style_cell),
            ])

        diff_table = Table(
            table_data,
            colWidths=[10 * mm, 24 * mm, 22 * mm, 63 * mm, 63 * mm],
            repeatRows=1
        )
        diff_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4FD580')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(diff_table)

        if len(diff_rows) > max_pdf_rows:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<i>Exibindo as primeiras {max_pdf_rows} de {len(diff_rows)} divergências encontradas.</i>",
                style_subtitle
            ))

    # 4. Visão Redline Unificada (Documento Compilado com Marcações)
    story.append(Spacer(1, 10))
    story.append(Paragraph("3. Visão Redline Unificada (Documento com Alterações Marcadas)", style_section))

    redline_rows = []
    for blk in redline_blocks[:300]:
        line_label = f"{blk['line_a'] or '-'} → {blk['line_b'] or '-'}"
        xml_content = _segments_to_reportlab_xml(blk['segments'])
        redline_rows.append([
            Paragraph(f'<font color="#64748B">{line_label}</font>', style_cell),
            Paragraph(xml_content, style_redline)
        ])

    if redline_rows:
        redline_table = Table(redline_rows, colWidths=[22 * mm, 160 * mm])
        redline_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(redline_table)

    # Rodapé Institucional com Crédito de Arquitetura
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        '<i>Relatório gerado automaticamente por ValidAí (https://validai.app.br) • Arquitetura e Inteligência de Dados por Vinícius Alves.</i>',
        style_subtitle
    ))

    doc.build(story)

