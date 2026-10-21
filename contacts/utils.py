import io
import csv
import re
import logging
import zipfile
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

# Mapeo de sinónimos para detectar columnas sin importar cómo las haya nombrado el usuario
COLUMN_SYNONYMS = {
    'email': [
        'email', 'correo', 'correo electronico', 'correo electrónico', 
        'correo_electronico', 'e-mail', 'mail', 'contacto', 'direccion de correo',
        'dirección de correo', 'email address', 'e_mail'
    ],
    'first_name': [
        'nombre', 'name', 'first_name', 'primer nombre', 'nombres', 
        'nombre de pila', 'first name'
    ],
    'last_name': [
        'apellido', 'apellidos', 'last_name', 'surname', 'primer apellido', 
        'segundo apellido', 'last name'
    ],
    'company': [
        'empresa', 'company', 'compañia', 'compañía', 'organizacion', 
        'organización', 'negocio', 'emprendimiento', 'razon social', 'razón social'
    ],
    'phone': [
        'telefono', 'teléfono', 'phone', 'celular', 'movil', 'móvil', 
        'whatsapp', 'fono', 'telefono contacto', 'teléfono contacto'
    ],
}

def normalize_header(header_str):
    """Limpia y normaliza un encabezado para comparación."""
    if not header_str:
        return ''
    s = str(header_str).strip().lower()
    # Eliminar tildes básicas para matcheo robusto
    s_clean = s.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    for field, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            syn_clean = syn.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
            if s_clean == syn_clean:
                return field
    return s_clean

def col2num(col_str):
    """Convierte letras de columna de Excel (A, B, AA...) a índice 0-based."""
    num = 0
    for char in col_str.upper():
        if 'A' <= char <= 'Z':
            num = num * 26 + (ord(char) - ord('A')) + 1
    return max(0, num - 1)

def parse_csv_content(content_bytes):
    """Decodifica y parsea un archivo CSV soportando múltiples delimitadores y encodings."""
    text = None
    for enc in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            text = content_bytes.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if text is None:
        return None, "No se pudo leer la codificación del archivo CSV. Asegúrate de que esté en formato UTF-8 o texto estándar."

    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return [], None

    # Detección inteligente de delimitador
    sample = '\n'.join(lines[:10])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        delimiter = dialect.delimiter
    except Exception:
        # Fallback analizando la primera línea
        first_line = lines[0]
        if ';' in first_line and first_line.count(';') >= first_line.count(','):
            delimiter = ';'
        elif '\t' in first_line:
            delimiter = '\t'
        elif '|' in first_line:
            delimiter = '|'
        else:
            delimiter = ','

    reader = csv.reader(lines, delimiter=delimiter)
    rows = []
    for r in reader:
        if any(cell.strip() for cell in r):
            rows.append([cell.strip() for cell in r])
    return rows, None

def parse_xlsx_with_openpyxl(content_bytes):
    """Intenta parsear un archivo XLSX usando openpyxl (muy rápido y bajo consumo de memoria)."""
    try:
        import openpyxl
        buf = io.BytesIO(content_bytes)
        wb = openpyxl.load_workbook(buf, read_only=True, data_only=True)
        sheet = wb.active
        rows = []
        for row in sheet.iter_rows(values_only=True):
            if row and any(v is not None and str(v).strip() for v in row):
                rows.append([str(v).strip() if v is not None else '' for v in row])
        wb.close()
        return rows, None
    except ImportError:
        logger.info("openpyxl no está disponible, usando parser XML nativo.")
        return None, "openpyxl_not_installed"
    except Exception as e:
        logger.warning(f"Error al leer XLSX con openpyxl ({e}), usando fallback nativo.")
        return None, str(e)

def parse_xlsx_with_stdlib(content_bytes):
    """Parser puro de la librería estándar (zipfile + xml) para archivos XLSX."""
    try:
        buf = io.BytesIO(content_bytes)
        with zipfile.ZipFile(buf, 'r') as z:
            # 1. Extraer tabla de cadenas compartidas (sharedStrings.xml)
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                sst_root = ET.fromstring(z.read('xl/sharedStrings.xml'))
                ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in sst_root.findall('.//ns:si', ns):
                    t_parts = [t.text for t in si.findall('.//ns:t', ns) if t.text]
                    shared_strings.append(''.join(t_parts))

            # 2. Encontrar la primera hoja de cálculo
            sheet_names = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
            if not sheet_names:
                return None, "No se encontró ninguna hoja válida dentro del libro Excel."
            sheet_xml = z.read(sorted(sheet_names)[0])
            sheet_root = ET.fromstring(sheet_xml)
            ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

            rows = []
            for row_el in sheet_root.findall('.//ns:row', ns):
                row_dict = {}
                max_col = -1
                for c_el in row_el.findall('ns:c', ns):
                    r_attr = c_el.get('r', '')
                    col_match = re.match(r'([A-Za-z]+)', r_attr)
                    col_idx = col2num(col_match.group(1)) if col_match else (max_col + 1)
                    
                    t_attr = c_el.get('t')
                    v_el = c_el.find('ns:v', ns)
                    val = v_el.text if v_el is not None and v_el.text is not None else ''

                    if t_attr == 's' and val.isdigit():
                        idx = int(val)
                        val = shared_strings[idx] if idx < len(shared_strings) else val
                    elif t_attr == 'inlineStr':
                        is_el = c_el.find('.//ns:t', ns)
                        val = is_el.text if is_el is not None and is_el.text else ''

                    val_str = str(val).strip()
                    row_dict[col_idx] = val_str
                    if col_idx > max_col:
                        max_col = col_idx

                if max_col >= 0:
                    row_list = [row_dict.get(i, '') for i in range(max_col + 1)]
                    if any(row_list):
                        rows.append(row_list)

            return rows, None
    except Exception as e:
        logger.error(f"Fallo parser stdlib XLSX: {e}", exc_info=True)
        return None, f"Error al procesar el archivo Excel XLSX: {str(e)}"

