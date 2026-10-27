"""Check trial exclusion, temporal integrity, split isolation and actual fine-tuning."""
import unittest

import numpy as np
import pandas as pd
import torch

from analysis.ml_data import model_signal, splits, trial_windows
from analysis.cbramod_benchmark import train_model
from analysis.vendor.cbramod.criss_cross_transformer import TransformerEncoderLayer


class DataTests(unittest.TestCase):
    def events(self):
        rows = []
        for trial in [1, 2, 3]:
            for label, phase, sample in [("cue_onset", "task", 1000), ("task_offset", "task", 3500),
                                         ("phase_end", "rest", 7500), ("trial_end", "rest", 7500)]:
                rows.append(dict(run="Kognitiv", block=trial, trial=trial, attempt=1,
                    source="automatic", condition="mental_arithmetic", label=label, phase=phase,
                    samples_received=sample + trial * 10000))
        return pd.DataFrame(rows)

    def test_invalid_incomplete_and_pairs(self):
        events = self.events()
        invalid = events.iloc[0].copy()
        invalid["label"] = "trial_invalidated"
        events = pd.concat([events, invalid.to_frame().T], ignore_index=True)
        events = events[~((events.trial == 2) & (events.label == "trial_end"))]
        rows, exclusions = trial_windows(events, 50000, 250)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows.trial.tolist(), [3, 3])
        self.assertEqual(set(e["reason"] for e in exclusions), {"invalidated", "incomplete"})

    def test_short_task_is_not_silently_padded(self):
        events = self.events()
        events.loc[events.label == "task_offset", "samples_received"] -= 2200
        rows = None
        with self.assertRaisesRegex(ValueError, "No complete"):
            rows, _ = trial_windows(events, 50000, 250)
        self.assertIsNone(rows)

    def test_pairs_stay_together_and_outer_test_used_once(self):
        rows, _ = trial_windows(self.events(), 50000, 250)
        all_test = []
        for _, _, train, val, test, outer in splits(rows):
            self.assertFalse(set(outer) & set(test))
            self.assertEqual(set(train) | set(val), set(outer))
            for subset in [train, val, test]:
                self.assertEqual(len(set(rows.iloc[subset].trial_key)), 1)
            all_test.extend(test)
        self.assertEqual(sorted(all_test), list(range(len(rows))))

    def test_resampling_preserves_duration_and_frequency(self):
        t = np.arange(750) / 250
        epoch = np.zeros((750, 8))
        epoch[:, 0] = 20 * np.sin(2 * np.pi * 10 * t)
        result = model_signal(epoch)
        self.assertEqual(result.shape, (8, 600))
        spectrum = np.abs(np.fft.rfft(result[0]))
        freq = np.fft.rfftfreq(600, 1 / 200)
        self.assertAlmostEqual(freq[spectrum.argmax()], 10)
        np.testing.assert_allclose(result.sum(0), 0, atol=1e-8)


class TrainingTests(unittest.TestCase):
    def test_freezing_and_weight_updates(self):
        torch.set_num_threads(2)
        torch.manual_seed(4)
        layer = TransformerEncoderLayer(200, 8, 800, batch_first=True, activation=torch.nn.functional.gelu)
        h, y = torch.randn(8, 8, 3, 200), torch.tensor([0, 1] * 4)
        reference = {k: v.clone() for k, v in layer.state_dict().items()}
        for tune in [False, True]:
            model, _, _ = train_model(layer, h, y, [0, 1, 2, 3], [4, 5], tune=tune, seed=11, epochs=2)
            changes = [not torch.equal(reference[k], v) for k, v in model.last_block.state_dict().items()]
            self.assertEqual(any(changes), tune)
            for k, v in layer.state_dict().items():
                self.assertTrue(torch.equal(v, reference[k]), "Original pretrained layer was mutated")

    def test_unused_test_values_do_not_change_fit(self):
        torch.manual_seed(2)
        layer = TransformerEncoderLayer(200, 8, 800, batch_first=True)
        h, y = torch.randn(8, 8, 3, 200), torch.tensor([0, 1] * 4)
        first, epoch1, history1 = train_model(layer, h, y, [0, 1, 2, 3], [4, 5], tune=True, seed=5, epochs=2)
        changed = h.clone(); changed[6:] = 1000
        second, epoch2, history2 = train_model(layer, changed, y, [0, 1, 2, 3], [4, 5], tune=True, seed=5, epochs=2)
        self.assertEqual((epoch1, history1), (epoch2, history2))
        for a, b in zip(first.parameters(), second.parameters()):
            torch.testing.assert_close(a, b, rtol=0, atol=0)


if __name__ == "__main__":
    unittest.main()
