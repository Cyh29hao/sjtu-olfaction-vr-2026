"""Read-only, background PowerPoint export for a finished local deck."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pythoncom
import win32com.client


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pptx', type=Path)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--png-dir', type=Path)
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--main-count', type=int)
    parser.add_argument('--append-last', action='store_true', help='Append the final contribution page to the main PDF')
    parser.add_argument('--width', type=int, default=1600)
    args = parser.parse_args()
    source = args.pptx.resolve(strict=True)
    output = (args.out_dir or source.parent).resolve()
    output.mkdir(parents=True, exist_ok=True)
    png_dir = (args.png_dir or output / (source.stem + '-pages')).resolve()
    png_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = (args.pdf or output / (source.stem + '.pdf')).resolve()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    before = sha256(source)
    app = None
    deck = None
    pythoncom.CoInitialize()
    try:
        app = win32com.client.DispatchEx('PowerPoint.Application')
        deck = app.Presentations.Open(str(source), ReadOnly=-1, Untitled=0, WithWindow=0)
        count = int(deck.Slides.Count)
        width_pt = float(deck.PageSetup.SlideWidth)
        height_pt = float(deck.PageSetup.SlideHeight)
        height_px = round(args.width * height_pt / width_pt)
        for index in range(1, count + 1):
            slide = deck.Slides(index)
            slide.Export(str(png_dir / f'{index:02}.png'), 'PNG', args.width, height_px)
            # Include every backup in the PDF, changing only the unsaved in-memory copy.
            slide.SlideShowTransition.Hidden = 0
        deck.SaveAs(str(pdf_path), 32)
        deck.Close()
        deck = None
        after = sha256(source)
        if before != after:
            raise RuntimeError('Source PPTX changed during read-only export')
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise RuntimeError('PowerPoint did not produce a nonempty PDF')
        report = {
            'source': str(source), 'source_sha256': after,
            'source_unchanged': True, 'native_open': True,
            'slides': count, 'slide_size_pt': [width_pt, height_pt],
            'png_dir': str(png_dir), 'png_size': [args.width, height_px],
            'pdf': str(pdf_path), 'pdf_sha256': sha256(pdf_path),
            'review_status': 'rendered; visual inspection still required',
        }
        if args.main_count is not None:
            if not 1 <= args.main_count <= count:
                raise ValueError('--main-count must be within the actual deck')
            import fitz
            main_path = output / (source.stem + '-main.pdf')
            with fitz.open(pdf_path) as full:
                if full.page_count != count:
                    raise RuntimeError(f'PDF has {full.page_count} pages, expected {count}')
                with fitz.open() as subset:
                    subset.insert_pdf(full, from_page=0, to_page=args.main_count - 1)
                    if args.append_last and args.main_count < count:
                        subset.insert_pdf(full, from_page=count - 1, to_page=count - 1)
                    subset.save(main_path)
            report['main_pdf'] = str(main_path)
            report['main_slides'] = args.main_count
            report['contribution_page_appended'] = args.append_last and args.main_count < count
        (png_dir / 'native-export.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
        )
        print(json.dumps({'native_open': True, 'slides': count, 'pdf': str(pdf_path),
                          'source_unchanged': True}, ensure_ascii=False))
    finally:
        if deck is not None:
            try:
                deck.Close()
            except Exception:
                pass
        if app is not None:
            try:
                if app.Presentations.Count == 0:
                    app.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
