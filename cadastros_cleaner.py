import os
import re
import unicodedata
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as OpenpyxlImage

import comparator

# ==============================================================================
# 1. VALIDAÇÃO MATEMÁTICA REAL DE CPF E CNPJ (MÓDULO 11)
# ==============================================================================

def clean_digits(val):
    """Extrai apenas os números de uma string ou valor."""
    if val is None or pd.isna(val):
        return ""
    # Trata valores float que vêm como 123456789.0
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return re.sub(r'\D', '', s)

def is_valid_cpf(cpf_str):
    """
    Validação real de CPF usando Módulo 11 da Receita Federal.
    Exige exatamente 11 dígitos numéricos e valida os dois dígitos verificadores.
    """
    digits = clean_digits(cpf_str)
    if len(digits) != 11:
        return False
    
    # Rejeita CPFs com todos os dígitos iguais (ex: 000.000.000-00, 111.111.111-11, etc.)
    if digits == digits[0] * 11:
        return False

    # Primeiro dígito verificador (pesos de 10 a 2)
    soma = sum(int(digits[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    if int(digits[9]) != d1:
        return False

    # Segundo dígito verificador (pesos de 11 a 2)
    soma = sum(int(digits[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    if int(digits[10]) != d2:
        return False

    return True

def is_valid_cnpj(cnpj_str):
    """
    Validação real de CNPJ usando Módulo 11 da Receita Federal.
    Exige exatamente 14 dígitos numéricos e valida os dois dígitos verificadores.
    """
    digits = clean_digits(cnpj_str)
    if len(digits) != 14:
        return False

    # Rejeita CNPJs com todos os dígitos iguais
    if digits == digits[0] * 14:
        return False

    # Primeiro dígito verificador
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(digits[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    d1 = 0 if resto < 2 else 11 - resto
    if int(digits[12]) != d1:
        return False

    # Segundo dígito verificador
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(digits[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    d2 = 0 if resto < 2 else 11 - resto
    if int(digits[13]) != d2:
        return False

    return True

def validate_and_clean_document(raw_val, auto_recover_zero=True):
    """
    Valida e higieniza CPF ou CNPJ.
    Retorna:
    - is_valid (bool)
    - doc_type ('CPF', 'CNPJ', 'INDEFINIDO')
    - digits (str com os dígitos tratados)
    - reason (motivo do erro, se houver)
    - recovered_zero (True se zeros à esquerda foram recuperados)
    """
    if raw_val is None or pd.isna(raw_val) or str(raw_val).strip() == "":
        return False, "INDEFINIDO", "", "Documento vazio ou não preenchido", False

    digits = clean_digits(raw_val)
    if not digits:
        return False, "INDEFINIDO", "", "Documento não contém caracteres numéricos", False

    recovered_zero = False

    # Recuperação de Zero à Esquerda (Erro clássico do Excel que remove o 0 inicial)
    if auto_recover_zero:
        # Se tiver 9 ou 10 dígitos, testa preencher com zeros até 11 e checa CPF
        if len(digits) in (9, 10):
            test_cpf = digits.zfill(11)
            if is_valid_cpf(test_cpf):
                return True, "CPF", test_cpf, None, True
        # Se tiver 12 ou 13 dígitos, testa preencher até 14 e checa CNPJ
        elif len(digits) in (12, 13):
            test_cnpj = digits.zfill(14)
            if is_valid_cnpj(test_cnpj):
                return True, "CNPJ", test_cnpj, None, True

    # Validação padrão por tamanho
    if len(digits) == 11:
        if digits == digits[0] * 11:
            return False, "CPF", digits, "Sequência repetida inválida (ex: 111.111.111-11)", False
        if is_valid_cpf(digits):
            return True, "CPF", digits, None, recovered_zero
        else:
            return False, "CPF", digits, "Dígito verificador do CPF inválido", False

    elif len(digits) == 14:
        if digits == digits[0] * 14:
            return False, "CNPJ", digits, "Sequência repetida inválida (todos dígitos iguais)", False
        if is_valid_cnpj(digits):
            return True, "CNPJ", digits, None, recovered_zero
        else:
            return False, "CNPJ", digits, "Dígito verificador do CNPJ inválido", False

    elif len(digits) < 11:
        return False, "CPF", digits, f"Quantidade insuficiente de dígitos ({len(digits)} dígitos em vez de 11)", False
    elif 11 < len(digits) < 14:
        return False, "CNPJ", digits, f"Tamanho intermediário inválido ({len(digits)} dígitos)", False
    else:
        return False, "INDEFINIDO", digits, f"Excesso de dígitos ({len(digits)} dígitos)", False

def format_document(digits, doc_type, use_mask=True):
    """Aplica máscara padrão em CPF ou CNPJ ou retorna apenas números."""
    if not digits:
        return ""
    if not use_mask:
        return digits
    if doc_type == "CPF" and len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    elif doc_type == "CNPJ" and len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return digits

# ==============================================================================
# 2. HIGIENIZAÇÃO DE NOMES E RAZÃO SOCIAL
# ==============================================================================

LOWERCASE_WORDS = {
    'da', 'de', 'do', 'das', 'dos', 'e', 'em', 'del', 'la', 'las', 'los', 'd\'', 'van', 'von'
}
UPPERCASE_WORDS = {
    's/a', 'sa', 'ltda', 'me', 'epp', 'eireli', 'ss', 's/s', 'cia', 'ii', 'iii', 'iv', 'v', 'vi'
}

def clean_name(raw_name):
    """
    Padroniza nomes e razão social para Title Case inteligente:
    - Converte 'JOAO DA SILVA' para 'João da Silva'
    - Preserva siglas como 'LTDA', 'ME', 'S/A'
    - Remove múltiplos espaços e caracteres estranhos
    - Detecta sujeiras como números ou caracteres inválidos
    """
    if raw_name is None or pd.isna(raw_name):
        return "", False, ["Nome não preenchido"]

    s = str(raw_name).strip()
    if not s:
        return "", False, ["Nome vazio"]

    issues = []
    # Detector de números no nome
    if re.search(r'\d', s):
        issues.append("Contém números no nome")

    # Detector de caracteres especiais estranhos
    if re.search(r'[\@\#\$\%\&\*\+\=\_\<\>\?\/\{\}\[\]\\]', s):
        issues.append("Contém caracteres especiais impróprios")

    # Remove espaços duplos
    tokens = [t for t in re.split(r'\s+', s) if t]
    if len(tokens) == 0:
        return "", False, ["Nome vazio"]

    formatted_tokens = []
    for i, token in enumerate(tokens):
        lower_t = token.lower()
        clean_token = re.sub(r'[\'\".,;:-]+$', '', lower_t)

        if lower_t in UPPERCASE_WORDS or clean_token in UPPERCASE_WORDS:
            formatted_tokens.append(token.upper())
        elif i > 0 and lower_t in LOWERCASE_WORDS:
            formatted_tokens.append(lower_t)
        else:
            # Capitaliza mantendo eventuais hífens (ex: Souza-Lima)
            parts = token.split('-')
            formatted_parts = [p.capitalize() for p in parts]
            formatted_tokens.append('-'.join(formatted_parts))

    result_name = " ".join(formatted_tokens)
    is_clean = len(issues) == 0
    return result_name, is_clean, issues

# ==============================================================================
# 3. VALIDAÇÃO E DETECÇÃO DE TYPOS EM E-MAILS
# ==============================================================================

TYPO_DOMAINS = {
    'gmial.com': 'gmail.com',
    'gamil.com': 'gmail.com',
    'gmai.com': 'gmail.com',
    'gmaill.com': 'gmail.com',
    'gmil.com': 'gmail.com',
    'gmeil.com': 'gmail.com',
    'hotmal.com': 'hotmail.com',
    'hotmial.com': 'hotmail.com',
    'hotmaill.com': 'hotmail.com',
    'hotmai.com': 'hotmail.com',
    'outlok.com': 'outlook.com',
    'outloo.com': 'outlook.com',
    'outllok.com': 'outlook.com',
    'yaho.com': 'yahoo.com',
    'yahooo.com': 'yahoo.com',
    'yhaoo.com': 'yahoo.com',
    'boll.com.br': 'bol.com.br',
    'uol.con.br': 'uol.com.br',
    'terra.con.br': 'terra.com.br',
}

EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
)

def clean_email(raw_email):
    """
    Padroniza e valida e-mail:
    - Converte para minúsculo e remove espaços
    - Valida formato RFC simplificado
    - Detecta typos em domínios comuns (@gmial.com -> @gmail.com)
    """
    if raw_email is None or pd.isna(raw_email):
        return "", False, "E-mail não preenchido", None

    email = str(raw_email).strip().lower()
    email = re.sub(r'\s+', '', email)

    if not email:
        return "", False, "E-mail vazio", None

    if '@' not in email:
        return email, False, "E-mail sem o caractere '@'", None

    parts = email.split('@')
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return email, False, "Estrutura de e-mail inválida", None

    user, domain = parts

    # Checagem de typo em domínio
    suggestion = None
    if domain in TYPO_DOMAINS:
        suggested_domain = TYPO_DOMAINS[domain]
        suggestion = f"{user}@{suggested_domain}"
        return email, False, f"Possível erro de digitação no domínio (@{domain} -> @{suggested_domain})", suggestion

    if domain.endswith('.con.br'):
        suggested_domain = domain[:-7] + '.com.br'
        suggestion = f"{user}@{suggested_domain}"
        return email, False, f"Extensão incorreta (.con.br -> .com.br)", suggestion

    if domain.endswith('.cmo'):
        suggested_domain = domain[:-4] + '.com'
        suggestion = f"{user}@{suggested_domain}"
        return email, False, f"Extensão incorreta (.cmo -> .com)", suggestion

    if not EMAIL_REGEX.match(email):
        return email, False, "Sintaxe de e-mail inválida ou extensão ausente", None

    return email, True, None, None

# ==============================================================================
# 4. VALIDAÇÃO E PADRONIZAÇÃO DE TELEFONE / CELULAR
# ==============================================================================

VALID_DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 24, 27, 28,
    31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49,
    51, 53, 54, 55,
    61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79,
    81, 82, 83, 84, 85, 86, 87, 88, 89,
    91, 92, 93, 94, 95, 96, 97, 98, 99
}

def clean_phone(raw_phone, output_format="mask"):
    """
    Padroniza e valida número de telefone ou celular no padrão brasileiro:
    - Remove caracteres não numéricos
    - Remove código DDI 55 se presente
    - Remove zero à esquerda do DDD (ex: 011 -> 11)
    - Valida DDD no Brasil
    - Formato 'mask': (11) 98765-4321 ou (11) 3456-7890
    - Formato 'digits': 5511987654321 (pronto para WhatsApp)
    """
    if raw_phone is None or pd.isna(raw_phone):
        return "", False, "Telefone não preenchido"

    digits = clean_digits(raw_phone)
    if not digits:
        return "", False, "Telefone não contém números"

    # Remove DDI 55 se vier com 12 ou 13 dígitos
    if len(digits) in (12, 13) and digits.startswith('55'):
        digits = digits[2:]

    # Remove 0 inicial no DDD se vier com 11 ou 12 dígitos
    if digits.startswith('0') and len(digits) in (11, 12):
        digits = digits[1:]

    # Validação do DDD
    if len(digits) < 2:
        return digits, False, "Telefone incompleto"

    try:
        ddd = int(digits[:2])
    except ValueError:
        return digits, False, "DDD inválido"

    if ddd not in VALID_DDDS:
        return digits, False, f"DDD {ddd} não existe no Brasil"

    # Checagem de comprimento
    # 11 dígitos = Celular (com 9º dígito)
    # 10 dígitos = Fixo (ou celular antigo sem 9)
    if len(digits) == 11:
        if digits[2] != '9':
            return digits, False, f"Celular com 11 dígitos deve iniciar com 9 após o DDD ({digits[:2]})"
        formatted = f"({digits[:2]}) {digits[2:7]}-{digits[7:]}" if output_format == "mask" else f"55{digits}"
        return formatted, True, None

    elif len(digits) == 10:
        # Fixo inicia tipicamente com 2, 3, 4 ou 5
        formatted = f"({digits[:2]}) {digits[2:6]}-{digits[6:]}" if output_format == "mask" else f"55{digits}"
        return formatted, True, None

    elif len(digits) < 10:
        return digits, False, f"Telefone incompleto com apenas {len(digits)} dígitos (falta DDD ou número)"
    else:
        return digits, False, f"Excesso de dígitos no telefone ({len(digits)} dígitos)"

def check_document_column_compatibility(series, col_name="Documento"):
    """
    Verifica se a coluna selecionada possui compatibilidade mínima com a referência de CPF/CNPJ.
    Se a coluna contiver valores numéricos curtos (ex: IDs com 4 a 6 dígitos como '555722'),
    ou textos sem números, ou nenhum registro compatível com os 11 ou 14 dígitos oficiais,
    retorna (is_compatible, error_message).
    """
    non_empty = [str(x).strip() for x in series if pd.notna(x) and str(x).strip() != ""]
    if not non_empty:
        return True, ""

    sample = non_empty[:250]
    compatible_count = 0
    incompatible_samples = []

    for val in sample:
        digits = clean_digits(val)
        # CPF válido/recuperável tem 9 a 11 dígitos; CNPJ tem 12 a 14 dígitos
        if len(digits) in (9, 10, 11, 12, 13, 14):
            compatible_count += 1
        else:
            if val not in incompatible_samples and len(incompatible_samples) < 3:
                incompatible_samples.append(val)

    ratio = compatible_count / len(sample)

    # Se menos de 10% dos valores possuem dígitos compatíveis com CPF/CNPJ
    # e encontramos valores claramente incompatíveis (ex: '555722', com 6 dígitos):
    if ratio < 0.10 and compatible_count < 2 and incompatible_samples:
        sample_val = incompatible_samples[0]
        digits_sample = clean_digits(sample_val)
        n_digits = len(digits_sample)
        if n_digits == 0:
            detail = f"o valor '{sample_val}' não contém caracteres numéricos"
        else:
            detail = f"o valor '{sample_val}' possui apenas {n_digits} dígitos numéricos"

        msg = (
            f"A coluna escolhida '{col_name}' não bate com a referência de CPF / CNPJ. "
            f"Na amostra analisada, {detail}, enquanto a referência oficial da Receita Federal "
            f"exige 11 dígitos para CPF (000.000.000-00) ou 14 dígitos para CNPJ (00.000.000/0000-00). "
            f"Por favor, selecione a coluna correspondente a Documento da sua base."
        )
        return False, msg

    return True, ""

def check_email_column_compatibility(series, col_name="E-mail"):
    """
    Verifica se a coluna selecionada possui compatibilidade mínima com a referência de E-mail.
    """
    non_empty = [str(x).strip() for x in series if pd.notna(x) and str(x).strip() != ""]
    if not non_empty:
        return True, ""

    sample = non_empty[:200]
    has_at_count = sum(1 for val in sample if '@' in val)
    ratio = has_at_count / len(sample)

    if ratio < 0.05 and has_at_count == 0:
        sample_val = sample[0]
        msg = (
            f"A coluna escolhida '{col_name}' não bate com a referência de E-mail. "
            f"Os valores encontrados (exemplo: '{sample_val}') não possuem o caractere '@' "
            f"nem o formato de endereço eletrônico (ex: usuario@empresa.com.br). "
            f"Por favor, revise o mapeamento das colunas."
        )
        return False, msg
    return True, ""

# ==============================================================================
# 5. PIPELINE PRINCIPAL DE HIGIENIZAÇÃO E AUDITORIA
# ==============================================================================

def process_cadastros(df, options):
    """
    Executa a auditoria e higienização completa da base de dados.
    options: dict contendo:
      - col_doc: nome da coluna de CPF/CNPJ (ou None)
      - col_name: nome da coluna de Nome (ou None)
      - col_email: nome da coluna de E-mail (ou None)
      - col_phone: nome da coluna de Telefone (ou None)
      - duplicate_keys: lista de colunas para checagem de duplicidade (ex: ['doc', 'email'])
      - doc_format: 'mask' ou 'digits'
      - auto_recover_zero: bool
      - name_title_case: bool
      - email_lowercase: bool
      - phone_format: 'mask' ou 'whatsapp'
      - remove_duplicates: bool
    """
    col_doc = options.get('col_doc')
    col_name = options.get('col_name')
    col_email = options.get('col_email')
    col_phone = options.get('col_phone')
    duplicate_keys = options.get('duplicate_keys', [])
    doc_format = options.get('doc_format', 'mask')
    auto_recover_zero = options.get('auto_recover_zero', True)
    name_title_case = options.get('name_title_case', True)
    email_lowercase = options.get('email_lowercase', True)
    phone_format = options.get('phone_format', 'mask')
    remove_duplicates = options.get('remove_duplicates', False)

    # Validação prévia de compatibilidade de referências para evitar mapeamentos incorretos
    if col_doc and col_doc in df.columns:
        is_compat, err_msg = check_document_column_compatibility(df[col_doc], col_doc)
        if not is_compat:
            raise ValueError(err_msg)

    if col_email and col_email in df.columns:
        is_compat, err_msg = check_email_column_compatibility(df[col_email], col_email)
        if not is_compat:
            raise ValueError(err_msg)

    total_rows = len(df)
    cols = list(df.columns)

    # Cópias para trabalho com conversão preventiva de tipos numéricos para object
    # para evitar conflitos de dtype (ex: 'Invalid value for dtype int64') ao atribuir máscaras/strings
    df_clean = df.copy()
    for c in df_clean.columns:
        df_clean[c] = df_clean[c].astype(object)
    
    # Rastreamento de inconsistências por linha
    invalid_docs = []
    suspicious_contacts = []
    auto_corrections_count = 0
    recovered_zeros_count = 0
    cpf_invalid_count = 0
    cnpj_invalid_count = 0
    invalid_emails_count = 0
    row_errors = {}  # r_idx -> list of error descriptions
    row_cell_errors = {}  # r_idx -> set of col_names with errors

    # Mapas de rastreamento de duplicidade
    duplicate_tracker = {}
    row_is_duplicate = {}

    for r_idx in range(total_rows):
        row_errors[r_idx] = []
        row_cell_errors[r_idx] = set()

    # --- 1. AUDITORIA E HIGIENIZAÇÃO DE DOCUMENTO (CPF/CNPJ) ---
    if col_doc and col_doc in df.columns:
        for r_idx, val in df[col_doc].items():
            raw_str = "" if pd.isna(val) else str(val).strip()
            is_valid, doc_type, digits, reason, recovered_zero = validate_and_clean_document(
                val, auto_recover_zero=auto_recover_zero
            )
            
            # Formata documento
            formatted_doc = format_document(digits, doc_type, use_mask=(doc_format == 'mask'))

            # Se houve recuperação de zero ou formatação alterada
            if raw_str and formatted_doc and raw_str != formatted_doc:
                auto_corrections_count += 1
            if recovered_zero:
                auto_corrections_count += 1
                recovered_zeros_count += 1

            df_clean.at[r_idx, col_doc] = formatted_doc

            if not is_valid:
                if doc_type == 'CPF' or 'CPF' in str(reason):
                    cpf_invalid_count += 1
                elif doc_type == 'CNPJ' or 'CNPJ' in str(reason):
                    cnpj_invalid_count += 1
                else:
                    cpf_invalid_count += 1

                row_errors[r_idx].append(f"Documento ({col_doc}): {reason}")
                row_cell_errors[r_idx].add(col_doc)
                name_val = df.at[r_idx, col_name] if (col_name and col_name in df.columns) else ""
                invalid_docs.append({
                    'row': r_idx + 1,
                    'name': "" if pd.isna(name_val) else str(name_val),
                    'original': raw_str,
                    'cleaned': formatted_doc,
                    'reason': reason
                })

    # --- 2. AUDITORIA E HIGIENIZAÇÃO DE NOME ---
    if col_name and col_name in df.columns:
        for r_idx, val in df[col_name].items():
            raw_str = "" if pd.isna(val) else str(val).strip()
            cleaned, is_clean, issues = clean_name(val)
            
            if name_title_case and raw_str and raw_str != cleaned:
                auto_corrections_count += 1
                df_clean.at[r_idx, col_name] = cleaned
            elif not name_title_case:
                df_clean.at[r_idx, col_name] = raw_str

            if not is_clean:
                msg = ", ".join(issues)
                row_errors[r_idx].append(f"Nome ({col_name}): {msg}")
                row_cell_errors[r_idx].add(col_name)

    # --- 3. AUDITORIA E HIGIENIZAÇÃO DE E-MAIL ---
    if col_email and col_email in df.columns:
        for r_idx, val in df[col_email].items():
            raw_str = "" if pd.isna(val) else str(val).strip()
            cleaned, is_valid, reason, suggestion = clean_email(val)

            if email_lowercase and raw_str and raw_str != cleaned:
                auto_corrections_count += 1
                df_clean.at[r_idx, col_email] = cleaned

            if not is_valid:
                invalid_emails_count += 1
                row_errors[r_idx].append(f"E-mail ({col_email}): {reason}")
                row_cell_errors[r_idx].add(col_email)
                name_val = df.at[r_idx, col_name] if (col_name and col_name in df.columns) else ""
                suspicious_contacts.append({
                    'row': r_idx + 1,
                    'name': "" if pd.isna(name_val) else str(name_val),
                    'type': 'E-mail',
                    'original': raw_str,
                    'cleaned': cleaned,
                    'issue': reason,
                    'suggestion': suggestion or "Revisar com o titular"
                })

    # --- 4. AUDITORIA E HIGIENIZAÇÃO DE TELEFONE ---
    if col_phone and col_phone in df.columns:
        for r_idx, val in df[col_phone].items():
            raw_str = "" if pd.isna(val) else str(val).strip()
            cleaned, is_valid, reason = clean_phone(val, output_format=phone_format)

            if raw_str and raw_str != cleaned:
                auto_corrections_count += 1
                df_clean.at[r_idx, col_phone] = cleaned

            if not is_valid:
                row_errors[r_idx].append(f"Telefone ({col_phone}): {reason}")
                row_cell_errors[r_idx].add(col_phone)
                name_val = df.at[r_idx, col_name] if (col_name and col_name in df.columns) else ""
                suspicious_contacts.append({
                    'row': r_idx + 1,
                    'name': "" if pd.isna(name_val) else str(name_val),
                    'type': 'Telefone',
                    'original': raw_str,
                    'cleaned': cleaned,
                    'issue': reason,
                    'suggestion': "Corrigir DDD ou acrescentar 9º dígito"
                })

    # --- 5. CHECAGEM DE DUPLICIDADE ---
    # Colunas de busca de duplicidade
    cols_to_check = []
    if 'doc' in duplicate_keys and col_doc and col_doc in df.columns:
        cols_to_check.append(col_doc)
    if 'email' in duplicate_keys and col_email and col_email in df.columns:
        cols_to_check.append(col_email)
    if 'phone' in duplicate_keys and col_phone and col_phone in df.columns:
        cols_to_check.append(col_phone)
    # Se usuário especificou colunas avulsas
    for k in duplicate_keys:
        if k not in ('doc', 'email', 'phone') and k in df.columns and k not in cols_to_check:
            cols_to_check.append(k)

    duplicates_list = []
    duplicate_rows_indices = set()

    for col in cols_to_check:
        val_map = {}  # norm_val -> list of (r_idx, original_val)
        for r_idx in range(total_rows):
            raw = df.at[r_idx, col]
            if raw is None or pd.isna(raw):
                continue
            # Normaliza valor para comparação de duplicados
            norm_val = str(raw).strip().lower()
            if col == col_doc:
                norm_val = clean_digits(norm_val)
            if not norm_val:
                continue

            if norm_val not in val_map:
                val_map[norm_val] = []
            val_map[norm_val].append(r_idx)

        # Filtra apenas os repetidos
        for norm_val, rows in val_map.items():
            if len(rows) > 1:
                # O primeiro registro é mantido, os seguintes são marcados como duplicados
                for dup_r in rows[1:]:
                    duplicate_rows_indices.add(dup_r)
                    row_errors[dup_r].append(f"Registro duplicado na coluna [{col}] (Primeira ocorrência na Linha {rows[0] + 1})")
                    row_cell_errors[dup_r].add(col)

                # Amostra para a tabela de duplicados
                sample_name = ""
                if col_name and col_name in df.columns:
                    val_n = df.at[rows[0], col_name]
                    sample_name = "" if pd.isna(val_n) else str(val_n)

                duplicates_list.append({
                    'column': col,
                    'value': str(df.at[rows[0], col]),
                    'count': len(rows),
                    'lines': [r + 1 for r in rows],
                    'sample_name': sample_name
                })

    # Remove duplicados da base higienizada se solicitado
    if remove_duplicates and duplicate_rows_indices:
        df_clean = df_clean.drop(index=list(duplicate_rows_indices)).reset_index(drop=True)

    # --- 6. GERAÇÃO DO DATAFRAME DE AUDITORIA ---
    df_audit = df.copy()
    statuses = []
    motivos = []
    valid_count = 0

    for r_idx in range(total_rows):
        errs = row_errors.get(r_idx, [])
        if not errs:
            statuses.append("OK")
            motivos.append("Conforme")
            valid_count += 1
        else:
            # Sintetiza status
            is_doc_err = any("Documento" in e for e in errs)
            is_dup = any("duplicado" in e for e in errs)
            is_contact_err = any("E-mail" in e or "Telefone" in e for e in errs)

            tags = []
            if is_doc_err:
                tags.append("DOCUMENTO_INVALIDO")
            if is_dup:
                tags.append("DUPLICADO")
            if is_contact_err:
                tags.append("CONTATO_SUSPEITO")
            if not tags:
                tags.append("INCONSISTENTE")

            statuses.append(" / ".join(tags))
            motivos.append("; ".join(errs))

    df_audit['Status_Validacao'] = statuses
    df_audit['Detalhes_Auditoria'] = motivos

    # --- 7. MONTAGEM DO RESUMO (KPIS) ---
    valid_percentage = round((valid_count / total_rows * 100), 1) if total_rows > 0 else 100.0

    summary = {
        'total_rows': total_rows,
        'valid_count': valid_count,
        'valid_percentage': valid_percentage,
        'invalid_docs_count': len(invalid_docs),
        'duplicates_count': len(duplicate_rows_indices),
        'suspicious_contacts_count': len(suspicious_contacts),
        'auto_corrections_count': auto_corrections_count,
        'clean_rows_count': len(df_clean),
        'removed_duplicates_count': len(duplicate_rows_indices) if remove_duplicates else 0,
        'inconsistency_breakdown': {
            'cpf_invalid': cpf_invalid_count,
            'cnpj_invalid': cnpj_invalid_count,
            'missing_zeros': recovered_zeros_count,
            'invalid_emails': invalid_emails_count,
            'duplicate_rows': len(duplicate_rows_indices)
        }
    }

    # Prévia da base higienizada (primeiras 60 linhas)
    preview_clean_rows = []
    for i, row in df_clean.head(60).iterrows():
        r_dict = {'_row_num': i + 1}
        for c in df_clean.columns:
            v = row[c]
            r_dict[c] = "" if pd.isna(v) else str(v)
        preview_clean_rows.append(r_dict)

    return {
        'summary': summary,
        'invalid_docs': invalid_docs[:300],  # Amostra de até 300 para renderização rápida
        'duplicates': duplicates_list[:300],
        'suspicious_contacts': suspicious_contacts[:300],
        'preview_clean': preview_clean_rows,
        'clean_columns': list(df_clean.columns),
        'df_clean': df_clean,
        'df_audit': df_audit,
        'row_cell_errors': row_cell_errors
    }

# ==============================================================================
# 6. GERAÇÃO DOS ARQUIVOS EXCEL (BASE HIGIENIZADA E RELATÓRIO PINTADO)
# ==============================================================================

COLOR_GREEN = "4FD580"
COLOR_DARK = "0B1F13"
COLOR_GRAY_BG = "F8FAFC"
COLOR_ERROR_BG = "FEE2E2"
COLOR_ERROR_TEXT = "B91C1C"
COLOR_WARN_BG = "FEF3C7"
COLOR_WARN_TEXT = "B45309"
COLOR_CONTACT_BG = "FFEDD5"
COLOR_CONTACT_TEXT = "C2410C"
COLOR_SUCCESS_BG = "DCFCE7"
COLOR_SUCCESS_TEXT = "15803D"

def generate_clean_excel(df_clean, output_path):
    """
    Gera a planilha 100% higienizada e pronta para uso:
    - Cabeçalho verde ValidAí (#4FD580)
    - Células formatadas como texto para evitar perda de zeros
    - Largura das colunas auto-ajustada
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Base Higienizada"
    ws.views.sheetView[0].showGridLines = True

    header_font = Font(name="Calibri", size=11, bold=True, color=COLOR_DARK)
    header_fill = PatternFill(start_color=COLOR_GREEN, end_color=COLOR_GREEN, fill_type="solid")
    regular_font = Font(name="Calibri", size=10)
    zebra_fill = PatternFill(start_color=COLOR_GRAY_BG, end_color=COLOR_GRAY_BG, fill_type="solid")
    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )
    align_left = Alignment(horizontal='left', vertical='center')

    # Cabeçalho
    for col_idx, col_name in enumerate(df_clean.columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=str(col_name))
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_left
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    # Dados
    for r_idx, row in df_clean.iterrows():
        row_num = r_idx + 2
        for col_idx, col_name in enumerate(df_clean.columns, 1):
            val = row[col_name]
            val_str = "" if pd.isna(val) else str(val)
            cell = ws.cell(row=row_num, column=col_idx, value=val_str)
            cell.font = regular_font
            cell.border = thin_border
            cell.alignment = align_left
            cell.number_format = '@'  # Força formato texto
            if row_num % 2 == 1:
                cell.fill = zebra_fill
        ws.row_dimensions[row_num].height = 20

    # Auto ajuste de larguras
    for col_idx, col_name in enumerate(df_clean.columns, 1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(col_name))
        for row_num in range(2, min(len(df_clean) + 2, 100)):
            val = ws.cell(row=row_num, column=col_idx).value
            if val:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 14), 50)

    try:
        ws.auto_filter.ref = ws.dimensions
    except Exception:
        pass

    wb.save(output_path)

def generate_audit_excel(df_audit, summary, invalid_docs, duplicates, suspicious_contacts, row_cell_errors, output_path):
    """
    Gera o relatório de auditoria profissional:
    - Aba 1: Resumo Executivo da Auditoria (com Logo ValidAí e KPIs)
    - Aba 2: Base Completa Auditada (com células destacadas em vermelho/amarelo/laranja)
    - Aba 3: Registros Inconsistentes (Apenas as linhas com erro para correção rápida)
    """
    wb = openpyxl.Workbook()

    # ==========================================
    # ABA 1: RESUMO DA AUDITORIA
    # ==========================================
    ws_res = wb.active
    ws_res.title = "Resumo da Auditoria"
    ws_res.views.sheetView[0].showGridLines = True

    # Inserção da logo ValidAí
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

    # Título
    title_cell = ws_res.cell(row=4, column=1, value="RELATÓRIO DE AUDITORIA E HIGIENIZAÇÃO DE CADASTROS")
    title_cell.font = Font(name="Calibri", size=14, bold=True, color=COLOR_DARK)

    sub_cell = ws_res.cell(row=5, column=1, value="ValidAí • Plataforma de Validação e Integridade de Dados")
    sub_cell.font = Font(name="Calibri", size=10, italic=True, color="64748B")

    # Tabela de KPIs
    kpi_header_fill = PatternFill(start_color=COLOR_GREEN, end_color=COLOR_GREEN, fill_type="solid")
    kpi_header_font = Font(name="Calibri", size=11, bold=True, color=COLOR_DARK)
    card_title_font = Font(name="Calibri", size=10, bold=True, color="334155")
    card_value_font = Font(name="Calibri", size=12, bold=True, color=COLOR_DARK)
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    kpis = [
        ("Total de Registros Analisados", f"{summary['total_rows']:,}".replace(',', '.'), None),
        ("Cadastros 100% Válidos", f"{summary['valid_count']:,} ({summary['valid_percentage']}%)".replace(',', '.'), COLOR_SUCCESS_BG),
        ("CPFs / CNPJs Inválidos", f"{summary['invalid_docs_count']:,}".replace(',', '.'), COLOR_ERROR_BG),
        ("Registros Duplicados", f"{summary['duplicates_count']:,}".replace(',', '.'), COLOR_WARN_BG),
        ("E-mails / Telefones com Inconsistências", f"{summary['suspicious_contacts_count']:,}".replace(',', '.'), COLOR_CONTACT_BG),
        ("Correções Automáticas Aplicadas", f"{summary['auto_corrections_count']:,}".replace(',', '.'), "E0F2FE")
    ]

    ws_res.cell(row=7, column=1, value="MÉTRICA / INDICADOR").font = kpi_header_font
    ws_res.cell(row=7, column=1).fill = kpi_header_fill
    ws_res.cell(row=7, column=1).border = thin_border

    ws_res.cell(row=7, column=2, value="QUANTIDADE / TAXA").font = kpi_header_font
    ws_res.cell(row=7, column=2).fill = kpi_header_fill
    ws_res.cell(row=7, column=2).border = thin_border

    for idx, (label, val, bg_color) in enumerate(kpis, 8):
        c1 = ws_res.cell(row=idx, column=1, value=label)
        c1.font = card_title_font
        c1.border = thin_border

        c2 = ws_res.cell(row=idx, column=2, value=val)
        c2.font = card_value_font
        c2.border = thin_border
        c2.alignment = Alignment(horizontal='center')
        if bg_color:
            c2.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
        ws_res.row_dimensions[idx].height = 22

    ws_res.column_dimensions['A'].width = 44
    ws_res.column_dimensions['B'].width = 28

    # ==========================================
    # ABA 2: BASE COMPLETA AUDITADA (COM CORES)
    # ==========================================
    ws_data = wb.create_sheet(title="Base Auditada Completa")
    ws_data.views.sheetView[0].showGridLines = True

    fill_error = PatternFill(start_color=COLOR_ERROR_BG, end_color=COLOR_ERROR_BG, fill_type="solid")
    font_error = Font(name="Calibri", size=10, bold=True, color=COLOR_ERROR_TEXT)

    fill_warn = PatternFill(start_color=COLOR_WARN_BG, end_color=COLOR_WARN_BG, fill_type="solid")
    font_warn = Font(name="Calibri", size=10, bold=True, color=COLOR_WARN_TEXT)

    fill_contact = PatternFill(start_color=COLOR_CONTACT_BG, end_color=COLOR_CONTACT_BG, fill_type="solid")
    font_contact = Font(name="Calibri", size=10, bold=True, color=COLOR_CONTACT_TEXT)

    fill_success = PatternFill(start_color=COLOR_SUCCESS_BG, end_color=COLOR_SUCCESS_BG, fill_type="solid")
    font_success = Font(name="Calibri", size=10, bold=True, color=COLOR_SUCCESS_TEXT)

    regular_font = Font(name="Calibri", size=10)
    zebra_fill = PatternFill(start_color=COLOR_GRAY_BG, end_color=COLOR_GRAY_BG, fill_type="solid")
    align_left = Alignment(horizontal='left', vertical='center')
    align_center = Alignment(horizontal='center', vertical='center')

    # Cabeçalhos: Linha | Status | Motivos | ...Colunas
    data_headers = ['Linha', 'Status_Validacao', 'Detalhes_Auditoria'] + [c for c in df_audit.columns if c not in ('Status_Validacao', 'Detalhes_Auditoria')]

    for col_idx, col_name in enumerate(data_headers, 1):
        cell = ws_data.cell(row=1, column=col_idx, value=col_name)
        cell.font = kpi_header_font
        cell.fill = kpi_header_fill
        cell.alignment = align_left
        cell.border = thin_border
    ws_data.row_dimensions[1].height = 28

    for r_idx, row in df_audit.iterrows():
        row_num = r_idx + 2
        status = row['Status_Validacao']
        detalhes = row['Detalhes_Auditoria']
        err_cols = row_cell_errors.get(r_idx, set())

        # Coluna 1: Linha
        c_line = ws_data.cell(row=row_num, column=1, value=r_idx + 1)
        c_line.font = regular_font
        c_line.border = thin_border
        c_line.alignment = align_center

        # Coluna 2: Status
        c_status = ws_data.cell(row=row_num, column=2, value=status)
        c_status.border = thin_border
        c_status.alignment = align_center
        if status == "OK":
            c_status.fill = fill_success
            c_status.font = font_success
        elif "DOCUMENTO" in status:
            c_status.fill = fill_error
            c_status.font = font_error
        elif "DUPLICADO" in status:
            c_status.fill = fill_warn
            c_status.font = font_warn
        else:
            c_status.fill = fill_contact
            c_status.font = font_contact

        # Coluna 3: Detalhes
        c_det = ws_data.cell(row=row_num, column=3, value=detalhes)
        c_det.font = regular_font
        c_det.border = thin_border
        c_det.alignment = align_left

        # Colunas de dados reais
        for col_idx, col_name in enumerate(data_headers[3:], 4):
            val = row[col_name]
            val_str = "" if pd.isna(val) else str(val)
            cell = ws_data.cell(row=row_num, column=col_idx, value=val_str)
            cell.font = regular_font
            cell.border = thin_border
            cell.alignment = align_left
            cell.number_format = '@'

            # Pinta de vermelho/amarelo se esta célula específica tiver erro
            if col_name in err_cols:
                cell.fill = fill_error
                cell.font = font_error
            elif row_num % 2 == 1:
                cell.fill = zebra_fill

        ws_data.row_dimensions[row_num].height = 20

    # Auto ajuste de larguras na aba de dados
    ws_data.column_dimensions['A'].width = 10
    ws_data.column_dimensions['B'].width = 24
    ws_data.column_dimensions['C'].width = 42
    for col_idx, col_name in enumerate(data_headers[3:], 4):
        col_letter = get_column_letter(col_idx)
        ws_data.column_dimensions[col_letter].width = max(len(str(col_name)) + 4, 15)

    try:
        ws_data.auto_filter.ref = ws_data.dimensions
    except Exception:
        pass

    # ==========================================
    # ABA 3: APENAS INCONSISTÊNCIAS E DUPLICADOS
    # ==========================================
    ws_err = wb.create_sheet(title="Inconsistências e Duplicados")
    ws_err.views.sheetView[0].showGridLines = True

    err_headers = ['Linha', 'Tipo_Inconsistencia', 'Detalhes_do_Erro', 'Acao_Recomendada']
    for col_idx, col_name in enumerate(err_headers, 1):
        cell = ws_err.cell(row=1, column=col_idx, value=col_name)
        cell.font = kpi_header_font
        cell.fill = kpi_header_fill
        cell.alignment = align_left
        cell.border = thin_border
    ws_err.row_dimensions[1].height = 28

    err_row_idx = 2
    for r_idx, row in df_audit.iterrows():
        status = row['Status_Validacao']
        if status != "OK":
            detalhes = row['Detalhes_Auditoria']
            ws_err.cell(row=err_row_idx, column=1, value=r_idx + 1).alignment = align_center
            ws_err.cell(row=err_row_idx, column=2, value=status).font = font_error
            ws_err.cell(row=err_row_idx, column=3, value=detalhes).alignment = align_left
            
            recom = "Verificar com o cliente/titular"
            if "DUPLICADO" in status:
                recom = "Remover registro duplicado ou manter o mais atual"
            elif "DOCUMENTO" in status:
                recom = "Solicitar CPF/CNPJ correto da Receita Federal"
            elif "E-mail" in status:
                recom = "Corrigir digitação do e-mail"
            ws_err.cell(row=err_row_idx, column=4, value=recom).alignment = align_left

            for c in range(1, 5):
                ws_err.cell(row=err_row_idx, column=c).border = thin_border
                ws_err.cell(row=err_row_idx, column=c).font = regular_font

            ws_err.row_dimensions[err_row_idx].height = 20
            err_row_idx += 1

    ws_err.column_dimensions['A'].width = 10
    ws_err.column_dimensions['B'].width = 26
    ws_err.column_dimensions['C'].width = 50
    ws_err.column_dimensions['D'].width = 40

    try:
        ws_err.auto_filter.ref = ws_err.dimensions
    except Exception:
        pass

    wb.save(output_path)


def create_demo_file(output_dir):
    """
    Cria uma planilha Excel (.xlsx) com uma base cadastral mista e realista para demonstração
    do Higienizador de Cadastros.
    Contém:
    - 11 registros com clientes e empresas
    - CPFs e CNPJs válidos (formatados e sem máscara)
    - 1 CPF com zero à esquerda ausente (10 dígitos - recuperável pelo Módulo 11)
    - 1 CPF matematicamente inválido (dígito verificador incorreto)
    - 1 CNPJ matematicamente inválido
    - 1 registro duplicado (mesmo CPF em duas linhas)
    - 1 e-mail com erro de digitação/sintaxe (sem domínio TLD)
    - Nomes com formatação despadronizada (maiúsculas excessivas e múltiplos espaços)
    - Telefones com e sem formatação
    """
    filepath = os.path.join(output_dir, "Base_Clientes_Para_Higienizar.xlsx")

    demo_data = [
        {
            "ID_Cliente": "CLI-1001",
            "Nome_Cliente": "   MARCOS   VINICIUS DE SOUZA   ",
            "CPF_CNPJ": "52998224725",  # CPF válido sem máscara (529.982.247-25)
            "Email": "marcos.souza@empresa.com.br",
            "Telefone_WhatsApp": "11987654321",
            "Cidade_UF": "São Paulo/SP"
        },
        {
            "ID_Cliente": "CLI-1002",
            "Nome_Cliente": "JULIANA FERREIRA LIMA ADVOCACIA",
            "CPF_CNPJ": "11.144.980/0001-12",  # CNPJ válido formatado
            "Email": "contato@julianalima.adv.br",
            "Telefone_WhatsApp": "(11) 3245-8899",
            "Cidade_UF": "Campinas/SP"
        },
        {
            "ID_Cliente": "CLI-1003",
            "Nome_Cliente": "carlos eduardo almeida silva",
            "CPF_CNPJ": "4589214750",  # CPF com zero à esquerda ausente (10 dígitos, vira 045.892.147-50)
            "Email": "carlos.almeida@email.com",
            "Telefone_WhatsApp": "21988776655",
            "Cidade_UF": "Rio de Janeiro/RJ"
        },
        {
            "ID_Cliente": "CLI-1004",
            "Nome_Cliente": "BEATRIZ SANTOS OLIVEIRA",
            "CPF_CNPJ": "123.456.789-00",  # CPF Inválido (dígitos verificadores incorretos)
            "Email": "beatriz.oliveira@gmail.com",
            "Telefone_WhatsApp": "(31) 99123-4567",
            "Cidade_UF": "Belo Horizonte/MG"
        },
        {
            "ID_Cliente": "CLI-1005",
            "Nome_Cliente": "AUTO MECANICA PROGRESSO LTDA",
            "CPF_CNPJ": "11.222.333/0001-99",  # CNPJ Inválido
            "Email": "financeiro@mecanicaprogresso.com.br",
            "Telefone_WhatsApp": "4133445566",
            "Cidade_UF": "Curitiba/PR"
        },
        {
            "ID_Cliente": "CLI-1006",
            "Nome_Cliente": "FERNANDA COSTA RIBEIRO",
            "CPF_CNPJ": "21589347862",  # CPF Válido
            "Email": "fernanda.costa@empresa",  # E-mail inválido (sem extensão de domínio)
            "Telefone_WhatsApp": "(61) 98111-2233",
            "Cidade_UF": "Brasília/DF"
        },
        {
            "ID_Cliente": "CLI-1007",
            "Nome_Cliente": "MARCOS VINICIUS DE SOUZA (FILIAL)",
            "CPF_CNPJ": "52998224725",  # Duplicado com CLI-1001!
            "Email": "marcos.souza@empresa.com.br",
            "Telefone_WhatsApp": "11987654321",
            "Cidade_UF": "São Paulo/SP"
        },
        {
            "ID_Cliente": "CLI-1008",
            "Nome_Cliente": "CAMILA ROCHA BARBOSA",
            "CPF_CNPJ": "87541236900",  # CPF Válido
            "Email": "camila.rocha@techcorp.io",
            "Telefone_WhatsApp": "71987651234",
            "Cidade_UF": "Salvador/BA"
        },
        {
            "ID_Cliente": "CLI-1009",
            "Nome_Cliente": "DISTRIBUIDORA ALIANCA NORTE S.A.",
            "CPF_CNPJ": "33.000.167/0001-01",  # CNPJ Válido
            "Email": "suprimentos@aliancanorte.com.br",
            "Telefone_WhatsApp": "(81) 3456-7890",
            "Cidade_UF": "Recife/PE"
        },
        {
            "ID_Cliente": "CLI-1010",
            "Nome_Cliente": "LUCAS SILVEIRA MENDES",
            "CPF_CNPJ": "04589214750",  # CPF Válido com zero à esquerda
            "Email": "lucas.mendes@provedor.com.br",
            "Telefone_WhatsApp": "48999887766",
            "Cidade_UF": "Florianópolis/SC"
        },
        {
            "ID_Cliente": "CLI-1011",
            "Nome_Cliente": "INDÚSTRIA METALÚRGICA SUL LTDA",
            "CPF_CNPJ": "04.123.456/0001-08",  # CNPJ Válido
            "Email": "fiscal@metalurgicasul.ind.br",
            "Telefone_WhatsApp": "(51) 3322-1100",
            "Cidade_UF": "Porto Alegre/RS"
        }
    ]

    df = pd.DataFrame(demo_data)
    df.to_excel(filepath, index=False)
    return filepath, "Base_Clientes_Para_Higienizar.xlsx"

