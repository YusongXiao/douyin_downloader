#!/usr/bin/env python3
"""
Douyin Downloader - 抖音视频/图集/动图批量下载器

通过已部署的 API 接口解析抖音链接，下载所有媒体文件到本地。

环境变量：
    DOUYIN_MEDIA_API  - 媒体提取 API 地址，可参考 https://github.com/YusongXiao/douyin_phaser
    DOUYIN_USER_API   - 用户主页 API 地址，可参考 https://github.com/YusongXiao/douyin_phaser

用法：
    python douyin_downloader.py <抖音链接>

    python douyin_downloader.py https://v.douyin.com/y2JACyhjdK8/
    python douyin_downloader.py https://www.douyin.com/video/7606413230298820595
    python douyin_downloader.py https://www.douyin.com/note/7606955181091438309
    python douyin_downloader.py https://www.douyin.com/user/MS4wLjABAAAAZnqWV7JEd23idoozs6TTJVcU8nP0pj_GWUAwGIm6fSkXtMYy-hrT3z61X8WMB1tJ
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

MEDIA_API = os.environ.get("DOUYIN_MEDIA_API").rstrip("/")
USER_API = os.environ.get("DOUYIN_USER_API").rstrip("/")

DOWNLOADS_DIR = Path("./downloads")

MEDIA_API_TIMEOUT = 30  # 单作品 API 超时（秒）
USER_API_TIMEOUT = 300  # 用户主页 API 超时（秒）

DOWNLOAD_REFERER = "https://www.douyin.com"

# 下载单个文件的超时
FILE_DOWNLOAD_TIMEOUT = 120

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def sanitize_filename(name: str) -> str:
    """移除文件名中的非法字符"""
    name = re.sub(r'[\\/:*?"<>|\n\r\t]', "", name)
    name = name.strip(". ")
    return name or "untitled"


def api_request(base_url: str, target_url: str, timeout: int) -> dict:
    """调用 API 并返回 JSON 响应"""
    api_url = f"{base_url}/?url={urllib.parse.quote(target_url, safe='')}"
    print(f"  → 请求 API: {api_url}")

    req = urllib.request.Request(api_url)
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f"  ✗ API HTTP 错误: {e.code} {e.reason}")
        try:
            body = e.read().decode("utf-8", errors="replace")
            print(f"    响应: {body[:500]}")
        except Exception:
            pass
        return None
    except urllib.error.URLError as e:
        print(f"  ✗ API 连接失败: {e.reason}")
        return None
    except Exception as e:
        print(f"  ✗ API 请求异常: {e}")
        return None

    if data.get("code") != 0:
        print(f"  ✗ API 返回错误: {data.get('message', 'unknown')}")
        return None

    return data


def download_file(url: str, dest: Path) -> bool:
    """下载单个文件，附带 Referer 头"""
    if dest.exists():
        print(f"  ⊘ 已存在，跳过: {dest.name}")
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers={
        "Referer": DOWNLOAD_REFERER,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    })

    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=FILE_DOWNLOAD_TIMEOUT, context=ctx) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total else None

            downloaded = 0
            start_time = time.time()
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total:
                        pct = downloaded * 100 // total
                        bar = "█" * (pct // 3) + "░" * (33 - pct // 3)
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            speed = downloaded / elapsed
                            if speed > 1024 * 1024:
                                speed_str = f"{speed / 1024 / 1024:.1f} MB/s"
                            else:
                                speed_str = f"{speed / 1024:.0f} KB/s"
                        else:
                            speed_str = "-- MB/s"
                        print(f"\r  ↓ [{bar}] {pct}% ({downloaded}/{total}) {speed_str}  ", end="", flush=True)

            if total:
                print()  # 换行

        size_kb = dest.stat().st_size / 1024
        if size_kb > 1024:
            print(f"  ✓ 已下载: {dest.name} ({size_kb / 1024:.1f} MB)")
        else:
            print(f"  ✓ 已下载: {dest.name} ({size_kb:.0f} KB)")
        return True

    except Exception as e:
        print(f"\n  ✗ 下载失败: {e}")
        # 清理不完整的文件
        if dest.exists():
            dest.unlink()
        return False


# ---------------------------------------------------------------------------
# 单作品下载
# ---------------------------------------------------------------------------


def download_single_work(share_url: str, base_dir: Path = None, index_prefix: str = "") -> bool:
    """
    解析并下载单个作品。

    如果 base_dir 为 None，使用 ./downloads/杂/ 作为基础目录，文件名为 作者名-标题。
    如果指定了 base_dir，直接在 base_dir 下按标题组织文件。
    index_prefix: 可选的序号前缀，如 "1 "，用于区分同名作品。
    """
    print(f"\n{'='*60}")
    print(f"解析作品: {share_url}")
    print(f"{'='*60}")

    data = api_request(MEDIA_API, share_url, MEDIA_API_TIMEOUT)
    if not data:
        return False

    info = data["data"]
    title = sanitize_filename(info.get("title", "untitled"))
    author = sanitize_filename(info.get("author", "unknown"))
    items = info.get("items", [])

    if not items:
        print("  ⚠ 没有找到可下载的内容")
        return False

    # 确定下载目录和命名前缀
    if base_dir is None:
        work_base = DOWNLOADS_DIR / "杂"
        name_prefix = f"{author}-{title}"
    else:
        work_base = base_dir
        name_prefix = f"{index_prefix}{title}"

    print(f"  作者: {author}")
    print(f"  标题: {title}")
    print(f"  类型: {info.get('type', 'unknown')}")
    print(f"  文件数: {len(items)}")

    # 仅一个 video 项 → 直接存为 作者名-title.mp4
    if len(items) == 1 and items[0]["type"] == "video":
        item = items[0]
        video_url = item.get("video_url")
        if video_url:
            dest = work_base / f"{name_prefix}.mp4"
            download_file(video_url, dest)
        return True

    # 多个元素 → 建子文件夹 作者名-title/
    work_dir = work_base / name_prefix

    for idx, item in enumerate(items, 1):
        item_type = item.get("type", "unknown")
        print(f"\n  [{idx}/{len(items)}] 类型: {item_type}")

        if item_type == "video":
            video_url = item.get("video_url")
            if video_url:
                dest = work_dir / f"{idx}.mp4"
                download_file(video_url, dest)

        elif item_type == "image":
            image_url = item.get("image_url")
            if image_url:
                # 根据 URL 判断扩展名
                ext = _guess_ext(image_url, default=".jpeg")
                dest = work_dir / f"{idx}{ext}"
                download_file(image_url, dest)

        elif item_type == "animated_image":
            # 动图同时有 webp 和 mp4
            image_url = item.get("image_url")
            video_url = item.get("video_url")
            if image_url:
                ext = _guess_ext(image_url, default=".webp")
                dest = work_dir / f"{idx}{ext}"
                download_file(image_url, dest)
            if video_url:
                dest = work_dir / f"{idx}.mp4"
                download_file(video_url, dest)

        else:
            print(f"  ⚠ 未知类型: {item_type}，跳过")

    return True


def _guess_ext(url: str, default: str = ".jpeg") -> str:
    """从 URL 路径猜测文件扩展名"""
    path = urllib.parse.urlparse(url).path
    for ext in [".webp", ".jpeg", ".jpg", ".png", ".gif", ".mp4", ".heic"]:
        if ext in path.lower():
            return ext
    return default


# ---------------------------------------------------------------------------
# 用户主页下载
# ---------------------------------------------------------------------------


def download_user_works(user_url: str) -> bool:
    """下载某用户的所有作品"""
    print(f"\n{'='*60}")
    print(f"获取用户作品列表: {user_url}")
    print(f"{'='*60}")
    print(f"  ⏳ 正在请求用户主页 API（可能需要较长时间，最多 {USER_API_TIMEOUT}s）...")

    start = time.time()
    data = api_request(USER_API, user_url, USER_API_TIMEOUT)
    elapsed = time.time() - start
    print(f"  ⏱ API 响应耗时: {elapsed:.1f}s")

    if not data:
        return False

    user_info = data["data"].get("user", {})
    works = data["data"].get("works", [])
    nickname = sanitize_filename(user_info.get("nickname", "unknown_user"))
    works_count = data["data"].get("works_count", len(works))

    print(f"\n  用户: {nickname}")
    print(f"  UID: {user_info.get('uid', 'N/A')}")
    print(f"  签名: {user_info.get('signature', '')}")
    print(f"  作品数: {works_count}")
    print(f"  已获取: {len(works)} 个作品链接")

    if not works:
        print("  ⚠ 没有找到任何作品")
        return False

    user_dir = DOWNLOADS_DIR / nickname

    success = 0
    fail = 0

    for idx, work in enumerate(works, 1):
        share_url = work.get("share_url", "")
        desc = work.get("desc", "")
        work_type = work.get("type", "unknown")
        aweme_id = work.get("aweme_id", "")

        print(f"\n{'─'*60}")
        print(f"  作品 [{idx}/{len(works)}] ({work_type}) {desc[:40]}")
        print(f"  ID: {aweme_id}")

        if not share_url:
            print("  ⚠ 缺少 share_url，跳过")
            fail += 1
            continue

        try:
            ok = download_single_work(share_url, base_dir=user_dir, index_prefix=f"{idx} ")
            if ok:
                success += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            fail += 1

        # 短暂延迟，避免请求过快
        if idx < len(works):
            time.sleep(0.5)

    print(f"\n{'='*60}")
    print(f"  下载完成！成功: {success}, 失败: {fail}, 总计: {len(works)}")
    print(f"  保存位置: {user_dir.resolve()}")
    print(f"{'='*60}")

    return True


# ---------------------------------------------------------------------------
# URL 分类
# ---------------------------------------------------------------------------


def is_user_url(url: str) -> bool:
    """判断是否为用户主页链接"""
    return "/user/" in url


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("示例:")
        print("  python douyin_downloader.py https://v.douyin.com/y2JACyhjdK8/")
        print("  python douyin_downloader.py https://www.douyin.com/user/MS4wLjABAAAA...")
        print()
        print("环境变量:")
        print(f"  DOUYIN_MEDIA_API = {MEDIA_API}")
        print(f"  DOUYIN_USER_API  = {USER_API}")
        sys.exit(0)

    url = sys.argv[1]
    print(f"Douyin Downloader")
    print(f"  媒体 API: {MEDIA_API}")
    print(f"  用户 API: {USER_API}")
    print(f"  目标 URL: {url}")

    if is_user_url(url):
        ok = download_user_works(url)
    else:
        ok = download_single_work(url)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
