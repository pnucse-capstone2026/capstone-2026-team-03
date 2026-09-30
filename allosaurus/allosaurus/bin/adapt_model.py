import argparse
from pathlib import Path
from allosaurus.model import copy_model, get_model_path
from allosaurus.am.factory import transfer_am
from allosaurus.am.trainer import Trainer
from allosaurus.am.loader import read_loader
from allosaurus.am.utils import torch_load, torch_save

if __name__ == '__main__':

    parser = argparse.ArgumentParser("fine-tune an existing model to your target dataset")

    # required options
    parser.add_argument('--pretrained_model', required=True, type=str, help='the pretrained model id which you want to start with' )
    parser.add_argument('--new_model',        required=True, type=str, help='the new fine-tuned model id, this id show in your model list and will be available later for your inference')
    parser.add_argument('--path',             required=True, type=str, help='the data path, it should contain train directory and validate directory')
    parser.add_argument('--lang',             required=True, type=str, help='the language id of your target dataset')
    parser.add_argument('--device_id',        required=True, type=int, help='gpu cuda_device_id. use -1 if you do not have gpu')

    # non required options
    parser.add_argument('--batch_frame_size', type=int,   default=6000,  help='this indicates how many frame in each batch, if you get any memory related errors, please use a lower value for this size')
    parser.add_argument('--criterion',        type=str,   default='ctc', choices=['ctc'], help='criterion, only ctc now')
    parser.add_argument('--optimizer',        type=str,   default='sgd', choices=['sgd', 'adamw'], help='optimizer')
    parser.add_argument('--lr',               type=float, default=0.01,  help='learning rate')
    parser.add_argument('--encoder_lr',       type=float, default=0.0,   help='encoder learning rate; 0 uses --lr')
    parser.add_argument('--phone_lr',         type=float, default=0.0,   help='phone head learning rate; 0 uses --lr')
    parser.add_argument('--momentum',         type=float, default=0.0,   help='SGD momentum')
    parser.add_argument('--weight_decay',     type=float, default=0.0,   help='optimizer weight decay')
    parser.add_argument('--scheduler',        type=str,   default='none', choices=['none', 'plateau', 'cosine'], help='learning-rate scheduler')
    parser.add_argument('--scheduler_factor', type=float, default=0.5,   help='plateau scheduler reduction factor')
    parser.add_argument('--scheduler_patience', type=int, default=2,     help='plateau epochs before reducing LR')
    parser.add_argument('--min_lr',            type=float, default=1e-6, help='minimum scheduled learning rate')
    parser.add_argument('--early_stopping_patience', type=int, default=3, help='epochs without validation PER improvement before stopping; 0 disables')
    parser.add_argument('--freeze_encoder_epochs', type=int, default=0, help='initial epochs that train only the phone head')
    parser.add_argument('--grad_clip',        type=float, default=5.0,   help='grad clipping')
    parser.add_argument('--dropout',          type=float, default=0.0,   help='dropout between recurrent layers')
    parser.add_argument('--time_mask_count',  type=int, default=0,       help='number of train-only time masks per utterance')
    parser.add_argument('--time_mask_width',  type=int, default=0,       help='maximum time-mask width in feature frames')
    parser.add_argument('--max_nonfinite_batches', type=int, default=5, help='abort an epoch after this many skipped non-finite batches; 0 disables the limit')
    parser.add_argument('--epoch',            type=int,   default=10,    help='number of epoch to run')
    parser.add_argument('--log',              type=str,   default='none',help='file to store training logs. do not save if none')
    parser.add_argument('--verbose',          type=bool,  default=True,  help='print all training logs on stdout')
    parser.add_argument('--report_per_batch', type=int,   default=10,    help='report training stats every N epoch')
    parser.add_argument('--expected_validate_size', type=int, default=5000, help='fail unless validation contains this many utterances; use 0 to disable')
    parser.add_argument('--wandb_project', type=str, default='allosaurus-finetune', help='W&B project name; use none to disable')
    parser.add_argument('--wandb_entity', type=str, default='', help='optional W&B entity/team')
    parser.add_argument('--wandb_run_name', type=str, default='', help='optional W&B run name')
    parser.add_argument('--wandb_mode', type=str, default='online', choices=['online', 'offline', 'disabled'], help='W&B operating mode')
    parser.add_argument('--phone_init_map', type=str, default='none', help='JSON map of custom target phone to pretrained source phone')
    parser.add_argument('--initial_checkpoint', type=str, default='none', help='model state to warm-start after constructing the target inventory')

    train_config = parser.parse_args()

    # prepare training and validating loaders
    data_path = Path(train_config.path)
    train_loader = read_loader(data_path / 'train', train_config)
    validate_loader = read_loader(data_path / 'validate', train_config)

    validate_size = len(validate_loader.dataset)
    if train_config.expected_validate_size and validate_size != train_config.expected_validate_size:
        train_loader.close()
        validate_loader.close()
        raise ValueError(
            f"expected {train_config.expected_validate_size} validation utterances, found {validate_size}"
        )

    # initialize the target model path with the old model
    copy_model(train_config.pretrained_model, train_config.new_model)

    # setup the target model path and create model
    model = transfer_am(train_config)

    # A warm start restores model weights only. The optimizer and scheduler
    # intentionally start fresh for the new fine-tuning phase.
    if train_config.initial_checkpoint != 'none':
        checkpoint_path = Path(train_config.initial_checkpoint)
        if not checkpoint_path.is_file():
            train_loader.close()
            validate_loader.close()
            raise FileNotFoundError(f"initial checkpoint does not exist: {checkpoint_path}")
        torch_load(model, checkpoint_path, train_config.device_id)
        torch_save(model, get_model_path(train_config.new_model) / 'model.pt')

    # setup trainer
    trainer = Trainer(model, train_config)

    # start training
    trainer.train(train_loader, validate_loader)

    # close datasets and loaders
    train_loader.close()
    validate_loader.close()
