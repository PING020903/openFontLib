#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTF字体转点阵字库工具
将TTF字体文件转换为嵌入式系统可用的二进制点阵字库
支持GB18030字符集（包含简体和繁体中文）
"""

import struct
import sys
import os
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont


class TTF2Bitmap:
    """TTF转点阵字库转换器"""
    
    # GB18030字符范围
    GB18030_RANGES = [
        (0x00, 0x7F),           # ASCII
        (0x4E00, 0x9FFF),       # 基本汉字
        (0x3400, 0x4DBF),       # 扩展A
        (0x20000, 0x2A6DF),     # 扩展B
    ]
    
    # 文件头魔数
    MAGIC = b'FONT'
    VERSION = 1
    
    def __init__(self, ttf_path, font_size=16, font_number=0):
        """
        初始化转换器
        
        Args:
            ttf_path: TTF/TTC字体文件路径
            font_size: 字号大小（像素）
            font_number: TTC集合中的字体编号
        """
        self.ttf_path = ttf_path
        self.font_size = font_size
        self.font_number = font_number
        self.font = None
        self.pil_font = None
        self.cmap = None
        self.char_data = []  # [(unicode, bitmap_data)]
        
    def load_font(self):
        """加载TTF/TTC字体"""
        print(f"加载字体: {self.ttf_path}")
        
        if self.ttf_path.lower().endswith('.ttc'):
            self.font = TTFont(self.ttf_path, fontNumber=self.font_number)
        else:
            self.font = TTFont(self.ttf_path)
        self.cmap = self.font.getBestCmap()
        
        self.pil_font = ImageFont.truetype(self.ttf_path, self.font_size, index=self.font_number)
        
        print(f"字体加载成功，共 {len(self.cmap)} 个字符")
        
    def get_gb18030_chars(self):
        """获取GB18030字符集中的字符"""
        chars = []
        
        for start, end in self.GB18030_RANGES:
            for code in range(start, end + 1):
                if code in self.cmap:
                    chars.append(code)
        
        print(f"GB18030字符集共 {len(chars)} 个字符")
        return chars
    
    def render_char_to_bitmap(self, char_code):
        """
        将字符渲染为点阵位图
        
        Args:
            char_code: Unicode编码
            
        Returns:
            bitmap_data: 点阵数据（字节序列）
            width: 字符宽度
            height: 字符高度
        """
        try:
            char = chr(char_code)
            bbox = self.pil_font.getbbox(char)
            
            if not bbox or (bbox[2] - bbox[0] == 0 and bbox[3] - bbox[1] == 0):
                return b'\x00' * ((self.font_size + 7) // 8 * self.font_size), self.font_size, self.font_size
            
            width = self.font_size
            height = self.font_size
            
            img = Image.new('L', (width, height), 0)
            draw = ImageDraw.Draw(img)
            draw.text((0, 0), char, font=self.pil_font, fill=255)
            
            bitmap_data = []
            for y in range(height):
                byte_val = 0
                bit_count = 0
                for x in range(width):
                    pixel = img.getpixel((x, y))
                    if pixel > 128:
                        byte_val |= (1 << (7 - bit_count))
                    bit_count += 1
                    
                    if bit_count == 8:
                        bitmap_data.append(byte_val)
                        byte_val = 0
                        bit_count = 0
                
                if bit_count > 0:
                    bitmap_data.append(byte_val)
            
            return bytes(bitmap_data), width, height
            
        except Exception as e:
            print(f"渲染字符 {hex(char_code)} 失败: {e}")
            return b'\x00' * ((self.font_size + 7) // 8 * self.font_size), self.font_size, self.font_size
    
    def convert(self, output_path, char_filter=None):
        """
        转换字体为点阵字库
        
        Args:
            output_path: 输出BIN文件路径
            char_filter: 字符过滤函数（可选）
        """
        print("开始转换...")
        
        # 获取字符列表
        chars = self.get_gb18030_chars()
        
        if char_filter:
            chars = [c for c in chars if char_filter(c)]
            print(f"过滤后剩余 {len(chars)} 个字符")
        
        # 渲染每个字符
        self.char_data = []
        for i, char_code in enumerate(chars):
            if i % 100 == 0:
                print(f"处理进度: {i}/{len(chars)}", flush=True)
            
            bitmap_data, width, height = self.render_char_to_bitmap(char_code)
            self.char_data.append((char_code, bitmap_data, width, height))
        
        print(f"字符渲染完成，共 {len(self.char_data)} 个字符")
        
        # 写入BIN文件
        self.write_bin_file(output_path)
        
        print(f"字库文件已生成: {output_path}")
    
    def unicode_to_utf8(self, code):
        """将Unicode码点转换为UTF-8编码"""
        if code <= 0x7F:
            return bytes([code])
        elif code <= 0x7FF:
            return bytes([0xC0 | (code >> 6), 0x80 | (code & 0x3F)])
        elif code <= 0xFFFF:
            return bytes([0xE0 | (code >> 12), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)])
        elif code <= 0x10FFFF:
            return bytes([0xF0 | (code >> 18), 0x80 | ((code >> 12) & 0x3F), 0x80 | ((code >> 6) & 0x3F), 0x80 | (code & 0x3F)])
        else:
            raise ValueError(f"无效的Unicode码点: {hex(code)}")
    
    def write_bin_file(self, output_path):
        """
        写入BIN文件（UTF-8编码索引）
        
        文件格式：
        - 文件头（16字节）
        - 索引表（变长，每项包含UTF-8编码 + 偏移 + 宽高）
        - 点阵数据区
        
        点阵排列：横置横排（从左到右，从上到下）
        """
        with open(output_path, 'wb') as f:
            # 写入文件头
            # 魔数（4字节）
            f.write(self.MAGIC)
            # 版本（4字节）
            f.write(struct.pack('<I', self.VERSION))
            # 字符数量（4字节）
            f.write(struct.pack('<I', len(self.char_data)))
            # 字号（4字节）
            f.write(struct.pack('<I', self.font_size))
            
            # 先计算索引表大小，确定数据区起始偏移
            # 索引表格式：UTF-8长度(1字节) + UTF-8编码(1-4字节) + 偏移(4字节) + 宽度(2字节) + 高度(2字节)
            index_size = 0
            for char_code, bitmap_data, width, height in self.char_data:
                utf8_bytes = self.unicode_to_utf8(char_code)
                index_size += 1 + len(utf8_bytes) + 4 + 2 + 2  # 1 + utf8_len + 4 + 2 + 2
            
            data_offset = 16 + index_size  # 头部 + 索引表
            
            # 写入索引表
            current_offset = data_offset
            for char_code, bitmap_data, width, height in self.char_data:
                utf8_bytes = self.unicode_to_utf8(char_code)
                # UTF-8编码长度（1字节）
                f.write(struct.pack('B', len(utf8_bytes)))
                # UTF-8编码（1-4字节）
                f.write(utf8_bytes)
                # 数据偏移（4字节）
                f.write(struct.pack('<I', current_offset))
                # 宽度（2字节）
                f.write(struct.pack('<H', width))
                # 高度（2字节）
                f.write(struct.pack('<H', height))
                
                current_offset += len(bitmap_data)
            
            # 写入点阵数据（横置横排格式）
            for char_code, bitmap_data, width, height in self.char_data:
                f.write(bitmap_data)
        
        file_size = os.path.getsize(output_path)
        print(f"文件大小: {file_size} 字节 ({file_size/1024:.2f} KB)")


def utf8_to_unicode(utf8_bytes):
    """将UTF-8编码转换为Unicode码点"""
    if len(utf8_bytes) == 1:
        return utf8_bytes[0]
    elif len(utf8_bytes) == 2:
        return ((utf8_bytes[0] & 0x1F) << 6) | (utf8_bytes[1] & 0x3F)
    elif len(utf8_bytes) == 3:
        return ((utf8_bytes[0] & 0x0F) << 12) | ((utf8_bytes[1] & 0x3F) << 6) | (utf8_bytes[2] & 0x3F)
    elif len(utf8_bytes) == 4:
        return ((utf8_bytes[0] & 0x07) << 18) | ((utf8_bytes[1] & 0x3F) << 12) | ((utf8_bytes[2] & 0x3F) << 6) | (utf8_bytes[3] & 0x3F)
    else:
        raise ValueError(f"无效的UTF-8编码: {utf8_bytes}")


def read_bitmap_from_bin(bin_path, unicode_code):
    """
    从BIN文件中读取指定字符的点阵数据（UTF-8编码索引）
    
    Args:
        bin_path: BIN文件路径
        unicode_code: Unicode编码
        
    Returns:
        bitmap_data: 点阵数据
        width: 字符宽度
        height: 字符高度
    """
    with open(bin_path, 'rb') as f:
        # 读取文件头
        magic = f.read(4)
        if magic != b'FONT':
            raise ValueError("无效的字库文件")
        
        version = struct.unpack('<I', f.read(4))[0]
        char_count = struct.unpack('<I', f.read(4))[0]
        font_size = struct.unpack('<I', f.read(4))[0]
        
        # 查找字符（UTF-8编码索引）
        for i in range(char_count):
            # 读取UTF-8编码长度
            utf8_len = struct.unpack('B', f.read(1))[0]
            # 读取UTF-8编码
            utf8_bytes = f.read(utf8_len)
            # 读取偏移和宽高
            offset = struct.unpack('<I', f.read(4))[0]
            width = struct.unpack('<H', f.read(2))[0]
            height = struct.unpack('<H', f.read(2))[0]
            
            # 转换为Unicode并比较
            code = utf8_to_unicode(utf8_bytes)
            if code == unicode_code:
                # 读取点阵数据
                bitmap_size = ((width + 7) // 8) * height
                f.seek(offset)
                bitmap_data = f.read(bitmap_size)
                return bitmap_data, width, height
        
        return None, 0, 0


def main():
    """主函数"""
    if len(sys.argv) < 3:
        print("用法: python ttf2bitmap.py <输入TTF/TTC文件> <输出BIN文件> [字号] [字体编号]")
        print("示例: python ttf2bitmap.py font.ttf font.bin 16")
        print("      python ttf2bitmap.py font.ttc font.bin 16 0")
        return
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    font_size = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    font_number = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误: 找不到文件 {input_file}")
        return
    
    # 创建转换器并执行转换
    converter = TTF2Bitmap(input_file, font_size, font_number)
    converter.load_font()
    converter.convert(output_file)
    
    print("转换完成！")


if __name__ == '__main__':
    main()
