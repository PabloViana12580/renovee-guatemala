"""F7 images: owner originals lose their hidden data and become web-sized copies with credits."""

import io
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from core import imagemeta

try:
    from PIL import Image, PngImagePlugin
except ImportError:  # Pillow is a development dependency
    Image = None

MAKE, ORIENTATION, GPS = 0x010F, 0x0112, 0x8825
ROTATED = 6  # the camera was held upright: viewers turn the picture 90 degrees


def exif_bytes(orientation=1):
    exif = Image.Exif()
    exif[MAKE] = 'PhoneMaker'
    exif[ORIENTATION] = orientation
    exif[GPS] = {1: 'N', 2: (14.0, 38.0, 4.0), 3: 'W', 4: (90.0, 30.0, 47.0)}
    return exif.tobytes()


def encoded(image_format, mode='RGB', **options):
    buffer = io.BytesIO()
    picture = Image.new(mode, (64, 48), (30, 120, 90, 128)[: len(mode)])
    picture.putpixel((5, 5), (250, 240, 10, 255)[: len(mode)])
    picture.save(buffer, image_format, **options)
    return buffer.getvalue()


class PillowTestCase(SimpleTestCase):
    def setUp(self):
        if Image is None:
            self.skipTest('Pillow is not installed (pip install -r requirements-dev.txt).')

    def assertSamePixels(self, before, after):
        with Image.open(io.BytesIO(before)) as first, Image.open(io.BytesIO(after)) as second:
            self.assertEqual((first.size, first.mode), (second.size, second.mode))
            self.assertEqual(first.tobytes(), second.tobytes())


