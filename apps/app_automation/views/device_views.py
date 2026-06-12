# -*- coding: utf-8 -*-
"""APP设备管理视图"""
import os
import tempfile
import subprocess
import base64
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
import logging

from .test_case_views import AppPagination
from ..models import AppDevice
from ..serializers import AppDeviceSerializer
from ..managers.device_manager import DeviceManager

logger = logging.getLogger(__name__)


PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


class DeviceAvailabilityError(Exception):
    """ADB 实时探测到设备不可用时抛出的异常。"""

    def __init__(self, adb_status: str, message: str, http_status: int):
        super().__init__(message)
        self.adb_status = adb_status
        self.message = message
        self.http_status = http_status


def get_adb_path() -> str:
    """
    获取 ADB 路径：优先使用数据库配置，否则使用默认值 'adb'
    """
    try:
        from ..models import AppTestConfig
        config = AppTestConfig.objects.first()
        return config.adb_path if config else 'adb'
    except Exception as e:
        logger.warning(f"获取 ADB 配置失败，使用默认路径: {e}")
        return 'adb'


def _get_subprocess_kwargs() -> dict:
    """统一补充 ADB 子进程参数。"""
    create_no_window = getattr(subprocess, 'CREATE_NO_WINDOW', None)
    return {'creationflags': create_no_window} if create_no_window is not None else {}



def _decode_adb_output(output) -> str:
    if isinstance(output, bytes):
        return output.decode('utf-8', errors='ignore')
    return output or ''



