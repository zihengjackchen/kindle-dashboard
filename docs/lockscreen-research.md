# How existing projects handle Kindle sleep and advertisements

Reviewed 2026-10-01. This is research, not an installation guide or authorization
to alter the device. The user requires a standalone dashboard and has rejected
KOReader/book-viewer integration. Original no-ad-bypass and no-guessed-suspend
boundaries remain in force.

## Approaches observed

| Approach | Example/evidence | Relevance |
| --- | --- | --- |
| Officially unsubscribe from Special Offers | [Amazon's own description](https://www.aboutamazon.com/news/devices/fun-kindle-features) | Changes device entitlement through Amazon; not a jailbreak bypass, but the user has not requested this change |
| Replace the ordinary screensaver | [Classic screensaver documentation](https://wiki.mobileread.com/wiki/Kindle_Screen_Saver_Hack_for_all_2.x%2C_3.x_%26_4.x_Kindles) explicitly excludes Special Offers devices in its covered generations | An ordinary screensaver hook is not proof of compatibility with the separate ad screen |
| Disable idle screensaver behavior for a visible dashboard | [Weather-dashboard issue](https://github.com/matopeto/kindle-weather-dashboard/issues/16) | Keeping a visible page by inhibiting normal sleep is not evidence of low power; actual state must be measured |
| Take over suspend/wake around framebuffer images | [pascalw/kindle-dash](https://github.com/pascalw/kindle-dash), particularly [its shell implementation](https://github.com/pascalw/kindle-dash/blob/main/src/dash.sh) | Targets Kindle 4 NT; stops framework, suppresses native screensaver flow and directly suspends with RTC wake. Not a verified Paperwhite recipe or compatible with the present boundaries |
| Alter Special Offers directly | [Kindle-Screensaver-Settings](https://github.com/sgoeds/Kindle-Screensaver-Settings) | Its author describes toggling native screensaver components, tested on one generation; this explicitly changes ad behavior and is excluded |
| Permit native sleep and redraw after wake | [jefftko/kindle-dashboard](https://github.com/jefftko/kindle-dashboard/blob/main/README.md) | Avoids drawing in sleep states and restores after a wake event. Useful lifecycle reference, but the project does not establish Special Offers compatibility for this user's Paperwhite |

The distinction between the third and fourth approaches matters: suppressing a
native screensaver does not prove that a project never suspends. Some then invoke
their own suspend path. Conversely, an unchanged e-ink page proves nothing about
CPU/radio power state. Neither a README's battery claim nor a working older Kindle
script is sufficient evidence for a new model/firmware.

Another [screensaver-based project](https://github.com/kaibuildsai/kindle-for-whoop/blob/main/kindle/README.md)
reports an unattended RTC cycle on a Paperwhite 2 with firmware 5.10.3, requires
linkss for its automatic mode, and labels the broader deployment experimental.
This is useful device-specific evidence, not a solution to unchanged Special
Offers on an unidentified Paperwhite.

## Implication for this project

The reviewed sources do not demonstrate a portable, verified method that keeps
our dashboard visible in deep sleep while preserving the normal ad lockscreen
on this user's device. This is an evidence limit, not a claim of universal
technical impossibility.

The closest matching lifecycle is standalone dashboard while active -> native
sleep/lockscreen -> cached dashboard restored after normal wake and lockscreen
exit. It preserves ordinary power management but is not continuously visible.
Wake alone must not be treated as permission to draw over an ad swipe screen;
the display adapter must wait for the verified native lockscreen exit state.

A longer active-session idle timeout is a separate possible tradeoff, contingent
on explicit scope agreement, device support, bounded restoration and measured
battery use. No such timeout change is currently implemented. An indefinite
keep-awake loop remains excluded.
