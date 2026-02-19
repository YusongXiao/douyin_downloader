# Douyin Downloader

抖音视频 / 图集 / 动图批量下载器。通过已部署的 API 解析抖音分享链接并下载。

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DOUYIN_MEDIA_API` | 媒体提取 API 地址 | 可参考 https://github.com/YusongXiao/douyin_phaser |
| `DOUYIN_USER_API` | 用户主页 API 地址 | 可参考 https://github.com/YusongXiao/douyin_phaser |

## 使用方法

### 下载单个作品

```bash
python douyin_downloader.py https://v.douyin.com/y2JACyhjdK8/
python douyin_downloader.py https://www.douyin.com/video/7606413230298820595
python douyin_downloader.py https://www.douyin.com/note/7606955181091438309
```

### 下载用户所有作品

```bash
python douyin_downloader.py https://www.douyin.com/user/MS4wLjABAAAA...
```

## 下载目录结构

```
downloads/
├── 杂/                                # 单个作品
│   ├── 作者名-视频标题.mp4
│   └── 作者名-图集标题/                # 多图/动图
│       ├── 1.webp
│       ├── 2.webp
│       └── 2.mp4
└── 用户名/                            # 用户主页批量下载
    ├── 视频标题.mp4
    └── 图集标题/
        ├── 1.webp
        └── 2.webp
```

## 依赖

- Python 3.6+
- 无第三方依赖
