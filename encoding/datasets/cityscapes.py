###########################################################################
# Created by: Hang Zhang
# Email: zhang.hang@rutgers.edu
# Copyright (c) 2018
###########################################################################

import os
import random
import numpy as np

import torch

from tqdm import tqdm
from PIL import Image, ImageOps, ImageFilter

from .base import BaseDataset

class CitySegmentation(BaseDataset):
    NUM_CLASS = 9
    def __init__(self, root=os.path.expanduser('~/.encoding/data'), split='train',
                 mode=None, transform=None, target_transform=None, **kwargs):
        super(CitySegmentation, self).__init__(
            root, split, mode, transform, target_transform, **kwargs)
        self.images, self.mask_paths = get_city_pairs(self.root, self.split)
        assert (len(self.images) == len(self.mask_paths))
    #     if len(self.images) == 0:
    #         raise RuntimeError("Found 0 images in subfolders of: \
    #             " + self.root + "\n")
    #     self._indices = np.array(range(-1, 19))
    #     self._classes = np.array([0, 7, 8, 11, 12, 13, 17, 19, 20, 21, 22,
    #                               23, 24, 25, 26, 27, 28, 31, 32, 33])
    #     self._key = np.array([-1, -1, -1, -1, -1, -1,
    #                           -1, -1,  0,  1, -1, -1, 
    #                           2,   3,  4, -1, -1, -1,
    #                           5,  -1,  6,  7,  8,  9,
    #                           10, 11, 12, 13, 14, 15,
    #                           -1, -1, 16, 17, 18])
    #     self._mapping = np.array(range(-1, len(self._key)-1)).astype('int32')

    # def _class_to_index(self, mask):
    #     # assert the values
    #     values = np.unique(mask)
    #     for i in range(len(values)):
    #         assert(values[i] in self._mapping)
    #     index = np.digitize(mask.ravel(), self._mapping, right=True)
    #     return self._key[index].reshape(mask.shape)

    # def _preprocess(self, mask_file):
    #     if os.path.exists(mask_file):
    #         masks = torch.load(mask_file)
        #     return masks
        # masks = []
        # print("Preprocessing mask, this will take a while." + \
        #     "But don't worry, it only run once for each split.")
        # tbar = tqdm(self.mask_paths)
        # for fname in tbar:
        #     tbar.set_description("Preprocessing masks {}".format(fname))
        #     mask = Image.fromarray(self._class_to_index(
        #         np.array(Image.open(fname))).astype('int8'))
        #     masks.append(mask)
        # torch.save(masks, mask_file)
        # return masks

    @property
    def pred_offset(self):
        return 0  # 根据实际数据集需求返回偏移量

    def __getitem__(self, index):
        img = Image.open(self.images[index]).convert('RGB')
        mask = Image.open(self.mask_paths[index])
        if self.mode == 'test':
            if self.transform is not None:
                img = self.transform(img)
                mask = self._mask_transform(mask)
            return img, mask
        mask = Image.open(self.mask_paths[index])
        # synchrosized transform
        if self.mode == 'train':
            img, mask = self._sync_transform(img, mask)
        elif self.mode == 'val':
            img, mask = self._val_sync_transform(img, mask)
        else:
            assert self.mode == 'testval'
            mask = self._mask_transform(mask)
        # general resize, normalize and toTensor
        if self.transform is not None:
            img = self.transform(img)
        if self.target_transform is not None:
            mask = self.target_transform(mask)
        return img, mask

    def _sync_transform(self, img, mask):
        # random mirror
        if random.random() < 0.5:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
            mask = mask.transpose(Image.FLIP_LEFT_RIGHT)
        crop_size = self.crop_size
        # random scale (short edge from 480 to 720)
        short_size = random.randint(int(self.base_size*0.5), int(self.base_size*2.0))
        w, h = img.size
        if h > w:
            ow = short_size
            oh = int(1.0 * h * ow / w)
        else:
            oh = short_size
            ow = int(1.0 * w * oh / h)
        img = img.resize((ow, oh), Image.BILINEAR)
        mask = mask.resize((ow, oh), Image.NEAREST)
        # random rotate -10~10, mask using NN rotate
        deg = random.uniform(-10, 10)
        img = img.rotate(deg, resample=Image.BILINEAR)
        mask = mask.rotate(deg, resample=Image.NEAREST)
        # pad crop
        if short_size < crop_size:
            padh = crop_size - oh if oh < crop_size else 0
            padw = crop_size - ow if ow < crop_size else 0
            img = ImageOps.expand(img, border=(0, 0, padw, padh), fill=0)
            mask = ImageOps.expand(mask, border=(0, 0, padw, padh), fill=0)
        # random crop crop_size
        w, h = img.size
        x1 = random.randint(0, w - crop_size)
        y1 = random.randint(0, h - crop_size)
        img = img.crop((x1, y1, x1+crop_size, y1+crop_size))
        mask = mask.crop((x1, y1, x1+crop_size, y1+crop_size))
        # gaussian blur as in PSP
        if random.random() < 0.5:
            img = img.filter(ImageFilter.GaussianBlur(
                radius=random.random()))
        # final transform
        return img, self._mask_transform(mask)

    def _mask_transform(self, mask):
        # target = self._class_to_index(np.array(mask).astype('int32'))
        target = np.array(mask).astype('int64')  # 根据需要调整数据类型
        return torch.from_numpy(target).long()

    def __len__(self):
        return len(self.images)

    def make_pred(self, mask):
        values = np.unique(mask)
        for i in range(len(values)):
            assert(values[i] in self._indices)
        index = np.digitize(mask.ravel(), self._indices, right=True)
        return self._classes[index].reshape(mask.shape)