def parse_xls_with_xlrd(content_bytes):
    """Intenta procesar formato antiguo .xls con xlrd."""
    try:
        import xlrd
        wb = xlrd.open_workbook(file_contents=content_bytes)
        sheet = wb.sheet_by_index(0)
        rows = []
        for row_idx in range(sheet.nrows):
            row = [str(sheet.cell_value(row_idx, col_idx)).strip() for col_idx in range(sheet.ncols)]
            if any(row):
                rows.append(row)
        return rows, None
    except ImportError:
        return None, "El formato Excel 97-2003 (.xls) requiere xlrd. Por favor guarda tu archivo como libro de Excel (.xlsx) o CSV e inténtalo nuevamente."
    except Exception as e:
        return None, f"Error al procesar el archivo XLS: {str(e)}"

def parse_imported_file(uploaded_file):
    """
    Función principal de parseo tolerante a fallos.
    Retorna (contacts_list, error_msg).
    Cada contacto es un dict con claves: 'email', 'first_name', 'last_name', 'company', 'phone'.
    """
    filename = uploaded_file.name.lower()
    content_bytes = uploaded_file.read()
    if not content_bytes:
        return None, "El archivo subido está vacío."

    rows = None
    err = None

    if filename.endswith('.csv'):
        rows, err = parse_csv_content(content_bytes)
    elif filename.endswith('.xlsx'):
        rows, err = parse_xlsx_with_openpyxl(content_bytes)
        if rows is None:
            rows, err = parse_xlsx_with_stdlib(content_bytes)
    elif filename.endswith('.xls'):
        rows, err = parse_xls_with_xlrd(content_bytes)
    else:
        # Intentar detección por firma binaria
        if content_bytes.startswith(b'PK\x03\x04'):
            rows, err = parse_xlsx_with_openpyxl(content_bytes)
            if rows is None:
                rows, err = parse_xlsx_with_stdlib(content_bytes)
        else:
            # Fallback a CSV
            rows, err = parse_csv_content(content_bytes)

    if err and not rows:
        return None, err

    if not rows or len(rows) < 2:
        return None, "El archivo no contiene suficientes filas de datos (debe incluir una fila de encabezados y al menos un contacto)."

    # Analizar encabezados
    raw_headers = rows[0]
    header_map = {}
    for idx, col_name in enumerate(raw_headers):
        norm = normalize_header(col_name)
        if norm and norm not in header_map:
            header_map[norm] = idx

    if 'email' not in header_map:
        detected = ", ".join([f"'{h}'" for h in raw_headers if str(h).strip()])
        return None, f"No se encontró una columna de correo electrónico. Columnas detectadas: [{detected}]. Asegúrate de incluir un encabezado llamado 'email' o 'correo'."

    email_idx = header_map['email']
    first_name_idx = header_map.get('first_name')
    last_name_idx = header_map.get('last_name')
    company_idx = header_map.get('company')
    phone_idx = header_map.get('phone')

    contacts_data = []
    seen_in_file = set()

    for row in rows[1:]:
        if email_idx >= len(row):
            continue
        email_val = str(row[email_idx]).strip().lower()
        if not email_val or '@' not in email_val or '.' not in email_val:
            continue

        first_name_val = str(row[first_name_idx]).strip() if first_name_idx is not None and first_name_idx < len(row) else ''
        last_name_val = str(row[last_name_idx]).strip() if last_name_idx is not None and last_name_idx < len(row) else ''
        company_val = str(row[company_idx]).strip() if company_idx is not None and company_idx < len(row) else ''
        phone_val = str(row[phone_idx]).strip() if phone_idx is not None and phone_idx < len(row) else ''

        # Si el número de teléfono vino como float (ej. 56912345678.0), limpiar el .0
        if phone_val.endswith('.0'):
            phone_val = phone_val[:-2]

        contacts_data.append({
            'email': email_val,
            'first_name': first_name_val,
            'last_name': last_name_val,
            'company': company_val,
            'phone': phone_val,
        })

    return contacts_data, None
