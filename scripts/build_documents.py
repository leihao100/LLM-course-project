"""Optional document builder. Run from repository root.

uv run --with python-docx --with reportlab --with matplotlib --with markdown \
  scripts/build_documents.py
Core research commands do not depend on these packages.
"""
from __future__ import annotations

import html
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import markdown
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                               Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "clinical-chart-safety-mpl"))


def make_figure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig, ax = plt.subplots(figsize=(11.2, 4.4))
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 4.4)
    ax.axis("off")
    blue, gray, orange = "#18446b", "#eaf1f7", "#b35c21"
    def box(x, y, w, h, title, body, fill=gray):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.08",linewidth=1.1,
                                    edgecolor=blue,facecolor=fill))
        ax.text(x+w/2,y+h-0.22,title,ha="center",va="top",fontsize=11,weight="bold",color=blue)
        ax.text(x+w/2,y+h/2-0.12,body,ha="center",va="center",fontsize=9.4,color="#223344",linespacing=1.5)
    def arrow(a,b,label=None,color=blue):
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle="-|>",mutation_scale=13,linewidth=1.4,color=color))
        if label:
            ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+0.12,label,ha="center",fontsize=8.5,color=color)
    box(.25,2.65,2.2,1.1,"Clean snapshot C0","Immutable reference\nFrozen scenario time")
    box(3.2,2.65,2.2,1.1,"Faulted chart Cf","Drop / decimal / unit / date\nRequery full history")
    box(6.15,2.65,2.2,1.1,"Agent and local store","Shared policy, paired arms\nCommit + read back")
    box(8.95,2.65,1.95,1.1,"Original scorer","Reference from Cf\nLegacy verdict")
    box(4.4,.65,3.15,1.05,"Independent evaluation","Observable policy violations\nClean-reference deviations",fill="#fff2e7")
    arrow((2.55,3.2),(3.05,3.2))
    arrow((5.5,3.2),(6.0,3.2))
    arrow((8.45,3.2),(8.8,3.2))
    arrow((1.35,2.5),(4.3,1.3),"clean target",orange)
    arrow((4.3,2.5),(5.1,1.8),"P1 evidence",orange)
    arrow((7.25,2.5),(6.8,1.8),"committed actions",orange)
    ax.text(.25,4.15,"Independent scoring under chart corruption",fontsize=16,weight="bold",color=blue)
    ax.text(.25,.15,"Local cached-chart execution; not a live EHR experiment. No model performance is shown.",fontsize=9,color="#4c5966")
    out = ROOT / "paper/figures"
    out.mkdir(exist_ok=True)
    fig.savefig(out/"evaluation_design.png",dpi=220,bbox_inches="tight",facecolor="white")
    fig.savefig(out/"evaluation_design.pdf",bbox_inches="tight",facecolor="white")
    plt.close(fig)


def text_of(element):
    return "".join(element.itertext())


def rich_pdf(element):
    result = html.escape(element.text or "")
    for child in element:
        inner = rich_pdf(child)
        if child.tag in ("strong", "b"):
            result += "<b>"+inner+"</b>"
        elif child.tag in ("em", "i"):
            result += "<i>"+inner+"</i>"
        elif child.tag == "code":
            result += '<font face="Courier" size="8">'+inner+"</font>"
        elif child.tag == "a":
            url = child.attrib.get("href", "")
            if url.startswith("http"):
                result += '<a href="'+html.escape(url,quote=True)+'" color="#175e95">'+inner+"</a>"
            else:
                result += inner
        elif child.tag == "br":
            result += "<br/>"
        else:
            result += inner
        result += html.escape(child.tail or "")
    return result


def add_runs(paragraph, element, bold=False, mono=False):
    if element.text:
        r = paragraph.add_run(element.text)
        r.bold = bold
        if mono:
            r.font.name = "Consolas"
            r.font.size = Pt(9)
    for child in element:
        add_runs(paragraph, child, bold or child.tag in ("strong", "b"), mono or child.tag == "code")
        if child.tag == "a" and child.attrib.get("href", "").startswith("http"):
            # Preserve usable reference URLs in the editable file.
            run = paragraph.add_run(" ("+child.attrib["href"]+")")
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor.from_string("175E95")
        if child.tail:
            paragraph.add_run(child.tail)


