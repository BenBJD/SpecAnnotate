SpecAnnotate — Project Guidelines

This document captures project-specific knowledge to help future development, testing, and debugging. It assumes an advanced developer familiar with Python packaging, Qt, and audio/DSP.

---

Build and Configuration

- Python version: The project targets Python 3.13 (see `pyproject.toml`). Use this exact version to avoid ABI/runtime mismatches with Qt or scientific deps.

- Dependency management:
  - With uv (recommended since `uv.lock` exists):
    - Install uv: `pip install uv` (or from official instructions).
    - Sync the environment (creates a virtualenv in `.venv` by default):
      - `uv sync` (uses `pyproject.toml` + `uv.lock` for reproducible resolves)
      - Activate venv if needed: `source .venv/bin/activate` (Unix) or `.venv\\Scripts\\activate` (Windows PowerShell).
  - With pip (if you must):
    - Create and activate a Python 3.13 venv, then install via:
      - `pip install -e .`  (editable install) — resolves from `pyproject.toml`.
    - Note: pip mode won’t use `uv.lock`, so versions may drift.

- Running the app (Qt GUI):
  - Console entry point (declared in `pyproject.toml`): `specannotate`
  - Or module invocation: `python -m app.main` or `python main.py`
  - GUI stack: PySide6; the app requires a windowing environment (Wayland/X11 on Linux, Quartz on macOS, Win32 on Windows). Headless environments require a virtual display (e.g., Xvfb) if you need to instantiate `QApplication`.

- Audio output (synth):
  - Uses `sounddevice` (PortAudio) rather than Qt’s audio. On Linux ensure ALSA/PulseAudio/PipeWire devices are available; on macOS grant microphone permissions if necessary (some backends enumerate IO devices); on Windows confirm WASAPI/WDM-KS availability.
  - Buffer underflows will be logged from the audio callback; failures should degrade to silence rather than crash.

---
Development and Debugging Notes

- Code layout highlights:
  - `app/main_window.py`, `app/spectrogram_widget.py`: Qt UI; avoid tight coupling of long-running DSP/audio in the GUI thread. The synth uses a PortAudio callback; keep GUI → audio interactions thread-safe and minimal.
  - `app/synth.py`: Real-time audio rendering with `sounddevice`; envelopes and phase are computed per callback chunk. Any heavy transforms must be precomputed or vectorized to keep callback within deadline.
  - `utils/cqt.py`: CQT via `librosa.hybrid_cqt`; outputs float32, [0,1] normalized spectrogram suitable for visualization.
  - `utils/midi.py`: Note import/export helpers via `mido`/`pretty_midi`.

- GUI/Qt specifics:
  - Always create `QApplication` exactly once (`main.py` already does this). If you need background workers, use `QThread` or `QtConcurrent` and avoid blocking the GUI.
  - For headless profiling or tests, do not import heavy Qt modules if not needed; factor logic into utils to maximize non-GUI testability.

Audio realtime considerations:
  - Keep allocations out of the audio callback; pre-allocate buffers or reuse numpy arrays.
  - Normalize/clip to avoid int16 overflow; current synth mixes to float in [-1,1] then converts to `int16`.
  - If glitches occur, reduce blocksize (or increase), adjust latency parameters in `sounddevice.Stream`, or temporarily disable voices to bisect sources of overload.

- Spectrogram parameters:
  - Defaults map CQT bins to MIDI indices starting at C0 with 12 bins/octave. Changing `f_min`, `n_bins`, or `bins_per_octave` must be mirrored in any visualization/annotation logic to keep pitch mapping consistent.

- Cross-platform notes:
  - macOS with ARM + Qt + Python 3.13: ensure wheels are available; if not, consider switching to uv-managed versions that have prebuilt wheels.
  - Linux: verify PortAudio backend devices; PipeWire setups sometimes need `--latency` tuning.

---

Quick Commands Reference

- Create environment (uv): `uv sync`
- Run app: `specannotate` or `python main.py`
- Run demo test: `python .junie/tmp_demo_test.py`
