# EasyOCR 本地模型目录

当前项目已切换为 **本地模型加载** 模式，默认行为如下：

- 模型目录：`third_party/easyocr/model/`
- 禁止运行时在线下载：`download_enabled=False`
- 当前移动端文字识别默认语言：`['ch_sim', 'en']`
- 当前检测模型：`craft`

## 必需模型文件

请将以下文件放入 `third_party/easyocr/model/`：

- `craft_mlt_25k.pth`
- `zh_sim_g2.pth`

## 说明

- 缺少以上任一文件时，`OCRHelper` 会直接报错，不再退回在线下载。
- 这样可以避免测试/生产环境因为网络不可达导致 OCR 初始化失败。
- 如果未来切换语言或检测模型，需要同步补齐对应的 EasyOCR 模型文件。