class HiddenDataTests(PillowTestCase):
    """imagemeta drops what the owner cannot see and leaves the picture untouched."""

    def test_jpeg_loses_position_camera_comment_and_appended_data(self):
        data = encoded('JPEG', exif=exif_bytes(ROTATED), comment=b'at home') + b'a short video appended by the phone'
        cleaned, removed = imagemeta.clean(data)
        self.assertEqual(removed, [imagemeta.EXIF_GPS, imagemeta.COMMENT, imagemeta.EXTRAS])
        self.assertSamePixels(data, cleaned)
        self.assertTrue(cleaned.endswith(b'\xff\xd9'))
        with Image.open(io.BytesIO(cleaned)) as result:
            self.assertEqual(dict(result.getexif()), {ORIENTATION: ROTATED})  # still shown the right way up
            self.assertNotIn('comment', result.info)

    def test_upright_jpeg_keeps_no_exif_and_its_color_profile(self):
        profile = b'not a real profile, only bytes that must survive'
        data = encoded('JPEG', exif=exif_bytes(), icc_profile=profile)
        cleaned, removed = imagemeta.clean(data)
        self.assertEqual(removed, [imagemeta.EXIF_GPS])
        with Image.open(io.BytesIO(cleaned)) as result:
            self.assertEqual(len(result.getexif()), 0)
            self.assertEqual(result.info['icc_profile'], profile)

    def test_png_loses_text_and_xmp_but_keeps_transparency(self):
        text = PngImagePlugin.PngInfo()
        text.add_text('Author', 'someone')
        text.add_itxt('XML:com.adobe.xmp', '<x:xmpmeta><pdf:Author>account-name</pdf:Author></x:xmpmeta>')
        data = encoded('PNG', mode='RGBA', pnginfo=text, exif=exif_bytes())
        cleaned, removed = imagemeta.clean(data)
        self.assertCountEqual(removed, [imagemeta.TEXT, imagemeta.XMP, imagemeta.EXIF_GPS])
        self.assertSamePixels(data, cleaned)
        self.assertNotIn(b'account-name', cleaned)
        with Image.open(io.BytesIO(cleaned)) as result:
            self.assertEqual(result.mode, 'RGBA')
            self.assertEqual(result.text, {})

    def test_webp_loses_exif_and_xmp(self):
        data = encoded('WEBP', exif=exif_bytes(ROTATED), xmp=b'<x:xmpmeta>account-name</x:xmpmeta>', lossless=True)
        cleaned, removed = imagemeta.clean(data)
        self.assertCountEqual(removed, [imagemeta.EXIF_GPS, imagemeta.XMP])
        self.assertSamePixels(data, cleaned)
        self.assertNotIn(b'account-name', cleaned)
        with Image.open(io.BytesIO(cleaned)) as result:
            self.assertEqual(dict(result.getexif()), {ORIENTATION: ROTATED})

    def test_clean_files_come_back_unchanged(self):
        cases = (('JPEG', {'exif': exif_bytes(ROTATED)}), ('JPEG', {'comment': b'\x00'}), ('PNG', {}), ('WEBP', {}))
        for image_format, options in cases:
            with self.subTest(image_format=image_format, options=sorted(options)):
                cleaned, _ = imagemeta.clean(encoded(image_format, **options))
                again, removed = imagemeta.clean(cleaned)
                self.assertEqual(removed, [])
                self.assertIs(again, cleaned)

    def test_content_credentials_are_reported_under_their_own_name(self):
        plain = encoded('PNG')
        record = imagemeta._png_chunk(b'caBX', b'jumb: made with an image generator')
        data = plain[:-12] + record + plain[-12:]  # before the closing IEND chunk
        cleaned, removed = imagemeta.clean(data)
        self.assertEqual(removed, [imagemeta.CREDENTIALS])
        self.assertEqual(cleaned, plain)

    def test_jpeg_segments_are_sorted_into_kept_and_removed(self):
        def segment(marker, payload):
            return bytes((0xFF, marker)) + (len(payload) + 2).to_bytes(2, 'big') + payload

        plain = encoded('JPEG')
        extras = [
            segment(0xE1, b'http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta>account-name</x:xmpmeta>'),
            segment(0xED, b'Photoshop 3.0\x00IPTC caption'),
            segment(0xE0, b'JFXX\x00\x10 a thumbnail'),
            segment(0xE5, b'a camera maker block'),
            segment(0xE1, b'Exif\x00\x00not a TIFF header'),
            segment(0xEE, b'Adobe\x00\x64\x00\x00\x00\x00\x01'),  # color transform: kept
            segment(0xE2, b'ICC_PROFILE\x00\x01\x01profile bytes'),  # color profile: kept
        ]
        data = plain[:2] + b''.join(extras) + plain[2:]
        cleaned, removed = imagemeta.clean(data)
        self.assertEqual(removed, [imagemeta.XMP, imagemeta.IPTC, imagemeta.THUMBNAIL, imagemeta.OTHER, imagemeta.EXIF])
        self.assertEqual(cleaned, plain[:2] + extras[5] + extras[6] + plain[2:])
        self.assertSamePixels(data, cleaned)

    def test_damaged_files_are_refused_rather_than_guessed(self):
        jpeg, png = encoded('JPEG'), encoded('PNG')
        damaged = {
            'JPEG segment longer than the file': jpeg[:2] + b'\xff\xe1\xff\xff short',
            'JPEG with bytes between segments': jpeg[:2] + b'\x00\x01' + jpeg[2:],
            'PNG chunk longer than the file': png[:33] + (10**6).to_bytes(4, 'big') + b'tEXt',
            'PNG with an unknown critical chunk': png[:-12] + imagemeta._png_chunk(b'ZzZz', b'?') + png[-12:],
            'WebP chunk longer than the file': encoded('WEBP')[:20] + b'\xff\xff\xff\x00',
        }
        for case, data in damaged.items():
            with self.subTest(case=case), self.assertRaises(imagemeta.UnsupportedImage):
                imagemeta.clean(data)

    def test_png_date_and_private_chunks_go_and_appended_data_too(self):
        plain = encoded('PNG')
        data = plain[:-12] + imagemeta._png_chunk(b'tIME', b'\x07\xea\x0b\x0d\x0c\x00\x00') + plain[-12:] + b'trailing data'
        data = data[:33] + imagemeta._png_chunk(b'prVt', b'private') + data[33:]
        cleaned, removed = imagemeta.clean(data)
        self.assertEqual(removed, [imagemeta.OTHER, imagemeta.DATE, imagemeta.EXTRAS])
        self.assertEqual(cleaned, plain)

    def test_upright_webp_loses_exif_and_its_header_flag(self):
        data = encoded('WEBP', exif=exif_bytes(), lossless=True)
        cleaned, removed = imagemeta.clean(data)
        self.assertEqual(removed, [imagemeta.EXIF_GPS])
        self.assertSamePixels(data, cleaned)
        with Image.open(io.BytesIO(cleaned)) as result:
            self.assertEqual(len(result.getexif()), 0)

    def test_other_files_are_refused(self):
        with self.assertRaises(imagemeta.UnsupportedImage):
            imagemeta.clean(b'GIF89a not one of the supported formats')


