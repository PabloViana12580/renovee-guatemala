# Owner images

Put the business's own photos and logos here (JPEG, PNG, or WebP, any size).
Then run:

    python manage.py optimize_images

It does three things:

1. **Cleans these originals in place.** This repository is public, so hidden data is removed
   from the files: GPS position, phone or camera model, dates, author and account names,
   comments, and Content Credentials (C2PA records of how an image was made). The picture
   itself is not re-encoded. Keep untouched copies somewhere else if you want that data.
2. **Writes web-sized WebP copies** to `static/img/`, turned the right way up.
3. **Lists them** in `static/img/CREDITS.md`.

## Publishing part of a picture

Social-media graphics often have a frame, text, or a phone number around the photo. To publish
only regions of an original, describe them in `crops.json` in this folder:

    {
      "lobby-sofa": {"from": "Post 12.jpg", "box": [0, 120, 1080, 740]}
    }

The key names the web copy (`static/img/lobby-sofa.webp`); `box` is left, top, right, bottom
in pixels of the original. An original with crops is published only as those crops; the other
originals are published whole.

These images belong to Rénovée Guatemala and are **not** covered by the
repository's MIT license: all rights reserved.
