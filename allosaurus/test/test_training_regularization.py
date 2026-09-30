import unittest
from argparse import Namespace

import torch

from allosaurus.am.allosaurus_torch import AllosaurusTorchModel
from allosaurus.am.trainer import Trainer


class TrainingRegularizationTest(unittest.TestCase):
    def test_model_applies_configured_inter_layer_dropout(self):
        config = Namespace(
            hidden_size=4,
            layer_size=3,
            proj_size=0,
            feat_size=6,
            lang_size_dict={},
            phone_size=5,
            dropout=0.2,
        )
        model = AllosaurusTorchModel(config)
        self.assertEqual(model.blstm_layer.dropout, 0.2)

    def test_time_masking_changes_only_valid_feature_frames(self):
        trainer = Trainer.__new__(Trainer)
        trainer.train_config = Namespace(time_mask_count=5, time_mask_width=10)
        features = torch.ones(2, 30, 4)
        lengths = torch.tensor([30, 10])

        torch.manual_seed(7)
        augmented = trainer.apply_time_masking(features, lengths)

        self.assertTrue(torch.any(augmented[0, :30] == 0))
        self.assertTrue(torch.any(augmented[1, :10] == 0))
        self.assertTrue(torch.all(augmented[1, 10:] == 1))
        self.assertTrue(torch.all(features == 1))


if __name__ == "__main__":
    unittest.main()
