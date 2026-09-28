import pytest
from unittest.mock import MagicMock

import wow_voice_chat


def service():
    return wow_voice_chat.WoWVoiceChat(lazy_load=True)


@pytest.fixture(autouse=True)
def reset_audio_mock():
    wow_voice_chat.sd.reset_mock(side_effect=True)
    wow_voice_chat.sd.default.device.__getitem__.return_value = 7
    wow_voice_chat.sd.query_devices.return_value = {
        "default_samplerate": 48000,
        "max_input_channels": 2,
    }
    wow_voice_chat.sd.check_input_settings.return_value = None


def test_stereo_audio_is_mixed_before_resampling(monkeypatch):
    voice = service()
    voice.whisper_sample_rate = 48000
    stereo = MagicMock()
    stereo.ndim = 2
    normalized = MagicMock()
    mixed = MagicMock()
    stereo.astype.return_value = normalized
    normalized.mean.return_value = mixed
    fake_numpy = MagicMock()
    fake_numpy.asarray.return_value = stereo
    fake_numpy.issubdtype.return_value = False
    fake_numpy.clip.return_value = mixed
    monkeypatch.setattr(wow_voice_chat, "np", fake_numpy)

    audio = voice._prepare_audio(stereo, 48000)

    normalized.mean.assert_called_once_with(axis=1)
    stereo.reshape.assert_not_called()
    assert audio is mixed


def test_capture_falls_back_to_stereo_when_mono_is_rejected(monkeypatch):
    voice = service()
    wow_voice_chat.sd.check_input_settings.side_effect = [RuntimeError("mono unsupported"), None]

    settings = voice._input_stream_settings()

    assert settings["device"] == 7
    assert settings["channels"] == 2
    assert voice.input_channels == 2


def test_recording_is_not_marked_active_when_stream_start_fails(monkeypatch):
    voice = service()
    stream = wow_voice_chat.sd.InputStream.return_value
    stream.start.side_effect = RuntimeError("cannot open")

    with pytest.raises(RuntimeError, match="cannot open"):
        voice.start_recording()

    assert voice.is_recording is False
    assert voice.recording_stream is None
