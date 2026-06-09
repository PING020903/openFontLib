# OpenFontLib - 开源点阵字库

嵌入式系统中文显示解决方案，将 TTF 字体转换为二进制点阵字库。

## 功能特性

- 支持 GB18030 字符集（简体/繁体中文、日韩汉字、ASCII）
- 两种字号：16px 和 32px
- UTF-8 编码索引，支持变长字符
- 横置横排点阵格式，适合 LCD/OLED 显示

## 文件说明

| 文件 | 说明 |
|------|------|
| font_16.bin | 16px 点阵字库（27,619 字符） |
| font_32.bin | 32px 点阵字库（27,579 字符） |
| font.ttf | 源字体文件（文泉驿点阵宋体） |
| ttf2bitmap.py | TTF 转点阵工具 |
| read_font.c | C 语言读取示例 |

## 字库文件格式

```
┌─────────────┐
│  文件头 16B  │  魔数 + 版本 + 字符数 + 字号
├─────────────┤
│   索引表     │  UTF-8长度(1B) + UTF-8编码(1-4B) + 偏移(4B) + 宽(2B) + 高(2B)
├─────────────┤
│  点阵数据    │  横置横排，每行字节对齐
└─────────────┘
```

## 在嵌入式项目中使用

### 1. 复制字库文件

将 `font_16.bin` 或 `font_32.bin` 放入项目资源目录。

### 2. 集成读取代码

```c
#include "read_font.h"

// 打开字库
FontFile *font = font_open("font_16.bin");

// 查找字符（Unicode 码点）
const FontIndex *ch = font_find_char(font, 0x4E2D);  // '中'

// 读取点阵数据
size_t size;
uint8_t *bitmap = font_read_bitmap(font, ch, &size);

// 发送到显示屏
LCD_DrawBitmap(x, y, ch->width, ch->height, bitmap);

free(bitmap);
font_close(font);
```

### 3. 显示 UTF-8 字符串

```c
const char *text = "你好世界";
const uint8_t *p = (const uint8_t *)text;

while (*p) {
    uint32_t unicode;
    int len = utf8_decode(p, &unicode);
    
    const FontIndex *ch = font_find_char(font, unicode);
    if (ch) {
        size_t size;
        uint8_t *bmp = font_read_bitmap(font, ch, &size);
        LCD_DrawBitmap(x, y, ch->width, ch->height, bmp);
        x += ch->width;
        free(bmp);
    }
    
    p += len;
}
```

## 生成自己的字库

### 环境准备

```bash
pip install fonttools freetype-py pillow
```

### 转换命令

```bash
# 生成 16px 字库
python ttf2bitmap.py your_font.ttf output_16.bin 16

# 生成 32px 字库
python ttf2bitmap.py your_font.ttf output_32.bin 32
```

### 推荐字体

| 字体 | 说明 |
|------|------|
| 文泉驿点阵宋体 | 开源，显示清晰 |
| 微软雅黑 | Windows 自带，适合屏幕 |
| 思源黑体/宋体 | Adobe + Google 开源字体 |

## 编译示例程序

```bash
gcc read_font.c -o read_font
./read_font font_16.bin
```

## 许可证

- 文泉驿点阵宋体：GPL v2+
- 转换工具及示例代码：MIT
