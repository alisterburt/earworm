"""chops command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from .library import build_library
from .lyrics import DEFAULT_MODEL
from .pipeline import DEFAULT_CONTENT
from .pipeline import process as process_song

app = typer.Typer(
    add_completion=False,
    help="Audio -> stems -> MIDI/harmonic/lyric analysis -> web app content.",
)


@app.command()
def process(
    project: Path = typer.Argument(..., help="Logic Pro project folder (contains a .logicx)."),
    out: Path = typer.Option(DEFAULT_CONTENT, help="Content output root (served by the web app)."),
    drums_midi: bool = typer.Option(
        False, "--drums-midi", help="Also transcribe the drum stem to MIDI."
    ),
    lyrics: bool = typer.Option(
        True, "--lyrics/--no-lyrics", help="Transcribe lyrics from the vocal stem (whisper)."
    ),
    whisper_model: str = typer.Option(
        DEFAULT_MODEL, help="faster-whisper model (e.g. base, small, medium, large-v3)."
    ),
    transcode: bool = typer.Option(
        True, "--transcode/--no-transcode", help="Transcode stems/mix to AAC m4a for the viewer."
    ),
    keep_wav: bool = typer.Option(
        False, "--keep-wav", help="Keep the source WAVs after transcoding."
    ),
    sections: bool = typer.Option(
        True, "--sections/--no-sections", help="Detect song sections (Claude)."
    ),
    motifs: bool = typer.Option(
        True, "--motifs/--no-motifs", help="Detect motifs to learn (Claude)."
    ),
) -> None:
    """Run the full pipeline on a Logic PROJECT folder and write its content assets."""
    song_dir = process_song(
        project, out, drums_midi=drums_midi, lyrics=lyrics, whisper_model=whisper_model,
        transcode=transcode, keep_wav=keep_wav, sections=sections, motifs=motifs,
    )
    typer.echo(str(song_dir))


@app.command()
def library(
    content: Path = typer.Option(DEFAULT_CONTENT, help="Content root to index."),
) -> None:
    """Rebuild library.json from the processed song dirs."""
    typer.echo(str(build_library(content)))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
