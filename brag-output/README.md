# Launch showcase

A 20-second product film created using the [brag skill](https://github.com/latent-spaces/brag)
and [Hyperframes](https://github.com/heygen-com/hyperframes).

The film uses a real Kindle framebuffer capture and screenshots from the running
NAS editor. The device casing is illustrated. The Kindle capture is from October
10, 2026; NAS captures are from October 11. The SSH banner is cropped, and the
editor uses an unsaved draft that omits private account usage. There is no fabricated
on-device page transition. [Capture provenance](../docs/showcase/live/README.md).
The soundtrack is an original, locally synthesized score.

[![Launch showcase poster](brag.jpg)](composition/index.html)

## Preview and rebuild

Requires Node.js 22+, a Chromium browser, FFmpeg and FFprobe. These tools are for
the showcase only; the Kindle app and NAS server do not depend on them.

```sh
# From the repository root, after installing the Python/browser dev dependencies:
python scripts/build-real-showcase.py
python scripts/build-brag-assets.py
cd brag-output/composition
npm run check
npm run dev
```

The composition pins Hyperframes 0.8.149 and GSAP 3.14.2. Review the local preview,
then export with:

```sh
npm run render -- --quality delivery --output ../brag.mp4
ffmpeg -ss 2 -i ../brag.mp4 -frames:v 1 -q:v 2 ../brag.jpg
```

Use the settled hook at two seconds as the poster, and bake it into frame zero
so players can show a useful thumbnail. The included `brag.jpg` previews that beat. The editable source and
storyboard remain in Git. See [asset provenance](composition/assets/NOTICE.md).

- [Storyboard](brag-plan.md)
- [Composition brief](composition-brief.md)
- [Share copy](share-copy.txt)

The Hyperframes audit covers runtime, layout and text contrast. Short scenes stay
in one source file, and the genuine Kindle capture is intentionally reused for
the opening and app-controls scenes.