def build(path):
    source = path.read_text()
    is_chinese = bool(re.search("[\u4e00-\u9fff]",source[:100]))
    tree = ET.fromstring("<root>"+markdown.markdown(source,extensions=["tables","fenced_code"])+"</root>")
    document = Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Cm(1.8)
    section.left_margin = section.right_margin = Cm(2.0)
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    normal.paragraph_format.space_after = Pt(6)
    for style in ["Title","Heading 1","Heading 2","Heading 3"]:
        document.styles[style].font.color.rgb = RGBColor.from_string("18446B")
        document.styles[style].element.rPr.rFonts.set(qn("w:eastAsia"), "Noto Sans CJK SC")
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    face = "STSong-Light" if is_chinese else "Times-Roman"
    styles = getSampleStyleSheet()
    body = ParagraphStyle("ResearchBody",fontName=face,fontSize=10,leading=15,
                          spaceAfter=7,wordWrap="CJK" if is_chinese else None)
    small = ParagraphStyle("ResearchSmall",parent=body,fontSize=8,leading=11)
    headings = {1: ParagraphStyle("TitleResearch",parent=body,fontSize=21,leading=28,spaceAfter=15,textColor=colors.HexColor("#18446b")),
                2: ParagraphStyle("H1Research",parent=body,fontSize=14,leading=19,spaceBefore=12,spaceAfter=8,keepWithNext=True,textColor=colors.HexColor("#18446b")),
                3: ParagraphStyle("H2Research",parent=body,fontSize=11.5,leading=16,spaceBefore=9,spaceAfter=6,keepWithNext=True,textColor=colors.HexColor("#18446b"))}
    story = []
    for element in tree:
        tag = element.tag
        if tag.startswith("h") and tag[1:].isdigit():
            level = int(tag[1:])
            document.add_heading(text_of(element),level=0 if level==1 else min(level-1,3))
            story.append(Paragraph(rich_pdf(element),headings.get(level,headings[3])))
        elif tag == "p":
            images = list(element.iter("img"))
            if images:
                for img in images:
                    imagepath = path.parent / img.attrib["src"]
                    document.add_picture(str(imagepath),width=Cm(16.5))
                    story.append(Image(str(imagepath),width=470,height=185,kind="proportional"))
            else:
                add_runs(document.add_paragraph(),element)
                story.append(Paragraph(rich_pdf(element),body))
        elif tag in ("ul", "ol"):
            for index, li in enumerate(element):
                p = document.add_paragraph(style="List Bullet" if tag=="ul" else "List Number")
                add_runs(p,li)
                marker = "- " if tag=="ul" else str(index+1)+". "
                story.append(Paragraph(marker+rich_pdf(li),body))
        elif tag == "pre":
            code = text_of(element)
            p=document.add_paragraph()
            for i,line in enumerate(code.splitlines()):
                if i:
                    p.add_run().add_break()
                r=p.add_run(line)
                r.font.name="Consolas"
                r.font.size=Pt(8)
            code_text="<br/>".join(html.escape(x).replace(" ","&#160;") for x in code.splitlines())
            code_style=ParagraphStyle("CodeResearch",parent=small,fontName="Courier",fontSize=7,leading=10,
                                      backColor=colors.HexColor("#f0f4f8"),borderPadding=7,spaceBefore=3,spaceAfter=10)
            story.append(Paragraph(code_text,code_style))
        elif tag == "table":
            rows = list(element.iter("tr"))
            cells = [[text_of(c) for c in row] for row in rows]
            if not cells:
                continue
            table=document.add_table(rows=1,cols=len(cells[0]))
            table.style="Light Shading Accent 1"
            for i,values in enumerate(cells):
                target=table.rows[0].cells if i==0 else table.add_row().cells
                for cell, value in zip(target,values):
                    cell.text=value
                    for p in cell.paragraphs:
                        for run in p.runs:
                            run.font.size=Pt(8.5)
            grid=[[Paragraph(html.escape(value),small) for value in values] for values in cells]
            widths=[470/len(cells[0])]*len(cells[0])
            pdf_table=Table(grid,colWidths=widths,repeatRows=1,hAlign="LEFT")
            pdf_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dce8f2")),
                ("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#c4cdd5")),
                ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
                ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
            story.extend([pdf_table,Spacer(1,9)])
    footer=section.footer.paragraphs[0]
    footer.alignment=2
    footer.add_run("Clinical Chart Safety · Draft · 2026-11-05")
    document.save(path.with_suffix(".docx"))
    def page_footer(canvas,doc):
        canvas.saveState()
        canvas.setFont("Helvetica",8)
        canvas.setFillColor(colors.HexColor("#657585"))
        canvas.drawString(42,25,"Clinical Chart Safety | Research draft | 2026-11-05")
        canvas.drawRightString(A4[0]-42,25,str(doc.page))
        canvas.restoreState()
    pdf=SimpleDocTemplate(str(path.with_suffix(".pdf")),pagesize=A4,leftMargin=42,rightMargin=42,
                          topMargin=38,bottomMargin=42,title=text_of(tree[0]),author="Clinical Chart Safety")
    pdf.build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    print(path.relative_to(ROOT),"-> Word + PDF")


if __name__ == "__main__":
    make_figure()
    for path in [ROOT/"docs/中期报告说明.md",ROOT/"docs/双路径实测报告.md",ROOT/"docs/研究报告.md",ROOT/"docs/实验协议.md",ROOT/"docs/运行指南.md",ROOT/"paper/manuscript.md"]:
        build(path)
