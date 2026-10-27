"""Regression tests for REVE scaling, frozen weights and held-out isolation."""
import unittest
import numpy as np
import torch
from torch import nn
from analysis.reve_benchmark import LastBlock, reve_input, train_model


class ReveTests(unittest.TestCase):
    def test_input_units_and_time_order(self):
        x = np.arange(4800, dtype=np.float32).reshape(1, 8, 3, 200)
        actual = reve_input(x)
        self.assertEqual(tuple(actual.shape), (1, 8, 600))
        np.testing.assert_allclose(actual.numpy(), x.reshape(1, 8, 600) / 10)

    def test_training_isolation(self):
        torch.set_num_threads(2)
        torch.manual_seed(123)
        layer = LastBlock(nn.ModuleList([nn.Linear(512, 512), nn.Linear(512, 512)]))
        original = {k: v.clone() for k, v in layer.state_dict().items()}
        h = torch.randn(8, 8, 3, 512)
        y = torch.tensor([0, 1] * 4)
        for tune in [False, True]:
            fitted, ep, hist = train_model(layer, h, y, [0, 1, 2, 3], [4, 5],
                tune=tune, seed=11, epochs=2)
            self.assertEqual(any(not torch.equal(v, original[k]) for k,v in fitted.last_block.state_dict().items()), tune)
            altered = h.clone(); altered[6:] = 1000
            other, ep2, hist2 = train_model(layer, altered, y, [0, 1, 2, 3], [4, 5],
                tune=tune, seed=11, epochs=2)
            self.assertEqual((ep, hist), (ep2, hist2))
            for a,b in zip(fitted.parameters(), other.parameters()):
                torch.testing.assert_close(a, b, rtol=0, atol=0)
        for k,v in layer.state_dict().items():
            torch.testing.assert_close(v, original[k], rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()
