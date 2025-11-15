import cv2
import aiohttp
import asyncio
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from ultralytics import YOLO
from modelscope import snapshot_download
import torch
import numpy as np
from io import BytesIO
from PIL import Image
from loguru import logger

from app.utils.decorator import log_class_decorator


@log_class_decorator.decorator
class AsyncCaptchaBreaker:
    """
    异步验证码坐标识别类，使用YOLO11模型进行目标检测
    返回的都是后面一半是提示目标，前面一半才是点击目标的坐标
    坐标以左上角为原点，向右为x轴正方向，向下为y轴正方向
    """

    def __init__(self, model_name: str = 'Amorter/CaptchaBreakerModels', device: Optional[str] = None):
        """
        初始化验证码识别器
        
        Args:
            model_name: 模型名称或路径
            device: 设备类型 ('cuda', 'cpu', 'mps')，如果为None则自动选择
        """
        self.model_name = model_name
        self.device = device if device else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.model_dir = None
        self._session = None
        self.logger = logger

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._load_model()
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._session:
            await self._session.close()

    async def _load_model(self):
        """异步加载YOLO11模型"""
        try:
            # 异步下载模型（使用线程池执行同步操作）
            loop = asyncio.get_event_loop()
            self.model_dir = await loop.run_in_executor(None, snapshot_download, self.model_name)

            # 查找模型文件
            model_path = self._find_model_file()

            if model_path:
                # 异步加载YOLO模型
                self.model = await loop.run_in_executor(None, YOLO, model_path)
                self.logger.info(f"模型加载成功，设备: {self.device}")
            else:
                raise FileNotFoundError(f"在 {self.model_dir} 中未找到合适的模型文件")

        except Exception as e:
            raise RuntimeError(f"模型加载失败: {str(e)}")

    def _find_model_file(self) -> Optional[str]:
        """在下载的模型目录中查找模型文件"""
        # 优先查找YOLO相关的模型文件
        yolo_patterns = ['yolo', 'yolov11']

        for pattern in yolo_patterns:
            for file_path in Path(self.model_dir).rglob(f'*{pattern}*.onnx'):
                if file_path.is_file():
                    self.logger.info(f"找到YOLO模型文件: {file_path}")
                    return str(file_path)

        # 如果没有找到YOLO模型，查找其他ONNX文件
        for file_path in Path(self.model_dir).rglob('*.onnx'):
            if file_path.is_file():
                self.logger.info(f"找到ONNX模型文件: {file_path}")
                return str(file_path)

        # 最后查找其他格式的模型文件
        model_extensions = ['.pt', '.pth']
        for ext in model_extensions:
            for file_path in Path(self.model_dir).rglob(f'*{ext}'):
                if file_path.is_file():
                    self.logger.info(f"找到模型文件: {file_path}")
                    return str(file_path)

        self.logger.warning(f"在 {self.model_dir} 中未找到合适的模型文件")
        return None

    async def _download_image_from_url(self, url: str, timeout: int = 30) -> np.ndarray:
        """
        异步从URL下载图像并转换为OpenCV格式
        
        Args:
            url: 图像URL
            timeout: 请求超时时间（秒）
            
        Returns:
            np.ndarray: OpenCV格式的图像数组
        """
        if not self._session:
            raise RuntimeError("会话未初始化，请使用异步上下文管理器")

        try:
            # 异步发送HTTP请求获取图像
            async with self._session.get(url, timeout=timeout) as response:
                response.raise_for_status()  # 检查请求是否成功

                # 读取图像数据
                image_data = await response.read()

                # 使用线程池处理图像转换（避免阻塞事件循环）
                loop = asyncio.get_event_loop()
                pil_image = await loop.run_in_executor(None, Image.open, BytesIO(image_data))

                # 转换为OpenCV格式
                if pil_image.mode == 'RGBA':
                    pil_image = await loop.run_in_executor(None, pil_image.convert, 'RGB')

                # 将PIL图像转换为numpy数组
                cv_image = await loop.run_in_executor(None, np.array, pil_image)

                # 如果图像是RGB格式，转换为BGR（OpenCV默认格式）
                if len(cv_image.shape) == 3 and cv_image.shape[2] == 3:
                    cv_image = await loop.run_in_executor(None, cv2.cvtColor, cv_image, cv2.COLOR_RGB2BGR)

                return cv_image

        except aiohttp.ClientError as e:
            raise RuntimeError(f"下载图像失败: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"处理图像失败: {str(e)}")

    async def _save_temp_image(self, image: np.ndarray) -> str:
        """
        异步将图像保存为临时文件
        
        Args:
            image: OpenCV格式的图像数组
            
        Returns:
            str: 临时文件路径
        """
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = temp_file.name

            # 异步保存图像
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, cv2.imwrite, temp_path, image)

            return temp_path

        except Exception as e:
            raise RuntimeError(f"保存临时图像失败: {str(e)}")

    async def predict(self, image_path: str, confidence_threshold: float = 0.5,
                      target_size: Tuple[int, int] = (96, 96)) -> List[Dict[str, float]]:
        """
        异步对验证码图像进行预测，返回检测到的目标坐标
        
        Args:
            image_path: 图像文件路径
            confidence_threshold: 置信度阈值
            target_size: 目标图像尺寸 (width, height)，默认为(96, 96)
            
        Returns:
            List[Dict]: 每个检测到的目标信息，包含坐标和置信度
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        # 验证图像文件存在
        if not await asyncio.get_event_loop().run_in_executor(None, Path(image_path).exists):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")

        try:
            # 异步读取图像并调整尺寸
            loop = asyncio.get_event_loop()
            original_image = await loop.run_in_executor(None, cv2.imread, image_path)
            if original_image is None:
                raise ValueError(f"无法读取图像: {image_path}")

            # 调整图像尺寸到目标尺寸
            resized_image = await loop.run_in_executor(
                None,
                cv2.resize,
                original_image,
                target_size
            )

            # 保存调整后的临时图像
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_path = temp_file.name

            await loop.run_in_executor(None, cv2.imwrite, temp_path, resized_image)

            try:
                # 使用调整后的图像进行预测
                results = await loop.run_in_executor(
                    None,
                    lambda: self.model(temp_path, conf=confidence_threshold, device=self.device)
                )

                # 解析结果
                detections = []

                for result in results:
                    if result.boxes is not None:
                        boxes = result.boxes.xyxy.cpu().numpy()  # 边界框坐标 [x1, y1, x2, y2]
                        confidences = result.boxes.conf.cpu().numpy()  # 置信度

                        # 获取原始图像尺寸以进行坐标缩放
                        original_height, original_width = original_image.shape[:2]
                        scale_x = original_width / target_size[0]
                        scale_y = original_height / target_size[1]

                        for i, (box, conf) in enumerate(zip(boxes, confidences)):
                            x1, y1, x2, y2 = box

                            # 将坐标缩放回原始图像尺寸
                            x1 = x1 * scale_x
                            y1 = y1 * scale_y
                            x2 = x2 * scale_x
                            y2 = y2 * scale_y

                            # 计算中心点坐标
                            center_x = (x1 + x2) / 2
                            center_y = (y1 + y2) / 2

                            # 计算宽度和高度
                            width = x2 - x1
                            height = y2 - y1

                            detection = {
                                'center_x': float(center_x),
                                'center_y': float(center_y),
                                'x1': float(x1),
                                'y1': float(y1),
                                'x2': float(x2),
                                'y2': float(y2),
                                'width': float(width),
                                'height': float(height),
                                'confidence': float(conf),
                                'class_id': int(result.boxes.cls[i].item()) if result.boxes.cls is not None else 0,
                                'original_width': original_width,
                                'original_height': original_height,
                                'target_width': target_size[0],
                                'target_height': target_size[1]
                            }

                            detections.append(detection)

                return detections

            except Exception as e:
                raise RuntimeError(f"预测失败: {str(e)}")
            finally:
                # 清理临时文件
                if 'temp_path' in locals():
                    await loop.run_in_executor(None, lambda: Path(temp_path).unlink(missing_ok=True))

        except Exception as e:
            raise RuntimeError(f"预测失败: {str(e)}")

    async def predict_coordinates(self, image_path: str, confidence_threshold: float = 0.5,
                                  target_size: Tuple[int, int] = (96, 96)) -> List[Tuple[float, float]]:
        """
        异步简化的预测方法，只返回中心点坐标
        
        Args:
            image_path: 图像文件路径
            confidence_threshold: 置信度阈值
            target_size: 目标图像尺寸 (width, height)，默认为(96, 96)
            
        Returns:
            List[Tuple]: 每个检测到的目标的中心点坐标 (x, y)
        """
        detections = await self.predict(image_path, confidence_threshold, target_size)
        return [(det['center_x'], det['center_y']) for det in detections]

    async def predict_with_image(self, image_path: str, confidence_threshold: float = 0.5,
                                 save_path: Optional[str] = None, target_size: Tuple[int, int] = (96, 96)) -> Dict:
        """
        异步预测并返回带标注的图像
        
        Args:
            image_path: 图像文件路径
            confidence_threshold: 置信度阈值
            save_path: 保存标注图像的可选路径
            target_size: 目标图像尺寸 (width, height)，默认为(96, 96)
            
        Returns:
            Dict: 包含检测结果和标注图像的信息
        """
        detections = await self.predict(image_path, confidence_threshold, target_size)

        # 异步读取原始图像
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, cv2.imread, image_path)
        if image is None:
            raise ValueError(f"无法读取图像: {image_path}")

        # 在图像上绘制检测结果
        annotated_image = image.copy()

        for det in detections:
            x1, y1, x2, y2 = int(det['x1']), int(det['y1']), int(det['x2']), int(det['y2'])
            center_x, center_y = int(det['center_x']), int(det['center_y'])

            # 绘制边界框
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # 绘制中心点
            cv2.circle(annotated_image, (center_x, center_y), 5, (0, 0, 255), -1)

            # 添加置信度标签
            label = f"Conf: {det['confidence']:.2f}"
            cv2.putText(annotated_image, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # 异步保存标注图像
        if save_path:
            await loop.run_in_executor(None, cv2.imwrite, save_path, annotated_image)

        return {
            'detections': detections,
            'annotated_image': annotated_image,
            'image_shape': image.shape
        }

    async def predict_from_url(self, url: str, confidence_threshold: float = 0.5,
                               target_size: Tuple[int, int] = (96, 96)) -> List[Dict[str, float]]:
        """
        异步从URL下载验证码图像并进行预测
        
        Args:
            url: 验证码图像的URL
            confidence_threshold: 置信度阈值
            target_size: 目标图像尺寸 (width, height)，默认为(96, 96)
            
        Returns:
            List[Dict]: 每个检测到的目标信息，包含坐标和置信度
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        try:
            # 异步下载图像
            cv_image = await self._download_image_from_url(url)

            # 异步保存为临时文件
            temp_path = await self._save_temp_image(cv_image)

            try:
                # 使用临时文件进行预测
                detections = await self.predict(temp_path, confidence_threshold, target_size)

                # 添加图像尺寸信息到每个检测结果
                height, width = cv_image.shape[:2]
                for det in detections:
                    det['image_width'] = width
                    det['image_height'] = height

                return detections

            finally:
                # 异步清理临时文件
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: Path(temp_path).unlink(missing_ok=True))

        except Exception as e:
            raise RuntimeError(f"URL预测失败: {str(e)}")

    async def predict_coordinates_from_url(self, url: str, confidence_threshold: float = 0.5,
                                           target_size: Tuple[int, int] = (96, 96)) -> List[Tuple[float, float]]:
        """
        异步从URL下载验证码图像并返回坐标
        
        Args:
            url: 验证码图像的URL
            confidence_threshold: 置信度阈值
            target_size: 目标图像尺寸 (width, height)，默认为(96, 96)
            
        Returns:
            List[Tuple]: 每个检测到的目标的中心点坐标 (x, y)
        """
        detections = await self.predict_from_url(url, confidence_threshold, target_size)
        return [(det['center_x'], det['center_y']) for det in detections]

    async def predict_with_image_from_url(self, url: str, confidence_threshold: float = 0.5,
                                          save_path: Optional[str] = None,
                                          target_size: Tuple[int, int] = (96, 96)) -> Dict:
        """
        异步从URL下载验证码图像，预测并返回带标注的图像
        
        Args:
            url: 验证码图像的URL
            confidence_threshold: 置信度阈值
            save_path: 保存标注图像的可选路径
            target_size: 目标图像尺寸 (width, height)，默认为(96, 96)
            
        Returns:
            Dict: 包含检测结果和标注图像的信息
        """
        if not self.model:
            raise RuntimeError("模型未加载")

        try:
            # 异步下载图像
            cv_image = await self._download_image_from_url(url)

            # 异步保存为临时文件
            temp_path = await self._save_temp_image(cv_image)

            try:
                # 使用临时文件进行预测
                detections = await self.predict(temp_path, confidence_threshold, target_size)

                # 在图像上绘制检测结果
                annotated_image = cv_image.copy()

                for det in detections:
                    x1, y1, x2, y2 = int(det['x1']), int(det['y1']), int(det['x2']), int(det['y2'])
                    center_x, center_y = int(det['center_x']), int(det['center_y'])

                    # 绘制边界框
                    cv2.rectangle(annotated_image, (x1, y1), (x2, y2), (0, 255, 0), 2)

                    # 绘制中心点
                    cv2.circle(annotated_image, (center_x, center_y), 5, (0, 0, 255), -1)

                    # 添加置信度标签
                    label = f"Conf: {det['confidence']:.2f}"
                    cv2.putText(annotated_image, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

                # 异步保存标注图像
                if save_path:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, cv2.imwrite, save_path, annotated_image)

                # 添加图像尺寸信息
                height, width = cv_image.shape[:2]

                return {
                    'detections': detections,
                    'annotated_image': annotated_image,
                    'image_shape': (height, width),
                    'original_url': url
                }

            finally:
                # 异步清理临时文件
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, lambda: Path(temp_path).unlink(missing_ok=True))

        except Exception as e:
            raise RuntimeError(f"URL图像标注预测失败: {str(e)}")

    async def get_model_info(self) -> Dict:
        """异步获取模型信息"""
        if not self.model:
            return {'status': '模型未加载'}

        return {
            'model_name': self.model_name,
            'device': self.device,
            'model_dir': self.model_dir,
            'status': '已加载'
        }


acb = AsyncCaptchaBreaker()

__all__ = ['acb']  # 导出单例实例
