import logging
from pathlib import Path

from transcritor.core.exceptions import SourceUnavailableError

try:
    import sounddevice as sd
    import wavio
    import numpy as np
except ImportError:
    sd = None  # type: ignore[assignment]
    wavio = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class SystemAudioSource:
    def __init__(self, output_dir: Path | str, filename: str = "system_audio.wav"):
        self._output_dir = Path(output_dir)
        self._filename = filename

    def acquire(self) -> Path:
        if sd is None:
            raise SourceUnavailableError(
                "sounddevice is not installed. "
                "Run: pip install 'transcritor[transcription]'"
            )
        device_index = self._select_device()
        return self._record(device_index)

    def _select_device(self) -> int:
        devices = sd.query_devices()
        logger.info("Available audio devices:")
        for i, device in enumerate(devices):
            name = device.get("name", "Unknown")
            max_in = device.get("max_input_channels", 0)
            max_out = device.get("max_output_channels", 0)
            logger.info("  %d: %s (%d in, %d out)", i, name, max_in, max_out)

        while True:
            try:
                selected = int(input("Select device index: "))
                if 0 <= selected < len(devices):
                    device_info = sd.query_devices(selected)
                    if device_info.get("max_input_channels", 0) < 1:
                        logger.warning("Device has no input channels. Choose another.")
                        continue
                    return selected
                logger.warning("Invalid index. Try again.")
            except ValueError:
                logger.warning("Please enter a number.")

    def _record(self, device_index: int, fs: int = 44100, channels: int = 2) -> Path:
        device_info = sd.query_devices(device_index)
        max_channels = device_info.get("max_input_channels", 0)
        if channels > max_channels:
            channels = max_channels

        frames = []

        def callback(indata, frame_count, time_info, status):
            if status:
                logger.warning("Audio stream status: %s", status)
            frames.append(indata.copy())

        logger.info("Recording... Press 's' + Enter to stop.")
        with sd.InputStream(
            callback=callback,
            samplerate=fs,
            channels=channels,
            device=device_index,
        ):
            while True:
                if input().strip().lower() == "s":
                    break

        all_data = np.concatenate(frames, axis=0)
        file_path = self._output_dir / self._filename
        wavio.write(str(file_path), all_data, fs, sampwidth=2)
        logger.info("Recording saved to %s", file_path)
        return file_path
