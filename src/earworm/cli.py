"""earworm command-line interface."""

from __future__ import annotations

import tempfile
from pathlib import Path

import typer

from . import fetch, logic_build
from .library import build_library
from .lyrics import DEFAULT_MODEL
from .pipeline import DEFAULT_CONTENT
from .pipeline import process as process_song
from .sync import sync as sync_content

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
def ingest(
    target: str = typer.Argument(
        ...,
        help="Either a local audio file (mp3/m4a/wav) or a search query "
        "(downloaded as the top YouTube match via yt-dlp).",
    ),
    artist: str = typer.Option(None, help="Override artist (else parsed from the filename)."),
    song: str = typer.Option(None, help="Override song title (else parsed from the filename)."),
    out: Path = typer.Option(DEFAULT_CONTENT, help="Content output root (served by the web app)."),
    keep_open: bool = typer.Option(
        False, "--keep-open", help="Save (don't discard) a project already open in Logic on reset."
    ),
    drums_midi: bool = typer.Option(False, "--drums-midi", help="Also transcribe the drum stem to MIDI."),
    lyrics: bool = typer.Option(True, "--lyrics/--no-lyrics", help="Transcribe lyrics from the vocal stem."),
    whisper_model: str = typer.Option(DEFAULT_MODEL, help="faster-whisper model (e.g. base, small, large-v3)."),
    transcode: bool = typer.Option(True, "--transcode/--no-transcode", help="Transcode stems/mix to AAC m4a."),
    keep_wav: bool = typer.Option(False, "--keep-wav", help="Keep the source WAVs after transcoding."),
    sections: bool = typer.Option(True, "--sections/--no-sections", help="Detect song sections (Claude)."),
    motifs: bool = typer.Option(True, "--motifs/--no-motifs", help="Detect motifs to learn (Claude)."),
    build_only: bool = typer.Option(
        False, "--build-only", help="Only build the Logic project; skip downstream processing."
    ),
) -> None:
    """Ingest a song from a local audio file OR a search query.

    If TARGET is an existing file it's used directly; otherwise it's treated as a
    query and the top YouTube match is downloaded. Either way, Logic Pro is driven
    to build the project, then the pipeline runs. Logic must stay frontmost and the
    keyboard/mouse untouched while the UI is driven.
    """
    name = f"{artist} - {song}" if artist and song else None

    local = Path(target).expanduser()
    if local.is_file():
        project = logic_build.build_project(local, name=name, discard_open=not keep_open)
    else:
        # Treat TARGET as a search query: download to a temp dir, build, then the
        # temp mp3 is disposable (Logic copies it into the project on save).
        with tempfile.TemporaryDirectory(prefix="earworm-dl-") as td:
            audio = fetch.download_audio(target, Path(td))
            project = logic_build.build_project(audio, name=name, discard_open=not keep_open)

    if build_only:
        typer.echo(str(project))
        return
    song_dir = process_song(
        project, out, drums_midi=drums_midi, lyrics=lyrics, whisper_model=whisper_model,
        transcode=transcode, keep_wav=keep_wav, sections=sections, motifs=motifs,
    )
    typer.echo(str(song_dir))


@app.command()
def sync(
    content: Path = typer.Option(DEFAULT_CONTENT, help="Content root to upload."),
    delete: bool = typer.Option(
        False, "--delete", help="Also remove remote files no longer present locally."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would change without touching the bucket."
    ),
) -> None:
    """Mirror the content dir to the Cloudflare R2 bucket (R2_* env vars / .env)."""
    sync_content(content, delete=delete, dry_run=dry_run)


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
