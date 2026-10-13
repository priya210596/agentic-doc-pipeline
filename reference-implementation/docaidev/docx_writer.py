"""Minimal .docx writer using only the standard library (zipfile + hand-written OOXML).
Supports headings, shaded paragraphs, tables, embedded PNGs, page breaks, and real margin
comments (word/comments.xml with range anchors), which is the part python-docx does not do."""
import struct
import zipfile
from xml.sax.saxutils import escape

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = ('xmlns:w="%s" xmlns:r="%s" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"') % (W, R)
MAX_IMG_EMU = 6 * 914400


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    return struct.unpack(">II", data[16:24])


class Doc:
    def __init__(self, author="doc-aidev", date="2026-01-01T00:00:00Z"):
        self.body, self.comments, self.images = [], [], []   # comments: [(author, text)]
        self.author, self.date = author, date

    # ---- inline pieces -------------------------------------------------
    @staticmethod
    def _run(text, bold=False, color=None, size=None, italic=False):
        pr = ""
        if bold: pr += "<w:b/>"
        if italic: pr += "<w:i/>"
        if color: pr += '<w:color w:val="%s"/>' % color
        if size: pr += '<w:sz w:val="%d"/>' % (size * 2)
        return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % ("<w:rPr>%s</w:rPr>" % pr if pr else "", escape(text))

    def _runs(self, content, **fmt):
        if isinstance(content, str):
            content = [(content, {})]
        return "".join(self._run(t, **{**fmt, **o}) for t, o in content)

    def _comment(self, c):
        """c is a text, or (author, text). Returns the new comment id."""
        author, text = (self.author, c) if isinstance(c, str) else c
        self.comments.append((author, text))
        return len(self.comments) - 1

    def _wrap(self, runs, comment):
        """Anchor one or more comments (str, (author, text), or a list of them) around `runs`."""
        if not comment:
            return runs
        ids = [self._comment(c) for c in (comment if isinstance(comment, list) else [comment])]
        return ("".join('<w:commentRangeStart w:id="%d"/>' % i for i in ids) + runs +
                "".join('<w:commentRangeEnd w:id="%d"/><w:r><w:commentReference w:id="%d"/></w:r>' % (i, i) for i in ids))

    def _para_xml(self, content, style=None, shade=None, comment=None, **fmt):
        ppr = ""
        if style: ppr += '<w:pStyle w:val="%s"/>' % style
        if shade: ppr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shade
        runs = self._wrap(self._runs(content, **fmt), comment)
        return "<w:p>%s%s</w:p>" % ("<w:pPr>%s</w:pPr>" % ppr if ppr else "", runs)

    # ---- block API ------------------------------------------------------
    def heading(self, text, level=1, comment=None):
        self.body.append(self._para_xml(text, style="Heading%d" % level, comment=comment))

    def para(self, content, shade=None, comment=None, **fmt):
        self.body.append(self._para_xml(content, shade=shade, comment=comment, **fmt))

    def banner(self, text, fill="C00000", color="FFFFFF"):
        self.body.append(self._para_xml(text, shade=fill, bold=True, color=color))

    def banner_table(self, text, fill="1F4E79", color="FFFFFF"):
        self.table([[(text, {"fill": fill, "color": color, "bold": True})]], header=False, widths=[9000])

    def page_break(self):
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def table(self, rows, header=True, widths=None, header_fill="D6E4F7"):
        """rows: list of rows; a cell is str, or (str|[str...], {"comment":..., "bold":..., "fill":...}).
        A list gives one paragraph per item."""
        xml = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblBorders>']
        xml += ['<w:%s w:val="single" w:sz="4" w:space="0" w:color="808080"/>' % s
                for s in ("top", "left", "bottom", "right", "insideH", "insideV")]
        xml.append("</w:tblBorders></w:tblPr>")
        ncols = max(len(r) for r in rows)
        grid = widths or [9000 // ncols] * ncols
        xml.append("<w:tblGrid>%s</w:tblGrid>" % "".join('<w:gridCol w:w="%d"/>' % w for w in grid))
        for ri, row in enumerate(rows):
            xml.append("<w:tr>")
            for ci, cell in enumerate(row):
                text, opt = (cell, {}) if isinstance(cell, str) else cell
                fill = opt.get("fill") or (header_fill if header and ri == 0 else None)
                tcpr = ""
                if widths: tcpr += '<w:tcW w:w="%d" w:type="dxa"/>' % widths[ci]
                if fill: tcpr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill
                fmt = dict(bold=opt.get("bold") or (header and ri == 0), color=opt.get("color"))
                if isinstance(text, list):
                    p = "".join(self._para_xml(t, comment=opt.get("comment") if k == 0 else None, **fmt) for k, t in enumerate(text))
                else:
                    p = self._para_xml(text, comment=opt.get("comment"), **fmt)
                xml.append("<w:tc>%s%s</w:tc>" % ("<w:tcPr>%s</w:tcPr>" % tcpr if tcpr else "", p))
            xml.append("</w:tr>")
        xml.append("</w:tbl><w:p/>")
        self.body.append("".join(xml))

    def image(self, path, alt="", comment=None):
        with open(path, "rb") as fh:
            data = fh.read()
        wpx, hpx = png_size(data)
        cx, cy = wpx * 9525, hpx * 9525
        if cx > MAX_IMG_EMU:
            cy, cx = int(cy * MAX_IMG_EMU / cx), MAX_IMG_EMU
        n = len(self.images) + 1
        self.images.append(data)
        drawing = (
            '<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="%d" cy="%d"/>'
            '<wp:docPr id="%d" name="Picture %d" descr="%s"/><a:graphic><a:graphicData '
            'uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr>'
            '<pic:cNvPr id="%d" name="image%d.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill>'
            '<a:blip r:embed="rIdImg%d"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr>'
            '<a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/>'
            "</a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>"
        ) % (cx, cy, n, n, escape(alt, {'"': "&quot;"}), n, n, n, cx, cy)
        drawing = self._wrap(drawing, comment)
        self.body.append("<w:p>%s</w:p>" % drawing)

    # ---- packaging ------------------------------------------------------
    def save(self, path):
        doc = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document %s><w:body>%s<w:sectPr/></w:body></w:document>' % (
            NS, "".join(self.body))
        comments = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:comments %s>%s</w:comments>' % (NS, "".join(
            '<w:comment w:id="%d" w:author="%s" w:date="%s" w:initials="DA"><w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:comment>'
            % (i, escape(a), self.date, escape(t)) for i, (a, t) in enumerate(self.comments)))
        rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rIdStyles" Type="%s/styles" Target="styles.xml"/>'
                '<Relationship Id="rIdComments" Type="%s/comments" Target="comments.xml"/>%s</Relationships>') % (
            R, R, "".join('<Relationship Id="rIdImg%d" Type="%s/image" Target="media/image%d.png"/>' % (i, R, i)
                          for i in range(1, len(self.images) + 1)))
        ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
              '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/></Types>')
        root = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="%s/officeDocument" Target="word/document.xml"/></Relationships>') % R
        styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="%s">'
                  '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>'
                  '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
                  '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="36"/></w:rPr></w:style>'
                  '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="2F5496"/><w:sz w:val="28"/></w:rPr></w:style>'
                  '</w:styles>') % W
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", ct)
            z.writestr("_rels/.rels", root)
            z.writestr("word/document.xml", doc)
            z.writestr("word/_rels/document.xml.rels", rels)
            z.writestr("word/styles.xml", styles)
            z.writestr("word/comments.xml", comments)
            for i, data in enumerate(self.images, 1):
                z.writestr("word/media/image%d.png" % i, data)
