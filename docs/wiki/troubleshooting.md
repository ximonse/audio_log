# Troubleshooting

## ffmpeg not found
Install FFmpeg and ensure `ffmpeg` and `ffprobe` are on PATH.

## ASR fails to load
`faster-whisper` requires model weights. Download once or set `ASR` to a smaller model.

## Timezone errors on Windows
Install `tzdata` (already in dependencies) so `Europe/Stockholm` resolves.