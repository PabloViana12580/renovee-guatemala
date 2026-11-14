"""Remove hidden data from image files without re-encoding the picture.

Photos and exported graphics carry data their owner may not know about: GPS
position, phone or camera model, dates, author and account names, comments,
thumbnails of the uncropped picture, even a short video (EXIF, XMP, IPTC, text
chunks, data appended after the image). This repository is public, so
`manage.py optimize_images` cleans the originals in src/images in place.

Only the containers of that data are dropped; the compressed picture is copied
byte for byte. What a viewer needs stays: color information (ICC profile,
gamma, transparency) and the EXIF orientation, reduced to that single value.

Content Credentials (C2PA) are a signed record of how an image was made, for
example with an AI tool, sometimes with a thumbnail of an earlier version.
They are reported under their own name so the owner can decide: callers that
want to keep them must leave the whole file alone, because the record stops
being valid when any other byte of the file changes.

Standard library only. JPEG, PNG, and WebP.
"""

import zlib

SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp'}

EXIF = 'EXIF (camera data)'
EXIF_GPS = 'EXIF with GPS position'
XMP = 'XMP'
IPTC = 'IPTC'
TEXT = 'text'
COMMENT = 'comment'
DATE = 'date'
THUMBNAIL = 'embedded thumbnail'
EXTRAS = 'extra pictures or video after the image'
CREDENTIALS = 'content credentials (C2PA record of how the image was made)'
OTHER = 'other embedded data'

ORIENTATION_TAG = 0x0112
GPS_TAG = 0x8825


class UnsupportedImage(ValueError):
    """The file is not a JPEG, PNG, or WebP image this module can read safely."""


def clean(data):
    """Return (cleaned bytes, what was removed); nothing to remove gives (data, [])."""
    if data[:2] == b'\xff\xd8':
        cleaned, removed = _clean_jpeg(data)
    elif data[:8] == PNG_SIGNATURE:
        cleaned, removed = _clean_png(data)
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        cleaned, removed = _clean_webp(data)
    else:
        raise UnsupportedImage('not a JPEG, PNG, or WebP image')
    removed = list(dict.fromkeys(removed))
    return (cleaned, removed) if removed else (data, [])


# --- EXIF (TIFF) helpers --------------------------------------------------------------------


def _ifd0(tiff):
    """Tags of the first image directory as {tag: (value bytes, byte order)}; {} if unreadable."""
    order = {b'II': 'little', b'MM': 'big'}.get(bytes(tiff[:2]))
    if order is None or int.from_bytes(tiff[2:4], order) != 42:
        return {}
    offset = int.from_bytes(tiff[4:8], order)
    count = int.from_bytes(tiff[offset : offset + 2], order)
    tags = {}
    for index in range(count):
        entry = tiff[offset + 2 + 12 * index : offset + 14 + 12 * index]
        if len(entry) < 12:
            break
        tags[int.from_bytes(entry[:2], order)] = (entry[8:12], order)
    return tags


def _orientation(tiff):
    """The EXIF orientation (2 to 8) when the picture must be rotated or mirrored, else None."""
    value, order = _ifd0(tiff).get(ORIENTATION_TAG, (b'', 'little'))
    orientation = int.from_bytes(value[:2], order) if value else 1
    return orientation if 2 <= orientation <= 8 else None


def _orientation_only(orientation):
    """TIFF data holding the orientation and nothing else."""
    entry = ORIENTATION_TAG.to_bytes(2, 'little') + (3).to_bytes(2, 'little') + (1).to_bytes(4, 'little')
    entry += orientation.to_bytes(2, 'little') + b'\x00\x00'
    return b'II*\x00' + (8).to_bytes(4, 'little') + (1).to_bytes(2, 'little') + entry + (0).to_bytes(4, 'little')


def _exif_label(tiff):
    return EXIF_GPS if GPS_TAG in _ifd0(tiff) else EXIF


