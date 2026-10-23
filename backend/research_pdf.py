"""Full PDF text plus page renders of embedded figures/vector plots."""

import re
from pathlib import Path

import pymupdf

from .research_quality import quality


def extract_pdf(raw, final, output):
    output = Path(output)
    with pymupdf.open(stream=raw, filetype="pdf") as doc:
        if doc.needs_pass:
            raise ValueError("PDF 已加密，无法提取正文")
        pages = min(len(doc), 150)
        texts, headings, images, warnings, sparse_pages = [], [], [], [], []
        for index in range(pages):
            page = doc[index]
            text = page.get_text(sort=True)
            if len(text.strip()) < 80:
                sparse_pages.append(index + 1)
            texts.append(f"[Page {index + 1}]\n{text}")
            for line in text.splitlines():
                if re.match(
                    r"^(?:\d+\.?\s+)?(?:Abstract|Introduction|Conclusion|References|Appendix|[1-9]\.\d+\s+)",
                    line,
                ):
                    headings.append(line.strip())
            # Vector plots have no image objects; keep rendered figure pages for review.
            if (page.get_images() or len(page.get_drawings()) >= 5) and len(images) < 12:
                name = f"page-{index + 1}.png"
                page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False).save(output / name)
                images.append(
                    dict(
                        url=final + f"#page={index + 1}",
                        local_file=name,
                        alt=f"论文第 {index + 1} 页（含图表，整页渲染）",
                        caption="页面包含正文与图表；可人工裁剪后使用",
                    )
                )
        if pages < len(doc):
            warnings.append(f"PDF 共 {len(doc)} 页，超过 150 页处理上限，正文提取不完整")
        text = "\n\n".join(texts)
        if sparse_pages:
            warnings.append(
                f"PDF 第 {','.join(map(str, sparse_pages[:20]))} 页文字较少；当前未执行 OCR，请核对扫描页或图表页"
            )
        first_lines = (
            [line.strip() for line in doc[0].get_text(sort=True).splitlines() if line.strip()]
            if pages
            else []
        )
        title = (doc.metadata or {}).get("title") or (
            first_lines[0] if first_lines else final.rsplit("/", 1)[-1]
        )
        return dict(
            title=title[:240],
            text=text,
            images=images,
            videos=[],
            embedded_media=[],
            headings=headings,
            published_at="",
            author=(doc.metadata or {}).get("author", ""),
            canonical_url=final,
            quality=quality(
                text,
                "pdf:pymupdf",
                warnings,
                total_pages=len(doc),
                extracted_pages=pages,
                discovered_images=len(images),
                discovered_videos=0,
                embedded_media=0,
            ),
        )
