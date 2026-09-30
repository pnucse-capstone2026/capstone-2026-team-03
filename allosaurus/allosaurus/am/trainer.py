from allosaurus.am.utils import move_to_tensor, torch_save
from allosaurus.am.criterion import read_criterion
from allosaurus.am.optimizer import read_optimizer
from allosaurus.am.reporter import Reporter
import editdistance
import numpy as np
import torch
from itertools import groupby
from allosaurus.model import get_model_path
import json
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau

class Trainer:

    def __init__(self, model, train_config):

        self.model = model
        self.train_config = train_config

        self.device_id = self.train_config.device_id

        # criterion, only ctc currently
        self.criterion = read_criterion(train_config)

        # optimizer, only sgd currently
        self.optimizer = read_optimizer(self.model, train_config)

        # reporter to write logs
        self.reporter = Reporter(train_config)

        # best per
        self.best_per = 100.0

        # intialize the model
        self.model_path = get_model_path(train_config.new_model)

        # counter for early stopping
        self.num_no_improvement = 0

        # Keep a model snapshot for every completed epoch.  model.pt remains
        # reserved for the best validation model used by inference.
        self.checkpoint_path = self.model_path / 'checkpoints'
        self.checkpoint_path.mkdir(parents=True, exist_ok=True)

        self.metrics_path = self.model_path / 'training_metrics.jsonl'
        self.scheduler = self._build_scheduler()


    def _build_scheduler(self):
        scheduler_name = getattr(self.train_config, 'scheduler', 'none')
        if scheduler_name == 'none':
            return None
        if scheduler_name == 'plateau':
            return ReduceLROnPlateau(
                self.optimizer,
                mode='min',
                factor=self.train_config.scheduler_factor,
                patience=self.train_config.scheduler_patience,
                min_lr=self.train_config.min_lr,
            )
        if scheduler_name == 'cosine':
            return CosineAnnealingLR(
                self.optimizer,
                T_max=self.train_config.epoch,
                eta_min=self.train_config.min_lr,
            )
        raise ValueError(f'unsupported scheduler: {scheduler_name}')


    def _learning_rates(self):
        return {
            group.get('name', f'group_{index}'): group['lr']
            for index, group in enumerate(self.optimizer.param_groups)
        }


    def _set_encoder_trainable(self, trainable):
        for parameter in self.model.blstm_layer.parameters():
            parameter.requires_grad = trainable


    def save_epoch_checkpoint(self, epoch, validate_phone_error_rate, **metrics):
        """Save an inference-compatible model snapshot and epoch metadata."""
        epoch_number = epoch + 1
        checkpoint_stem = f'epoch_{epoch_number:04d}'
        checkpoint_model_path = self.checkpoint_path / f'{checkpoint_stem}.pt'
        checkpoint_metadata_path = self.checkpoint_path / f'{checkpoint_stem}.json'

        torch_save(self.model, checkpoint_model_path)
        metadata = {
            'epoch': epoch_number,
            'validate_phone_error_rate': validate_phone_error_rate,
        }
        metadata.update(metrics)
        checkpoint_metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        self.reporter.write(f"saved epoch checkpoint: {checkpoint_model_path}")


    def sum_edit_distance(self, output_ndarray, output_lengths_ndarray, token_ndarray, token_lengths_ndarray):
        """
        compute SUM of ter in this batch

        """

        error_cnt_sum = 0.0

        for i in range(len(token_lengths_ndarray)):
            target_list = token_ndarray[i, :token_lengths_ndarray[i]].tolist()
            logit = output_ndarray[i][:output_lengths_ndarray[i]]

            raw_token = [x[0] for x in groupby(np.argmax(logit, axis=1))]
            decoded_token = list(filter(lambda a: a != 0, raw_token))

            error_cnt_sum += editdistance.distance(target_list, decoded_token)

        return error_cnt_sum


    def step(self, feat_batch, token_batch):

        # prepare torch tensors from numpy arrays
        feat_tensor, feat_lengths_tensor = move_to_tensor(feat_batch, self.device_id)
        token_tensor, token_lengths_tensor = move_to_tensor(token_batch, self.device_id)

        if self.model.training:
            feat_tensor = self.apply_time_masking(feat_tensor, feat_lengths_tensor)

        #print(feat_tensor)
        #print(feat_lengths_tensor)
        output_tensor = self.model(feat_tensor, feat_lengths_tensor)

        #print(output_tensor)
        #print(token_tensor)
        #print(token_lengths_tensor)

        loss = self.criterion(output_tensor, feat_lengths_tensor, token_tensor, token_lengths_tensor)
        #print(loss.item())

        # extract numpy format for edit distance computing
        output_ndarray = output_tensor.cpu().detach().numpy()
        feat_ndarray, feat_lengths_ndarray = feat_batch
        token_ndarray, token_lengths_ndarray = token_batch

        phone_error_sum = self.sum_edit_distance(output_ndarray, feat_lengths_ndarray, token_ndarray,
                                                 token_lengths_ndarray)

        phone_count = sum(token_lengths_ndarray)

        return loss, phone_error_sum, phone_count


    def apply_time_masking(self, feat_tensor, feat_lengths_tensor):
        """Mask short time spans during training; padded and validation data stay unchanged."""
        mask_count = getattr(self.train_config, 'time_mask_count', 0)
        max_width = getattr(self.train_config, 'time_mask_width', 0)
        if mask_count <= 0 or max_width <= 0:
            return feat_tensor

        augmented = feat_tensor.clone()
        lengths = feat_lengths_tensor.detach().cpu().tolist()
        for batch_index, length_value in enumerate(lengths):
            length = int(length_value)
            if length <= 1:
                continue
            width_limit = min(max_width, length - 1)
            for _ in range(mask_count):
                width = int(torch.randint(0, width_limit + 1, (1,)).item())
                if width == 0:
                    continue
                start = int(torch.randint(0, length - width + 1, (1,)).item())
                augmented[batch_index, start:start + width, :] = 0
        return augmented


    def train(self, train_loader, validate_loader):

        self.best_per = 100.0

        expected_validate_size = getattr(self.train_config, 'expected_validate_size', 0)
        validate_size = len(validate_loader.dataset)
        if expected_validate_size and validate_size != expected_validate_size:
            raise ValueError(
                f"expected {expected_validate_size} validation utterances, found {validate_size}"
            )
        self.reporter.write(f"validation utterances per epoch: {validate_size}")

        if getattr(self.train_config, 'initial_checkpoint', 'none') != 'none':
            baseline_loss, baseline_per = self.validate(validate_loader)
            self.best_per = baseline_per
            self.reporter.write(
                f"warm-start baseline | validate loss: {baseline_loss:0.5f} "
                f"validate per: {baseline_per:0.5f}"
            )

        batch_count = len(train_loader)

        global_step = 0
        freeze_encoder_epochs = getattr(self.train_config, 'freeze_encoder_epochs', 0)
        early_stopping_patience = getattr(self.train_config, 'early_stopping_patience', 3)

        self.reporter.write(
            f"optimizer: {self.train_config.optimizer} | learning rates: {self._learning_rates()} "
            f"| scheduler: {getattr(self.train_config, 'scheduler', 'none')}"
        )

        for epoch in range(self.train_config.epoch):

            # shuffle
            train_loader.shuffle()

            # set to the training mode
            self.model.train()
            encoder_trainable = epoch >= freeze_encoder_epochs
            self._set_encoder_trainable(encoder_trainable)
            self.reporter.write(
                f"epoch{epoch + 1} encoder: {'trainable' if encoder_trainable else 'frozen'}"
            )

            # reset all stats
            all_phone_count = 0.0
            all_loss_sum = 0.0
            all_phone_error_sum = 0.0
            epoch_phone_count = 0.0
            epoch_loss_sum = 0.0
            epoch_phone_error_sum = 0.0
            nonfinite_batch_count = 0
            max_nonfinite_batches = getattr(self.train_config, 'max_nonfinite_batches', 5)

            # training loop
            for ii in range(batch_count):

                self.optimizer.zero_grad()

                feat_batch, token_batch = train_loader.read_batch(ii)

                # forward step
                loss_tensor, phone_error_sum, phone_count = self.step(feat_batch, token_batch)

                if not torch.isfinite(loss_tensor).item():
                    nonfinite_batch_count += 1
                    self.optimizer.zero_grad()
                    self.reporter.write(
                        f"non-finite loss at epoch {epoch + 1} batch {ii}; "
                        f"skipping optimizer step ({nonfinite_batch_count}/{max_nonfinite_batches})"
                    )
                    if max_nonfinite_batches and nonfinite_batch_count >= max_nonfinite_batches:
                        raise ValueError(
                            f"aborting epoch {epoch + 1}: encountered "
                            f"{nonfinite_batch_count} non-finite batches"
                        )
                    continue

                # backprop and optimize
                loss_tensor.backward()

                gradient_norm = torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(), self.train_config.grad_clip
                )
                if not torch.isfinite(gradient_norm).item():
                    nonfinite_batch_count += 1
                    self.optimizer.zero_grad()
                    self.reporter.write(
                        f"non-finite gradient at epoch {epoch + 1} batch {ii}; "
                        f"skipping optimizer step ({nonfinite_batch_count}/{max_nonfinite_batches})"
                    )
                    if max_nonfinite_batches and nonfinite_batch_count >= max_nonfinite_batches:
                        raise ValueError(
                            f"aborting epoch {epoch + 1}: encountered "
                            f"{nonfinite_batch_count} non-finite batches"
                        )
                    continue

                self.optimizer.step()

                # update stats
                loss_sum = loss_tensor.item()
                all_phone_count += phone_count
                all_loss_sum += loss_sum
                all_phone_error_sum += phone_error_sum
                epoch_phone_count += phone_count
                epoch_loss_sum += loss_sum
                epoch_phone_error_sum += phone_error_sum
                global_step += 1

                if ii % self.train_config.report_per_batch == 0:
                    train_loss = all_loss_sum / all_phone_count
                    train_per = all_phone_error_sum / all_phone_count
                    message = f'epoch[batch]: {epoch:02d}[{ii:04d}] | train loss {train_loss:0.5f} train per {train_per:0.5f}'
                    self.reporter.write(message)
                    self.reporter.log_metrics({
                        'batch/train_loss': train_loss,
                        'batch/train_per': train_per,
                        'batch/epoch': epoch + 1,
                        'batch/global_step': global_step,
                    })

                    # reset all stats
                    all_phone_count = 0.0
                    all_loss_sum = 0.0
                    all_phone_error_sum = 0.0


            # evaluate this model
            epoch_train_loss = epoch_loss_sum / epoch_phone_count
            epoch_train_per = epoch_phone_error_sum / epoch_phone_count
            validate_loss, validate_phone_error_rate = self.validate(validate_loader)

            self.reporter.write(
                f"epoch{epoch + 1} | train loss: {epoch_train_loss:0.5f} "
                f"train per: {epoch_train_per:0.5f} validate loss: {validate_loss:0.5f} "
                f"validate per: {validate_phone_error_rate:0.5f}"
            )

            # Save every completed epoch, regardless of whether validation PER
            # improved. This is separate from model.pt, which tracks the best.
            learning_rates = self._learning_rates()
            self.save_epoch_checkpoint(
                epoch,
                validate_phone_error_rate,
                train_loss=epoch_train_loss,
                train_phone_error_rate=epoch_train_per,
                validate_loss=validate_loss,
                learning_rates=learning_rates,
                nonfinite_batches=nonfinite_batch_count,
            )

            if validate_phone_error_rate <= self.best_per:
                self.best_per = validate_phone_error_rate
                self.num_no_improvement = 0
                self.reporter.write("saving model")

                model_name = f"model_{validate_phone_error_rate:0.5f}.pt"

                # save model
                torch_save(self.model, self.model_path / model_name)

                # overwrite the best model
                torch_save(self.model, self.model_path / 'model.pt')

            else:
                self.num_no_improvement += 1

            if self.scheduler:
                if isinstance(self.scheduler, ReduceLROnPlateau):
                    self.scheduler.step(validate_phone_error_rate)
                else:
                    self.scheduler.step()

            next_learning_rates = self._learning_rates()

            epoch_metrics = {
                'epoch': epoch + 1,
                'train_loss': epoch_train_loss,
                'train_per': epoch_train_per,
                'validate_loss': validate_loss,
                'validate_per': validate_phone_error_rate,
                'best_validate_per': self.best_per,
                'validate_utterances': validate_size,
                'learning_rates': learning_rates,
                'next_learning_rates': next_learning_rates,
                'encoder_trainable': encoder_trainable,
                'nonfinite_batches': nonfinite_batch_count,
            }
            with self.metrics_path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(epoch_metrics, ensure_ascii=False) + '\n')

            self.reporter.log_metrics({
                'epoch': epoch + 1,
                'epoch/train_loss': epoch_train_loss,
                'epoch/train_per': epoch_train_per,
                'epoch/validate_loss': validate_loss,
                'epoch/validate_per': validate_phone_error_rate,
                'epoch/best_validate_per': self.best_per,
                'epoch/validate_utterances': validate_size,
                'epoch/encoder_learning_rate': next_learning_rates.get('encoder'),
                'epoch/phone_learning_rate': next_learning_rates.get('phone_layer'),
                'epoch/nonfinite_batches': nonfinite_batch_count,
            })

            if validate_phone_error_rate > self.best_per:
                if early_stopping_patience and self.num_no_improvement >= early_stopping_patience:
                    self.reporter.write("no improvements for several epochs, early stopping now")
                    break

        # close reporter stream
        self.reporter.close()


    def validate(self, validate_loader):

        self.model.eval()

        batch_count = len(validate_loader)

        all_phone_error_sum = 0
        all_phone_count = 0
        all_loss_sum = 0.0

        # validation loop
        with torch.no_grad():
            for ii in range(batch_count):
                feat_batch, token_batch = validate_loader.read_batch(ii)

                # one step
                loss_tensor, phone_error_sum, phone_count = self.step(feat_batch, token_batch)

                if not torch.isfinite(loss_tensor).item():
                    raise ValueError(f"non-finite validation loss at batch {ii}")

                # update stats
                all_loss_sum += loss_tensor.item()
                all_phone_error_sum += phone_error_sum
                all_phone_count += phone_count

        return all_loss_sum/all_phone_count, all_phone_error_sum/all_phone_count
