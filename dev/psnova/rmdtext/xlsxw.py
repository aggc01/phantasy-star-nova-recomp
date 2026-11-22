"""xlsxw.py - a minimal .xlsx writer (standard library only; inline strings, one header row, frozen, column widths,
wrapped text). Written 2026-11-18 so the text sheet needs no extra package."""
import zipfile
from xml.sax.saxutils import escape


def _col(i):
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _clean(v):
    s = '' if v is None else str(v)
    return ''.join(ch for ch in s if ch in '\t\n\r' or ord(ch) >= 0x20)


def write_xlsx(path, sheets):
    """sheets: list of (name, header list, rows list of lists, widths list)"""
    z = zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED)
    z.writestr('[Content_Types].xml',
               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
               '<Default Extension="xml" ContentType="application/xml"/>'
               '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
               '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
               + ''.join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1) for i in range(len(sheets)))
               + '</Types>')
    z.writestr('_rels/.rels',
               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
               '</Relationships>')
    z.writestr('xl/workbook.xml',
               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
               + ''.join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (escape(n[:31]), i + 1, i + 1) for i, (n, _, _, _) in enumerate(sheets))
               + '</sheets></workbook>')
    z.writestr('xl/_rels/workbook.xml.rels',
               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + ''.join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i + 1, i + 1) for i in range(len(sheets)))
               + '<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' % (len(sheets) + 1)
               + '</Relationships>')
    z.writestr('xl/styles.xml',
               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
               '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
               '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
               '<fill><patternFill patternType="solid"><fgColor rgb="FFDDEBF7"/></patternFill></fill></fills>'
               '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>'
               '<cellXfs count="3"><xf/><xf fontId="1" fillId="2" applyFont="1" applyFill="1"/>'
               '<xf applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs>'
               '</styleSheet>')
    for si, (name, header, rows, widths) in enumerate(sheets):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
               '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
               '<cols>' + ''.join('<col min="%d" max="%d" width="%s" customWidth="1"/>' % (i + 1, i + 1, w) for i, w in enumerate(widths)) + '</cols><sheetData>']
        for ri, row in enumerate([header] + rows):
            st = 1 if ri == 0 else 2
            cells = []
            for ci, v in enumerate(row):
                s = _clean(v)
                if s == '':
                    continue
                cells.append('<c r="%s%d" t="inlineStr" s="%d"><is><t xml:space="preserve">%s</t></is></c>' % (_col(ci), ri + 1, st, escape(s)))
            out.append('<row r="%d">%s</row>' % (ri + 1, ''.join(cells)))
        out.append('</sheetData><autoFilter ref="A1:%s%d"/></worksheet>' % (_col(len(header) - 1), len(rows) + 1))
        z.writestr('xl/worksheets/sheet%d.xml' % (si + 1), ''.join(out))
    z.close()
