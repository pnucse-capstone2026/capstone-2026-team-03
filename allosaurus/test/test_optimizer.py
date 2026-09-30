import unittest
from argparse import Namespace

import torch

from allosaurus.am.optimizer import read_optimizer


class TinyModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.blstm_layer = torch.nn.LSTM(3, 4)
        self.phone_layer = torch.nn.Linear(4, 2)


class OptimizerTest(unittest.TestCase):
    def make_config(self, optimizer):
        return Namespace(
            optimizer=optimizer,
            lr=0.01,
            encoder_lr=0.0003,
            phone_lr=0.001,
            momentum=0.9,
            weight_decay=0.0001,
        )

    def test_adamw_uses_separate_encoder_and_phone_rates(self):
        optimizer = read_optimizer(TinyModel(), self.make_config("adamw"))
        self.assertIsInstance(optimizer, torch.optim.AdamW)
        self.assertEqual([group["name"] for group in optimizer.param_groups], ["encoder", "phone_layer"])
        self.assertEqual([group["lr"] for group in optimizer.param_groups], [0.0003, 0.001])

    def test_sgd_supports_momentum(self):
        optimizer = read_optimizer(TinyModel(), self.make_config("sgd"))
        self.assertIsInstance(optimizer, torch.optim.SGD)
        self.assertEqual(optimizer.defaults["momentum"], 0.9)


if __name__ == "__main__":
    unittest.main()