class OptimizeImagesTests(PillowTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / 'src'
        self.output = Path(self.tmp.name) / 'img'
        self.source.mkdir()
        settings_override = override_settings(IMAGES_SOURCE_DIR=self.source, IMAGES_OUTPUT_DIR=self.output)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

    def run_command(self):
        out = StringIO()
        call_command('optimize_images', stdout=out)
        return out.getvalue()

    def test_large_photo_is_resized_to_webp_without_metadata(self):
        Image.new('RGB', (3000, 1500), 'green').save(self.source / 'Front Door.JPG', exif=exif_bytes())
        self.run_command()
        with Image.open(self.output / 'front-door.webp') as result:
            self.assertEqual(result.size, (2000, 1000))
            self.assertEqual(len(result.getexif()), 0)

    def test_original_is_cleaned_in_place_and_stays_the_right_way_up(self):
        original = self.source / 'lobby.jpg'
        Image.new('RGB', (80, 40), 'navy').save(original, exif=exif_bytes(ROTATED))
        self.assertIn('lobby.jpg: removed hidden data (EXIF with GPS position)', self.run_command())
        with Image.open(original) as cleaned:
            self.assertEqual(dict(cleaned.getexif()), {ORIENTATION: ROTATED})
        with Image.open(self.output / 'lobby.webp') as copy:
            self.assertEqual(copy.size, (40, 80))  # the web copy is turned upright
        self.assertNotIn('removed hidden data', self.run_command())
        self.assertEqual([path.name for path in self.source.iterdir()], ['lobby.jpg'])

    def test_images_added_to_the_output_folder_by_hand_are_cleaned_too(self):
        self.output.mkdir()
        stock = self.output / 'stock-photo.jpg'
        Image.new('RGB', (20, 20)).save(stock, exif=exif_bytes())
        self.assertIn('stock-photo.jpg: removed hidden data', self.run_command())
        with Image.open(stock) as cleaned:
            self.assertEqual(len(cleaned.getexif()), 0)

    def credentialed_portrait(self):
        path = self.source / 'portrait.png'
        plain = encoded('PNG')
        path.write_bytes(plain[:-12] + imagemeta._png_chunk(b'caBX', b'jumb: made with an image generator') + plain[-12:])
        return path, plain

    def test_content_credentials_are_removed_unless_the_project_keeps_them(self):
        path, plain = self.credentialed_portrait()
        self.assertIn('portrait.png: removed hidden data (content credentials', self.run_command())
        self.assertEqual(path.read_bytes(), plain)

    @override_settings(IMAGES_KEEP_CREDENTIALS=True)
    def test_file_with_content_credentials_is_left_untouched_when_the_project_keeps_them(self):
        path, _ = self.credentialed_portrait()
        before = path.read_bytes()
        self.assertIn('portrait.png: left untouched', self.run_command())
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue((self.output / 'portrait.webp').exists())

    def test_two_originals_with_the_same_web_name_are_refused(self):
        Image.new('RGB', (10, 10)).save(self.source / 'Front Door.jpg')
        Image.new('RGB', (10, 10)).save(self.source / 'front-door.png')
        with self.assertRaisesMessage(CommandError, 'would both become static/img/front-door.webp'):
            self.run_command()

    def test_file_that_is_not_really_an_image_stops_the_command(self):
        (self.source / 'notes.jpg').write_text('not a picture', encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'notes.jpg: cannot check this file for hidden data'):
            self.run_command()

    def social_post(self):
        """A 200x100 graphic: the photo on the left half, a frame with text on the right half."""
        post = Image.new('RGB', (200, 100), 'black')
        post.paste(Image.new('RGB', (100, 100), 'red'), (0, 0))
        post.save(self.source / 'Post 1.png')

    def write_crops(self, crops):
        (self.source / 'crops.json').write_text(json.dumps(crops), encoding='utf-8')

    def test_crops_file_publishes_regions_instead_of_the_whole_picture(self):
        self.social_post()
        self.write_crops({'sofa-photo': {'from': 'Post 1.png', 'box': [0, 0, 100, 100]}})
        self.run_command()
        with Image.open(self.output / 'sofa-photo.webp') as crop:
            self.assertEqual(crop.size, (100, 100))
            red, green, blue = crop.convert('RGB').getpixel((50, 50))
            self.assertTrue(red > 200 and green < 60 and blue < 60)
        self.assertFalse((self.output / 'post-1.webp').exists())
        self.assertIn('`src/images/Post 1.png (crop)`', (self.output / 'CREDITS.md').read_text(encoding='utf-8'))

    def test_mistakes_in_the_crops_file_stop_the_command(self):
        self.social_post()
        mistakes = {
            'is missing or is not an image': {'photo': {'from': 'Other.png', 'box': [0, 0, 10, 10]}},
            'does not fit in Post 1.png (200x100)': {'photo': {'from': 'Post 1.png', 'box': [0, 0, 300, 100]}},
            'needs a lowercase-and-hyphens name': {'My Photo': {'from': 'Post 1.png', 'box': [0, 0, 10, 10]}},
        }
        for message, crops in mistakes.items():
            with self.subTest(message=message):
                self.write_crops(crops)
                with self.assertRaisesMessage(CommandError, message):
                    self.run_command()

    def test_copies_no_original_produces_any_more_are_removed(self):
        Image.new('RGB', (10, 10)).save(self.source / 'old.png')
        self.run_command()
        (self.source / 'old.png').unlink()
        Image.new('RGB', (10, 10)).save(self.source / 'new.png')
        Image.new('RGB', (10, 10)).save(self.output / 'added-by-hand.png')
        self.assertIn('static/img/old.webp: removed', self.run_command())
        self.assertEqual(sorted(path.name for path in self.output.iterdir()), ['CREDITS.md', 'added-by-hand.png', 'new.webp'])

    def test_credits_list_owner_images_and_are_rewritten_not_duplicated(self):
        Image.new('RGBA', (100, 100)).save(self.source / 'logo.png')
        self.run_command()
        self.run_command()
        credits = (self.output / 'CREDITS.md').read_text(encoding='utf-8')
        self.assertEqual(credits.count('`logo.webp`'), 1)
        self.assertIn('Owner-provided; all rights reserved', credits)

    def test_empty_folder_is_reported(self):
        self.assertIn('No images', self.run_command())


class RepositoryImagesTests(SimpleTestCase):
    """This repository is public: the images in it must not carry hidden data."""

    def test_committed_images_carry_no_hidden_data(self):
        findings = []
        for folder in (settings.IMAGES_SOURCE_DIR, settings.IMAGES_OUTPUT_DIR):
            for path in sorted(folder.rglob('*')) if folder.is_dir() else []:
                if path.is_file() and path.suffix.lower() in imagemeta.SUFFIXES:
                    try:
                        removed = imagemeta.clean(path.read_bytes())[1]
                    except imagemeta.UnsupportedImage as error:
                        removed = [str(error)]
                    if imagemeta.CREDENTIALS in removed and settings.IMAGES_KEEP_CREDENTIALS:
                        continue  # the project chose to keep these files as they are
                    if removed:
                        findings.append(f'{path.relative_to(settings.BASE_DIR).as_posix()}: {", ".join(removed)}')
        self.assertEqual(findings, [], 'Run "python manage.py optimize_images": it removes hidden data from these files.')
