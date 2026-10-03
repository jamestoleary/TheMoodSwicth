# TheMoodSwicth

A Raspberry Pi device with five physical buttons for recording emotional states.
Develop on your computer, keep source code in GitHub, and run the device on the Pi.
Built with assistance from Codex.

## Where the code and data live

Choose a source folder on your computer, such as `~/Documents/TheMoodSwicth`.
The examples below deploy to `~/TheMoodSwicth` on the Pi. `~` means the home
directory of the user on the machine where the command runs. Replace
`<pi-user>` and `<pi-host>` with your Pi login and hostname or IP address.
The bundled service files expect the Pi app at `~/TheMoodSwicth`; edit their
paths if you choose a different location.

| Purpose | Example location |
| --- | --- |
| Source checkout on your computer (edit here) | `~/Documents/TheMoodSwicth/` |
| GitHub remote | `https://github.com/jamestoleary/TheMoodSwicth.git` |
| Deployed application folder on the Pi | `~/TheMoodSwicth/` |
| Python application code on the Pi | `~/TheMoodSwicth/moodswitch/` |
| Dashboard page on the Pi | `~/TheMoodSwicth/moodswitch/dashboard.html` |
| Ordinary button/audio settings on the Pi | `~/TheMoodSwicth/config.json` |
| Numbered WAV files on the Pi | `~/TheMoodSwicth/audio/` |
| Persistent SQLite event database on the Pi | `~/TheMoodSwicth/data/events.db` |
| Sync process lock on the Pi | `~/TheMoodSwicth/data/events.sync.lock` |
| Private Google sync settings | `~/.config/moodswitch/sync.json` |
| Private Google key | `~/.config/moodswitch/google-service-account.json` |
| Installed recorder service | `~/.config/systemd/user/moodswitch.service` |
| Installed active sync service and timer | `~/.config/systemd/user/moodswitch-sync.service` and `~/.config/systemd/user/moodswitch-sync.timer` |
| Separate sync dependency environment | `~/TheMoodSwicth/.venv-sync/` |

Edit your **local checkout**, then copy changes over SSH to the Pi's
deployed application folder. With the copy workflow below, the Pi folder is a
deployment copy rather than a Git clone. Local edits and new audio are not
automatically copied to the Pi or pushed to GitHub. GitHub commits and pushes are separate steps.

SQLite stores each accepted response on the Pi's SD card and commits it before
audio is queued. The file persists across application restarts and normal Pi
shutdowns. A failed save produces no confirmation sound. Clean shutdown is
recommended; abruptly removing power can interrupt writes or damage the SD
card/filesystem. Google Sheets now receives periodic copies of accepted responses.
Application logs are in the systemd user journal, separate from the event database.

### Configuration and secrets

No `.env` file is needed or read by the app. `config.json` holds ordinary
settings and can be committed. `sync.example.json` is a safe template; the real
sync settings and Google key live under `~/.config/moodswitch/`,
outside the deployed repository folder. Protect the directory with mode 700
and the files with mode 600. Never commit passwords or private keys.
Keep downloaded keys outside your source checkout where possible. If you keep
a key inside the checkout, add its filename to a local Git exclusion before
committing and verify it with `git check-ignore <key-file>` and
`git ls-files -- <key-file>` (the latter must return no tracked file).
Never include real credential filenames or contents in public documentation.
The ignore rules also exclude `.env`, local databases, dependency environments,
`sync.json`, and service-account key filenames as a secondary safeguard.

### Copy subsequent changes from your computer

From your local checkout directory, this copies code and audio while preserving
the Pi's event database and dependency environments:

```sh
rsync -av --exclude='.git/' --exclude='data/' --exclude='.venv/' \
  --exclude='.venv-sync/' --exclude='__pycache__/' --exclude='.env' \
  --exclude='sync.json' --exclude='*service-account*.json' \
  --exclude='<your-key-filename>.json' \
  --exclude='credentials*.json' --exclude='*.db' --exclude='*.db-*' \
  ./ "<pi-user>@<pi-host>:~/TheMoodSwicth/"
ssh "<pi-user>@<pi-host>" 'systemctl --user restart moodswitch.service'
```

Replace the key-file exclusion with your actual filename, or remove that line
if your key is outside the checkout. The sync credentials remain outside that copy. There is no `--delete`, so this
does not remove existing Pi files. When replacing a numbered audio file, avoid
leaving two WAVs with the same leading number in the Pi's audio folder.

## Hardware and connection

