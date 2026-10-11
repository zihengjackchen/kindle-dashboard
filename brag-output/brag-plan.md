# Brag plan: Kindle Dashboard

## Planning rubric

1. A self-hosted NAS service turns a jailbroken Kindle into a configurable e-ink dashboard.
2. One refresh downloads every page; switching pages works offline.
3. Crisp grayscale widget pages against the editor's warm paper and sage palette.
4. Show the actual editor, client navigation, and rendered pages.
5. Twenty seconds gives four readable beats.
6. Polished: a quiet product film for a quiet screen.
7. Original soft plucked synth bed with two gentle interface accents. No narration.
8. “A quieter place for your day. Weather, markets, Markdown and your home server, on a Kindle you already own.”
9. Arrange widgets in a browser → refresh once → browse cached pages on the Kindle.

## Identity and scope

Background #f4f5ef, ink #23332c, muted #627268, accent #dced8b.
Sans-serif display and body, matching the existing editor. Landscape 1920×1080.
Use the real October 10 Kindle framebuffer capture and October 11 NAS/editor captures. Device outlines are illustrations, not photos. The SSH address banner is cropped and account usage is omitted from the unsaved editor preview.
Do not claim dashboard-preserving suspend, measured battery life, brokerage access,
or support for all Kindle models. Special Offers are untouched.

## Storyboard — 20 seconds

| Time | Beat | Visual and readable text | Motion / audio |
| --- | --- | --- | --- |
| 0–4 | Hook | Real Kindle screen, including native chrome, in a Kindle casing. “A quieter place for your day.” | Frame enters from right; headline settles quickly. Soft original music begins. |
| 4–10 | Editor | Actual widget editor. “Arrange it your way.” “Choose widgets. Pick the details.” | UI settles into a large panel, gentle push-in. Small click accent. |
| 10–16 | Use it | Actual Kindle client screen; retain the captured pixels without fabricating a page change. “One refresh. Every page.” “Browse your cached pages offline.” | Gently move the device frame while the genuine captured UI remains visible. |
| 16–20 | Outro | Real weather, markets and NAS preview PNGs. “Kindle Dashboard” / “Self-hosted. Yours to arrange.” | Three pages arrive sequentially then hold; music resolves and fades. |

## Music cue guidance

Generate a deterministic original score locally at 96 BPM. Use natural scene
timing for readability; the native controls remain visible long enough to inspect.
Audio-reactivity: none; the still, paper-like presentation is deliberate. No
bundled music is redistributed because its exact licensing is undocumented.

## Output

Editable Hyperframes composition in `composition/`; final review in local Studio.
After review, render `brag.mp4`, choose the settled hook as `brag.jpg`, and bake
that poster into frame zero. Share copy lives beside the composition.