def _run_adb_command(adb_path: str, args: list, *, timeout: int, text: bool = False, check: bool = False):
    return subprocess.run(
        [adb_path, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        text=text,
        check=check,
        **_get_subprocess_kwargs(),
    )



def _parse_adb_device_status(devices_output: str, device_id: str) -> str:
    lines = (devices_output or '').splitlines()
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line or line.startswith('*'):
            continue

        parts = line.split()
        if not parts or parts[0] != device_id:
            continue

        status_token = parts[1].lower() if len(parts) > 1 else ''
        remainder = ' '.join(parts[1:]).lower()

        if status_token == 'device':
            return 'online'
        if status_token in {'offline', 'unauthorized'}:
            return status_token
        if 'no permissions' in remainder or 'unauthorized' in remainder:
            return 'unauthorized'
        if 'offline' in remainder:
            return 'offline'
        return 'offline'

    return 'disconnected'



def _get_unavailable_device_error(adb_status: str):
    if adb_status == 'unauthorized':
        return status.HTTP_403_FORBIDDEN, '设备未授权 ADB 调试，请先在设备上确认调试授权后重试'
    if adb_status == 'offline':
        return status.HTTP_409_CONFLICT, '设备当前处于 offline 状态，请检查 USB 或网络连接后重试'
    return status.HTTP_409_CONFLICT, 'ADB 当前未发现该设备，请确认设备已连接并重新发现设备'



def _sync_device_status(device: AppDevice, adb_status: str) -> None:
    next_status = None
    if adb_status == 'online' and device.status == 'offline':
        next_status = 'online'
    elif adb_status != 'online' and device.status != 'offline':
        next_status = 'offline'

    if next_status and next_status != device.status:
        AppDevice.objects.filter(pk=device.pk).update(status=next_status)
        device.status = next_status



def _probe_device_status(adb_path: str, device: AppDevice) -> str:
    result = _run_adb_command(adb_path, ['devices', '-l'], timeout=10, text=True)
    if result.returncode != 0:
        error_text = _decode_adb_output(result.stderr) or _decode_adb_output(result.stdout)
        raise RuntimeError(error_text or 'ADB 设备检测失败')

    adb_status = _parse_adb_device_status(result.stdout, device.device_id)
    _sync_device_status(device, adb_status)

    if adb_status != 'online':
        http_status, message = _get_unavailable_device_error(adb_status)
        raise DeviceAvailabilityError(adb_status, message, http_status)

    return adb_status



def _infer_device_status_from_error(error_text: str):
    normalized = (error_text or '').lower()
    if 'unauthorized' in normalized or 'no permissions' in normalized:
        return 'unauthorized'
    if 'offline' in normalized:
        return 'offline'
    if 'not found' in normalized or 'no devices/emulators found' in normalized:
        return 'disconnected'
    return None



def _raise_device_unavailable_from_error(device: AppDevice, error_text: str) -> None:
    adb_status = _infer_device_status_from_error(error_text)
    if not adb_status:
        return

    _sync_device_status(device, adb_status)
    http_status, message = _get_unavailable_device_error(adb_status)
    raise DeviceAvailabilityError(adb_status, message, http_status)



def _extract_command_error_text(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        return ' '.join(
            part for part in [
                _decode_adb_output(getattr(error, 'stderr', '')),
                _decode_adb_output(getattr(error, 'stdout', '')),
            ]
            if part
        ).strip()
    return str(error)



def _capture_screenshot_with_exec_out(adb_path: str, device_id: str) -> bytes:
    result = _run_adb_command(
        adb_path,
        ['-s', device_id, 'exec-out', 'screencap', '-p'],
        timeout=15,
        check=True,
    )
    if not result.stdout:
        raise RuntimeError('exec-out screencap 未返回图片数据')
    if not result.stdout.startswith(PNG_SIGNATURE):
        raise RuntimeError('exec-out screencap 返回的不是有效 PNG 数据')
    return result.stdout



def _capture_screenshot_with_fallback(adb_path: str, device_id: str) -> bytes:
    remote_path = f"/data/local/tmp/testhub_screenshot_{int(timezone.now().timestamp() * 1000)}.png"
    local_fd = None
    local_path = None

    try:
        local_fd, local_path = tempfile.mkstemp(prefix='testhub_screenshot_', suffix='.png')
        os.close(local_fd)

        capture_result = _run_adb_command(
            adb_path,
            ['-s', device_id, 'shell', 'screencap', '-p', remote_path],
            timeout=20,
            text=True,
        )
        if capture_result.returncode != 0:
            error_text = _decode_adb_output(capture_result.stderr) or _decode_adb_output(capture_result.stdout)
            raise RuntimeError(error_text or '设备临时截图生成失败')

        pull_result = _run_adb_command(
            adb_path,
            ['-s', device_id, 'pull', remote_path, local_path],
            timeout=20,
            text=True,
        )
        if pull_result.returncode != 0:
            error_text = _decode_adb_output(pull_result.stderr) or _decode_adb_output(pull_result.stdout)
            raise RuntimeError(error_text or '设备临时截图拉取失败')

        with open(local_path, 'rb') as screenshot_file:
            image_bytes = screenshot_file.read()

        if not image_bytes:
            raise RuntimeError('设备临时截图读取失败：无返回数据')
        if not image_bytes.startswith(PNG_SIGNATURE):
            raise RuntimeError('设备临时截图读取失败：返回的不是有效 PNG 数据')

        return image_bytes
    finally:
        try:
            _run_adb_command(
                adb_path,
                ['-s', device_id, 'shell', 'rm', '-f', remote_path],
                timeout=5,
                text=True,
            )
        except Exception as cleanup_error:
            logger.warning(f"清理设备临时截图失败: {cleanup_error}")

        try:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
        except OSError as cleanup_error:
            logger.warning(f"清理本地临时截图失败: {cleanup_error}")


class AppDeviceViewSet(viewsets.ModelViewSet):
    """APP设备管理 ViewSet"""
    queryset = AppDevice.objects.all()
    serializer_class = AppDeviceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'connection_type']
    search_fields = ['device_id', 'name']
    
    @action(detail=False, methods=['get'])
    def discover(self, request):
        """发现ADB设备"""
        try:
            adb_path = get_adb_path()
            logger.info(f"使用 ADB 路径: {adb_path}")
            
            manager = DeviceManager(adb_path=adb_path)
            devices_info = manager.list_devices()
            
            # 更新或创建设备记录
            db_devices = []
            for device_info in devices_info:
                # 判断连接类型和 IP 地址
                device_id = device_info['device_id']
                if ':' in device_id:
                    # 远程设备（IP:端口格式）
                    connection_type = 'remote_emulator'
                    ip_address = device_info.get('ip_address') or ''
                elif device_id.startswith('emulator-'):
                    # 本地模拟器 - 使用 localhost
                    connection_type = 'emulator'
                    ip_address = '127.0.0.1'
                else:
                    # USB 连接的真机
                    connection_type = 'usb'
                    ip_address = device_info.get('ip_address') or ''
                
                device, created = AppDevice.objects.update_or_create(
                    device_id=device_info['device_id'],
                    defaults={
                        'name': device_info.get('name') or '',
                        'status': device_info.get('status') or 'offline',
                        'android_version': device_info.get('android_version') or '',
                        'ip_address': ip_address,
                        'port': device_info.get('port') or 5555,
                        'connection_type': connection_type,
                    }
                )
                db_devices.append(device)
            
            # 返回序列化后的数据库对象
            return Response({
                'success': True,
                'message': f'发现 {len(db_devices)} 个设备',
                'devices': AppDeviceSerializer(db_devices, many=True).data
            })
        except Exception as e:
            logger.error(f"发现设备失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'发现设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """锁定设备"""
        device = self.get_object()
        
        if device.status == 'locked':
            return Response({
                'success': False,
                'message': '设备已被锁定'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        device.lock(request.user)
        
        return Response({
            'success': True,
            'message': '设备锁定成功',
            'device': AppDeviceSerializer(device).data
        })
    
    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        """释放设备"""
        device = self.get_object()
        
        if device.locked_by and device.locked_by != request.user:
            return Response({
                'success': False,
                'message': '无权释放他人锁定的设备'
            }, status=status.HTTP_403_FORBIDDEN)
        
        device.unlock()
        
        return Response({
            'success': True,
            'message': '设备释放成功',
            'device': AppDeviceSerializer(device).data
        })
    
    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        """断开远程设备连接"""
        device = self.get_object()
        
        # 只有远程设备可以断开
        if device.connection_type not in ['remote', 'remote_emulator']:
            return Response({
                'success': False,
                'message': '只能断开远程设备的连接'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            adb_path = get_adb_path()
            manager = DeviceManager(adb_path=adb_path)
            success = manager.disconnect_device(f'{device.ip_address}:{device.port}')
            
            if not success:
                return Response({
                    'success': False,
                    'message': '断开设备失败'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # 更新设备状态为离线
            device.status = 'offline'
            device.save()
            
            return Response({
                'success': True,
                'message': f'设备 {device.name or device.device_id} 已断开连接',
                'device': AppDeviceSerializer(device).data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'断开设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def connect(self, request):
        """连接远程设备"""
        try:
            ip_address = request.data.get('ip_address')
            port = request.data.get('port', 5555)
            
            if not ip_address:
                return Response({
                    'success': False,
                    'message': '请提供设备IP地址'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            adb_path = get_adb_path()
            manager = DeviceManager(adb_path=adb_path)
            device_info = manager.connect_device(ip_address, port)
            
            # 创建或更新设备记录
            device, created = AppDevice.objects.update_or_create(
                device_id=device_info['device_id'],
                defaults={
                    'name': device_info.get('name') or '',
                    'status': 'online',
                    'android_version': device_info.get('android_version', ''),
                    'ip_address': ip_address,
                    'port': port,
                    'connection_type': 'remote_emulator',
                }
            )
            
            return Response({
                'success': True,
                'message': '设备连接成功',
                'device': AppDeviceSerializer(device).data
            })
        except Exception as e:
            logger.error(f"连接设备失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'连接设备失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], url_path='screenshot')
    def screenshot(self, request, pk=None):
        """
        获取设备实时截图
        
        功能：
        1. 截图前实时校验设备连接状态
        2. 优先使用 exec-out screencap -p 截图
        3. 必要时回退到设备临时文件方案
        4. 返回 Base64 data URL
        """
        device = self.get_object()

        try:
            adb_path = get_adb_path()
            _probe_device_status(adb_path, device)

            try:
                image_bytes = _capture_screenshot_with_exec_out(adb_path, device.device_id)
            except (subprocess.CalledProcessError, RuntimeError) as capture_error:
                error_text = _extract_command_error_text(capture_error)
                _raise_device_unavailable_from_error(device, error_text)
                logger.warning(
                    f"设备 {device.device_id} exec-out 截图失败，尝试 fallback: {error_text or 'unknown error'}"
                )
                image_bytes = _capture_screenshot_with_fallback(adb_path, device.device_id)

            timestamp = int(timezone.now().timestamp())
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            logger.info(f"设备 {device.device_id} 截图成功")

            return Response({
                'code': 0,
                'msg': '截图成功',
                'success': True,
                'data': {
                    'filename': f"device_{device.id}_{timestamp}.png",
                    'content': f"data:image/png;base64,{image_base64}",
                    'device_id': device.device_id,
                    'timestamp': timestamp,
                }
            })
        except DeviceAvailabilityError as availability_error:
            logger.warning(
                f"设备 {device.device_id} 当前不可截图，实时状态={availability_error.adb_status}: "
                f"{availability_error.message}"
            )
            return Response({
                'code': availability_error.http_status,
                'msg': availability_error.message,
                'success': False,
            }, status=availability_error.http_status)
        except subprocess.TimeoutExpired:
            logger.error(f"设备 {device.device_id} 截图超时")
            return Response({
                'code': 500,
                'msg': '截图超时，请检查设备连接后重试',
                'success': False,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except FileNotFoundError:
            logger.error('ADB 命令不存在，无法执行设备截图')
            return Response({
                'code': 500,
                'msg': '截图失败：未找到 ADB 命令，请检查 ADB 路径配置',
                'success': False,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            error_text = _extract_command_error_text(e)
            try:
                _raise_device_unavailable_from_error(device, error_text)
            except DeviceAvailabilityError as availability_error:
                logger.warning(
                    f"设备 {device.device_id} 在截图过程中状态变化为 {availability_error.adb_status}: "
                    f"{availability_error.message}"
                )
                return Response({
                    'code': availability_error.http_status,
                    'msg': availability_error.message,
                    'success': False,
                }, status=availability_error.http_status)

            logger.error(f"设备 {device.device_id} 截图失败: {error_text or str(e)}")
            return Response({
                'code': 500,
                'msg': f"截图失败: {error_text or str(e)}",
                'success': False,
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