def _replace_exif(tiff, removed):
    """What to keep of an EXIF block: None, or orientation-only TIFF data. Records the removal."""
    orientation = _orientation(tiff)
    minimal = _orientation_only(orientation) if orientation else None
    if minimal is None or bytes(tiff) != minimal:
        removed.append(_exif_label(tiff))
    return minimal


# --- JPEG -----------------------------------------------------------------------------------

JPEG_EXIF_HEADER = b'Exif\x00\x00'
JPEG_STANDALONE = {0x01, *range(0xD0, 0xD9)}  # TEM, restart, and start-of-image markers have no length


def _jpeg_removal(marker, payload):
    """Label for a segment that must go, or None to keep it."""
    if marker == 0xFE:
        return COMMENT if payload.strip(b'\x00 \t\r\n') else None  # some encoders add an empty one
    if not 0xE0 <= marker <= 0xEF:
        return None  # tables, frame and scan headers: the picture itself
    if marker == 0xE0:
        return THUMBNAIL if payload.startswith(b'JFXX\x00') else None
    if marker == 0xE1:
        return XMP if payload.startswith(b'http://ns.adobe.com/') else OTHER
    if marker == 0xE2:
        if payload.startswith(b'ICC_PROFILE\x00'):
            return None  # color profile
        return EXTRAS if payload.startswith(b'MPF\x00') else OTHER
    if marker == 0xEB and payload.startswith(b'JP'):
        return CREDENTIALS
    if marker == 0xED:
        return IPTC
    if marker == 0xEE and payload.startswith(b'Adobe'):
        return None  # color transform flag the decoder needs
    return OTHER


def _jpeg_scan_end(data, position):
    """Index of the marker that ends the compressed data starting at `position`."""
    while True:
        index = data.find(b'\xff', position)
        if index < 0 or index + 1 >= len(data):
            return len(data)  # truncated file: everything left is picture data
        following = data[index + 1]
        if following == 0x00 or 0xD0 <= following <= 0xD7:
            position = index + 2  # a stuffed 0xFF or a restart marker, still picture data
        elif following == 0xFF:
            position = index + 1  # padding before a marker
        else:
            return index


def _clean_jpeg(data):
    out, removed, position, size = [data[:2]], [], 2, len(data)
    while position < size:
        if data[position] != 0xFF:
            raise UnsupportedImage('JPEG structure not understood')
        while position < size and data[position] == 0xFF:
            position += 1
        if position >= size:
            break
        marker = data[position]
        position += 1
        if marker == 0xD9:  # end of image
            out.append(b'\xff\xd9')
            if position < size:
                removed.append(EXTRAS)
            break
        if marker in JPEG_STANDALONE:
            out.append(bytes((0xFF, marker)))
            continue
        length = int.from_bytes(data[position : position + 2], 'big')
        if length < 2 or position + length > size:
            raise UnsupportedImage('JPEG segment runs past the end of the file')
        payload = data[position + 2 : position + length]
        segment = bytes((0xFF, marker)) + data[position : position + length]
        position += length
        if marker == 0xE1 and payload.startswith(JPEG_EXIF_HEADER):
            minimal = _replace_exif(payload[len(JPEG_EXIF_HEADER) :], removed)
            if minimal:
                body = JPEG_EXIF_HEADER + minimal
                out.append(b'\xff\xe1' + (len(body) + 2).to_bytes(2, 'big') + body)
            continue
        label = _jpeg_removal(marker, payload)
        if label:
            removed.append(label)
            continue
        out.append(segment)
        if marker == 0xDA:  # start of scan: compressed data follows, up to the next marker
            end = _jpeg_scan_end(data, position)
            out.append(data[position:end])
            position = end
    return b''.join(out), removed


