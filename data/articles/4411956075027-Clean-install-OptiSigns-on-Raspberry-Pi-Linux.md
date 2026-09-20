# Clean install OptiSigns on Raspberry Pi/Linux

Article URL: https://support.optisigns.com/hc/en-us/articles/4411956075027-Clean-install-OptiSigns-on-Raspberry-Pi-Linux
Article ID: 4411956075027
Updated: 2026-09-10T09:47:36Z

To completely clean out old installation of OptiSigns on Linux or Raspberry Pi

Please run:

```
rm -rf ~/.config/OptiSignsrm ~/.config/autostart/'OptiSigns Digital Signage.desktop'
```

Also delete the long string text on this ~/.config folder

Then install the new AppImage download from <https://www.optisigns.com/download>
