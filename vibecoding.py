
import time
import re
import pyautogui
import pytesseract
from PIL import ImageOps, ImageEnhance
from pynput import keyboard


BOARD_X = 336
BOARD_Y = 162
BOARD_SIZE = 640
SQUARE_SIZE = BOARD_SIZE / 8


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True


# -----------------------------------------
# KEYBOARD SHORTCUT MAPPING
# -----------------------------------------

KEY_ROWS = [
    "qwertyui",  # Rank 1: a1=q, b1=w, ... h1=i
    "asdfghjk",  # Rank 2
    "zxcvbnm1",  # Rank 3
    "23456789",  # Rank 4
    "QWERTYUI",  # Rank 5
    "ASDFGHJK",  # Rank 6
    "ZXCVBNM!",  # Rank 7
    "@#$%^&*(",  # Rank 8
]

SQUARE_KEYS = {}
KEY_SQUARES = {}

for rank, row in enumerate(KEY_ROWS, start=1):
    for file_index, key_name in enumerate(row):
        square = ("abcdefgh"[file_index], rank)
        SQUARE_KEYS[square] = key_name
        KEY_SQUARES[key_name.lower()] = square

selected_square = None

# -----------------------------------------
# AUTOMATIC BOARD ORIENTATION DETECTION
# -----------------------------------------

def detect_board_orientation():
    """
    Read the rank labels on the left edge of the board.

    Normal orientation: 8 at top, 1 at bottom.
    Flipped orientation: 1 at top, 8 at bottom.

    Returns True if flipped, False if normal.
    Raises RuntimeError if detection is uncertain.
    """

    screenshot = pyautogui.screenshot()

    # Crop a narrow strip containing the rank labels.
    label_strip = screenshot.crop((
        max(0, BOARD_X),
        max(0, BOARD_Y),
        min(screenshot.width, BOARD_X + 28),
        min(screenshot.height, BOARD_Y + BOARD_SIZE)
    ))

    # Enlarge and improve contrast for OCR.
    label_strip = label_strip.resize(
        (label_strip.width * 4, label_strip.height * 4)
    )
    label_strip = ImageOps.grayscale(label_strip)
    label_strip = ImageEnhance.Contrast(label_strip).enhance(2.5)

    # OCR returns recognized characters with their positions.
    data = pytesseract.image_to_data(
        label_strip,
        config="--psm 11 -c tessedit_char_whitelist=12345678",
        output_type=pytesseract.Output.DICT
    )

    recognized = []

    for i, raw_text in enumerate(data["text"]):
        text = raw_text.strip()

        if text not in "12345678" or len(text) != 1:
            continue

        confidence = float(data["conf"][i])
        if confidence < 20:
            continue

        center_y = (
            data["top"][i] + data["height"][i] / 2
        ) / 4

        recognized.append((center_y, int(text)))

    # Find labels near the top and bottom of the board.
    top_candidates = [
        digit for y, digit in recognized
        if y < BOARD_SIZE * 0.20
    ]
    bottom_candidates = [
        digit for y, digit in recognized
        if y > BOARD_SIZE * 0.80
    ]

    if not top_candidates or not bottom_candidates:
        raise RuntimeError(
            "Could not read board labels. "
            "Check BOARD_X, BOARD_Y and BOARD_SIZE."
        )

    # Use the recognized label nearest each edge.
    top_y, top_digit = min(
        (item for item in recognized
         if item[1] in top_candidates),
        key=lambda item: item[0]
    )

    bottom_y, bottom_digit = max(
        (item for item in recognized
         if item[1] in bottom_candidates),
        key=lambda item: item[0]
    )

    if top_digit == 1 and bottom_digit == 8:
        print("Detected Black at the bottom: flipping coordinates.")
        return True

    if top_digit == 8 and bottom_digit == 1:
        print("Detected White at the bottom: normal coordinates.")
        return False

    raise RuntimeError(
        f"Unclear orientation: top={top_digit}, "
        f"bottom={bottom_digit}. Please recalibrate."
    )


# Detect orientation once when the script starts.
print("Detecting Chess.com board orientation...")
time.sleep(1)

try:
    BOARD_FLIPPED = detect_board_orientation()
except Exception as error:
    print("Orientation detection failed:", error)
    print("Check the board coordinates and Tesseract installation.")
    raise SystemExit(1)


# -----------------------------------------
# SQUARE COORDINATES
# -----------------------------------------

def square_center(square):
    """Return screen coordinates for a chess square."""

    file_name, rank = square

    col = ord(file_name) - ord("a")
    row = 8 - rank

    if BOARD_FLIPPED:
        col = 7 - col
        row = 7 - row

    x = BOARD_X + (col + 0.5) * SQUARE_SIZE
    y = BOARD_Y + (row + 0.5) * SQUARE_SIZE

    return int(x), int(y)


# -----------------------------------------
# MOUSE CONTROL
# -----------------------------------------

def click_square(square):
    x, y = square_center(square)
    pyautogui.click(x, y)


def move_piece(source, destination):
    """Drag a piece from source to destination."""

    sx, sy = square_center(source)
    dx, dy = square_center(destination)

    print(
        f"Moving {source[0]}{source[1]} "
        f"to {destination[0]}{destination[1]}"
    )

    pyautogui.moveTo(sx, sy, duration=0.12)
    pyautogui.mouseDown()
    time.sleep(0.12)
    pyautogui.moveTo(dx, dy, duration=0.25)
    pyautogui.mouseUp()


# -----------------------------------------
# KEYBOARD HANDLING
# -----------------------------------------

def normalize_key(key):
    """Convert pynput keys into shortcut names."""

    if key in (
        keyboard.Key.ctrl,
        keyboard.Key.ctrl_l,
        keyboard.Key.ctrl_r
    ):
        return "ctrl"

    if key in (
        keyboard.Key.alt,
        keyboard.Key.alt_l,
        keyboard.Key.alt_r,
        keyboard.Key.alt_gr
    ):
        return "alt"

    if key in (
        keyboard.Key.shift,
        keyboard.Key.shift_l,
        keyboard.Key.shift_r
    ):
        return "shift"

    if hasattr(key, "char") and key.char:
        return key.char.lower()

    if key == keyboard.Key.esc:
        return "esc"

    return None


def on_press(key):
    global selected_square

    name = normalize_key(key)

    if name in {"ctrl", "alt", "shift"}:
        held_modifiers.add(name)
        return

    if name == "esc":
        print("Stopping bot.")
        return False

    if name not in BASE_KEYS:
        return

    shortcut = (frozenset(held_modifiers), name)
    square = KEY_SQUARES.get(shortcut)

    if square is None:
        return

    if selected_square is None:
        selected_square = square
        click_square(square)
        print(f"Selected {square[0]}{square[1]}")

    else:
        if square == selected_square:
            selected_square = None
            print("Selection cancelled.")
            return

        move_piece(selected_square, square)
        selected_square = None


def on_release(key):
    name = normalize_key(key)

    if name in {"ctrl", "alt", "shift"}:
        held_modifiers.discard(name)


# -----------------------------------------
# START
# -----------------------------------------

print("Chess mouse bot running.")
print(f"Board flipped: {BOARD_FLIPPED}")
print("Press a square shortcut to select a square.")
print("Press another square shortcut to drag to it.")
print("Press Esc to quit.")
print("Move mouse to top-left corner for emergency stop.")

with keyboard.Listener(
    on_press=on_press,
    on_release=on_release
) as listener:
    listener.join()
## git remote add origin https://github.com/SUPPAWEEB/chess_cursor.git
##git branch -M main
##git push -u origin main