# --- PNG ------------------------------------------------------------------------------------

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
PNG_KEEP = {
    *(b'IHDR', b'PLTE', b'IDAT', b'IEND'),  # the picture
    *(b'tRNS', b'gAMA', b'cHRM', b'sRGB', b'iCCP', b'sBIT', b'bKGD', b'pHYs', b'hIST', b'sPLT'),  # how to show it
    *(b'cICP', b'mDCV', b'cLLI'),  # HDR color
    *(b'acTL', b'fcTL', b'fdAT'),  # animation
}
PNG_LABELS = {b'tEXt': TEXT, b'zTXt': TEXT, b'iTXt': TEXT, b'tIME': DATE, b'caBX': CREDENTIALS}


def _png_chunk(kind, payload):
    return len(payload).to_bytes(4, 'big') + kind + payload + zlib.crc32(kind + payload).to_bytes(4, 'big')


def _clean_png(data):
    out, removed, position, size = [PNG_SIGNATURE], [], 8, len(data)
    while position < size:
        length = int.from_bytes(data[position : position + 4], 'big')
        kind = data[position + 4 : position + 8]
        end = position + 12 + length
        if len(kind) < 4 or end > size:
            raise UnsupportedImage('PNG chunk runs past the end of the file')
        chunk, payload = data[position:end], data[position + 8 : end - 4]
        position = end
        if kind in PNG_KEEP:
            out.append(chunk)
        elif kind == b'eXIf':
            minimal = _replace_exif(payload, removed)
            if minimal:
                out.append(_png_chunk(b'eXIf', minimal))
        elif kind[:1].isupper():
            raise UnsupportedImage(f'PNG has an unknown critical chunk {kind!r}')
        elif kind == b'iTXt' and payload.startswith(b'XML:com.adobe.xmp\x00'):
            removed.append(XMP)
        else:
            removed.append(PNG_LABELS.get(kind, OTHER))
        if kind == b'IEND':
            if position < size:
                removed.append(EXTRAS)
            break
    return b''.join(out), removed


# --- WebP -----------------------------------------------------------------------------------

WEBP_KEEP = {b'VP8 ', b'VP8L', b'VP8X', b'ALPH', b'ANIM', b'ANMF', b'ICCP'}
WEBP_EXIF_FLAG, WEBP_XMP_FLAG = 0x08, 0x04


def _clean_webp(data):
    end = min(len(data), 8 + int.from_bytes(data[4:8], 'little'))
    kept, removed, position = [], [], 12
    while position + 8 <= end:
        kind = data[position : position + 4]
        length = int.from_bytes(data[position + 4 : position + 8], 'little')
        payload = data[position + 8 : position + 8 + length]
        if len(payload) != length:
            raise UnsupportedImage('WebP chunk runs past the end of the file')
        position += 8 + length + (length & 1)
        if kind in WEBP_KEEP:
            kept.append([kind, payload])
        elif kind == b'EXIF':
            tiff = payload[len(JPEG_EXIF_HEADER) :] if payload.startswith(JPEG_EXIF_HEADER) else payload
            minimal = _replace_exif(tiff, removed)
            if minimal:
                kept.append([kind, minimal])
        else:
            removed.append({b'XMP ': XMP, b'C2PA': CREDENTIALS}.get(kind, OTHER))
    if len(data) > end:
        removed.append(EXTRAS)
    has_exif = any(kind == b'EXIF' for kind, _ in kept)
    for item in kept:
        if item[0] == b'VP8X' and item[1]:
            flags = (item[1][0] & ~(WEBP_EXIF_FLAG | WEBP_XMP_FLAG)) | (WEBP_EXIF_FLAG if has_exif else 0)
            item[1] = bytes((flags,)) + item[1][1:]
    body = b''.join(kind + len(payload).to_bytes(4, 'little') + payload + b'\x00' * (len(payload) & 1) for kind, payload in kept)
    return b'RIFF' + (len(body) + 4).to_bytes(4, 'little') + b'WEBP' + body, removed
