# TheMoodSwicth

A Raspberry Pi device with five physical buttons for recording mood responses.
Develop on the Mac, keep source code in GitHub, and run the device on the Pi.

## Hardware and connection

- Verified device: Raspberry Pi 3 Model B Rev 1.2, hostname `alivetracker`.
- Observed operating system: Debian 13 (Trixie).
- SSH is enabled. Login username: `admin`.
- Last observed local address: `192.168.1.20` (may change with DHCP).
- Passwords and Google credentials must never be committed to this repository.

Connect from your Mac terminal using `ssh admin@192.168.1.20`.
Enter the password when prompted. Confirm a new host key against the Pi before
accepting it. To shut down cleanly, run `sudo shutdown -h now` on the Pi, wait
for shutdown to finish, and disconnect its power before changing wiring.

## Button wiring

These are **physical positions on the 40-pin header**, not GPIO numbers.
Each two-terminal switch connects one input to ground. Either switch terminal
can be used for either wire. Leave separate LED leads disconnected.

| Button | Physical input pin | BCM GPIO | Physical ground pin |
| --- | --- | --- | --- |
| 1 | 11 | 17 | 9 |
| 2 | 13 | 27 | 14 |
| 3 | 15 | 22 | 20 |
| 4 | 16 | 23 | 25 |
| 5 | 18 | 24 | 30 |

Pins 13 and 14 are opposite each other across the two rows. Pin 18 is opposite
17, and pin 30 is opposite 29. Do not assume which row is top or bottom without
checking board orientation.

Reference: [official Raspberry Pi GPIO documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html).

## Current implementation

- `moodswitch/recorder.py`: records events to SQLite with a unique event ID,
  response identifier, UTC timestamp, and unsynced status.
- A thread-safe, global five-second cooldown ignores all other presses after
  an accepted response. The cooldown duration is configurable.
- `button_test.py`: live wiring diagnostic using gpiozero, internal pull-ups,
  and 50 ms debounce. Prints press and release events; does not save responses.
- Tests verify cooldown boundaries, persistence, and simultaneous presses.

The recorder and GPIO diagnostic are separate at this stage. No automatic
startup service, audio confirmation, dashboard, or cloud sync is installed yet.

## Run the wiring test

On the Pi, from the repository directory:

```sh
python3 button_test.py
```

The Pi already has gpiozero available. Wait for the readiness message, then
press and release one physical button at a time. Match the displayed number
to the table. Stop with Ctrl+C. If a held button produces repeated transitions,
check the switch contacts and wiring before relying on logged responses.

## Run software tests

From the repository directory on the Mac or Pi:

```sh
python3 -m unittest discover -s tests -v
```

## Hardware validation status

- Buttons 1–4 produced matching press/release events during individual tests.
- Button 5 initially produced no events. After the user corrected its wiring,
  the restarted test detected matching button-five press and release events.
  All five inputs have now registered.
- Subsequent three-second holds of all five buttons each produced exactly one
  press and one release, confirming stable signals for those tests. All five
  buttons passed individual mapping and sustained-press checks. Earlier repeated
  transitions alone did not establish a wiring fault.

## Planned behaviour and next steps

1. Hardware milestone complete: all five buttons verified with stable holds.
2. Connect GPIO events to the SQLite recorder. An accepted press saves one
   response; presses during the shared five-second cooldown save nothing.
3. Play a response-specific WAV only after a successful save. Ignored presses
   produce no sound.
4. Add a locally hosted dashboard showing recent presses and per-button totals
   for all time, each day, and each week. Use Europe/London calendar boundaries.
   Access from the Mac will need the Pi's address or an SSH tunnel; `localhost`
   on the Mac refers to the Mac itself.
5. Add a systemd service for startup and recovery after crashes.
6. Sync unsynced SQLite events to Google Sheets with retry and deduplication by
   event ID. Keep SQLite authoritative when Wi-Fi is unavailable.
7. Add separate weekly reporting once storage and sync are reliable.

Mood labels, sound files, and Google Sheets destination remain to be chosen.