- Tested hardware: Raspberry Pi 3 Model B Rev 1.2, with a 40-pin GPIO header.
- Tested operating system: Debian 13 (Trixie).
- Enable SSH and Wi-Fi during operating-system setup. Choose your own username
  and hostname; use those values in the connection examples.
- Passwords and Google credentials must never be committed to this repository.

Connect from your computer's terminal using `ssh "<pi-user>@<pi-host>"`.
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
- `moodswitch/app.py` connects all five physical inputs to the recorder and
  provides a read-only local dashboard.
- The dashboard shows held buttons and short press flashes, whether or not the
  press was accepted; separate saved-response totals cover today, this week,
  and all time, with a recent-events list and a cooldown countdown.
- `config.json` configures button labels, BCM pins, debounce, timezone, and
  cooldown. These are five distinct categories, not an ordered happiness score.
  Stable stored IDs remain `button_1`–`button_5`.

| Button | Phrase / dashboard label | Meaning |
| --- | --- | --- |
| 1 | ⚡ I'm alive | Energetic, lots of energy |
| 2 | 😴 I'm dead | Exhausted, wants to curl up and sleep |
| 3 | 📺 I'm watching TV | Chilling, zoning out |
| 4 | 👀 I'm watching you | Anxious, on edge, looking around |
| 5 | 😠 Fuck you | Angry |

Button numbers identify categories and their audio files; do not average them
or interpret 1–5 as a severity scale. Labels and meanings can be changed in
configuration without changing existing stored button IDs.

The app is deployed to `~/TheMoodSwicth` on the Pi and runs as the
`moodswitch.service` user service. Numbered WAV playback is implemented; cloud
Google Sheets sync is implemented. The wiring diagnostic is separate and must not run
alongside the app.

## Audio files

Place WAV files in the repository's `audio/` folder, starting each filename
with its button number: `1-alive.wav`, `2-dead.wav`, and so on through `5`.
Words after the number do not affect matching. Use exactly one WAV per number;
multiple matches are logged as an error rather than choosing an arbitrary file.
Files beginning with `10` do not match button `1`. WAV extensions are matched
without regard to case.

Only successfully saved responses queue audio. A press during cooldown stays
silent. Missing files and playback failures are logged but do not prevent event
storage. The playback worker runs separately from button detection. Keep clips
shorter than five seconds for immediate feedback before the next accepted press.

The configured device `plughw:CARD=Headphones,DEV=0` routes through the Pi's
3.5 mm jack using `aplay`. Connect that jack to a powered speaker and check the
speaker's volume. Set `audio_device` to `null` to use the system default output.
New files are discovered on the next accepted press **after copying them to
the Pi's audio folder**; adding a file on your computer alone does not transfer it.

## Google Sheets sync

The optional sync component uploads accepted responses every five minutes
when its timer is configured and enabled. The recorder continues saving
locally when the internet is unavailable. The Pi authenticates using a private
service-account key; it does not need a connected Codex Google Drive account.

Create your own destination spreadsheet and configure its ID using the setup
below. Do not publish your private spreadsheet link or service-account details.

Use a dedicated spreadsheet with a tab named `Events`. Its header row must be:

| A | B | C | D | E | F | G | H |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Event ID | Recorded at (UTC) | Button | Phrase | Emotion | Local date | Local time | Timezone |

An empty tab will receive these headers automatically. The job refuses to write
to a tab with different headers. It uploads up to 1,000 queued events per run in
batches of 100. Every batch checks existing event IDs first, so a later retry can
recognise an upload whose acknowledgement was lost. Local events are marked
synced only after a successful response or confirmation that their ID already
exists remotely. SQLite events are never deleted by sync.

Run only this Pi's sync writer against the Events tab. Do not delete or edit its
IDs; use a separate tab for analysis. The file lock prevents overlapping sync
jobs on this Pi. Once marked synced, an event isn't automatically recreated if
someone later deletes its Google Sheets row.

### One-time Google setup

1. Enable the Google Sheets API in a Google Cloud project.
2. Create a service account for this device. No project administrator role or
   domain-wide delegation is required to access a specifically shared sheet.
3. Create and download its JSON key, keep it private, and share only the target
   spreadsheet with the service account email as Editor.
4. Store the key on the Pi at
   `~/.config/moodswitch/google-service-account.json`, outside Git.
5. Copy `sync.example.json` to `~/.config/moodswitch/sync.json`, replace
   the spreadsheet ID, and keep the `Events` tab name or set the exact chosen tab.
6. Protect that directory and both files with permissions 700 and 600 respectively.

