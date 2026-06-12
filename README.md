# earworm′

A notebook for melodies you want to keep. Static site, no build step, no dependencies, no services. The git repo *is* the archive — every melody file embeds its own audio, key, and annotations, so a clone of this repo is a complete backup.

## Layout

```
index.html            the app (Collection + Annotater)
add_melody.py         adds an exported melody to the collection
melodies/
  manifest.json       index of the collection
  *.melody.json       one self-contained file per melody (audio embedded as base64)
```

## Adding a melody

1. Clip the section you care about (keeps files small; a hook is usually 10–30s).
   The **Clipper** tab does the fiddly part: open the mp3, drag on the waveform to set the
   window (drag the edges to adjust, the middle to slide it), preview it, then copy the
   generated command and run it in the file's folder. It produces something like:

   ```sh
   ffmpeg -i 'song.mp3' -ss 0:42.00 -to 1:05.00 -c copy 'song.clip.mp3'
   ```

2. Open the site → **Annotater** tab → open `clip.mp3`, set the key and a title.
3. Play it (space), tap `1`–`7` at the playhead to mark scale degrees (`shift` for the upper octave); hold the key to give the note length. Notes land on a piano roll — drag them to move in time or pitch, drag the right edge to resize, select + backspace to delete. Drag on the waveform for a loop region; `L` loops it; the speed control slows playback (down to 0.25×) with pitch preserved.
4. Click **Export melody file** — you get `your-title.melody.json` with everything inside it.
5. From the repo root:

   ```sh
   python add_melody.py ~/Downloads/your-title.melody.json
   git add -A && git commit -m "add: your title" && git push
   ```

The Collection tab on the live site picks it up on the next load. **Quiz mode** (`Q`) hides the degree labels so you can work them out by ear and check yourself.

## Local preview

`fetch()` needs a server, so from the repo root:

```sh
python -m http.server 8000   # then open http://localhost:8000
```

## Deploying

GitHub repo → Settings → Pages → deploy from branch, root folder. Done.

A note on the repo's visibility: the melody files contain audio clips of the songs. Consider keeping the repo (and ideally the Pages site) private if the clips aren't yours to redistribute — short personal-study clips are low-stakes, but a public repo full of them is worth a thought. GitHub Pages on a private repo requires a paid plan; the free alternative is keeping the repo private and previewing locally with `http.server`, or accepting a public repo with short clips only.

## Durability notes

- Melody files are versioned (`"format": "earworm-melody", "v": 1`) so the app can stay backward-compatible forever. Files exported before the rename carry `"earmarks-melody"`; both markers are accepted.
- Keys are stored by name (`"E♭"`), not index.
- Nothing depends on localStorage except in-progress Annotater scratch work; the collection itself lives entirely in git.
