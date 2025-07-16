# Castle Pong

*Breakout meets tower-defence in a retro 8-bit castle siege*

Castle Pong is an arcade action game built with **pygame**.  Deflect
cannonballs with four paddles, protect your castle walls, collect coins
and power-ups, and survive increasingly difficult waves.

---

## Objectives

1. **Keep your castle intact** - Use your paddles to deflect incoming cannonballs.
2. **Destroy the enemy castle** - Break the enemy castle blocks to get hearts to heal your paddle or coins to spend on upgrades.
3. **Get the highest score** - Get the highest score you can on each wave and top the leaderboard.

A game ends when the castle wall is fully destroyed.

---

## Core Mechanics

| Mechanic | Details |
|----------|---------|
| **Four-sided paddles** | Top/bottom paddles move horizontally; left/right paddles move vertically.
| **Spin & curves** | Striking a ball with a moving paddle imparts spin and extra velocity.
| **Castle blocks** | Each block has multiple health tiers that crack, crumble and eventually break.
| **Power-ups** | Potions grant temporary effects like sticky paddles or power balls.
| **Coins & Store** | Destroyed blocks drop coins. Pause the game or wait till the end of a wave to view the store and buy permanent upgrades.
| **Wave system** | Each successive wave grows the castle footprint and cannon count.

---

## Controls (default)

| Action | Keys |
|--------|------|
| Move Bottom / Top paddle | `←` `→`  or `A` `D`
| Move Left / Right paddle | `W` `S`  or `↑` `↓`
| Launch stuck balls       | `Space`
| Select Menu / UI Option  | `Space` / `Enter`
| Pause / Options          | `Esc`

---

## Packaging Guide

The following section explains how to build standalone executables for
Windows and macOS.  If you only wish to *play* the game from source just
install the requirements (`pip install -r requirements.txt`) and run
`python main.py`.

<!--  The content below is imported from the former PACKAGING.md  -->

## Castle Pong – Packaging Guide

This guide shows how to turn the game into a standalone executable for
both Windows **(.exe)** and macOS **(.app)**.  The workflow relies on
[PyInstaller](https://pyinstaller.org) because it is cross-platform and
requires no changes to the source code.  Thanks to the automatic helper
added to `utils.py`, all assets are discovered at run-time no matter
where they live inside the frozen application.

---

### 0. Prerequisites (both platforms)

1. Install Python 3.9 – 3.12 (the game was tested with 3.11).
2. Create a virtual environment (optional but recommended):

   ```bash
   python -m venv venv
   source venv/bin/activate          # Windows: venv\Scripts\activate
   ```
3. Install runtime requirements:

   ```bash
   pip install -r requirements.txt   # installs pygame, numpy, PyInstaller …
   ```

---

### 1. Windows 10 / 11 – building `CastlePong.exe`

```powershell
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name CastlePong ^
    --add-data "*.wav;." ^
    --add-data "*.aac;." ^
    --add-data "*.mp3;." ^
    --add-data "PressStart2P-Regular.ttf;." ^
    main.py
```

Key points
- `--windowed` prevents a console window from popping up.
- Every `--add-data` entry copies the listed files into the bundle.
  The semicolon (`;`) separates *source_pattern* and *destination*
  on Windows.  We copy into `.` (the application root) so that the
  in-game helper can still locate assets with their original filenames.
- The resulting executable lives in `dist\CastlePong.exe`.

---

### 2. macOS (Apple Silicon & Intel) – building `Castle Pong.app`

```bash
pyinstaller \
    --noconfirm \
    --windowed \
    --name "Castle Pong" \
    --add-data "*.wav:." \
    --add-data "*.aac:." \
    --add-data "*.mp3:." \
    --add-data "PressStart2P-Regular.ttf:." \
    main.py
```

Differences from Windows
- Use a **colon (`:`)** between *source* and *destination* on macOS/Linux.
- The output is an application bundle at `dist/Castle Pong.app`.
- To notarise and ship on modern macOS you must sign and staple the app:

  ```bash
  codesign --deep --force --options runtime --sign "Developer ID Application: …" dist/Castle\ PONG.app
  xcrun stapler staple dist/Castle\ PONG.app
  ```
  (Full notarisation is outside the scope of this guide.)

---

### 3. Testing the build

```bash
# Windows
start dist\CastlePong.exe

# macOS
open dist/Castle\ PONG.app
```

If the game launches **with music, sound-effects and the pixel font**
visible in the UI, the data files were bundled correctly.

---

### 4. Troubleshooting

| Symptom                               | Fix |
|---------------------------------------|-----|
| Font falls back to system monospace   | Verify the font is listed in every `--add-data` section and the filename case matches. |
| No sound                              | Ensure `*.wav`, `*.aac`, `*.mp3` are included; confirm your system has an audio device. |
| App launches from Finder but crashes  | Remove spaces/new-line characters in `--add-data` patterns; codesign on macOS. |

---

Enjoy the game – and good luck defending your castle! 