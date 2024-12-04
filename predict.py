import time
import cv2
import os
import global_var
import numpy as np
from PIL import Image

from yolo import YOLO

if __name__ == "__main__":
    mode = "video"
    video_path = 0
    video_save_path = "detected_video/"
    video_fps = 17.0
    yolo = YOLO()

    if mode == "video":
        dir_path = "D:\\yolov7-pytorch-shuchuan\\detected_video"
        capture = cv2.VideoCapture(video_path)
        out = None
        video_start_time = None
        is_recording = False
        frame_count = 0  # 新增，用于记录帧数

        ref, frame = capture.read()
        if not ref:
            raise ValueError("未能正确读取摄像头（视频），请注意是否正确安装摄像头（是否正确填写视频路径）。")

        original_fps = capture.get(cv2.CAP_PROP_FPS)  # 获取原始FPS
        video_fps = original_fps  # 使用原始FPS作为视频录制的帧率
        fps = 0.0
        target_frame_count = int(video_fps * 4)  # 根据帧率计算4秒对应的帧数

        while True:
            t1 = time.time()
            ref, frame = capture.read()
            if not ref:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_image = Image.fromarray(np.uint8(frame_rgb))
            frame_detected = yolo.detect_image(frame_image)

            frame = cv2.cvtColor(np.array(frame_detected), cv2.COLOR_RGB2BGR)

            fps = (fps + (1. / (time.time() - t1))) / 2
            frame = cv2.putText(frame, "fps= %.2f" % (fps), (0, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            cv2.imshow("video", frame)
            c = cv2.waitKey(1) & 0xff

            # 当can_record为1且当前未在录制视频时，开始录制视频
            if global_var.can_record == 1 and not is_recording:
                video_start_time = time.time()
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # 设置编码格式
                size = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))  # 设置视频尺寸
                timestamp = int(time.time())
                filepath = os.path.join(dir_path, f"{timestamp}_personMoved.mp4")

                # 设置视频写入属性，包括较高的比特率和帧率
                out = cv2.VideoWriter(filepath, fourcc, video_fps, size)
                is_recording = True
                frame_count = 0  # 开始录制时初始化帧数
                print("开始录制视频")

            # 录制4秒的视频，确保在录制过程中保持can_record为1
            if is_recording:
                frame_count += 1  # 每循环一次，帧数加1
                if frame_count >= target_frame_count:  # 根据帧数判断是否达到4秒
                    global_var.can_record = 0  # 结束录制后，停止can_record的控制
                    is_recording = False
                    out.release()
                    out = None
                    global_var.video_size_kb = os.path.getsize(filepath) / 1024
                    global_var.saved_memory = (global_var.video_size_kb - global_var.img_size_kb) / global_var.video_size_kb
                    print(f"视频录制完成！生成视频文件：{filepath}，视频文件大小：{global_var.video_size_kb:.2f}KB，节省流量：{global_var.saved_memory * 100 :.2f}%")
                else:
                    if filepath!= "" and global_var.can_record == 1 and is_recording:
                        out.write(frame)  # 继续写入帧

            if c == 27:  # ESC键
                capture.release()
                break

        print("Video Detection Done!")
        capture.release()
        cv2.destroyAllWindows()