def get_city_pairs(folder, split='train'):
    # def get_path_pairs(img_folder, mask_folder):
    #     img_paths = []  
    #     mask_paths = []  
    #     for root, directories, files in os.walk(img_folder):
    #         for filename in files:
    #             if filename.endswith(".png"):
    #                 imgpath = os.path.join(root, filename)
    #                 foldername = os.path.basename(os.path.dirname(imgpath))
    #                 maskname = filename.replace('leftImg8bit','gtFine_labelIds')
    #                 maskpath = os.path.join(mask_folder, foldername, maskname)
    #                 if os.path.isfile(imgpath) and os.path.isfile(maskpath):
    #                     img_paths.append(imgpath)
    #                     mask_paths.append(maskpath)
    #                 else:
    #                     print('cannot find the mask or image:', imgpath, maskpath)
    #     print('Found {} images in the folder {}'.format(len(img_paths), img_folder))
    #     return img_paths, mask_paths

    # if split == 'train' or split == 'val' or split == 'test':
    #     img_folder = os.path.join(folder, 'leftImg8bit/' + split)
    #     mask_folder = os.path.join(folder, 'gtFine/'+ split)
    #     img_paths, mask_paths = get_path_pairs(img_folder, mask_folder)
    #     return img_paths, mask_paths
    # else:
    #     assert split == 'trainval'
    #     print('trainval set')
    #     train_img_folder = os.path.join(folder, 'leftImg8bit/train')
    #     train_mask_folder = os.path.join(folder, 'gtFine/train')
    #     val_img_folder = os.path.join(folder, 'leftImg8bit/val')
    #     val_mask_folder = os.path.join(folder, 'gtFine/val')
    #     train_img_paths, train_mask_paths = get_path_pairs(train_img_folder, train_mask_folder)
    #     val_img_paths, val_mask_paths = get_path_pairs(val_img_folder, val_mask_folder)
    #     img_paths = train_img_paths + val_img_paths
    #     mask_paths = train_mask_paths + val_mask_paths
    # return img_paths, mask_paths
    # 实现获取图像和掩码路径的逻辑
    # 这里需要根据你的数据集组织方式来实现
    # ir_img_paths = []
    img_paths = []
    mask_paths = []
    
    if split == 'train':
        # ir_img_folder = os.path.join(folder, 'infrared/train')
        img_folder = os.path.join(folder, 'visible/train')
        mask_folder = os.path.join(folder, 'masks/train')
        # 遍历文件夹获取图像和掩码路径
        for filename in os.listdir(img_folder):
            if filename.endswith(".png"):  # 根据你的图像格式调整
                # img_path = os.path.join(ir_img_folder, filename)
                img_path = os.path.join(img_folder, filename)
                mask_filename = filename.replace('.jpg', '.png')  # 根据你的掩码格式调整
                mask_path = os.path.join(mask_folder, mask_filename)
                if os.path.exists(mask_path) and os.path.exists(img_path):
                    # ir_img_paths.append(ir_img_path)
                    img_paths.append(img_path)
                    mask_paths.append(mask_path)
    elif split == 'val':
        img_folder = os.path.join(folder, 'visible/val')
        mask_folder = os.path.join(folder, 'masks/val')
        # 遍历文件夹获取图像和掩码路径
        for filename in os.listdir(img_folder):
            if filename.endswith(".png"):  # 根据你的图像格式调整
                # ir_img_path = os.path.join(ir_img_folder, filename)
                img_path = os.path.join(img_folder, filename)
                mask_filename = filename.replace('.jpg', '.png')  # 根据你的掩码格式调整
                mask_path = os.path.join(mask_folder, mask_filename)
                if os.path.exists(mask_path) and os.path.exists(img_path):
                    # ir_img_paths.append(ir_img_path)
                    img_paths.append(img_path)
                    mask_paths.append(mask_path)
    elif split == 'test':
        # ir_img_folder = os.path.join(folder, 'infrared/test')
        img_folder = os.path.join(folder, 'visible/test')
        mask_folder = os.path.join(folder, 'masks/test')
        # 遍历文件夹获取图像和掩码路径
        for filename in os.listdir(img_folder):
            if filename.endswith(".png"):  # 根据你的图像格式调整
                # ir_img_path = os.path.join(ir_img_folder, filename)
                img_path = os.path.join(img_folder, filename)
                mask_filename = filename.replace('.jpg', '.png')  # 根据你的掩码格式调整
                mask_path = os.path.join(mask_folder, mask_filename)
                if os.path.exists(mask_path) and os.path.exists(img_path):
                    # ir_img_paths.append(ir_img_path)
                    img_paths.append(img_path)
                    mask_paths.append(mask_path)
    # 可以继续添加其他 split 的逻辑，例如 'test'
    else:
        raise ValueError(f"Unsupported split: {split}")
    
    return img_paths, mask_paths    
