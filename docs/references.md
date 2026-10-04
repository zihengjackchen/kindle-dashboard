# Upstream references

Reviewed during implementation on 2026-09-30 / 2026-10-01. Upstream command support
does not prove that the same version/build exists on the target Kindle.

- [KOReader KUAL menu](https://github.com/koreader/koreader/blob/master/platform/kindle/extensions/koreader/menu.json)
  and [extension descriptor](https://github.com/koreader/koreader/blob/master/platform/kindle/extensions/koreader/config.xml):
  nested items/actions and XML discovery. Stop keeps KUAL open and reloads its menu.
- [KUAL Booklet source](https://github.com/coplate/KUAL_Booklet/blob/master/src/com/mobileread/ixtab/kindlelauncher/KualBooklet.java):
  exit-menu behavior varies with launcher implementation.
- [FBInk command source/help](https://github.com/NiLuJe/FBInk/blob/master/fbink_cmd.c):
  image, flash, clear, refresh, and read-only state-query flags. All framebuffer
  calls are isolated in the display library. Do not eval state-query output.
- [KOReader Kindle power adapter](https://github.com/koreader/koreader/blob/master/frontend/device/kindle/powerd.lua):
  read-only battery percentage and charging properties, plus gasgauge fallback.
  This project does not use its power-setting operations.
- [FastAPI query validation](https://fastapi.tiangolo.com/tutorial/query-params-str-validations/)
  and [responses](https://fastapi.tiangolo.com/advanced/custom-response/).
- [Pillow font API](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html):
  packaged TrueType fonts and scalable default font.

eips `-f -g IMAGE` is a common Kindle image-display convention. Support and
reported geometry formats must be checked on your device. No eips power or
lockscreen command is used here.
