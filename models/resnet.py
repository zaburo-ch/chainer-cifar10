import chainer
import chainer.functions as F
import chainer.links as L


# https://github.com/zaburo-ch/chainercv/blob/master/chainercv/links/connection/seblock.py
class SEBlock(chainer.Chain):

    """A squeeze-and-excitation block.
    This block is part of squeeze-and-excitation networks. Channel-wise
    multiplication weights are inferred from and applied to input feature map.
    Please refer to `the original paper
    <https://arxiv.org/pdf/1709.01507.pdf>`_ for more details.
    .. seealso::
        :class:`chainercv.links.model.senet.SEResNet`
    Args:
        n_channel (int): The number of channels of the input and output array.
        ratio (int): Reduction ratio of :obj:`n_channel` to the number of
            hidden layer units.
    """

    def __init__(self, n_channel, ratio=16):

        super(SEBlock, self).__init__()
        reduction_size = n_channel // ratio

        with self.init_scope():
            self.down = L.Linear(n_channel, reduction_size)
            self.up = L.Linear(reduction_size, n_channel)

    def __call__(self, u):
        B, C, H, W = u.shape

        z = F.average(u, axis=(2, 3))
        x = F.relu(self.down(z))
        x = F.sigmoid(self.up(x))

        x = F.broadcast_to(x, (H, W, B, C))
        x = x.transpose((2, 3, 0, 1))

        return u * x


class BottleNeck(chainer.Chain):

    def __init__(self, n_in, n_mid, n_out, stride=1, use_conv=False, add_seblock=False):
        w = chainer.initializers.HeNormal()
        super(BottleNeck, self).__init__()
        with self.init_scope():
            self.conv1 = L.Convolution2D(n_in, n_mid, 1, stride, 0, True, w)
            self.bn1 = L.BatchNormalization(n_mid)
            self.conv2 = L.Convolution2D(n_mid, n_mid, 3, 1, 1, True, w)
            self.bn2 = L.BatchNormalization(n_mid)
            self.conv3 = L.Convolution2D(n_mid, n_out, 1, 1, 0, True, w)
            self.bn3 = L.BatchNormalization(n_out)
            if add_seblock:
                self.se = SEBlock(n_out)
            if use_conv:
                self.conv4 = L.Convolution2D(
                    n_in, n_out, 1, stride, 0, True, w)
                self.bn4 = L.BatchNormalization(n_out)
        self.use_conv = use_conv
        self.add_seblock = add_seblock

    def __call__(self, x):
        h = F.relu(self.bn1(self.conv1(x)))
        h = F.relu(self.bn2(self.conv2(h)))
        h = self.bn3(self.conv3(h))
        if self.add_seblock:
            h = self.se(h)
        return h + self.bn4(self.conv4(x)) if self.use_conv else h + x


class Block(chainer.ChainList):

    def __init__(self, n_in, n_mid, n_out, n_bottlenecks, stride=2):
        super(Block, self).__init__()
        self.add_link(BottleNeck(n_in, n_mid, n_out, stride, True))
        for _ in range(n_bottlenecks - 1):
            self.add_link(BottleNeck(n_out, n_mid, n_out))

    def __call__(self, x):
        for f in self:
            x = f(x)
        return x


class ResNet(chainer.Chain):

    def __init__(self, n_class=10, n_blocks=[3, 4, 6, 3]):
        super(ResNet, self).__init__()
        w = chainer.initializers.HeNormal()
        with self.init_scope():
            self.conv1 = L.Convolution2D(None, 64, 3, 1, 0, True, w)
            self.bn2 = L.BatchNormalization(64)
            self.res3 = Block(64, 64, 256, n_blocks[0], 1)
            self.res4 = Block(256, 128, 512, n_blocks[1], 2)
            self.res5 = Block(512, 256, 1024, n_blocks[2], 2)
            self.res6 = Block(1024, 512, 2048, n_blocks[3], 2)
            self.fc7 = L.Linear(None, n_class)

    def __call__(self, x):
        h = F.relu(self.bn2(self.conv1(x)))
        h = self.res3(h)
        h = self.res4(h)
        h = self.res5(h)
        h = self.res6(h)
        h = F.average_pooling_2d(h, h.shape[2:])
        h = self.fc7(h)
        return h


class ResNet50(ResNet):

    def __init__(self, n_class=10):
        super(ResNet50, self).__init__(n_class, [3, 4, 6, 3])


class ResNet101(ResNet):

    def __init__(self, n_class=10):
        super(ResNet101, self).__init__(n_class, [3, 4, 23, 3])


class ResNet152(ResNet):

    def __init__(self, n_class=10):
        super(ResNet152, self).__init__(n_class, [3, 8, 36, 3])


if __name__ == '__main__':
    import numpy as np
    x = np.random.randn(1, 3, 32, 32).astype(np.float32)
    model = ResNet(10)
    y = model(x)
