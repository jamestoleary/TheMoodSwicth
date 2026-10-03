"""Run on the Pi to verify wiring without recording mood responses."""
from functools import partial
from signal import pause
from gpiozero import Button


def report(number, state):
    print(f"Button {number}: {state}", flush=True)


def main():
    buttons = []
    try:
        for number, pin in enumerate([17, 27, 22, 23, 24], start=1):
            button = Button(pin, pull_up=True, bounce_time=0.05)
            buttons.append(button)
            button.when_pressed = partial(report, number, "PRESSED")
            button.when_released = partial(report, number, "released")
        print("Ready. Press each button individually. Ctrl+C to stop.", flush=True)
        pause()
    except KeyboardInterrupt:
        pass
    finally:
        for button in buttons:
            button.close()


if __name__ == "__main__":
    main()
