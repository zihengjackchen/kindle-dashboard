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


### Native app and frontlight references

- https://github.com/crizmo/KWordle/blob/main/kwordle.sh ? app registration pattern.
- https://github.com/crizmo/KWordle/blob/main/kwordle/index.html ? system Close control.
- https://github.com/penguins184/Penguins-Kindle-Wiki/blob/main/Illusion-Guide.md ? Mesquite manifests and ES5 constraints.
- https://github.com/koreader/koreader/blob/master/frontend/device/kindle/powerd.lua ? native brightness zero differs from true light-off on older Paperwhites.

The dashboard implementation is original; no Wordle source/assets or KOReader
runtime is bundled. References establish API patterns, not proof of compatibility
with an untested device.

### Power approaches revisited, 2026-10-10

- [jstriblet/kindle-wall-display](https://github.com/jstriblet/kindle-wall-display):
  alarm readback, opt-in suspend testing, cached images and bounded recovery are
  useful principles. Its calendar.sh also stops the native GUI/webreader and changes
  the CPU governor during takeover. That is incompatible with simply dropping it
  into the active Mesquite app and does not prove Special Offers compatibility.
- [1RandomDev/kindle-smarthome-dashboard](https://github.com/1RandomDev/kindle-smarthome-dashboard):
  native WAF interaction and server offloading are relevant; its persistent
  WebSocket and standby prevention are explicitly described as battery hungry.
  We retain cached PNG navigation and short requests.
- [alexishida/kindle-dashboard](https://github.com/alexishida/kindle-dashboard):
  server-rendered images, atomic publication and diagnostics are useful patterns.
  Its Electron/local AI usage dependencies do not fit this standalone NAS service.

No upstream code was copied in this update. No boot integration, GUI shutdown,
lockscreen replacement, hardware alteration or raw suspend was introduced.