Reference: [Google service-account credentials and file sharing](https://developers.google.com/workspace/guides/create-credentials).

On the Pi, from the repository directory, install the sync dependencies:

```sh
python3 -m venv .venv-sync
.venv-sync/bin/python -m pip install -r requirements-sync.txt
```

After credentials and the destination are configured, test one sync first:

```sh
.venv-sync/bin/python -m moodswitch.sync
```

Check the remote event rows against local responses, then enable periodic sync:

```sh
cp moodswitch-sync.service moodswitch-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now moodswitch-sync.timer
```

The first run is scheduled after startup, with later runs five minutes after
the preceding run finishes. Failed runs leave queued data local for the next
run. Check `systemctl --user list-timers moodswitch-sync.timer` and
`journalctl --user -u moodswitch-sync.service`. Recording and audio continue
independently while sync runs or Wi-Fi is unavailable.

## Open the live dashboard

The installed Pi service listens on its network interfaces and starts automatically
at boot. On a device on the same local network, open:

- Local hostname: `http://<pi-hostname>.local:8080/`
- IP address: `http://<pi-ip-address>:8080/`

Replace the placeholders with the hostname or current address of your Pi.

No SSH tunnel is required. The name before `.local` is the Pi’s configured hostname, not its login
username or the project name. For example, a Pi named `mood-switch` is
available at `http://mood-switch.local:8080/`. Check its hostname by running
`hostname` on the Pi. The service uses port `8080` by default and starts at
boot after the user service is enabled and lingering is configured below.
Give the Pi a unique hostname on your network to avoid name conflicts.
The local name uses mDNS (Avahi on the Pi);
if your device cannot resolve it, use the IP address. The router may change
the IP address, so reserve it for the Pi in the router's DHCP settings if you
want that address to stay fixed. The dashboard has no login: devices on your
local network can read it. Do not forward this port through your router.

Reference: [Raspberry Pi local hostname documentation](https://www.raspberrypi.com/documentation/computers/remote-access.html).

Manual app launches default to loopback; use `--host 0.0.0.0` for LAN access.
The dashboard refreshes approximately five times
per second and preserves brief press flashes between updates. A held button
lights up, while a press during cooldown is displayed but not saved or counted.
Statistics use Europe/London dates; weeks start on Monday.

## Run and manage the app

On the Pi, from the repository directory:

```sh
python3 -m moodswitch.app
```

Events live in `data/events.db`; this database is ignored by Git. Do not delete
it during deployments. To install the user service from the Pi checkout:

```sh
mkdir -p ~/.config/systemd/user
cp moodswitch.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now moodswitch.service
sudo loginctl enable-linger "$USER"
```

Lingering lets the user service run at boot without an interactive login.
Check status and logs with:

```sh
systemctl --user status moodswitch.service
journalctl --user -u moodswitch.service -f
```

After updating code or configuration, run
`systemctl --user restart moodswitch.service`. Stop the service with
`systemctl --user stop moodswitch.service` before running `button_test.py`,
then start it again with `systemctl --user start moodswitch.service` afterwards.
On your development computer, a dashboard-only preview is available using
`python3 -m moodswitch.app --no-gpio`; it does not receive physical presses.

## Run the wiring test

On the Pi, from the repository directory:

```sh
python3 button_test.py
```

Install gpiozero on the Pi if it is not already available. Wait for the readiness message, then
press and release one physical button at a time. Match the displayed number
to the table. Stop with Ctrl+C. If a held button produces repeated transitions,
check the switch contacts and wiring before relying on logged responses.

## Run software tests

From the repository directory on your computer or Pi:

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
2. Implemented: GPIO events feed SQLite. An accepted press saves one response;
   presses during the shared five-second cooldown save nothing. Live hardware
   validation of the combined app passed through user button presses.
3. Implemented: response-specific numbered WAVs play only after a successful
   save. Ignored presses produce no sound. The user confirmed audible playback.
4. Implemented: locally hosted live dashboard with recent responses and button
   totals for today, this week, and all time, using Europe/London boundaries.
5. Installed: systemd user service for startup and recovery after crashes.
   Automatic startup was verified after a power cycle on the development device.
6. Implemented and tested: Google Sheets sync with event-ID reconciliation and
   offline retry. Credentials, destination, and live upload are validated; the
   five-minute timer is active. SQLite remains authoritative offline.
7. Add separate weekly reporting once storage and sync are reliable.

Configure your own Google Sheets destination and Pi authentication before
enabling sync. Separate weekly reporting remains future work.
