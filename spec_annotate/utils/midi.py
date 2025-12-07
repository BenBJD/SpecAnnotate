from dataclasses import dataclass
from typing import Iterable, Tuple, List, Dict
import math

import mido


@dataclass
class Note:
    pitch: int
    start: float  # seconds
    end: float  # seconds
    velocity: int = 64


def export_notes_to_midi(
    notes: Iterable[Tuple[int, float, float, int]] | Iterable[Note],
    out_path: str,
    tempo_bpm: int = 120,
    ppq: int = 480,
    channel: int = 0,
    duration_sec: float = None,
) -> None:
    """
    Export a collection of notes to a single-track MIDI file.

    Parameters
    - notes: iterable of (pitch, start_sec, end_sec, velocity) or Note objects
    - out_path: destination .mid path
    - tempo_bpm: tempo used to convert seconds to ticks (usually wont be used)
    - ppq: pulses per quarter note (usually wont be used)
    - channel: MIDI channel for note events
    - duration_sec: optional track length in seconds; if provided, ensures MIDI file matches this duration
    """

    # Convert to list of tuples
    norm: List[Tuple[int, float, float, int]] = []
    for n in notes:
        if isinstance(n, Note):
            norm.append((int(n.pitch), float(n.start), float(n.end), int(n.velocity)))
        else:
            p, s, e, v = n  # type: ignore
            norm.append((int(p), float(s), float(e), int(v)))

    # Sort by start time, then by end time
    norm.sort(key=lambda x: (x[1], x[2]))

    # Set up the midi file; first the file
    mid = mido.MidiFile(ticks_per_beat=ppq)
    # Then the track
    track = mido.MidiTrack()
    # Add the track to the file
    mid.tracks.append(track)

    # Convert bqm tempo to MIDI tempo (they are very different)
    tempo = mido.bpm2tempo(tempo_bpm)
    # Set tempo can be useful depending on use
    track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))

    # Build note events in order (without timing in MIDI message yet)
    events: List[Tuple[float, mido.Message]] = []
    for pitch, start, end, vel in norm:
        start = max(0.0, start)
        end = max(start, end)  # Make sure end is at least start
        events.append((start, mido.Message('note_on', note=pitch, velocity=vel, channel=channel, time=0)))
        events.append((end, mido.Message('note_off', note=pitch, velocity=0, channel=channel, time=0)))

    # Sort by absolute time; if equal, note_off before note_on to avoid zero-length overlaps
    events.sort(key=lambda e: (e[0], 0 if e[1].type == 'note_off' else 1))

    # Convert absolute seconds to delta ticks and set message times
    last_time_sec = 0.0
    for abs_sec, msg in events:
        delta_sec = abs_sec - last_time_sec
        delta_ticks = int(round(mido.second2tick(delta_sec, ticks_per_beat=ppq, tempo=tempo)))
        msg.time = max(0, delta_ticks)
        track.append(msg)
        last_time_sec = abs_sec

    # Compute track length from the last note
    track_length_sec = duration_sec
    if track_length_sec < last_time_sec:
        # Shouldn't happen but make sure EOT is not before the last event
        track_length_sec = last_time_sec

    # Now calculate where to put the EOT message
    remaining_sec = track_length_sec - last_time_sec
    remaining_ticks = int(round(mido.second2tick(remaining_sec, ticks_per_beat=ppq, tempo=tempo)))
    track.append(mido.MetaMessage('end_of_track', time=max(0, remaining_ticks)))
    mid.save(out_path)


def import_notes_from_midi(path: str, *, target_duration_sec: float | None = None) -> List[Note]:
    """
    Load a MIDI file and extract notes as a list of Note(pitch, start_sec, end_sec, velocity).
    Args:
        path: path to MIDI file
        target_duration_sec: If provided, scales all note times to align with CQT.
    """
    mid = mido.MidiFile(path)

    # Merge tracks to a single stream of messages
    merged = mido.merge_tracks(mid.tracks)

    abs_time = 0.0  # seconds
    tempo = mido.bpm2tempo(120)  # default MIDI tempo if none set (500000 microsec/beat)

    # Active note stacks: key -> list of (start_time_sec, velocity)
    active: Dict[tuple[int, int], List[tuple[float, int]]] = {}
    out: List[Note] = []

    # Iterate over merged messages
    for msg in merged:
        # Convert delta ticks to seconds using the tempo (accuracy doesnt matter as it'll be scaled anyway
        delta_sec = float(mido.tick2second(msg.time, mid.ticks_per_beat, tempo))
        abs_time += delta_sec

        # Handle tempo changes just in case
        if msg.type == 'set_tempo':
            tempo = int(msg.tempo)
            continue

        if msg.type == 'note_on' and getattr(msg, 'velocity', 0) > 0:
            key = (int(getattr(msg, 'channel', 0)), int(msg.note))
            active.setdefault(key, []).append((abs_time, int(msg.velocity)))
        elif msg.type in ('note_off', 'note_on') and (msg.type == 'note_off' or getattr(msg, 'velocity', 0) == 0):
            key = (int(getattr(msg, 'channel', 0)), int(msg.note))
            stack = active.get(key)
            if stack:
                start_time, vel = stack.pop()
                end_time = max(abs_time, start_time)
                out.append(Note(pitch=int(msg.note), start=float(start_time), end=float(end_time), velocity=int(vel)))
            else:
                # Unmatched note_off; ignore
                pass

    # If any notes are still active, stop them
    if active:
        final_time = float(abs_time)
        for key, stack in active.items():
            for start_time, vel in stack:
                end_time = max(final_time, start_time)
                pitch = key[1]
                out.append(Note(pitch=int(pitch), start=float(start_time), end=float(end_time), velocity=int(vel)))

    # Optionally scale to CQT length
    if target_duration_sec is not None and abs_time > 0:
        scale = float(target_duration_sec) / float(abs_time)
        if math.isfinite(scale) and scale > 0:
            for i, n in enumerate(out):
                out[i] = Note(
                    pitch=int(n.pitch),
                    start=float(n.start * scale),
                    end=float(n.end * scale),
                    velocity=int(n.velocity),
                )

    # Sort result for stability
    out.sort(key=lambda n: (n.start, n.end, n.pitch))
    return out
