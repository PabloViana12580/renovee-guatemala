import io
import json
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from core import imagemeta

CROPS_FILE = 'crops.json'
CREDITS_START = '<!-- owner-images:start -->'
CREDITS_END = '<!-- owner-images:end -->'
CREDITED_FILE = re.compile(r'^\| `([^`]+\.webp)` \|', re.MULTILINE)


class Command(BaseCommand):
    help = (
        'Prepares the images in src/images for a public repository and for the web. '
        'Removes hidden data from the originals in place (GPS position, camera, author, '
        'comments; the picture is not re-encoded), writes web-sized WebP copies to '
        'static/img, and lists them in static/img/CREDITS.md as owner-provided. '
        'src/images/crops.json can publish regions of an original instead of the whole picture.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--max-width', type=int, default=2000)
        parser.add_argument('--quality', type=int, default=80)

    def handle(self, *args, max_width, quality, **options):
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise CommandError('Pillow is required: pip install -r requirements-dev.txt') from exc

        source_dir = settings.IMAGES_SOURCE_DIR
        output_dir = settings.IMAGES_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        originals = self._images(source_dir)
        plan = self._plan(originals, self._crops(source_dir, originals))

        written = []
        for path in originals:
            self._clean(path, Image)
            with Image.open(path) as original:
                upright = ImageOps.exif_transpose(original)
                upright = upright.convert('RGBA' if 'A' in upright.getbands() else 'RGB')
                for name, box in plan[path]:
                    image = upright
                    if box:
                        if not (0 <= box[0] < box[2] <= upright.width and 0 <= box[1] < box[3] <= upright.height):
                            size = f'{upright.width}x{upright.height}'
                            raise CommandError(f'{CROPS_FILE}: the box of "{name[:-5]}" does not fit in {path.name} ({size}).')
                        image = upright.crop(box)
                    if image.width > max_width:
                        height = round(image.height * max_width / image.width)
                        image = image.resize((max_width, height), Image.Resampling.LANCZOS)
                    # Saved without any of the original's metadata.
                    image.save(output_dir / name, 'WEBP', quality=quality, method=6)
                    written.append((name, path.name + (' (crop)' if box else ''), image.width, image.height))
                    self.stdout.write(f'{written[-1][1]} -> static/img/{name} ({image.width}x{image.height})')

        credits_path = output_dir / 'CREDITS.md'
        names = {name for name, *_ in written}
        if originals:
            self._remove_stale(output_dir, credits_path, names)
        # Images put into static/img by hand (stock photos, icons) are published too.
        for path in self._images(output_dir):
            if path.name not in names:
                self._clean(path, Image)

        if not originals:
            self.stdout.write(f'No images in {source_dir}.')
            return
        self._update_credits(credits_path, written)
        self.stdout.write(self.style.SUCCESS(f'{len(written)} image(s) written.'))

    @staticmethod
    def _images(folder):
        if not folder.is_dir():
            return []
        return sorted(path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in imagemeta.SUFFIXES)

    @staticmethod
    def _crops(source_dir, originals):
        """crops.json as {original path: [(output name, box)]}. See src/images/README.md."""
        crops_path = source_dir / CROPS_FILE
        if not crops_path.is_file():
            return {}
        by_name = {path.name: path for path in originals}
        try:
            entries = json.loads(crops_path.read_text(encoding='utf-8'))
            crops = {}
            for name, entry in entries.items():
                box = tuple(entry['box'])
                if slugify(name) != name or len(box) != 4 or not all(isinstance(value, int) for value in box):
                    raise ValueError(f'"{name}" needs a lowercase-and-hyphens name and a box of four whole numbers')
                crops.setdefault(by_name[entry['from']], []).append((f'{name}.webp', box))
        except KeyError as exc:
            raise CommandError(f'{CROPS_FILE}: {exc} is missing or is not an image in src/images.') from exc
        except (ValueError, TypeError, AttributeError) as exc:
            raise CommandError(f'{CROPS_FILE}: {exc}') from exc
        return crops

    @staticmethod
    def _plan(originals, crops):
        """What to write for each original: its crops when it has any, otherwise the whole picture."""
        plan, taken = {}, {}
        for path in originals:
            plan[path] = crops.get(path) or [((slugify(path.stem) or 'image') + '.webp', None)]
            for name, _ in plan[path]:
                if name in taken:
                    raise CommandError(f'{taken[name]} and {path.name} would both become static/img/{name}. Rename one.')
                taken[name] = path.name
        return plan

    def _clean(self, path, Image):
        """Remove hidden data from one image file in place. The picture itself must not change."""
        data = path.read_bytes()
        try:
            cleaned, removed = imagemeta.clean(data)
        except imagemeta.UnsupportedImage as exc:
            raise CommandError(
                f'{path.name}: cannot check this file for hidden data ({exc}). Export it again as JPEG or PNG, or remove it.'
            ) from exc
        if not removed:
            return
        if imagemeta.CREDENTIALS in removed and settings.IMAGES_KEEP_CREDENTIALS:
            self.stdout.write(f'{path.name}: left untouched, it carries content credentials (IMAGES_KEEP_CREDENTIALS)')
            return
        if not self._same_picture(Image, data, cleaned):
            raise CommandError(
                f'{path.name}: removing its hidden data would change the picture, so the file was left untouched. '
                'Export it again without metadata, or remove it.'
            )
        temporary = path.with_name(path.name + '.cleaning')
        temporary.write_bytes(cleaned)
        os.replace(temporary, path)
        self.stdout.write(f'{path.name}: removed hidden data ({", ".join(removed)})')

    @staticmethod
    def _same_picture(Image, before, after):
        try:
            with Image.open(io.BytesIO(before)) as first, Image.open(io.BytesIO(after)) as second:
                orientation = imagemeta.ORIENTATION_TAG
                if first.getexif().get(orientation, 1) != second.getexif().get(orientation, 1):
                    return False
                return (first.size, first.mode) == (second.size, second.mode) and first.tobytes() == second.tobytes()
        except Exception:
            return False  # any decoding problem means: do not touch the original

    def _remove_stale(self, output_dir, credits_path, names):
        """Delete copies an earlier run wrote (they are listed in the credits) and this run no longer writes."""
        if not credits_path.exists():
            return
        text = credits_path.read_text(encoding='utf-8')
        if CREDITS_START not in text or CREDITS_END not in text:
            return
        block = text.split(CREDITS_START, 1)[1].split(CREDITS_END, 1)[0]
        for name in sorted(set(CREDITED_FILE.findall(block)) - names):
            stale = output_dir / name
            if stale.is_file():
                stale.unlink()
                self.stdout.write(f'static/img/{name}: removed, no original produces it any more')

    @staticmethod
    def _update_credits(credits_path, written):
        lines = [CREDITS_START, '', '| File | Original | Size | Source |', '| --- | --- | --- | --- |']
        lines += [
            f'| `{name}` | `src/images/{original}` | {width}x{height} | Owner-provided; all rights reserved |'
            for name, original, width, height in written
        ]
        lines += ['', CREDITS_END]
        block = '\n'.join(lines)
        text = credits_path.read_text(encoding='utf-8') if credits_path.exists() else '# Image credits\n\n'
        if CREDITS_START in text and CREDITS_END in text:
            before, rest = text.split(CREDITS_START, 1)
            after = rest.split(CREDITS_END, 1)[1]
            text = before + block + after
        else:
            text = text.rstrip('\n') + '\n\n## Owner-provided images\n\n' + block + '\n'
        credits_path.write_text(text, encoding='utf-8', newline='\n')
