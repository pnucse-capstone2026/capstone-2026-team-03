import tempfile
import unittest
from pathlib import Path

from scripts.run_finetune import build_parser, load_config_defaults


class RunFinetuneConfigTest(unittest.TestCase):
    def test_loads_nested_yaml_config(self):
        defaults = load_config_defaults(Path("configs/experiments/kspon_v1.yaml"))
        args = build_parser(defaults).parse_args([])
        self.assertEqual(args.stage, "train")
        self.assertEqual(args.work_dir, Path("workspace/kspon_v1"))
        self.assertEqual(args.lang, "configs/inventories/kspon_korean_ipa.txt")
        self.assertEqual(args.phone_init_map, "configs/inventories/kspon_phone_init.json")
        self.assertEqual(args.expected_validate_size, 5000)
        self.assertEqual(args.wandb_project, "allosaurus-finetune")

    def test_cli_overrides_yaml_defaults(self):
        defaults = load_config_defaults(Path("configs/experiments/kspon_v1.yaml"))
        args = build_parser(defaults).parse_args(["--epoch", "2", "--wandb-mode", "offline"])
        self.assertEqual(args.epoch, 2)
        self.assertEqual(args.wandb_mode, "offline")

    def test_loads_recovery_training_config(self):
        defaults = load_config_defaults(Path("configs/experiments/kspon_v2_recovery.yaml"))
        args = build_parser(defaults).parse_args([])
        self.assertEqual(args.optimizer, "adamw")
        self.assertEqual(args.encoder_lr, 0.0001)
        self.assertEqual(args.phone_lr, 0.0003)
        self.assertEqual(args.scheduler, "plateau")
        self.assertEqual(args.early_stopping_patience, 8)
        self.assertEqual(
            args.initial_checkpoint,
            "allosaurus/pretrained/kspon_ko_v2_fresh/model.pt",
        )
        self.assertEqual(args.wandb_project, "none")

    def test_unknown_yaml_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.yaml"
            path.write_text("training:\n  typo_epoch: 10\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown key"):
                load_config_defaults(path)


if __name__ == "__main__":
    unittest.main()
