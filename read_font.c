#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* ========== 文件格式定义 ========== */

typedef struct {
    uint8_t  magic[4];      // 魔数 "FONT"
    uint32_t version;       // 版本号
    uint32_t char_count;    // 字符数量
    uint32_t font_size;     // 字号
} FontHeader;

typedef struct {
    uint32_t unicode;       // Unicode码点
    uint32_t offset;        // 点阵数据偏移
    uint16_t width;         // 字符宽度
    uint16_t height;        // 字符高度
} FontIndex;

typedef struct {
    FILE *fp;
    FontHeader header;
    FontIndex *index;       // 索引表
    uint32_t index_count;   // 索引项数量
} FontFile;

/* ========== UTF-8编解码 ========== */

/**
 * 将UTF-8字节序列解码为Unicode码点
 * 返回UTF-8字节长度，失败返回0
 */
int utf8_decode(const uint8_t *buf, uint32_t *unicode) {
    if (buf[0] < 0x80) {
        *unicode = buf[0];
        return 1;
    } else if ((buf[0] & 0xE0) == 0xC0) {
        *unicode = ((buf[0] & 0x1F) << 6) | (buf[1] & 0x3F);
        return 2;
    } else if ((buf[0] & 0xF0) == 0xE0) {
        *unicode = ((buf[0] & 0x0F) << 12) | ((buf[1] & 0x3F) << 6) | (buf[2] & 0x3F);
        return 3;
    } else if ((buf[0] & 0xF8) == 0xF0) {
        *unicode = ((buf[0] & 0x07) << 18) | ((buf[1] & 0x3F) << 12) 
                 | ((buf[2] & 0x3F) << 6) | (buf[3] & 0x3F);
        return 4;
    }
    return 0;
}

/**
 * 将Unicode码点编码为UTF-8
 * 返回写入的字节数
 */
int utf8_encode(uint32_t unicode, uint8_t *buf) {
    if (unicode <= 0x7F) {
        buf[0] = (uint8_t)unicode;
        return 1;
    } else if (unicode <= 0x7FF) {
        buf[0] = 0xC0 | (unicode >> 6);
        buf[1] = 0x80 | (unicode & 0x3F);
        return 2;
    } else if (unicode <= 0xFFFF) {
        buf[0] = 0xE0 | (unicode >> 12);
        buf[1] = 0x80 | ((unicode >> 6) & 0x3F);
        buf[2] = 0x80 | (unicode & 0x3F);
        return 3;
    } else if (unicode <= 0x10FFFF) {
        buf[0] = 0xF0 | (unicode >> 18);
        buf[1] = 0x80 | ((unicode >> 12) & 0x3F);
        buf[2] = 0x80 | ((unicode >> 6) & 0x3F);
        buf[3] = 0x80 | (unicode & 0x3F);
        return 4;
    }
    return 0;
}

/* ========== 字库文件操作 ========== */

/**
 * 打开字库文件并加载索引
 */
FontFile* font_open(const char *path) {
    FontFile *font = (FontFile*)calloc(1, sizeof(FontFile));
    if (!font) return NULL;
    
    font->fp = fopen(path, "rb");
    if (!font->fp) {
        free(font);
        return NULL;
    }
    
    // 读取文件头
    fread(&font->header, sizeof(FontHeader), 1, font->fp);
    
    // 验证魔数
    if (memcmp(font->header.magic, "FONT", 4) != 0) {
        fclose(font->fp);
        free(font);
        return NULL;
    }
    
    // 读取索引表
    font->index_count = font->header.char_count;
    font->index = (FontIndex*)calloc(font->index_count, sizeof(FontIndex));
    
    for (uint32_t i = 0; i < font->index_count; i++) {
        uint8_t utf8_len;
        fread(&utf8_len, 1, 1, font->fp);
        
        uint8_t utf8_buf[4];
        fread(utf8_buf, 1, utf8_len, font->fp);
        utf8_decode(utf8_buf, &font->index[i].unicode);
        
        fread(&font->index[i].offset, 4, 1, font->fp);
        fread(&font->index[i].width, 2, 1, font->fp);
        fread(&font->index[i].height, 2, 1, font->fp);
    }
    
    return font;
}

/**
 * 关闭字库文件
 */
void font_close(FontFile *font) {
    if (font) {
        if (font->fp) fclose(font->fp);
        if (font->index) free(font->index);
        free(font);
    }
}

/**
 * 打印字库信息
 */
