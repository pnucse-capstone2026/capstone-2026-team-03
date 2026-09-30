from torch.optim import AdamW, SGD

def read_optimizer(model, train_config):
    """Build an optimizer, optionally with separate encoder/head rates."""
    optimizer_name = train_config.optimizer
    base_lr = train_config.lr
    encoder_lr = getattr(train_config, 'encoder_lr', 0.0) or base_lr
    phone_lr = getattr(train_config, 'phone_lr', 0.0) or base_lr
    weight_decay = getattr(train_config, 'weight_decay', 0.0)

    param_groups = [
        {
            'params': model.blstm_layer.parameters(),
            'lr': encoder_lr,
            'name': 'encoder',
        },
        {
            'params': model.phone_layer.parameters(),
            'lr': phone_lr,
            'name': 'phone_layer',
        },
    ]

    if optimizer_name == 'sgd':
        return SGD(
            param_groups,
            lr=base_lr,
            momentum=getattr(train_config, 'momentum', 0.0),
            weight_decay=weight_decay,
        )
    if optimizer_name == 'adamw':
        return AdamW(param_groups, lr=base_lr, weight_decay=weight_decay)
    raise ValueError(f'unsupported optimizer: {optimizer_name}')
