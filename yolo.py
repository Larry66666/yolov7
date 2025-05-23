import colorsys
import os
import time
import global_var
import threading
import numpy as np
import torch
import torch.nn as nn
from PIL import ImageDraw, ImageFont, Image

import movement_sender
from nets.yolo import YoloBody
from upload_to_ftp import upload_to_ftp_threaded
from utils.utils import (cvtColor, get_anchors, get_classes, preprocess_input,
                         resize_image, show_config)
from utils.utils_bbox import DecodeBox, DecodeBoxNP


class YOLO(object):
    _defaults = {
        #--------------------------------------------------------------------------#
        #   使用自己训练好的模型进行预测一定要修改model_path和classes_path！
        #   model_path指向logs文件夹下的权值文件，classes_path指向model_data下的txt
        #
        #   训练好后logs文件夹下存在多个权值文件，选择验证集损失较低的即可。
        #   验证集损失较低不代表mAP较高，仅代表该权值在验证集上泛化性能较好。
        #   如果出现shape不匹配，同时要注意训练时的model_path和classes_path参数的修改
        #--------------------------------------------------------------------------#
        "model_path"        : 'model_data/yolov7_weights.pth',
        "classes_path"      : 'model_data/coco_classes.txt',
        #---------------------------------------------------------------------#
        #   anchors_path代表先验框对应的txt文件，一般不修改。
        #   anchors_mask用于帮助代码找到对应的先验框，一般不修改。
        #---------------------------------------------------------------------#
        "anchors_path"      : 'model_data/yolo_anchors.txt',
        "anchors_mask"      : [[6, 7, 8], [3, 4, 5], [0, 1, 2]],
        #---------------------------------------------------------------------#
        #   输入图片的大小，必须为32的倍数。
        #---------------------------------------------------------------------#
        "input_shape"       : [640, 640],
        #------------------------------------------------------#
        #   所使用到的yolov7的版本，本仓库一共提供两个：
        #   l : 对应yolov7
        #   x : 对应yolov7_x
        #------------------------------------------------------#
        "phi"               : 'l',
        #---------------------------------------------------------------------#
        #   只有得分大于置信度的预测框会被保留下来
        #---------------------------------------------------------------------#
        "confidence"        : 0.6,
        #---------------------------------------------------------------------#
        #   非极大抑制所用到的nms_iou大小
        #---------------------------------------------------------------------#
        "nms_iou"           : 0.3,
        #---------------------------------------------------------------------#
        #   该变量用于控制是否使用letterbox_image对输入图像进行不失真的resize，
        #   在多次测试后，发现关闭letterbox_image直接resize的效果更好
        #---------------------------------------------------------------------#
        "letterbox_image"   : True,
        #-------------------------------#
        #   是否使用Cuda
        #   没有GPU可以设置成False
        #-------------------------------#
        "cuda"              : True,
    }

    @classmethod
    def get_defaults(cls, n):
        if n in cls._defaults:
            return cls._defaults[n]
        else:
            return "Unrecognized attribute name '" + n + "'"

    #---------------------------------------------------#
    #   初始化YOLO
    #---------------------------------------------------#
    previous_box = None
    def __init__(self, **kwargs):
        self.__dict__.update(self._defaults)
        self.previous_box = None  # 用于存储上一帧人体的位置
        self.last_capture_time = 0  # 上次截图的时间戳
        self.capture_interval = 5  # 截图的时间间隔（秒）
        #self.capture_count = 0  # 初始化计数器
        for name, value in kwargs.items():
            setattr(self, name, value)
            self._defaults[name] = value

            #---------------------------------------------------#
        #   获得种类和先验框的数量
        #---------------------------------------------------#
        self.class_names, self.num_classes  = get_classes(self.classes_path)
        self.anchors, self.num_anchors      = get_anchors(self.anchors_path)
        self.bbox_util                      = DecodeBox(self.anchors, self.num_classes, (self.input_shape[0], self.input_shape[1]), self.anchors_mask)

        #---------------------------------------------------#
        #   画框设置不同的颜色
        #---------------------------------------------------#
        hsv_tuples = [(x / self.num_classes, 1., 1.) for x in range(self.num_classes)]
        self.colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
        self.colors = list(map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)), self.colors))
        self.generate()

        show_config(**self._defaults)

    #---------------------------------------------------#
    #   生成模型
    #---------------------------------------------------#
    def generate(self, onnx=False):
        #---------------------------------------------------#
        #   建立yolo模型，载入yolo模型的权重
        #---------------------------------------------------#
        self.net    = YoloBody(self.anchors_mask, self.num_classes, self.phi)
        device      = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.net.load_state_dict(torch.load(self.model_path, map_location=device))
        self.net    = self.net.fuse().eval()
        print('{} model, and classes loaded.'.format(self.model_path))
        if not onnx:
            if self.cuda:
                self.net = nn.DataParallel(self.net)
                self.net = self.net.cuda()

    #---------------------------------------------------#
    #   检测图片
    #---------------------------------------------------#
    def detect_image(self, image):
        dir_path = "D:\\yolov7-pytorch-shuchuan\\moved_detected_img"
        #---------------------------------------------------#
        #   计算输入图片的高和宽
        #---------------------------------------------------#
        image_shape = np.array(np.shape(image)[0:2])
        #---------------------------------------------------------#
        #   在这里将图像转换成RGB图像，防止灰度图在预测时报错。
        #   代码仅仅支持RGB图像的预测，所有其它类型的图像都会转化成RGB
        #---------------------------------------------------------#
        image       = cvtColor(image)
        #---------------------------------------------------------#
        #   给图像增加灰条，实现不失真的resize
        #   也可以直接resize进行识别
        #---------------------------------------------------------#
        image_data  = resize_image(image, (self.input_shape[1], self.input_shape[0]), self.letterbox_image)
        #---------------------------------------------------------#
        #   添加上batch_size维度
        #   h, w, 3 => 3, h, w => 1, 3, h, w
        #---------------------------------------------------------#
        image_data  = np.expand_dims(np.transpose(preprocess_input(np.array(image_data, dtype='float32')), (2, 0, 1)), 0)

        with torch.no_grad():
            images = torch.from_numpy(image_data)
            if self.cuda:
                images = images.cuda()
            #---------------------------------------------------------#
            #   将图像输入网络当中进行预测！
            #---------------------------------------------------------#
            outputs = self.net(images)
            outputs = self.bbox_util.decode_box(outputs)
            #---------------------------------------------------------#
            #   将预测框进行堆叠，然后进行非极大抑制
            #---------------------------------------------------------#
            results = self.bbox_util.non_max_suppression(torch.cat(outputs, 1), self.num_classes, self.input_shape,
                                                         image_shape, self.letterbox_image, conf_thres = self.confidence, nms_thres = self.nms_iou)

            if results[0] is None:
                return image

            top_label   = np.array(results[0][:, 6], dtype = 'int32')
            top_conf    = results[0][:, 4] * results[0][:, 5]
            top_boxes   = results[0][:, :4]
        #---------------------------------------------------------#
        #   设置字体与边框厚度
        #---------------------------------------------------------#
        font        = ImageFont.truetype(font='model_data/simhei.ttf', size=np.floor(3e-2 * image.size[1] + 0.5).astype('int32'))
        thickness   = int(max((image.size[0] + image.size[1]) // np.mean(self.input_shape), 1))
        #---------------------------------------------------------#
        #   图像绘制
        #---------------------------------------------------------#
        # 控制发送逻辑
        can_send = True  # 初始状态为可以发送
        for i, c in list(enumerate(top_label)):
            predicted_class = self.class_names[int(c)]
            if predicted_class != 'person':  # 只对‘person’类进行处理
                continue
            box = top_boxes[i]
            score = top_conf[i]

            top, left, bottom, right = box
            top, left, bottom, right = (
                max(0, np.floor(top).astype('int32')),
                max(0, np.floor(left).astype('int32')),
                min(image.size[1], np.floor(bottom).astype('int32')),
                min(image.size[0], np.floor(right).astype('int32')),
            )

            label = '{} {:.2f}'.format(predicted_class, score)
            draw = ImageDraw.Draw(image)
            label_size = draw.textsize(label, font)
            label = label.encode('utf-8')
            #print(label, top, left, bottom, right)

            if top - label_size[1] >= 0:
                text_origin = np.array([left, top - label_size[1]])
            else:
                text_origin = np.array([left, top + 1])

            for i in range(thickness):
                draw.rectangle([left + i, top + i, right - i, bottom - i], outline=self.colors[c])
            draw.rectangle([tuple(text_origin), tuple(text_origin + label_size)], fill=self.colors[c])
            draw.text(text_origin, str(label,'UTF-8'), fill=(0, 0, 0), font=font)
            del draw

            current_time = time.time()
            # 计算与前一帧的位移
            if self.previous_box:
                prev_top, prev_left, prev_bottom, prev_right = self.previous_box
                displacement = np.sqrt((top - prev_top) ** 2 + (left - prev_left) ** 2)
                scale_change = abs((bottom - top) - (prev_bottom - prev_top))

                # 如果位移或形变超过阈值，并且可以发送，则保存图片
                if (displacement > 50 or scale_change > 25) and (current_time - self.last_capture_time > self.capture_interval):
                    global_var.can_record = 1
                    print("可以录制了")
                    if can_send:  # 只有在可以发送时才发送
                        timestamp = int(time.time())
                        filename = f"{timestamp}_1_movementDetected.png"
                        filepath = os.path.join(dir_path, filename)
                        # 调整图像尺寸（如果需要）
                        image_resized = image.resize((640, 480))  # 根据需要调整尺寸
                        # 保存为JPEG格式，压缩质量为85
                        image_resized.save(filepath, format='JPEG', quality=85, subsampling=0)
                        global_var.img_size_kb = os.path.getsize(filepath) / 1024
                        print(f"监测到人移动！生成截图文件：{filename}，图片大小：{global_var.img_size_kb:.2f} KB")
                        self.last_capture_time = current_time

                        # 数传接口
                        # movement_data = movement_sender.MovementData(os.path.join(dir_path, filename))
                        # movement_sender.send_single_movement(movement_data)
                        # ftp接口
                        # upload_to_ftp_threaded(filepath, server='59.110.238.62', username='Bjut_sat', password='123456', ftp_dir='/home/Bjut_sat/ftp/uploads')
                        # upload_to_ftp_threaded(filepath, server='25.25.25.2', username='t1', password='123456', ftp_dir='/detected_img_dir')
                        can_send = False  # 发送后禁用
                    else:
                        can_send = True  # 允许再次发送

            # 更新上一次的框位置
            self.previous_box = (top, left, bottom, right)

        return image
