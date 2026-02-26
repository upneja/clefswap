import pytest
from backend.instruments import INSTRUMENTS, get_instrument, InstrumentNotFound

def test_all_required_instruments_present():
    required = {'violin', 'viola', 'cello', 'double_bass', 'flute',
                'clarinet_bb', 'trumpet_bb', 'trombone', 'piano_rh', 'piano_lh'}
    assert required.issubset(set(INSTRUMENTS.keys()))

def test_instrument_has_required_fields():
    v = get_instrument('violin')
    assert v['name'] == 'Violin'
    assert v['clef'] == 'treble'
    assert v['midi_program'] == 40
    assert v['range_low'] == 'G3'
    assert v['range_high'] == 'E7'

def test_viola_clef_is_alto():
    assert get_instrument('viola')['clef'] == 'alto'

def test_cello_clef_is_bass():
    assert get_instrument('cello')['clef'] == 'bass'

def test_double_bass_clef_is_bass_8vb():
    assert get_instrument('double_bass')['clef'] == 'bass_8vb'

def test_get_instrument_unknown_raises():
    with pytest.raises(InstrumentNotFound):
        get_instrument('theremin')

def test_all_instruments_have_valid_clef():
    from backend.clef_map import CLEF_MAP
    for key, inst in INSTRUMENTS.items():
        assert inst['clef'] in CLEF_MAP, f"{key} has unknown clef {inst['clef']}"

def test_all_instruments_have_midi_program():
    for key, inst in INSTRUMENTS.items():
        assert 0 <= inst['midi_program'] <= 127, f"{key} has invalid MIDI program"
