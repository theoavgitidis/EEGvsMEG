# Unicorn Hybrid Black and Suite Summary

This is a practical summary of the Unicorn Suite Hybrid Black user manual. The system is intended for non-medical EEG and BCI work by developers, artists, makers, and gamers.

## Unicorn Hybrid Black Headset

- The bundle includes the battery-powered Unicorn Brain Interface, a size-M cap, eight hybrid EEG electrodes, 50 disposable sticky electrodes, a USB charging cable, a Bluetooth dongle, and Unicorn Suite software.
- The brain interface is an 8-channel, 24-bit EEG amplifier sampling each channel at 250 Hz. It also includes a 3-axis accelerometer and gyroscope, and sends data over Bluetooth 2.1 + EDR.
- Hybrid electrodes may be used dry for quick setup or with Unicorn Gel to improve contact and signal quality. The eight cap positions are Fz, C3, Cz, C4, Pz, PO7, Oz, and PO8. Attach the disposable L and R sticky electrodes to the mastoids behind the ears.
- Secure the brain interface to the cap using its magnetic docking station. Lift the interface rather than pulling electrode leads; the dock self-centers and cannot be connected upside down.
- Hold the power button for more than two seconds to turn the interface on or off. The status LED indicates battery state: cyan is OK, yellow is low, red is empty, and green is charging. A flashing LED means Bluetooth is disconnected, slow blinking means connected, and continuous light means acquisition is running.
- Charge via the supplied USB cable. Charging takes about three hours from empty; the device cannot be turned on while USB is connected. Store batteries around 50% charge and cycle them every 90 days during long storage.

### Recording Setup

1. Check the device, leads, connectors, and cap for damage before every session.
2. Fit the cap so electrode pressure is gentle but firm. Align cap position 3 to the subject's vertex, then secure the chin strap.
3. Clean the skin behind each ear with 70% medical alcohol, apply the L and R sticky electrodes, and connect their clips.
4. Twist each cap electrode gently in both directions to move its pins through hair and improve scalp contact.
5. Wait two to three minutes for channels to stabilize. If signals remain poor, repeat electrode preparation and check fit, pressure, movement, and environmental interference.
6. For clearer EEG, the manual recommends a 0.5-30 Hz or 2-30 Hz bandpass filter and a 50/60 Hz notch filter.

### Signal Quality and Safety

- Keep the subject relaxed and still, and route leads so they are not under tension or near moving objects. Motion, loose electrodes, cable movement, and static charge create artifacts.
- Prefer an antistatic room, natural-material furnishings and clothing, and grounded equipment where possible. Discharge static electricity by touching grounded metal before handling the device.
- Use only on healthy, intact skin. Do not use near wounds, on irritated skin, or with people who have skin sensitivity. Remove the cap if irritation occurs. Limit a single recording session to three hours.
- Do not use the device in wet or explosive environments, with high-frequency devices, or on people with pacemakers or electrical stimulators. Remove electrodes before defibrillation.
- Keep conductive electrode parts away from earth and other conductive objects. The headset is for non-medical use only.

### Cleaning and Storage

- Disconnect USB before cleaning. Keep the brain interface and cables dry: wipe them with a damp cloth or suitable disinfection wipes; never submerge them or allow liquid, gel, or germicide inside.
- Clean dry electrodes with a soft cloth and 70% isopropyl alcohol or disinfection wipes. For wet use, brush all gel from electrodes.
- Wash the cap in 30-35 C water with shampoo, soap, or an approved enzymatic cleaner. Do not soak it for more than 10 minutes; rinse thoroughly.
- Air dry the cap in a ventilated location, without stretching it. Do not use a dryer, hot air, iron, washing machine, ultrasonic bath, or autoclave.
- Store only fully dry components. Do not pinch, kink, knot, or pull electrode cables. Replace caps that have lost elasticity and replace worn electrodes as needed.

## Unicorn Suite Hybrid Black

- Unicorn Suite is the Windows software environment for pairing the headset, acquiring data, running licensed applications, and accessing development tools and APIs.
- The manual specifies Windows 11 Pro, 64-bit, English edition, a 2 GHz or faster CPU, 4 GB RAM, 20-30 GB free disk space, and Bluetooth 2.1 + EDR support.
- Install by running the Win64 `setup.exe`; uninstall older Suite versions first. The default installation directory is `C:\Program Files\gtec\`.

### Bluetooth and Pairing

- Use the supplied Unicorn Bluetooth dongle, identified as `CSR8510 A10`; other dongles can cause data loss or unexpected behavior.
- In the My Unicorn tab, a green Bluetooth symbol means the recommended adapter is active. A blinking red symbol indicates a missing, invalid, or incorrectly configured adapter.
- If the computer uses its internal Bluetooth adapter, disable it in Windows Device Manager, reconnect the Unicorn dongle, and confirm it appears as `Generic Bluetooth Radio`.
- Disable power saving for the Generic Bluetooth Radio by clearing `Allow the computer to turn off this device to save power` in its Power Management properties.
- Pair a discovered headset from the My Unicorn tab or Windows Bluetooth settings, then follow the Windows pairing prompt. A green circle indicates paired devices ready for use.
- Configure Windows power settings so the computer does not sleep, hibernate, or activate a screensaver during recording or paradigms.

### Apps, Development Tools, and Licenses

- The Apps tab provides standalone applications; the DevTools tab provides APIs. Some tools are free and others require a license.
- Download an app or development tool, then select its play button to install it.
- Activate a purchased license from the Licenses tab using the Product ID, license key, and license email supplied by g.tec. Licenses can also be deactivated there.
- Licenses refresh when the Suite starts and the license server is reachable. Offline use is supported for up to one week after a successful refresh; after that, an online refresh is required.
- When upgrading from version 1.18.00 to 1.24.00, uninstall the old Suite, install the latest release, then download and install required apps and development tools. Existing license keys should remain installed.