void font_print_info(const FontFile *font) {
    printf("===== 字库信息 =====\n");
    printf("魔数: %.4s\n", font->header.magic);
    printf("版本: %u\n", font->header.version);
    printf("字符数: %u\n", font->header.char_count);
    printf("字号: %upx\n", font->header.font_size);
}

/**
 * 根据Unicode码点查找字符索引
 * 找到返回索引指针，未找到返回NULL
 */
const FontIndex* font_find_char(const FontFile *font, uint32_t unicode) {
    for (uint32_t i = 0; i < font->index_count; i++) {
        if (font->index[i].unicode == unicode) {
            return &font->index[i];
        }
    }
    return NULL;
}

/**
 * 根据UTF-8字符串查找字符索引
 */
const FontIndex* font_find_utf8(const FontFile *font, const char *utf8_str) {
    uint32_t unicode;
    utf8_decode((const uint8_t*)utf8_str, &unicode);
    return font_find_char(font, unicode);
}

/**
 * 读取字符的点阵数据
 * 返回的缓冲区需要调用者free()
 * bitmap_size 返回数据大小
 */
uint8_t* font_read_bitmap(const FontFile *font, const FontIndex *entry, size_t *bitmap_size) {
    if (!entry) return NULL;
    
    size_t row_bytes = (entry->width + 7) / 8;
    *bitmap_size = row_bytes * entry->height;
    
    uint8_t *data = (uint8_t*)malloc(*bitmap_size);
    if (!data) return NULL;
    
    fseek(font->fp, entry->offset, SEEK_SET);
    fread(data, 1, *bitmap_size, font->fp);
    
    return data;
}

/* ========== 显示函数 ========== */

/**
 * 以ASCII艺术方式显示字符点阵
 */
void font_print_char(const FontFile *font, uint32_t unicode) {
    const FontIndex *entry = font_find_char(font, unicode);
    if (!entry) {
        printf("字符 U+%04X 未找到\n", unicode);
        return;
    }
    
    size_t bitmap_size;
    uint8_t *bitmap = font_read_bitmap(font, entry, &bitmap_size);
    if (!bitmap) return;
    
    // 编码为UTF-8用于显示
    uint8_t utf8_buf[5];
    int utf8_len = utf8_encode(unicode, utf8_buf);
    utf8_buf[utf8_len] = '\0';
    
    printf("字符: %s (U+%04X) 尺寸: %dx%d\n", utf8_buf, unicode, entry->width, entry->height);
    printf("┌");
    for (int x = 0; x < entry->width; x++) printf("─");
    printf("┐\n");
    
    size_t row_bytes = (entry->width + 7) / 8;
    for (int y = 0; y < entry->height; y++) {
        printf("│");
        for (int x = 0; x < entry->width; x++) {
            size_t byte_idx = y * row_bytes + (x / 8);
            int bit_idx = 7 - (x % 8);
            int pixel = (bitmap[byte_idx] >> bit_idx) & 1;
            printf("%s", pixel ? "█" : " ");
        }
        printf("│\n");
    }
    
    printf("└");
    for (int x = 0; x < entry->width; x++) printf("─");
    printf("┘\n");
    
    free(bitmap);
}

/* ========== 主程序示例 ========== */

int main(int argc, char *argv[]) {
    const char *font_path = "font_16.bin";
    
    // 命令行参数指定字库文件
    if (argc > 1) {
        font_path = argv[1];
    }
    
    printf("打开字库: %s\n\n", font_path);
    
    // 打开字库
    FontFile *font = font_open(font_path);
    if (!font) {
        printf("错误: 无法打开字库文件\n");
        return 1;
    }
    
    // 打印字库信息
    font_print_info(font);
    printf("\n");
    
    // 显示示例字符
    printf("===== 字符显示示例 =====\n\n");
    
    uint32_t test_chars[] = {
        // 简体字
        0x4E2D,  // 中
        0x56FD,  // 国
        0x4EBA,  // 人
        0x6C11,  // 民
        // 繁体字
        0x570B,  // 國
        0x5B78,  // 學
        0x9580,  // 門
        0x9F8D,  // 龍
        0x83EF,  // 華
        0x66F8,  // 書
        // ASCII
        0x0041,  // A
        0x0061,  // a
        0x0030,  // 0
    };
    int test_count = sizeof(test_chars) / sizeof(test_chars[0]);
    
    for (int i = 0; i < test_count; i++) {
        font_print_char(font, test_chars[i]);
        printf("\n");
    }
    
    // 关闭字库
    font_close(font);
    
    return 0;
}
