"""chops command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from .lyrics import DEFAULT_MODEL
from .pipeline import process as process_song
from .render import render_song

app = typer.Typer(
    add_completion=False,
    help="Audio -> stems -> MIDI + harmonic analysis -> Logic-like HTML viewer.",
)


@app.command()
def process(
    audio: Path = typer.Argument(..., help="Input audio file (mp3, wav, ...)."),
    out: Path = typer.Option(Path("out"), help="Output root directory."),
    drums_midi: bool = typer.Option(
        False, "--drums-midi", help="Also transcribe the drum stem to MIDI."
    ),
    lyrics: bool = typer.Option(
        True, "--lyrics/--no-lyrics", help="Transcribe lyrics from the vocal stem (whisper)."
    ),
    whisper_model: str = typer.Option(
        DEFAULT_MODEL, help="faster-whisper model (e.g. base, small, medium, large-v3)."
    ),
) -> None:
    """Run the full pipeline on AUDIO and build the viewer."""
    song_dir = process_song(
        audio, out, drums_midi=drums_midi, lyrics=lyrics, whisper_model=whisper_model
    )
    typer.echo(str(song_dir / "index.html"))


@app.command()
def render(
    song_dir: Path = typer.Argument(..., help="A song dir containing analysis.json."),
) -> None:
    """Re-render index.html from an existing analysis.json (no re-analysis)."""
    out = render_song(song_dir)
    typer.echo(str(out))


@app.command()
def serve(
    directory: Path = typer.Argument(Path("out"), help="Directory to serve (the out/ root or a song dir)."),
    port: int = typer.Option(8000, help="Port to serve on."),
) -> None:
    """Serve DIRECTORY over HTTP so the viewer can fetch the audio files.

    Browsers block fetch() over file://, so open the viewer through this server,
    e.g. http://localhost:8000/<song>/index.html
    """
    import functools
    import http.server
    import socketserver

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with socketserver.TCPServer(("", port), handler) as httpd:
        typer.echo(f"Serving {directory} at http://localhost:{port}/  (Ctrl-C to stop)")
        httpd.serve_forever()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
